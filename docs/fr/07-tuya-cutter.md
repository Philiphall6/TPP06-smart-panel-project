# Étape 7 — TPP06 Tuya Cutter

> **Référence avancée et journal chronologique.** Le [guide débutant](DEMARRER-ICI.md)
> présente le parcours courant. La [V5](11-interface-v5.md) est installée sur le
> panneau de référence, API chiffrée et état sain contrôlés, politique persistante
> conservée. Les comptes rendus ci-dessous conservent leurs limites au moment
> des essais. La première activation permanente n’est pas automatisée par `install`.

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

L'installation lit les arguments du processus `wpa_supplicant` de `wlan0`
pour sélectionner son vrai fichier `-c`, puis le copie vers
`/data/tpp06-cutter/network/wpa_supplicant.conf`. Elle ne suppose plus que
`/etc/wpa_supplicant.conf` est le profil actif : sur le panneau examiné, le
processus utilisait un autre fichier dans les données Tuya. La sélection refuse
un processus ambigu, une autre interface ou plusieurs blocs réseau. En cas
d'échec, le mode réseau devient `unavailable`, sans copie d'un modèle arbitraire.
La copie est vérifiée par empreinte avant remplacement et protégée en `0600`.
Le contrôle utilise SHA-256 ou, à défaut, MD5 pour comparer les fichiers locaux
car certains BusyBox du panneau n'ont pas `cmp` ; ce n'est pas une signature.
Le Cutter n'affiche jamais le SSID, la clé ni l'empreinte du profil.

Diagnostic seul, sans redémarrage ni modification :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 network-check
```

`SAVED_PROFILE=identical` confirme seulement que la copie correspond au fichier
actif. `AUTONOMOUS_WIFI=not_verified` reste explicite : cela ne teste ni une
réassociation Wi-Fi ni le lancement des pilotes sans Tuya. L'état `COMPLETED`
de [wpa_supplicant STATUS](https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html)
décrit la connexion courante, pas un futur démarrage autonome.

Les deux politiques réseau sont distinctes, sans transition automatique :

1. **apprentissage** : Tuya conserve le Wi-Fi, ESPHome doit survivre 60 secondes
   et ouvrir son API sur le port `6053` ;
2. **isolé (expérimental, sélection explicite seulement)** : le superviseur lance lui-même
   `wpa_supplicant` et `udhcpc`, attend une adresse IPv4, conserve seulement
   `tuya_factory` sur le port local `8090`, puis lance ESPHome.

Un essai en apprentissage réussi ne valide pas le Wi-Fi autonome. Ne pas
sélectionner le mode isolé à distance sans moyen de récupération sur place.

Le superviseur corrigé refuse le mode isolé si l'application Tuya ou son
moniteur est encore présent. Il refuse aussi de traiter une adresse existante
ou des processus Wi-Fi/DHCP préexistants comme un réseau qu'il a lui-même
démarré. Il ne tue pas ces processus pour contourner le refus. Ces protections
sont testées hors ligne ; elles ne prouvent pas encore le démarrage matériel.

Le 18 novembre 2026, la copie de secours a été préparée depuis le profil actif
sur le panneau, après sauvegarde privée et vérification. Les paramètres réseau
actifs, le programme flash et le superviseur installé n'ont pas changé ; les
modes restent `tuya` et `learning`. Le nouveau superviseur n'a pas été déployé
pendant cette préparation. Aucun redémarrage ni arrêt de Tuya n'a été envoyé.

#### Prérequis du démarrage autonome

Les scripts récupérés du firmware actuel montrent que `rc.local` charge les
pilotes écran, tactile et Wi-Fi, relève `wlan0`, démarre ADB et lance
`ak_watchdog` avant `S99tuya-app`. Le sélecteur doit conserver cet ordre : il
ne recharge pas les modules, ne commute pas les GPIO et n'ouvre pas lui-même
`/dev/watchdog`.

Le superviseur préparé exige désormais :

- l'interface `wlan0` et les périphériques écran, tactile et watchdog présents ;
- un processus `ak_watchdog` ayant un descripteur ouvert sur le watchdog ;
- les outils réseau et le script DHCP d'origine disponibles ;
- une association `wpa_state=COMPLETED` **et** une IPv4 utilisable ;
- les deux écouteurs locaux ADB `5555` et secours `8090` avant le lancement ESPHome.

Le script DHCP est donné explicitement à `udhcpc`. L'échec de `ifconfig wlan0 up`
interrompt la tentative. Une adresse `0.0.0.0`, de boucle locale ou link-local
n'est pas acceptée comme bail prêt. Ces contrôles restent nécessaires mais non
suffisants : un port en écoute ne prouve pas un accès distant authentifié, et
un descripteur watchdog ouvert ne prouve pas son alimentation à long terme.

À cette étape, les 69 tests hors ligne passaient. Sur le panneau, les contrôles matériels en
lecture seule passent dans l'état Tuya actuel. Un essai séparé en RAM a vérifié
uniquement le **refus** du mode isolé lorsque Tuya est actif : aucun moteur
personnalisé lancé, processus réseau inchangés, programme flash, profil Wi-Fi
et superviseur installé inchangés. Le programme sentinelle de cet essai n'était
pas ESPHome. Ce test ne valide pas le démarrage autonome ni le retour après une
panne réseau réelle. Un essai matériel de bascule exige encore une récupération
sur place ; aucun redémarrage n'a été effectué pour ces contrôles.

#### Essai autonome court du 18 novembre 2026

Un essai distinct a ensuite démarré ESPHome après un redémarrage logiciel,
sans lancer l'application graphique Tuya. Un lanceur temporaire a restauré
le lanceur d'origine **avant** la tentative ; les choix globaux sont restés
`tuya` et `learning`. Le binaire compilé dans Home Assistant a été copié dans
un répertoire d'essai séparé, sans remplacer le programme installé.

Le Wi-Fi autonome a établi l'association et obtenu une IPv4. ADB et le port
`8090` sont restés accessibles pendant la session. Les 18 contrôles de l'API
chiffrée ont réussi. Une capture du framebuffer montre l'interface LVGL,
et non l'horloge Tuya ; ESPHome ouvrait l'écran et le tactile, sans processus
graphique Tuya concurrent. Aucun toucher ni aucune action domotique n'a été
envoyé pour ce contrôle distant.

Le superviseur a arrêté ESPHome après 120 secondes et déclenché son retour
à Tuya. Un minuteur indépendant a ensuite demandé un redémarrage, après
210 secondes, via le lanceur d'origine déjà restauré. Une connexion ADB
conservée côté client était devenue `offline` après ce redémarrage : sa
déconnexion/reconnexion ciblée a rétabli l'accès, sans redémarrage supplémentaire.
Une vérification finale distincte a confirmé 93 secondes de stabilité de Tuya,
le Wi-Fi connecté et les sommes de contrôle d'origine restaurées ou inchangées.

Il s'agit d'un **essai court**, pas d'une installation permanente ni d'une
validation après coupure électrique. Il ne valide pas le secours en cas de
blocage du noyau, la stabilité prolongée, les actions domotiques ou l'OTA en
mode autonome. Les journaux, profils, clés et captures restent privés. Le
minuteur d'essai n'est pas une garantie matérielle de récupération.

#### Essai autonome prolongé de 15 minutes

Le même binaire compilé dans Home Assistant a ensuite été testé pendant une
session de 900 secondes, avec un retour par redémarrage indépendant prévu à
990 secondes. Aucun transfert OTA ni aucune action domotique n'a été envoyé.
Le lanceur d'origine était restauré avant de démarrer le superviseur d'essai.

Les observations montrent un seul processus ESPHome sur le même démarrage,
une mémoire résidente constante de **4 792 Kio**, et **51 contrôles chiffrés
réussis**. Les captures du début et de la fin montrent la même interface LVGL.
Cela ne constitue pas un nouveau test du tactile physique.

Un relevé ADB a échoué pendant la session ; le suivant a retrouvé le même
processus, sans redémarrage. Une tentative API supplémentaire a échoué au
moment de l'arrêt : le relevé d'uptime et le journal du superviseur la situent
à l'expiration programmée des 900 secondes. Ces incidents d'observation sont
conservés dans le bilan, plutôt que présentés comme des contrôles tous réussis.

Le retour à Tuya et le redémarrage de secours ont été observés, puis la
stabilité de Tuya vérifiée pendant 90 secondes. Les sommes de contrôle des
quatre fichiers d'origine suivis confirment leur restauration ou leur absence
de modification. L'horloge
système autonome est restée en 1970 dans ce premier binaire. Les essais v3/V4
suivants ont ajouté la synchronisation depuis HA ; un décalage de fuseau a
été observé dans V4, voir le [bilan de l'interface mobile](06-esphome-lvgl-natif.md#variante-mobile-inspirée-dios).
Un contrôle complémentaire mDNS côté HA n'a pas été effectué, l'accès Docker
de l'outil SSH étant protégé ; cette protection n'a pas été modifiée.
L'endurance de longue durée, l'OTA autonome, les actions domotiques et les
coupures électriques restent hors de cette validation.

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

L'essai **ESPHome** conserve Tuya actif et possède un arrêt automatique : il
ne valide pas la prise de contrôle exclusive de l'écran. Le chemin historique
**openHASP** suspend encore Tuya avec `SIGSTOP` ; ce n'est pas une pause de la
seule interface graphique et ce chemin n'est pas sûr pour un essai distant
sans accès physique de secours. Ne pas l'utiliser comme solution d'affichage.
Le programme est copié sous `/tmp/tpp06-cutter`, donc disparaît au redémarrage.
Pour revenir immédiatement :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 stop-test
```

### Installation permanente réversible

#### Politique de redémarrage persistante — option expérimentale

Le superviseur conserve `boot_policy=one-shot` par défaut. L'installateur
réinitialise explicitement cette valeur et la confirmation : une installation
ou un essai réussi ne sélectionne jamais automatiquement le mode persistant.

L'option `boot_policy=persistent` est réservée à ESPHome avec
`network_mode=isolated`, une session non bornée et un port API vérifiable.
À chaque démarrage, le superviseur sélectionne d'abord Tuya pour le prochain
cycle. Après le délai de grâce et uniquement si `persistent_confirmed=yes`,
il resélectionne ESPHome lorsque processus, Wi-Fi, IPv4 et écouteurs API/ADB/8090
sont présents. Cette confirmation doit suivre une vérification authentifiée
du premier démarrage ; les écouteurs seuls ne prouvent pas l'authentification.

En fonctionnement, trois contrôles locaux consécutifs en échec (intervalle
de dix secondes) arrêtent ESPHome et sélectionnent Tuya **avant** le nettoyage
du réseau. Une sortie du processus entraîne également le secours. La perte
de Home Assistant ou d'Internet, à elle seule, n'est pas un motif de redémarrage.
Un arrêt explicite du superviseur laisse Tuya sélectionné.

Le démarrage vérifie aussi l'identifiant du démarrage Linux et la ligne de
commande du superviseur : un ancien PID réutilisé ne peut plus être pris pour
un superviseur déjà actif. Les 84 tests hors ligne couvrent notamment ce cas,
les refus de politiques incohérentes et le retour à Tuya après perte de santé.

Ce mécanisme ne garantit pas le secours en cas de blocage du noyau après
réarmement, de stockage défaillant ou de panne matérielle. Un accès physique
de récupération reste requis. Le premier déploiement utilise séparément un
lanceur de retour Tuya et un minuteur de secours, désarmé seulement après
vérification distante. Aucun changement du bootloader ou de la NAND brute
n'est nécessaire. L'activation persistante n'est pas effectuée par la commande
`install` standard ; ne pas copier des fichiers d'état sans cette procédure.

#### Installation standard : sélection ponctuelle

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
