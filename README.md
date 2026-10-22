# TPP06 · Local, sans Tuya

> Redonner le contrôle local à un panneau **MOES / Tuya TPP06** : essayer d’abord les accès communautaires connus, comprendre le matériel si nécessaire, accéder au système, puis remplacer les dépendances cloud par une intégration ESPHome locale.

[🇫🇷 Documentation française](README.fr.md) &nbsp;·&nbsp; [🇬🇧 English documentation](README.en.md)

---

## Le projet en quatre étapes

| Étape | Objectif | État |
|:--|:--|:--|
| **00 · Mots de passe à essayer** | Essayer une petite liste communautaire avant de démonter le panneau. Elle n’est pas liée au numéro de série ; une même valeur peut fonctionner sur plusieurs appareils. | ✅ Documenté |
| **01 · Matériel & NAND** | Créer une sauvegarde vérifiée et retrouver l’accès propre au panneau si l’étape 0 échoue. | ✅ Terminé |
| **02 · UART & système** | Ouvrir la console série et valider l’accès à l’ensemble du système, sans modification. | 🟡 En cours |
| **03 · Local & ESPHome** | Conserver l’Anyka, modifier le logiciel pour retirer Tuya et fournir un accès local à ESPHome. | 🔜 Préparé |

## Commencer par l’étape 0

La liste de [mots de passe communautaires](docs/fr/00-mots-de-passe-a-essayer.md) doit être prête avant toute lecture NAND, mais son essai nécessite d’abord l’[UART](docs/fr/02-uart-acces-systeme.md). Elle n’est pas liée au numéro de série : c’est une petite liste de valeurs partagées. Sur notre panneau, le mot de passe récupéré correspondait à l’un des candidats du forum ; le même résultat peut se répéter sur d’autres appareils, sans être garanti.

L’ordre pratique est donc : UART → essai de la liste → sauvegarde NAND avec le XGecu et recherche locale si aucun candidat ne donne accès.

## Prochaine étape : accès système par UART

Le panneau a redémarré après la lecture puis la remise en place de la NAND. La prochaine session sert uniquement à obtenir et documenter l’accès UART : démarrage, services actifs et interfaces locales.

Une fois cet accès complet validé, l’étape 3 commencera :

- comprendre comment Tuya démarre et communique ;
- conserver l’interface, l’écran et le processeur **Anyka** déjà présents ;
- créer ou adapter un service local, sans cloud ;
- exposer les commandes et états du panneau à **ESPHome** ;
- désactiver Tuya seulement après validation du fonctionnement local.

[Voir le plan de l’étape 3 en français →](docs/fr/03-suppression-tuya-esphome.md)
[See the Phase 3 plan in English →](docs/en/03-remove-tuya-esphome.md)

## Ce que contient le dépôt

- guides matériels, brochages et retours d’expérience ;
- photos de la lecture de la NAND et du remontage ;
- procédure UART réversible ;
- feuille de route pour une intégration ESPHome locale.

Les dumps NAND, hashes, identifiants propres à un appareil, clés et données personnelles restent hors du dépôt. Les mots de passe de l’étape 0 sont une liste communautaire de candidats à essayer, et non des données extraites d’un appareil.

## Remerciements

Merci à **[tom101](https://community.home-assistant.io/u/tom101)** et aux participants du fil [*Integration in HA of new mini 3.5 smart control panel TPP06*](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6) sur la communauté Home Assistant. Leurs retours ont permis de lancer l’exploration matérielle et la lecture de la NAND.

---

*Projet communautaire indépendant, sans affiliation avec MOES, Tuya, Home Assistant ou ESPHome.*
