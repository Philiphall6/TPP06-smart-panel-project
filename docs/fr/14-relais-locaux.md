# Trois relais, touches physiques et voyants (expérimental)

Statut au 18 novembre 2026 : pilote testé sur matériel simulé, puis installé
en observation et enfin en commande locale (`0.1.5-relays.1`). Le propriétaire
a confirmé la commutation des trois éclairages par les touches de façade.
Les niveaux GPIO et voyants concordaient ; les trois switches sont exposés par
l'API chiffrée. **Les essais sans point d'accès/HA et de démarrage hors réseau
restent à réaliser.**
Ce document n'est pas une validation de
câblage secteur ni une garantie de compatibilité avec toutes les variantes.

## Sorties locales

| Canal logiciel Tuya | Fichier de commande | GPIO dans l'arbre matériel |
| --- | --- | --- |
| Relais 1 | `/sys/class/gpio/KC_CTL1/value` | 65 |
| Relais 2 | `/sys/class/gpio/KC_CTL2/value` | 66 |
| Relais 3 | `/sys/class/gpio/KC_CTL3/value` | 67 |

Les trois sorties sont déjà exportées par Linux, en direction `out` et avec
`active_low=0`. L'arbre matériel donne une valeur initiale de zéro. Cela décrit
le niveau logiciel, **pas une mesure de tension sur les bornes**.

La bibliothèque d'origine `libtuya_app.so` contient :

- `tuya_relay_mgr_init` : associe, dans cet ordre, les trois canaux aux trois
  chemins `KC_CTL` et appelle `tuya_cc_relay_init` avec trois canaux ;
- `tuya_cc_set_relay_status` : vérifie le numéro de canal, convertit l'état
  en texte et le transmet à `tkl_file_write`, puis publie le changement ;
- des routines de test distinctes contenant des commandes zéro/un vers les
  mêmes sorties. **Ne pas exécuter ces routines : certaines activent les trois
  sorties simultanément.**

Empreinte SHA-256 de la bibliothèque analysée :
`f940aeee4a70e6ccb7f12eda075b40c7a3577484f1a460c327d9055d5d8477f7`.
La bibliothèque propriétaire et les dumps ne sont pas inclus dans le dépôt.

## Entrées et voyants

| Entrée Linux `gpiokeys` | Code d'événement | GPIO | Anti-rebond déclaré |
| --- | --- | --- | --- |
| `key_f1` | 59 (`KEY_F1`) | 62 | 30 ms |
| `key_f2` | 60 (`KEY_F2`) | 63 | 30 ms |
| `key_f3` | 61 (`KEY_F3`) | 64 | 30 ms |

Les entrées sont actives à l'état bas. Elles sont accessibles via evdev,
séparément du tactile. Sur le panneau inspecté : `event0` pour les touches,
`event1` pour Goodix. Le pilote vérifie le nom et les capacités du
périphérique, et non uniquement son numéro.

Les voyants `button1_led`, `button2_led`, `button3_led` correspondent aux GPIO
6, 85 et 79. Leur luminosité ne constitue pas une preuve de l'état des relais.

Sur le panneau de référence, les appuis et les charges ont confirmé :
**haut → F1 → relais 1 ; milieu → F2 → relais 2 ; bas → F3 → relais 3**.
Vérifier cette correspondance sur chaque variante. Des événements supplémentaires
avaient été observés pendant le repérage initial ; leur cause n'est pas établie.
Répéter les essais d'appui/relâchement et vérifier l'absence de double bascule.

### Quatrième commande / bouton du haut

L'arbre matériel déclare aussi `mic_mute`, libellé `mic mute switch`, sur GPIO
19 actif bas. Il produit le type `EV_SW` (5), code `SW_MUTE_DEVICE` (14), pas
une quatrième touche F ni `KEY_POWER`. L'utilisateur signale un bouton Power
sur le haut ; son association à cette entrée reste à observer. **Le pilote
journalise cet événement sans action : il ne coupe ni Linux ni les relais.** Ne pas affecter
un arrêt système ou une commande générale sur la seule base de son emplacement.

## Pilote expérimental et réglages

Le composant `tpp06_local_relays` lit les touches evdev et commande les sorties
directement : aucun appel à HA, Internet ou au Wi-Fi dans ce chemin de commande.
Il expose trois entités `switch` par l'API native ESPHome. Après une commande
locale ou HA, il relit le niveau GPIO et publie cet état (pas une mesure électrique
du contact). Les mêmes identifiants peuvent être utilisés dans des actions
LVGL `switch.toggle` ; les pages V5/V6 existantes ne sont pas encore modifiées.

Le [package optionnel](../../esphome/packages/local-relays-experimental.yaml)
doit être intégré dans la configuration native complète du panneau, avec
`tpp06_local_relays` ajouté à la liste des composants externes. Ce n'est pas un
firmware autonome et ce n'est pas une configuration pour ESP32. Compiler dans
Home Assistant ; aucune compilation de firmware sur Mint n'est nécessaire.

Réglages éditables dans Device Builder :

- `control_enabled: false` par défaut : observation uniquement, aucune écriture
  de relais **ni de voyant**, même si HA envoie une commande ;
- `key_map: [1, 2, 3]` : canaux associés à F1/F2/F3, permutation à adapter après
  identification physique ;
- `indicator_mode: follow_relay` : voyant allumé pour le relais actif ; `off`
  pour laisser les trois voyants éteints. Une panne de voyant ne bloque pas les
  relais. Les voyants ne sont synchronisés que lorsque le contrôle est activé ;
- `pulse_duration: 0s` sur chaque switch : marche/arrêt maintenu, choix par défaut ;
- `pulse_duration: 500ms`, par exemple : impulsion locale avec retour à l'arrêt.
  La plage acceptée est 100 ms à 60 s. Une commande ON répétée ne prolonge pas
  l'impulsion. OFF l'interrompt. Le relais reste une entité switch dans HA.

Au démarrage, les niveaux existants sont lus sans commuter les relais : aucun
restore depuis des préférences anciennes. `restore_mode: DISABLED` est imposé.
L'arrêt ordonné ne commute pas non plus les relais. Une coupure d'alimentation
est différente : l'arbre matériel d'origine initialise les GPIO à zéro.

**L'impulsion est un minuteur logiciel, pas une fonction de sécurité.** Une panne
du processus ou du système peut empêcher l'arrêt temporisé. Un état ON hérité
au démarrage est conservé, sans inventer la durée restante ; seule une commande
ON explicite arme une nouvelle impulsion. Ne pas utiliser pour une charge dont
la sécurité dépend d'une durée maximale garantie.

Le pilote vérifie noyau, architecture, arbre matériel, direction/polarité et
capacité des touches. Il refuse la concurrence détectée avec Tuya et prend un
verrou entre instances du pilote. Ce verrou n'est pas partagé par Tuya :
l'absence du programme et de son moniteur reste un prérequis. Une erreur de
commande verrouille les nouvelles commandes jusqu'au redémarrage du processus,
sans basculer automatiquement d'autres sorties.

### Retour du premier essai d'observation

La version `0.1.5-observation.1` expose les trois switches par l'API chiffrée,
mais son pilote ne devient pas prêt : son fichier de verrou était placé dans
`/run`, sur la racine squashfs en lecture seule du panneau. Le message initial
suggérant un autre contrôleur était trop général et ne prouvait pas une
concurrence réelle. La correction utilise `/var/run`, sur le tmpfs `/var`, et
distingue l'échec d'ouverture de l'échec de verrouillage, avec le code d'erreur.
Les tests simulés couvrent désormais un répertoire en lecture seule.
**Correction compilée dans HA et installée sous `0.1.5-observation.2` :
verrou et entrées prêts, API chiffrée accessible pendant le contrôle de 90 s.**
La version `0.1.5-relays.1` a ensuite permis les essais physiques confirmés
ci-dessus. Redémarrer la première version ne corrige pas son chemin de verrou.

## Continuité sans réseau : deux couches à valider

`api.reboot_timeout: 0s` est obligatoire ; le composant refuse une configuration
qui redémarre à la perte du client API (même contrôle pour MQTT si utilisé).

Le superviseur historique contrôlait aussi l'association Wi-Fi et le bail DHCP.
Une option distincte est préparée dans `device/tpp06-multiboot.sh` : seulement
si `local_control_confirmed=yes`, `persistent_confirmed=yes`,
`boot_policy=persistent` et `network_mode=isolated`, hors essai temporisé, il
laisse le programme fonctionner quand le point d'accès ou le bail manque.
WPA/DHCP continuent en arrière-plan ; les contrôles de processus et des ports
locaux API/secours sont conservés. Internet et la connexion HA ne sont pas des
critères de santé. Les premières installations et essais non confirmés gardent
les anciens garde-fous. **Aucun de ces marqueurs n'a été activé sur le panneau
par cette préparation.** L'OTA du programme ne met pas à jour ce script Linux.

Validation restante, sur place : essais répétés des touches et voyants ;
commande et état dans HA ; absence de double bascule après reconnexion ; perte HA puis
point d'accès ; démarrage sans point d'accès avec récupération disponible.
La politique autonome ne doit être confirmée qu'après ces contrôles supervisés.
Le secteur peut être présent : aucun démontage ni manipulation des conducteurs
sous tension.

## Premier essai : observation uniquement

1. Conserver une copie privée de la configuration et du programme fonctionnels.
   Garder les clés API/OTA et les paramètres réseau existants ; ne pas les publier.
2. Compiler dans HA avec `control_enabled: false`. Avant tout transfert, vérifier
   le binaire ARMv5TE statique soft-float et la place pour le fichier temporaire
   OTA **en plus** du programme actuel et d'une réserve de 2 Mio.
3. Après une installation explicitement décidée, vérifier le retour de l'API
   chiffrée, de l'affichage et des accès de récupération. Ne pas activer encore
   la politique de fonctionnement hors réseau du superviseur.
4. Ouvrir les journaux ESPHome, puis observer un appui bref à la fois sur les
   trois touches de façade. Noter la position physique et la ligne
   `F… press -> channel … (observation only)`. Aucun relais ni voyant n'est
   commandé par ce pilote dans ce mode ; les trois switches HA ne sont pas
   encore utilisables pour commander les charges.
5. Le bouton supérieur n'est pas encore identifié : ne pas lui attribuer
   d'action Power. Une éventuelle ligne `SW_MUTE_DEVICE=…` est seulement un
   indice à corréler à une manipulation observée, pas une preuve de sa fonction.

La compilation et ces observations ne valident pas encore l'ordre des sorties
électriques, les voyants ni l'autonomie sans réseau. L'activation des commandes
et leurs essais supervisés constituent une étape distincte.

Après identification des charges et des touches, avec surveillance sur place,
passer explicitement à `control_enabled: true`, compiler dans HA et installer
par OTA. Tester un relais à la fois et vérifier son voyant et l'état HA.
Le package public conserve `false` : importer cet exemple ne doit pas activer
à l'aveugle les sorties d'un autre panneau. Le mode impulsion n'a été testé
que par simulation, pas avec les charges du panneau de référence.

## English summary

Read-only investigation identified Tuya's three local relay paths (`KC_CTL1`
through `KC_CTL3`, GPIOs 65–67), three evdev keys (F1–F3, GPIOs 62–64), and
independent LEDs (GPIOs 6, 85, 79). The runtime-lock fix was installed, followed
by confirmed physical lighting control: top/middle/bottom map to channels 1/2/3
on the reference panel. Offline startup and HA/AP-loss acceptance remain pending;
the public package keeps control disabled until on-site checks. See the
[English guide](../en/14-local-relays.md).
