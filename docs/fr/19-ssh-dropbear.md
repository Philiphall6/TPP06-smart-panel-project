# Installer Dropbear et changer le mot de passe root du TPP06

Dropbear permet d'ouvrir un terminal SSH sur le Linux du panneau depuis un
ordinateur. Ce guide explique une **première installation manuelle**, puis le
changement du mot de passe root, sans remplacer ESPHome, modifier les relais ou
redémarrer Linux. Il ne nécessite ni Tuya Cloud ni un compte cloud.

**Déjà installé ?** Aller directement à [Changer le mot de passe](#changer-le-mot-de-passe).
Les fichiers restent dans `/data`, mais **le démarrage automatique de SSH n'est
pas activé par cette procédure**. Après un redémarrage du panneau, utiliser ADB
pour relancer le service. Ne pas confondre stockage persistant et service lancé au boot.

## Ce qui a été vérifié

Sur un panneau de référence ARMv5TEJ avec noyau Linux `4.4.192V2.4`, le
19 novembre 2026 :

- Dropbear **2026.94**, compilé statiquement avec la chaîne Bootlin
  `armv5-eabi--uclibc--stable-2018.02-2` ;
- connexion par mot de passe, terminal interactif et refus d'un mauvais mot de passe ;
- passage d'un port d'essai au port 22, sans redémarrage du panneau ;
- ESPHome, états des relais, API, OTA, ADB et secours 8090 conservés ;
- binaire de 268 392 octets, environ 267 Kio pour l'installation et 304 Kio de
  mémoire résidente du serveur au repos. Ces mesures ne sont pas des limites garanties.

La chaîne uClibc `2026.08-1` essayée initialement utilisait un appel système
time64 absent de ce noyau : `select` renvoyait `ENOSYS` et le serveur quittait
avec `Listening socket error`. Un binaire ARMv5 n'est donc **pas nécessairement
compatible avec le noyau**, même s'il démarre avec `-V`.

La chaîne ancienne est un choix de compatibilité testé, pas une garantie de
sécurité à long terme. Aucun essai de redémarrage automatique SSH n'est revendiqué.

## Précautions et vocabulaire

- **Ordinateur** : machine utilisée pour préparer les fichiers et ouvrir SSH.
- **Panneau** : console root obtenue par ADB ou SSH.
- `IP_DU_PANNEAU` : remplacer ce texte par l'adresse de votre propre panneau.
- Le mot de passe **root Linux** n'est ni la clé API ESPHome, ni le secret OTA,
  ni le mot de passe du Wi-Fi.
- Garder une session ADB root ouverte et une récupération locale disponible.
  Ne pas supprimer ADB, le secours 8090 ou les fichiers de démarrage Tuya.
- Ne pas rediriger les ports 22, 5555 ou 8090 vers Internet. La liaison à
  `wlan0` n'est pas un pare-feu : les appareils pouvant joindre le panneau sur
  le réseau peuvent tenter une connexion.
- Aucun mot de passe commun n'est fourni. Choisir le sien et ne publier ni
  `/etc/shadow`, ni sauvegarde d'authentification, ni clé privée SSH.

Les [accès réseau](00-acces-reseau-authkey.md) et
[ADB](04-adb-wifi-sans-uart.md) doivent déjà fonctionner. Cette procédure ne
débloque pas un panneau inaccessible. Si une commande échoue, ne pas poursuivre
les étapes suivantes à l'aveugle.

## Vérifier le panneau

Dans la console du **panneau**, sans rien modifier :

```sh
uname -m
uname -r
df -h /data
readlink -f /data
test -c /dev/ptmx && echo "PTY present"
netstat -lnt
```

Le matériel testé indique `armv5tejl`, une partition `/data` inscriptible et
`/dev/pts` disponible. Les ports **2222 et 22 doivent être libres**. Préserver
aussi la marge de stockage nécessaire à la prochaine OTA, pas seulement la
place du petit serveur SSH.

Sur ce Linux embarqué, `apt` n'est pas disponible et la racine est un SquashFS
en lecture seule. Ne pas tenter d'y installer une distribution Debian ou
OpenSSH avec `apt`. L'installation ci-dessous reste dans `/data/tpp06-ssh`.

## Préparer le binaire sur un ordinateur

Cette partie est avancée. Elle compile **Dropbear uniquement**, pas ESPHome.
La compilation habituelle d'ESPHome reste dans Device Builder sur Home Assistant.
Les commandes suivantes nécessitent un ordinateur Linux x86_64 avec `gcc`,
`make`, `curl`, `tar`, `bzip2`, `gpg` et les certificats HTTPS. Les outils de
compilation sont installés sur cet ordinateur, jamais avec `apt` sur le panneau.

Depuis la racine d'une copie de ce dépôt, dans un même terminal **ordinateur** :

```sh
TPP06_REPO="$PWD"
TPP06_WORK=$(mktemp -d)
cd "$TPP06_WORK"

curl -fLO https://matt.ucc.asn.au/dropbear/releases/dropbear-2026.94.tar.bz2
curl -fLO https://matt.ucc.asn.au/dropbear/releases/dropbear-2026.94.tar.bz2.asc
curl -fLO https://matt.ucc.asn.au/dropbear/releases/dropbear-key-2015.asc
mkdir -m 700 gpg-check
gpg --homedir "$TPP06_WORK/gpg-check" --import dropbear-key-2015.asc
gpg --homedir "$TPP06_WORK/gpg-check" --verify \
  dropbear-2026.94.tar.bz2.asc dropbear-2026.94.tar.bz2
```

Exiger une signature valide. La clé publiée par le projet lors de cet essai a
pour empreinte `F734 7EF2 EE2E 07A2 6762 8CA9 4493 1494 F29C 6773`.
Il s'agit de la clé **publique** de signature du projet Dropbear, pas d'une clé
du panneau ni d'un secret personnel : ne pas modifier cette empreinte pour
l'anonymiser. La contrôler sur le fichier officiel `dropbear-key-2015.asc` avec
`gpg --show-keys --with-colons dropbear-key-2015.asc` (ligne `fpr`).
Une clé téléchargée depuis le même site n'apporte pas une validation indépendante
de son propriétaire ; un avertissement de confiance GPG est distinct d'une
signature incorrecte. Vérifier la provenance sur le [site officiel Dropbear](https://matt.ucc.asn.au/dropbear/dropbear.html).

Toujours sur l'**ordinateur** :

```sh
curl -fLO https://toolchains.bootlin.com/downloads/releases/toolchains/armv5-eabi/tarballs/armv5-eabi--uclibc--stable-2018.02-2.tar.bz2
curl -fLO https://toolchains.bootlin.com/downloads/releases/toolchains/armv5-eabi/tarballs/armv5-eabi--uclibc--stable-2018.02-2.sha256
sha256sum -c armv5-eabi--uclibc--stable-2018.02-2.sha256
tar -xjf armv5-eabi--uclibc--stable-2018.02-2.tar.bz2
tar -xjf dropbear-2026.94.tar.bz2
TPP06_TC="$TPP06_WORK/armv5-eabi--uclibc--stable-2018.02-2/bin/arm-buildroot-linux-uclibcgnueabi"
cd "$TPP06_WORK/dropbear-2026.94"
cp "$TPP06_REPO/device/dropbear/localoptions.h" localoptions.h

./configure --host=arm-buildroot-linux-uclibcgnueabi \
  --enable-static --disable-zlib --disable-lastlog --disable-utmp \
  --disable-utmpx --disable-wtmp --disable-wtmpx \
  CC="$TPP06_TC-gcc" AR="$TPP06_TC-ar" RANLIB="$TPP06_TC-ranlib" \
  CFLAGS='-Os -march=armv5te -mfloat-abi=soft -ffunction-sections -fdata-sections' \
  LDFLAGS='-Wl,--gc-sections' LTM_CFLAGS='-Os'
make -j2 PROGRAMS='dropbear dropbearkey' MULTI=1
"$TPP06_TC-strip" dropbearmulti
"$TPP06_TC-readelf" -h -A -l dropbearmulti
sha256sum dropbearmulti
wc -c dropbearmulti
```

Le résultat doit être ELF32 ARM little-endian, soft-float, ARMv5TE/TEJ, sans
interpréteur dynamique `INTERP`. Garder sa somme SHA256 pour le transfert.
Les [options fournies](../../device/dropbear/localoptions.h) désactivent les
tunnels, le transfert d'agent, X11 et SFTP. Il n'y a pas de client SSH sur le
panneau ; le même binaire contient le serveur et le générateur de clés.

## Transférer et tester sans changer le démarrage

Cette section vise une **première installation**. Si `/data/tpp06-ssh` existe
déjà, ne pas l'écraser : vérifier son service et conserver sa clé hôte.

Sur le **panneau** :

```sh
umask 077
test ! -e /data/tpp06-ssh && mkdir -m 700 /data/tpp06-ssh
```

Sur l'**ordinateur**, remplacer `IP_DU_PANNEAU` dans chaque commande :

```sh
adb connect IP_DU_PANNEAU:5555
adb -s IP_DU_PANNEAU:5555 push "$TPP06_WORK/dropbear-2026.94/dropbearmulti" /data/tpp06-ssh/dropbearmulti
adb -s IP_DU_PANNEAU:5555 push "$TPP06_REPO/device/dropbear/service.sh" /data/tpp06-ssh/service.sh
sha256sum "$TPP06_REPO/device/dropbear/service.sh"
```

Si votre variante d'ADB refuse `push`, arrêter ici et utiliser un transfert
accompagné ; ne pas ouvrir un serveur de transfert anonyme pour contourner le refus.

Sur le **panneau**, comparer les deux sommes avec celles de l'ordinateur avant
d'exécuter les fichiers :

```sh
sha256sum /data/tpp06-ssh/dropbearmulti /data/tpp06-ssh/service.sh
chmod 700 /data/tpp06-ssh/dropbearmulti /data/tpp06-ssh/service.sh
sh -n /data/tpp06-ssh/service.sh
/data/tpp06-ssh/dropbearmulti dropbear -V
/data/tpp06-ssh/dropbearmulti dropbearkey -t ed25519 -f /data/tpp06-ssh/host_ed25519
chmod 600 /data/tpp06-ssh/host_ed25519
/data/tpp06-ssh/dropbearmulti dropbear -E -m -l wlan0 -p 0.0.0.0:2222 \
  -r /data/tpp06-ssh/host_ed25519 -P /var/run/tpp06-dropbear-test.pid \
  -I 900 -K 60 -T 3 -W 32768 \
  </dev/null >/tmp/tpp06-dropbear-test.log 2>&1
netstat -lnt
```

La clé hôte est **créée sur chaque panneau**, jamais partagée ou téléchargée
depuis GitHub. Ne pas la régénérer à chaque lancement. Seule sa partie publique
et son empreinte sont affichables avec :

```sh
/data/tpp06-ssh/dropbearmulti dropbearkey -y -f /data/tpp06-ssh/host_ed25519
```

Sur l'**ordinateur**, ouvrir une vraie fenêtre de terminal :

```sh
ssh -p 2222 root@IP_DU_PANNEAU
```

Comparer l'empreinte SSH avec celle obtenue par ADB avant de l'accepter. Saisir
le **mot de passe root actuel du panneau**, puis vérifier `id`, `uname -m` et
`tty`. Un test automatisé fermant immédiatement l'entrée standard peut fermer
le pseudo-terminal trop tôt : ce n'est pas un test de session interactive.

## Changer le mot de passe

Cela change le compte **Linux root**, utilisé par SSH et par la connexion root
ADB du panneau testé. Il n'existe pas de mot de passe SSH séparé dans cette
configuration. Une session déjà ouverte reste utile, mais ne prouve pas que le
nouveau mot de passe fonctionne.

> **Compatibilité des anciens outils :** Cutter et certains scripts calculent
> encore le mot de passe d'origine à partir de l'AUTHKEY. Après changement,
> ce calcul ne donne plus nécessairement le mot de passe valide. Ces outils
> peuvent refuser la connexion même si ADB fonctionne. Ne pas relancer une
> installation ou une restauration automatique sans adapter son authentification.

Dans une première console root du **panneau**, garder cette session ouverte :

```sh
umask 077
TPP06_AUTH_BACKUP=$(mktemp -d /data/tpp06-auth.XXXXXX)
cp -p /etc/passwd "$TPP06_AUTH_BACKUP/passwd.before"
cp -p /etc/shadow "$TPP06_AUTH_BACKUP/shadow.before"
chmod 600 "$TPP06_AUTH_BACKUP/passwd.before" "$TPP06_AUTH_BACKUP/shadow.before"
printf 'Sauvegarde privee : %s\n' "$TPP06_AUTH_BACKUP"
passwd root
```

Saisir deux fois son nouveau mot de passe **à l'invite**, pas dans une commande
qui serait enregistrée dans l'historique. Rien ne s'affiche pendant la saisie.
Noter le chemin de sauvegarde et conserver une copie privée hors du panneau.

**Limite importante :** sur le firmware testé, le hachage stocké était du DES
historique, qui ne prend en compte que les huit premiers caractères. Une longue
phrase ne corrige donc pas forcément cette limite. Choisir des caractères
aléatoires dès le début et garder l'accès sur un réseau de confiance. La migration
vers un autre hachage ou vers l'authentification exclusivement par clé nécessite
une validation distincte de SSH **et** du login ADB ; elle n'est pas réalisée ici.

Ouvrir une **deuxième** connexion SSH avec le nouveau mot de passe, puis une
nouvelle connexion ADB root. Tester aussi qu'un mauvais mot de passe est refusé.
Ne fermer la première session qu'après ces validations. Ne pas redémarrer pour
« essayer » un mot de passe.

Si le nouveau mot de passe est refusé, dans la **première session restée ouverte**,
restaurer uniquement la sauvegarde qui vient d'être créée :

```sh
test -n "$TPP06_AUTH_BACKUP" && \
test -f "$TPP06_AUTH_BACKUP/passwd.before" && \
test -f "$TPP06_AUTH_BACKUP/shadow.before" && \
command cp -p "$TPP06_AUTH_BACKUP/passwd.before" /etc/passwd && \
command cp -p "$TPP06_AUTH_BACKUP/shadow.before" /etc/shadow && \
chmod 644 /etc/passwd && chmod 600 /etc/shadow && sync
```

Vérifier à nouveau l'ancien accès avant de fermer la console. Si toutes les
sessions sont perdues, cette recette ne remplace pas une récupération locale.

## Passer au port SSH standard

Depuis la session **ADB** conservée, démarrer le service indépendant :

```sh
sh /data/tpp06-ssh/service.sh start
sh /data/tpp06-ssh/service.sh status
```

Depuis l'**ordinateur** :

```sh
ssh root@IP_DU_PANNEAU
```

Après validation sur le port 22, fermer le serveur d'essai depuis **ADB**.
Ne pas utiliser `killall`, qui pourrait arrêter des connexions utiles :

```sh
TPP06_TEST_PID=$(cat /var/run/tpp06-dropbear-test.pid)
case "$TPP06_TEST_PID" in
  ''|*[!0-9]*) echo "PID invalide" ;;
  *)
    if test "$(readlink /proc/"$TPP06_TEST_PID"/exe)" = \
            "$(readlink -f /data/tpp06-ssh/dropbearmulti)"; then
      kill "$TPP06_TEST_PID"
    fi
    ;;
esac
netstat -lnt
```

Le port 2222 doit disparaître et le port 22 rester ouvert. Vérifier aussi
l'interface ESPHome et les accès habituels, sans commuter les charges.

## Arrêt manuel et limites

Depuis **ADB**, arrêter SSH si nécessaire :

```sh
sh /data/tpp06-ssh/service.sh stop
```

La clé et le binaire restent disponibles pour un prochain `start`. La procédure
ne modifie ni `rc.local`, ni `S99tuya-app`, ni la NAND de démarrage. **Après un
reboot Linux, SSH doit être relancé par ADB.** L'intégration automatique au boot
est une étape séparée à sauvegarder et tester avec récupération sur place.

Les journaux sont dans `/tmp/tpp06-dropbear.log` et restent privés. Leur croissance
et l'endurance à long terme ne sont pas validées. L'absence volontaire de SFTP
signifie qu'un client SFTP ou un `scp` moderne utilisant SFTP ne fonctionnera
pas tel quel. Ne pas remplacer le serveur en cours d'exécution par un simple
`adb push` : la mise à jour d'un serveur existant mérite une procédure distincte.

## Sources

- [Dropbear officiel et versions](https://matt.ucc.asn.au/dropbear/dropbear.html).
- [Instructions de compilation Dropbear](https://github.com/mkj/dropbear/blob/DROPBEAR_2026.94/INSTALL.md).
- [Options du serveur](https://github.com/mkj/dropbear/blob/DROPBEAR_2026.94/manpages/dropbear.8).
- [Chaînes ARMv5 Bootlin](https://toolchains.bootlin.com/downloads/releases/toolchains/armv5-eabi/tarballs/).
- [Fonctionnement de crypt et limite du DES](https://man7.org/linux/man-pages/man3/crypt.3.html).
