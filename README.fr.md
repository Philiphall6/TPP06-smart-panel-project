# TPP06 — Projet local sans Tuya

[English version](README.en.md)

## Objectif

Transformer le panneau TPP06 en équipement local, sans application ni cloud Tuya, en conservant d’abord toutes les possibilités de retour arrière.

## Étape 0 — Mots de passe à essayer

Tester d’abord une petite liste communautaire de mots de passe avant de lire la NAND. Elle n’est pas liée au numéro de série ; une même valeur peut fonctionner sur plusieurs panneaux. Si aucun candidat ne fonctionne, passer à la récupération locale par NAND.

- [Guide étape 0](docs/fr/00-mots-de-passe-a-essayer.md)

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

## Références

- [Matériel à identifier](docs/materiel.md)
- [NAND et sauvegarde](docs/nand.md)
- [Carte et remontage](docs/remontage.md)

## Source communautaire

Une partie des repères matériels, de la liste de mots de passe et de la méthode de lecture provient des retours publiés dans le sujet Home Assistant : [Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6). Les procédures du dépôt sont adaptées et vérifiées sur notre propre panneau ; aucun dump, hash, clé ou identifiant propre à un appareil n’est publié.
