# Étape 7 — TPP06 Tuya Cutter

> [!CAUTION]
> Le superviseur multiboot V1 est testé hors ligne mais pas encore validé par
> un cycle électrique complet sur le panneau. L'installation ESPHome reste
> protégée par l'option explicite `--experimental-multiboot`. Garder l'UART
> disponible pendant cette première validation matérielle.

`tpp06_tuya_cutter.py` rassemble les opérations du projet dans un installateur
réversible. On lui donne l'adresse IP du panneau ; il lit l'`AUTHKEY` par le
port `8090`, calcule le mot de passe root uniquement en mémoire, se connecte à
ADB et propose sauvegarde, restauration et basculement d'interface.

> **Version de développement.** La logique locale et la validation des
> archives sont testées automatiquement. Les opérations ADB doivent encore être
> validées de bout en bout sur le panneau après son prochain redémarrage. Ne pas
> utiliser le mode permanent avant les essais temporaires.

## Principes de sécurité

- l'`AUTHKEY` et le mot de passe ne sont ni affichés ni enregistrés ;
- les sauvegardes locales sont créées en mode `0600` et ignorées par Git ;
- une restauration refuse chemins absolus, `..`, liens symboliques et fichiers
  extérieurs au périmètre autorisé ;
- une installation permanente crée automatiquement une sauvegarde préalable ;
- les binaires Tuya d'origine ne sont jamais effacés ;
- le « retrait de Tuya » est un **basculement réversible** du script
  `S99tuya-app`, pas une suppression des partitions d'origine ;
- aucun redémarrage n'est envoyé automatiquement.

## Multiboot V1 et secours automatique

Pour installer les fichiers sans sélectionner ESPHome au prochain démarrage :

```bash
python3 tools/tpp06_tuya_cutter.py IP_DU_PANNEAU install esphome \
  --binary program --experimental-multiboot --keep-stock
```

Le mode reste `tuya`. Un essai temporaire utilise la copie flash si sa somme
de contrôle correspond au binaire local, afin d'économiser la RAM. Le contrôle
`reboot-check` est un diagnostic : il ne bloque pas un redémarrage effectué par
un autre outil et ne prouve pas que le Wi-Fi autonome fonctionne après reboot.

Validation sur un panneau le 18 novembre 2026 : essai ESPHome de 60 secondes,
API TCP 6053 accessible aux contrôles, ADB et 8090 conservés, processus Tuya
inchangé, arrêt automatique confirmé et aucun reboot. Mémoire disponible
pendant l'essai : environ 40 Mio. Le superviseur a ensuite été installé avec
`--keep-stock`, vérifié par checksum et exécuté dans son mode Tuya. Cela ne
valide pas encore le démarrage à froid, le Wi-Fi autonome, le rendu de l'écran,
le tactile ou une session authentifiée Home Assistant. La sauvegarde et les
journaux contenant des données du panneau restent hors du dépôt.

Second essai sur ce panneau : le superviseur corrigé a piloté ESPHome dans un
répertoire temporaire séparé, avec 60 secondes de contrôle puis arrêt borné à
80 secondes. Le mode temporaire est passé de `esphome-starting` à
`esphome-healthy`, puis `tuya-fallback`. Le processus Tuya est resté identique,
l'uptime a progressé sans reboot, ADB/8090 sont restés accessibles aux sondages
et l'API 6053 s'est fermée après arrêt. Un moteur de test quittant avec le code
7 a également déclenché le secours attendu. Le superviseur corrigé a ensuite
été installé et vérifié par checksum, après sauvegarde du précédent, avec
`MODE=tuya`, `ACTIVE=tuya`, `NETWORK=learning`. Les 29 tests automatisés passent.
Cela ne constitue toujours pas une validation de démarrage à froid ou du Wi-Fi
sans l'application Tuya.

Le sélecteur installé dans l'overlay `/data/etc/init.d` est désormais un
superviseur persistant. Le script Tuya du SquashFS reste inchangé et sa copie
de lancement est conservée sous `/data/tpp06-cutter/S99tuya-app.stock`.

Au démarrage d'une interface personnalisée :

1. le choix personnalisé est immédiatement consommé et le prochain démarrage
   est remis sur Tuya puis synchronisé sur le stockage ;
2. le moniteur Tuya original démarre d'abord afin de conserver le Wi-Fi et le
   service de secours local sur le port `8090` ;
3. un marqueur `boot_pending` est créé ;
4. openHASP ou ESPHome est lancé avec une période de validation de 60 secondes ;
5. si les contrôles réussissent, la session est marquée saine, mais le prochain
   démarrage reste Tuya : aucun réarmement automatique ;
6. s'il quitte, si le watchdog redémarre la carte ou si l'alimentation est
   coupée, même après validation, Tuya reste le mode du prochain démarrage.

Une API ouverte n'est pas une validation du tactile, de l'affichage ou de la
connexion authentifiée à Home Assistant. `TPP06_SESSION_SECONDS` permet de
borner une session de test du superviseur (par défaut `0`, sans limite) ;
l'expiration arrête le moteur et revient à Tuya sans compter un échec.
Ces protections logicielles ne garantissent pas la récupération en cas de
corruption du stockage ou de panne du noyau/matériel.

### Apprentissage puis Wi-Fi autonome

L'installation recopie le profil Wi-Fi déjà utilisé depuis
`/etc/wpa_supplicant.conf` vers
`/data/tpp06-cutter/network/wpa_supplicant.conf`. Le fichier reste uniquement
sur le panneau, en mode `0600` ; le Cutter n'affiche jamais le SSID ni la clé.

Les deux politiques réseau sont distinctes, sans transition automatique :

1. **apprentissage** : Tuya conserve le Wi-Fi, ESPHome doit survivre 60 secondes
   et ouvrir son API sur le port `6053` ;
2. **isolé (expérimental, sélection explicite seulement)** : le superviseur lance lui-même
   `wpa_supplicant` et `udhcpc`, attend une adresse IPv4, conserve seulement
   `tuya_factory` sur le port local `8090`, puis lance ESPHome.

Un essai en apprentissage réussi ne valide pas le Wi-Fi autonome. Ne pas
sélectionner le mode isolé à distance sans moyen de récupération sur place.

Si le profil est absent, si DHCP échoue ou si l'API ESPHome n'écoute pas, le
mode isolé n'est pas validé et le moniteur Tuya original reprend la main. Le
champ `NETWORK` de la commande `status` indique `learning`, `isolated` ou
`unavailable`.

> [!IMPORTANT]
> Les sauvegardes du Cutter incluent alors le profil Wi-Fi. Elles sont créées
> en mode `0600`, mais doivent être conservées comme des fichiers sensibles et
> ne doivent jamais être publiées dans Git.

`status` affiche aussi `ACTIVE`, `FAILURES`, `NETWORK` et `PENDING` pour
diagnostiquer le dernier démarrage.

Avant chaque redémarrage manuel, exécuter le verrou en lecture seule :

```bash
python3 tools/tpp06_tuya_cutter.py IP_DU_PANNEAU reboot-check
```

Il refuse de donner un état favorable si le lanceur Tuya de secours, le
superviseur, le moteur, le profil Wi-Fi, l'espace libre ou l'état `PENDING`
ne sont pas sûrs. Cette commande ne redémarre jamais le panneau.

## Prérequis

- Python 3.10 ou plus récent ;
- Android Platform Tools (`adb`) ;
- panneau et ordinateur sur le même réseau local isolé ;
- overlay ADB de l'étape 4 si le port `5555` n'est pas encore actif ;
- binaire openHASP ou ESPHome-LVGL compilé selon les étapes 5 et 6.

## Assistant interactif

Depuis la racine du dépôt :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1
```

Le menu permet de :

1. vérifier le panneau et le mode actif ;
2. créer une sauvegarde ;
3. restaurer une sauvegarde ;
4. envoyer l'overlay ADB par `8090` ;
5. essayer openHASP ou ESPHome temporairement ;
6. arrêter l'essai et reprendre Tuya ;
7. préparer une interface permanente ;
8. sélectionner `tuya`, `openhasp` ou `esphome` pour le prochain démarrage ;
9. retirer le sélecteur et retrouver le démarrage Tuya d'origine.

## Commandes non interactives

### État et sauvegarde

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 status
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 backup
```

Les archives sont placées par défaut dans `./tpp06-backups/`, accompagnées
d'un manifeste JSON et d'une somme SHA-256.

### Activer ADB par 8090

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 enable-adb \
  /chemin/tpp06-adb-network-final.tar.gz
```

Cette action conserve la règle de l'étape 4 : une coupure/remise sous tension
est nécessaire après l'envoi du paquet.

### Essai temporaire openHASP

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 test openhasp \
  --binary /chemin/openhasp-tpp06 \
  --config /chemin/config.json \
  --pages /chemin/pages.jsonl
```

### Essai temporaire ESPHome + LVGL

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 test esphome \
  --binary /chemin/esphome-lvgl-program
```

Pendant un essai, le processus Tuya est suspendu avec `SIGSTOP`, pas tué. Le
programme est copié sous `/tmp/tpp06-cutter`, donc disparaît au redémarrage.
Pour revenir immédiatement :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 stop-test
```

### Installation permanente réversible

Après plusieurs essais réussis :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 install esphome \
  --binary /chemin/esphome-lvgl-program \
  --experimental-multiboot
```

Ou pour openHASP :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 install openhasp \
  --binary /chemin/openhasp-tpp06 \
  --config /chemin/config.json \
  --pages /chemin/pages.jsonl
```

Le Cutter installe les fichiers sous `/data/tpp06-cutter`, conserve une copie
du script Tuya d'origine et place un sélecteur dans l'overlay
`/data/etc/init.d/S99tuya-app`. Le mode choisi prend effet seulement au prochain
redémarrage électrique. L'option expérimentale est volontairement requise
pour éviter une installation ESPHome permanente accidentelle.

Changer de mode :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 switch tuya
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 switch openhasp
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 switch esphome
```

### Restaurer ou désinstaller

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 restore \
  tpp06-backups/tpp06-192.0.2.1-DATE.tar.gz

python3 tools/tpp06_tuya_cutter.py 192.0.2.1 uninstall
```

Une restauration crée elle-même une sauvegarde de l'état qu'elle va remplacer.
`uninstall` retire uniquement le sélecteur et les programmes ajoutés par le
Cutter ; la couche inférieure d'origine redevient alors visible.

## Transferts

Le Cutter essaie `adb push`/`adb pull`, vérifie systématiquement SHA-256, puis
utilise automatiquement un port `nc` temporaire du panneau si l'ancien démon
ADB Tuya interrompt le protocole de transfert. Aucun serveur permanent n'est
laissé actif.
