# TPP06 · Local, sans Tuya

> Redonner le contrôle local à un panneau **MOES / Tuya TPP06** : comprendre le matériel, accéder au système, puis remplacer les dépendances cloud par une intégration ESPHome locale.

[🇫🇷 Documentation française](README.fr.md) &nbsp;·&nbsp; [🇬🇧 English documentation](README.en.md)

---

## Le projet en trois étapes

| Étape | Objectif | État |
|:--|:--|:--|
| **01 · Matériel & NAND** | Identifier la mémoire, effectuer plusieurs lectures vérifiées et retrouver les identifiants de maintenance autorisés. | ✅ Terminé |
| **02 · UART & système** | Ouvrir la console série et valider l’accès à l’ensemble du système, sans modification. | 🟡 En cours |
| **03 · Local & ESPHome** | Conserver l’Anyka, modifier le logiciel pour retirer Tuya et fournir un accès local à ESPHome. | 🔜 Préparé |

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

Les dumps NAND, hashes, identifiants propres à un appareil, clés et données personnelles restent hors du dépôt. Les [candidats de mot de passe non vérifiés](docs/fr/candidats-mot-de-passe.md) sont publiés séparément pour les essais autorisés.

## Remerciements

Merci à **[tom101](https://community.home-assistant.io/u/tom101)** et aux participants du fil [*Integration in HA of new mini 3.5 smart control panel TPP06*](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6) sur la communauté Home Assistant. Leurs retours ont permis de lancer l’exploration matérielle et la lecture de la NAND.

---

*Projet communautaire indépendant, sans affiliation avec MOES, Tuya, Home Assistant ou ESPHome.*
