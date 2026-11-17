# TPP06 — Projet local sans Tuya

[English version](README.en.md)

> [!CAUTION]
> **ESPHome n'est pas encore fonctionnel en installation permanente.** Le
> binaire ARMv5 démarre en essai temporaire, mais le basculement au démarrage
> peut couper le Wi-Fi et provoquer une boucle liée au watchdog Tuya.
> N'utilisez pas `install esphome` ni `switch esphome` et gardez un accès UART.

## Objectif

Transformer le panneau TPP06 en équipement local, sans application ni cloud Tuya, en conservant d’abord toutes les possibilités de retour arrière.

## Étape 0 — Accès réseau sans démontage

Interroger en lecture seule le service de test local du panneau afin de récupérer son `AUTHKEY` et de calculer son mot de passe `root`/ADB. Cette voie ne nécessite ni UART ni dessoudage de la NAND.

- [Guide d'accès réseau et outil AUTHKEY](docs/fr/00-acces-reseau-authkey.md)
- [Outil Python](tools/tpp06_authkey_reader.py)

**État :** méthode vérifiée sur un TPP06 ; mot de passe propre au panneau récupéré par Wi-Fi.

## Étape 0b — Mots de passe communautaires à essayer

Préparer une petite liste communautaire, puis l’essayer après connexion de l’UART et avant toute lecture NAND. Elle n’est pas liée au numéro de série ; une même valeur peut fonctionner sur plusieurs panneaux. Si aucun candidat ne fonctionne, passer à la récupération locale par NAND.

- [Liste communautaire](docs/fr/00-mots-de-passe-a-essayer.md)

**État :** liste documentée ; un candidat a correspondu au mot de passe récupéré sur ce panneau.

## Étape 1 — Matériel et NAND

Identifier la carte et sa NAND, puis créer une sauvegarde vérifiée uniquement si l’étape 0 ne donne pas accès ou si une analyse matérielle est nécessaire.

- [Guide étape 1](docs/fr/01-materiel-nand-mot-de-passe.md)
- [Journal détaillé de lecture NAND](docs/lecture-nand.md)
- [Retour d’expérience — Français](docs/retour-experience-lecture-nand.md)

**État :** sauvegarde NAND vérifiée et démarrage du panneau confirmé après remontage.

## Étape 2 — UART et accès système

Ouvrir une console série, documenter le démarrage, puis accéder au système avec les identifiants récupérés et autorisés.

- [Guide étape 2](docs/fr/02-uart-acces-systeme.md)
- [Brochage UART détaillé](docs/uart.md)

**État :** brochage identifié ; connexion terminal à réaliser.

## Étape 3 — Suppression de Tuya et accès via ESPHome

Conserver le processeur Anyka et modifier son logiciel pour supprimer Tuya, remplacer ses dépendances cloud par un service local et rendre le panneau accessible via ESPHome.

- [Guide étape 3 : suppression de Tuya et ESPHome](docs/fr/03-suppression-tuya-esphome.md)

**État :** à réaliser après l’accès UART et l’inventaire du logiciel existant.

## Étape 4 — ADB par Wi-Fi sans UART

Installer par le service de production local `8090` un overlay persistant qui
lance ADB sur le port `5555`, puis se connecter avec le compte `root` et le mot
de passe calculé à l'étape 0.

- [Tutoriel d'installation, sécurité et retour arrière](docs/fr/04-adb-wifi-sans-uart.md)
- [Outil d'envoi du paquet](tools/tpp06_ota_uploader.py)

**État :** vérifié sur un TPP06/AK3761E avec noyau `4.4.192V2.4` ; publié en
préversion expérimentale. Le paquet remplace `/data/app` et `/data/customize`
et ne doit pas être utilisé sur une variante inconnue.

## Étape 5 — Interface locale openHASP

Compiler et exécuter openHASP directement sur le Linux Anyka du panneau afin
d'obtenir une interface locale 320×480 et, ensuite, de relier ses commandes à
Home Assistant par MQTT.

- [Guide étape 5 : portage openHASP local](docs/fr/05-openhasp-local.md)
- [Correctif à appliquer au dépôt openHASP](openhasp/openhasp-tpp06.patch)

**État :** binaire ARMv5/uClibc démarré sur le panneau ; framebuffer, ordre
BGR565, orientation portrait et détection Goodix validés. L'installation au
démarrage et la validation physique complète du tactile restent à terminer.

## Étape 6 — ESPHome + LVGL natif

Compiler ESPHome `host` directement pour l'Anyka ARMv5 et utiliser LVGL avec
des composants Linux natifs pour `/dev/fb0` et `/dev/input/event1`.

- [Guide étape 6 : ESPHome + LVGL natif](docs/fr/06-esphome-lvgl-natif.md)
- [YAML portable pour Device Builder](esphome/tpp06-device-builder.yaml)
- [Correctif à appliquer au dépôt ESPHome](esphome-lvgl/esphome-tpp06-lvgl.patch)

**État :** compilation et essai temporaire du framebuffer/tactile validés.
L'installation permanente est **non fonctionnelle** : le Wi-Fi peut ne pas
être initialisé et le panneau peut entrer en boucle de démarrage. Elle est
bloquée dans Tuya Cutter en attendant une solution vérifiée sur matériel.

## Étape 7 — Installateur réversible Tuya Cutter

Automatiser la lecture de l'accès propre au panneau, la connexion ADB, les
sauvegardes et les essais ou installations openHASP/ESPHome-LVGL.

- [Guide étape 7 : TPP06 Tuya Cutter](docs/fr/07-tuya-cutter.md)
- [Outil Python](tools/tpp06_tuya_cutter.py)

**État :** CLI et protections de restauration testées hors ligne ; validation
ADB complète prévue après le prochain redémarrage du panneau.

## Références

- [Matériel à identifier](docs/materiel.md)
- [NAND et sauvegarde](docs/nand.md)
- [Carte et remontage](docs/remontage.md)

## Source communautaire

Une partie des repères matériels, de la liste de mots de passe et de la méthode de lecture provient des retours publiés dans le sujet Home Assistant : [Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6). La découverte de l'extraction réseau de l'`AUTHKEY` et du calcul du mot de passe revient à [t0m1o1](https://github.com/t0m1o1), auteur du projet TPPwned. Les procédures du dépôt sont adaptées et vérifiées sur notre propre panneau ; aucun dump, hash, clé ou identifiant propre à un appareil n'est publié.
