# TPP06 · Local, sans Tuya

> Redonner le contrôle local à un panneau **MOES / Tuya TPP06** : récupérer d’abord son accès propre par le réseau local, comprendre le matériel si nécessaire, accéder au système, puis remplacer les dépendances cloud par une intégration ESPHome locale.

[🇫🇷 Documentation française](README.fr.md) &nbsp;·&nbsp; [🇬🇧 English documentation](README.en.md)

> [!CAUTION]
> **Le multiboot ESPHome est encore expérimental.** Le superviseur V1 conserve
> Tuya, le Wi-Fi et le port 8090 pendant les essais en mode apprentissage.
> Chaque sélection personnalisée est ponctuelle : le prochain démarrage reste
> Tuya même après validation. Ce secours logiciel n'est pas une garantie. Les tests hors ligne
> passent, mais le cycle électrique réel reste à valider. L'installation exige
> `--experimental-multiboot` et un accès UART de secours.

Le Wi-Fi autonome (`wpa_supplicant`/DHCP) reste expérimental et exige une
sélection explicite. Aucun essai réussi ne l'active automatiquement.

**Validation actuelle :** tactile validé, essai supervisé de 15 minutes réussi,
OTA chiffrée testée sur une copie isolée en RAM, sans redémarrage Linux.
La MAC réelle, le mDNS et le chiffrement de l'API sont préparés dans le nouveau
modèle, mais restent à valider ensemble sur le panneau. L'installation OTA
depuis le bouton du Builder et le démarrage permanent ne sont pas validés.

**Configuration portable :** noms et entités modifiables dans le YAML,
composants chargés depuis GitHub, aucune dépendance à un ordinateur.
Chaque installation crée sa clé locale dans `secrets.yaml` (jamais publiée).
Les adresses `192.0.2.1` des exemples sont fictives et doivent être remplacées.

## Commencer ici — accès réseau sans démontage

La nouvelle **étape 0** récupère en lecture seule l'`AUTHKEY` du panneau sur le réseau local et calcule son mot de passe `root`/ADB. Elle ne nécessite ni UART, ni ouverture du boîtier, ni dessoudage de la NAND.

```bash
python3 tools/tpp06_authkey_reader.py ADRESSE_IP_DU_PANNEAU
```

- [Guide français — récupération réseau de l'AUTHKEY](docs/fr/00-acces-reseau-authkey.md)
- [English guide — network AUTHKEY recovery](docs/en/00-network-authkey-access.md)
- [Outil Python en lecture seule](tools/tpp06_authkey_reader.py)

L'outil masque l'`AUTHKEY` et n'affiche jamais les éventuels identifiants Wi-Fi présents dans la réponse.

## Les deux variantes du panneau

<p align="center">
  <img src="media/visuels-produit/01-panneau-blanc.png" alt="TPP06 avec commandes blanches" width="300">
  &nbsp;&nbsp;
  <img src="media/visuels-produit/02-panneau-noir.png" alt="TPP06 avec commandes noires" width="300">
</p>

*Visuels de référence des deux panneaux utilisés dans le projet.*
---

## Le projet en six étapes

| Étape | Objectif | État |
|:--|:--|:--|
| **00 · Accès par le réseau** | Lire l'`AUTHKEY` sur le port local `8090`, puis calculer le mot de passe propre au panneau sans démontage. | ✅ Vérifié |
| **00b · Candidats communautaires** | Essayer la petite liste connue seulement si la récupération réseau n'est pas disponible. | ✅ Documenté |
| **01 · Matériel & NAND** | Créer une sauvegarde vérifiée si les méthodes sans démontage échouent ou si une analyse matérielle est nécessaire. | ✅ Terminé |
| **02 · ADB/USB ou UART** | Utiliser le mot de passe récupéré ; conserver l'UART comme solution de secours. | ✅ Validé |
| **03 · Local & ESPHome** | Conserver l’Anyka et préparer le remplacement des services Tuya. | 🧪 En cours |
| **04 · ADB par Wi-Fi** | Installer par le port `8090` un accès ADB persistant sur `5555`, sans ouvrir le panneau. | 🧪 Préversion expérimentale |
| **05 · openHASP local** | Exécuter une interface locale 320×480 sur l’écran, avec tactile et MQTT/Home Assistant. | 🧪 Premier portage validé |
| **06 · ESPHome + LVGL natif** | Exécuter le moteur LVGL d'ESPHome directement sur Linux Anyka avec framebuffer et tactile natifs. | 🧪 Essai temporaire validé ; multiboot V1 à valider sur matériel |
| **07 · Tuya Cutter** | Automatiser détection, sauvegarde, restauration, essais et basculement réversible entre Tuya, openHASP et ESPHome. | 🧪 Outil en validation |

## Commencer par l’étape 0

Utiliser d'abord le [lecteur réseau AUTHKEY](docs/fr/00-acces-reseau-authkey.md). Le panneau expose son service de test sur le port TCP `8090`; l'outil active temporairement son contexte de lecture, demande la configuration et calcule les huit derniers caractères hexadécimaux du MD5 de l'`AUTHKEY`. Il n'envoie ni écriture persistante, ni redémarrage, ni mise à jour OTA.

Si cette méthode n'est pas disponible, essayer ensuite la [liste de mots de passe communautaires](docs/fr/00-mots-de-passe-a-essayer.md), puis envisager l'UART ou la sauvegarde NAND seulement en dernier recours.

L'ordre pratique devient donc : **récupération réseau → ADB par Wi-Fi → ADB
par USB → candidats communautaires → UART/NAND en dernier recours**.

## Nouveau : ADB par Wi-Fi sans démontage

La première préversion permet maintenant d'installer ADB sur le réseau par le
service local `8090`, sans UART. Elle est limitée au firmware TPP06/AK3761E
testé et remplace `/data/app` ainsi que `/data/customize`. Son correctif RSA
accepte tout client ADB du LAN : le shell garde son identifiant et son mot de
passe, mais le port `5555` doit rester isolé et ne jamais être publié sur
Internet.

- [Tutoriel complet en français](docs/fr/04-adb-wifi-sans-uart.md)
- [English installation guide](docs/en/04-adb-over-wifi-without-uart.md)
- [Outil d'envoi du paquet](tools/tpp06_ota_uploader.py)

Une fois cet accès complet validé, l’étape 3 commencera :

- comprendre comment Tuya démarre et communique ;
- conserver l’interface, l’écran et le processeur **Anyka** déjà présents ;
- créer ou adapter un service local, sans cloud ;
- exposer les commandes et états du panneau à **ESPHome** ;
- désactiver Tuya seulement après validation du fonctionnement local.

[Voir le plan de l’étape 3 en français →](docs/fr/03-suppression-tuya-esphome.md)
[See the Phase 3 plan in English →](docs/en/03-remove-tuya-esphome.md)

## Dernière étape : interface locale openHASP

Un premier portage openHASP fonctionne maintenant directement sur l'Anyka du
TPP06. Le binaire ARMv5/uClibc démarre, utilise `/dev/fb0` en 320×480, corrige
l'ordre BGR565 du panneau et détecte le tactile Goodix sur
`/dev/input/event1`. Les essais restent volontaires et temporaires dans `/tmp` :
Tuya n'est pas encore remplacé au démarrage.

- [Guide français de compilation et d'essai](docs/fr/05-openhasp-local.md)
- [English build and test guide](docs/en/05-openhasp-local.md)
- [Correctif reproductible pour openHASP](openhasp/openhasp-tpp06.patch)

## Alternative ESPHome native avec LVGL

ESPHome officiel 2026.10.2 compile maintenant en ARMv5/uClibc grâce à une
couche de composants externes pour le framebuffer et le tactile. L'interface
LVGL, le tactile et l'API Home Assistant sont validés sur le TPP06. Le dépôt
GitHub sert de source portable à Device Builder ; chaque maison ne conserve
localement que ses substitutions. La première installation reste réversible
via Tuya Cutter ; une fois ESPHome lancé, les mises à jour suivantes utilisent
l'OTA ESPHome natif sur le port 8082.

- [Guide ESPHome + LVGL natif](docs/fr/06-esphome-lvgl-natif.md)
- [Native ESPHome + LVGL guide](docs/en/06-native-esphome-lvgl.md)
- [YAML portable Device Builder](esphome/tpp06-device-builder.yaml)
- [Correctif reproductible ESPHome](esphome-lvgl/esphome-tpp06-lvgl.patch)

## Installateur réversible Tuya Cutter

Le nouvel assistant Python prend seulement l'adresse IP, récupère l'accès du
panneau sans afficher ses secrets, crée des sauvegardes vérifiées et automatise
les essais temporaires ou le basculement réversible entre Tuya, openHASP et
ESPHome-LVGL.

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1
```

- [Tutoriel complet Tuya Cutter](docs/fr/07-tuya-cutter.md)
- [Tuya Cutter English guide](docs/en/07-tuya-cutter.md)
- [Installateur Python](tools/tpp06_tuya_cutter.py)

## Ce que contient le dépôt

- guides matériels, brochages et retours d’expérience ;
- outil réseau en lecture seule pour récupérer l'accès propre au panneau ;
- installateur expérimental et retour arrière pour ADB par Wi-Fi ;
- photos de la lecture de la NAND et du remontage ;
- procédure UART réversible ;
- feuille de route pour une intégration ESPHome locale.

Les dumps NAND, hashes, identifiants propres à un appareil, clés et données personnelles restent hors du dépôt. Les mots de passe de l’étape 0 sont une liste communautaire de candidats à essayer, et non des données extraites d’un appareil.

## Remerciements

Merci à **[t0m1o1](https://github.com/t0m1o1)**, auteur de TPPwned et collaborateur du projet, ainsi qu'aux participants du fil [*Integration in HA of new mini 3.5 smart control panel TPP06*](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6) sur la communauté Home Assistant. Leurs travaux ont permis l'extraction réseau de l'`AUTHKEY`, l'exploration matérielle et la lecture de la NAND.

---

*Projet communautaire indépendant, sans affiliation avec MOES, Tuya, Home Assistant ou ESPHome.*
