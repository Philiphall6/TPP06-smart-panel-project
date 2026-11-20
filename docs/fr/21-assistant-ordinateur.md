# Assistant TPP06 sur ordinateur — installation et maintenance

Version de l’assistant : **0.1.0-rc2**. Les huit parcours sont raccordés à la
fenêtre ; les opérations ne partent jamais au lancement. **L’orchestration
complète n’est pas encore validée sur un panneau neuf, ni sur Windows réel.**
Les tests automatisés utilisent des consoles, fichiers, API et NAND simulés.
Une validation matérielle accompagnée reste nécessaire avant une diffusion
comme installateur grand public.

## 1. Ouvrir l’assistant

Garder le dossier complet du paquet. Sur le PC : Python **3.11 ou plus récent**
avec Tkinter et Android Platform Tools (`adb`) sont requis. Les bibliothèques
Python sont installées dans un environnement privé au projet :

- Linux : `sh Installer-dependances.sh`, puis `sh Assistant-TPP06.sh`.
- Windows : ouvrir `Installer-dependances.cmd`, puis `Assistant-TPP06.cmd`.

Sur Mint, si Tkinter manque, installer `python3-tk` **sur le PC**, pas sur le
Linux embarqué. Aucun `apt`, Python ou compilateur n’est installé sur le panneau.
Ne pas lancer l’assistant en administrateur/root. Le contrôle ELF fonctionne
en Python avec pyelftools ; Windows n’a pas besoin de binutils/readelf.

Le paquet est un **paquet de sources lançable avec Python**, pas un EXE Windows
autonome. Le transport ADB utilise des tubes et un lecteur dédié, sans
`select` sur les tubes Windows. Ce portage est testé contre une console simulée
sur Linux ; il n’est pas présenté comme validé sur Windows matériel.

## 2. Avant toute écriture

Utiliser uniquement son propre TPP06 **AK3761E**, variante connue avec noyau
`4.4.192V2.4`, et un réseau local de confiance. Une apparence similaire,
un port ouvert ou une architecture ARMv5 ne prouve pas toute la compatibilité.

Saisir l’IP du **panneau**, pas celle de HA, puis son mot de passe root.
Un choix de chemin permet d’utiliser `adb` ou `adb.exe` hors du PATH.
Les diagnostics ne coupent pas le réseau et ne commandent aucun relais.
Le port 5555 n’est pas sondé avec une connexion TCP brute : l’ancien adbd peut
mal la supporter ; seul son client ADB est utilisé.

Chaque écriture exige une confirmation distincte : variante compatible,
présence avec récupération UART possible, alimentation stable et absence
d’OTA/maintenance concurrente. **Une confirmation n’est pas une preuve
automatique du matériel.** Ne jamais exposer 22, 5555 ou 8090 à Internet.

## 3. Les huit actions

| Action | Fonction et limite |
| --- | --- |
| Mot de passe d’origine | Lecture 8090 après confirmation ; ne retrouve pas un mot de passe modifié. |
| Activer ADB Wi-Fi | Paquets reconnus ; référence après ADB acceptée explicitement, sans dump préalable obligatoire ; pas de reboot automatique. |
| Sauvegarder | Acquisition des partitions NAND exposées après ADB ; archive Cutter partielle disponible séparément. |
| Restaurer une opération | Retour ciblé d’un journal ESPHome, SSH ou mot de passe ; pas de restauration NAND globale. |
| Changer le mot de passe | Saisie masquée deux fois, sauvegardes, nouveau login ADB et SSH si actif ; console de secours conservée. |
| Changer le logo | Partition logo uniquement, géométrie et outils connus, deux originaux sauvegardés, relecture après écriture. |
| Installer SSH | Dropbear reconnu, clé hôte propre à l’appareil, test du bon/mauvais mot de passe, démarrage configuré. |
| Installer ESPHome seul | Programme compilé dans HA à fournir ; sauvegarde du lanceur et du profil Wi-Fi, installation sans reboot. |

### Mot de passe

La lecture d’origine entre dans le mode de test temporaire du service 8090.
Elle ne modifie pas les identifiants et n’écrit pas de firmware. Le secret reste
masqué, sauf demande d’affichage, et disparaît du formulaire si l’adresse change.

Le firmware connu utilise un hachage DES historique : l’assistant demande
**exactement huit caractères ASCII imprimables**, choisis aléatoirement.
Une longue phrase ne compense pas cette limite. La migration de hachage
n’est pas faite implicitement. Le changement utilise les invites de `passwd`,
jamais un mot de passe dans les arguments d’une commande ou dans un journal.

Les fichiers passwd/shadow sont sauvegardés avant modification ; une console
authentifiée reste ouverte pendant le test du nouvel accès. En cas d’échec,
elle tente de restaurer l’ancien accès et le vérifie. Une perte totale du réseau
ou de l’alimentation peut toujours nécessiter la récupération locale.

### SSH

L’empreinte de la clé hôte est obtenue par ADB et épinglée pour la vérification SSH.
La clé privée est créée sur le panneau, jamais fournie dans un paquet commun.
L’assistant refuse d’écraser une installation SSH existante ou un port occupé.

Sous Tuya seul, il sauvegarde `rc.local` et insère un appel conditionnel au
service avant l’unique ligne reconnue de démarrage de l’application. L’insertion
est atomique à travers le montage `/etc`, seulement après le test SSH.
Sous ESPHome seul, le superviseur existant lance ce service. **La configuration
d’autostart ne vaut pas validation physique après reboot.** Aucun reboot n’est
envoyé par l’installation SSH.

### Sauvegarde et restauration

#### État de référence après ADB

Le parcours est **activer ADB → contrôler l’accès → sauvegarder l’état après
ADB → qualifier la sauvegarde → installer**. L’état usine strict n’est plus
un prérequis. Le bouton « Sauvegarde NAND après ADB » conserve l’état courant :
sur un panneau déjà passé à ESPHome, il ne recrée évidemment pas Tuya d’origine.

L’acquisition expérimentale :

- inventorie les partitions `/proc/mtd`, leurs tailles, géométrie, compteurs
  ECC, les montages et la ligne de commande noyau dans un dossier PC privé ;
- lit **toutes les partitions exposées**, uniquement via `/dev/mtdNro`, en
  morceaux de 1 Mio transférés par ADB ; le tampon et l’outil sont dans `/tmp`
  après vérification que ce montage est un tmpfs ;
- conserve un fichier données et un fichier données + OOB par partition,
  avec empreintes SHA-256 et tailles dans `nand-manifest.json` ;
- refait une seconde passe complète et compare chaque morceau ; une variation,
  un reboot, une erreur de lecture ou une copie tronquée invalide l’acquisition ;
- refuse pour l’instant tout bloc déclaré défectueux, erreur ECC non corrigible
  ou géométrie inconnue : aucun bloc n’est silencieusement remplacé ou omis ;
- ne commande pas les relais, ne remonte aucun système de fichiers, n’arrête
  aucun service et ne redémarre pas le panneau.

Le lecteur épinglé est BusyBox 1.21.1 : son option `nanddump -o` **inclut**
l’OOB. Ne pas substituer les options d’une autre implémentation.
[Code source du lecteur](https://raw.githubusercontent.com/mirror/busybox/1_21_1/miscutils/nandwrite.c).
Les données lues utilisent la correction ECC du noyau ; le fichier avec OOB
n’est **pas** présenté comme un dump brut de programmateur à reflasher tel quel.

**Deux lectures identiques et des SHA-256 corrects prouvent la répétabilité et
l’intégrité du transfert, pas la cohérence d’un système vivant ni la couverture
des zones NAND cachées/non exposées.** Le manifeste garde donc
`consistency_validated: false` et `restore_validated: false`. Même en présence
de montages en lecture seule, l’outil ne transforme pas ces contrôles en preuve
de restauration. Il n’existe pas de bouton « forcer validé ».

Pour en faire une véritable référence de récupération, restent à qualifier sur
matériel le plan physique complet et une acquisition cohérente depuis un
environnement de récupération, puis la restauration et le redémarrage. Aucun
flash global depuis le Linux actif n’est proposé. **Ne pas prendre cette
nouvelle copie pour une autorisation d’effacer les sauvegardes existantes.**
Le parcours n’enchaîne jamais une installation automatiquement après la copie.

Le contrôle local « Contrôler une copie NAND » vérifie les fichiers attendus,
leurs tailles et empreintes. Comme tout manifeste non signé, il ne garantit pas
l’authenticité si les images et le manifeste ont été remplacés ensemble.
Conserver ces dossiers hors Git : ils peuvent contenir tous les secrets du panneau.

#### Archive partielle et retours ciblés

L’archive Cutter comprend les chemins présents parmi `/data/app`,
`/data/customize`, `/data/etc/init.d` et `/data/tpp06-cutter`.
Elle ne sauvegarde pas tous les réglages Wi-Fi/SSH, la NAND ou les partitions
système. Une archive temporaire est créée dans un dossier privé de `/tmp`,
téléchargée par ADB et comparée à sa somme distante. Aucun repli vers netcat.

Chaque opération d’écriture ajoute ses sauvegardes **spécifiques** dans un
nouveau dossier privé du PC, avec `operation.json`. La restauration de ce journal
contrôle l’identité MAC et les empreintes ; elle ne fait jamais un `tar -x`
arbitraire sur la racine. Elle sauvegarde d’abord l’état qu’elle va remplacer.

- ESPHome : restaure le lanceur d’origine pour le prochain reboot manuel,
  sans effacer les fichiers du programme ni arrêter le processus en cours.
- SSH : retire l’insertion de démarrage si elle est inchangée, arrête le service,
  puis déplace son dossier dans l’archive de l’opération sur le panneau.
- Mot de passe : demande le mot de passe correspondant à la sauvegarde pour
  vérifier l’accès restauré, en conservant une console de secours.
- Logo : choisir `logo.before` dans l’action Logo ; c’est une nouvelle opération
  NAND confirmée, avec une nouvelle sauvegarde avant écriture.

Ne sélectionner que **ses propres sauvegardes fiables**. Un SHA-256 cohérent
détecte une différence, pas le remplacement malveillant du fichier et de sa
fiche ensemble. Les secrets sauvegardés ne doivent jamais être publiés.

### Logo

Fournir une image binaire opaque **RGB565 320 × 480**, complétée à **512 Kio**.
Le [convertisseur existant](12-logo-demarrage.md) prépare ce format hors ligne.
Un PNG, un ELF ESPHome et un dump NAND complet ne sont pas des images logo.

L’action est limitée au profil reconnu : `mtd3` nommé `logo`, NAND de 512 Kio,
blocs de 128 Kio, pages de 2 Kio, aucun mauvais bloc ni échec ECC. Elle exige
l’outil NAND et l’effaceur connus, conserve deux lectures identiques hors appareil,
puis relit et compare le résultat. Une transaction indépendante du PC prévoit
une seule restauration de l’original en cas d’échec logiciel.

**Cela ne protège pas d’une coupure électrique pendant l’effacement.** Aucun
reboot n’est envoyé. Après une déconnexion, utiliser « Réconcilier une écriture
du logo » : cette action lit le résultat, elle ne réécrit pas la NAND.

## 4. Première installation ESPHome seul

1. Obtenir ADB fonctionnel et conserver une sauvegarde privée.
2. Installer SSH et choisir un mot de passe root si souhaité.
3. Fournir le programme Linux ARMv5 statique compilé dans **Home Assistant**,
   pas un firmware ESP32. La compilation n’est jamais faite sur Mint par cet outil.
4. Choisir « Installer ESPHome seul ». Un panneau déjà sous ESPHome est refusé :
   ses mises à jour doivent passer par l’OTA.
5. L’assistant copie le **profil Wi-Fi réellement utilisé**, conserve l’ancien
   lanceur et prépare le programme. Il vérifie les transferts avant de remplacer
   atomiquement le lanceur monté dans `/etc`. Il conserve une réserve de stockage
   pour une prochaine OTA de taille comparable ; un gros ELF non optimisé peut
   être refusé. Aucun fichier existant n’est supprimé pour créer de la place.
6. Dans « Reprendre / vérifier », choisir le journal de cette opération puis
   « Démarrer ESPHome préparé ». Un seul reboot est demandé et journalisé avant
   envoi ; une réponse perdue ne permet pas d’en envoyer un second.
7. Choisir « Vérifier / reprendre » et saisir la **clé API propre au programme**.
   La vérification compare MAC, projet, démarrage et processus, puis exige
   120 secondes continues avec API chiffrée. Elle ne renvoie aucun reboot.

Pas de choix de dual boot ni de retour automatique Tuya : en cas d’échec,
le superviseur prévoit le maintien des accès de maintenance. Les fichiers
d’origine restent conservés pour une récupération manuelle ; leur présence
n’est pas une sélection automatique du logiciel Tuya au démarrage.

Le fonctionnement sans Wi-Fi, le tactile, les relais, le bip, l’affichage et
un cycle d’alimentation restent des **essais matériels séparés**. Une connexion
API ne les valide pas. La sélection de la politique locale hors réseau après
validation n’est pas déduite de la seule réussite du premier boot.

L’assistant ne demande pas votre YAML HA : il utilise un programme déjà compilé.
Il ne fournit pas un firmware universel contenant une clé API commune.
L’ajout à HA et les entités de votre installation restent personnels.

## 5. Fichiers auxiliaires reconnus

Le paquet de sources ne contient aucun binaire personnel, dump ou clé.
Créer un dossier local avec les fichiers nécessaires à l’action choisie.
Leurs noms et SHA-256 reconnus pour le profil testé sont :

| Nom dans le dossier local | SHA-256 |
| --- | --- |
| `dropbearmulti` | `81bb1b18b527971fbf4690a62a13ba5a055e98feff51cab5d4711c0986b59bc1` |
| `nandtool` | `514d3d76e49b9e1ef65fb1a3b3ab838925f026632329a057e2e369a99ca67c78` |
| `adb-overlay.tar.gz` | `16bbafe333380458bcae1362d9775a4492abc8bd2209dd41469958e6e6802ed7` |
| `adb-rollback.tar.gz` | `e3e6e98af9ac4bf7cd46681872efa121a99c910be9e6069cbb45d57a07ba98b1` |

Le paquet ADB publié historiquement porte le nom
`tpp06-adb-network-final.tar.gz` : sa copie locale doit être nommée
`adb-overlay.tar.gz`, **sans modifier ses octets**. Le guide
[ADB sans UART](04-adb-wifi-sans-uart.md) explique sa portée.
Un outil d’une autre empreinte est refusé comme **non validé**, même s’il
annonce ARMv5. Les anciens noyaux peuvent manquer d’appels système time64.

### Choix de référence après ADB

L’overlay ADB remplace `/data/app` et `/data/customize`. Avant de l’envoyer,
l’assistant exige les deux paquets reconnus et une confirmation explicite :
**l’état de référence souhaité est celui APRÈS ADB**, pas celui d’usine.
Le dump préalable n’est plus obligatoire. Le backend accepte encore un dump
existant en option et en conserve une copie, sans prétendre en prouver l’origine.

Une sauvegarde après activation ne sauvegarde pas rétroactivement les
personnalisations écrasées. Le paquet `adb-rollback.tar.gz` n’est pas une NAND
de secours et ne remplace pas une sauvegarde. La confirmation des risques
locaux/UART et de la variante compatible reste obligatoire avant l’envoi.
Une réponse réseau perdue après l’envoi ne déclenche jamais un second envoi.

## 6. Reprise, verrou et confidentialité

Une opération acquiert un verrou exclusif sur le panneau. Le journal privé
est écrit avant les étapes critiques. Si la connexion est perdue pendant une
écriture, ne pas supprimer le verrou ni relancer l’action : inspecter le
journal, puis utiliser la vérification de boot ou la réconciliation du logo.
Un état ambigu non réconciliable nécessite un diagnostic accompagné.

Le dossier privé choisi doit être conservé : une nouvelle sous-arborescence
`tpp06-operation-…` est créée à chaque opération. En cas d’échec, les copies
partielles sont gardées. Aucun journal brut contenant des commandes ou secrets
n’est affiché dans l’interface. Les mots de passe et clés API ne sont pas
enregistrés dans `operation.json`. Les sauvegardes d’authentification, elles,
restent sensibles. Windows utilise des ACL privées, Linux des permissions 0700/0600.

Pas de télémétrie, d’envoi GitHub, de nettoyage permanent ou de téléchargement
automatique de firmware. Le seul nettoyage automatique de la sauvegarde Cutter
concerne son archive temporaire et son dossier ; un échec de nettoyage est signalé.
L’acquisition NAND retire uniquement ses propres morceaux temporaires, outil
copié en RAM et dossier de travail. Les images PC sont conservées, même en cas
d’échec. Un verrou `/tmp/tpp06-nand.lock` empêche les opérations concurrentes
de cet assistant ; il ne peut pas empêcher un autre client d’écrire sur le panneau.

## 7. Vérification du logiciel et paquet

Les tests couvrent l’interface Tk, la console interactive simulée, les erreurs
de mot de passe, les archives, les journaux, la préparation, l’anti-double-reboot,
l’API simulée, les formats ELF, une transaction logo entièrement simulée et
l’acquisition NAND simulée (variation, troncature, panne de transfert, ECC,
montage temporaire, fichiers altérés et consentement après ADB).
Ils ne constituent pas une certification matérielle.

Le générateur `tools/package_assistant.py` produit un ZIP de sources et son
SHA-256 à partir d’une liste explicite. Il exclut les environnements Python,
journaux, sauvegardes, programmes compilés et outils binaires privés.
