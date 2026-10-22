# TPP06 — Projet local sans Tuya

[English version](README.en.md)

## Objectif

Transformer le panneau TPP06 en équipement local, sans application ni cloud Tuya, en conservant d’abord toutes les possibilités de retour arrière.

## Étape 1 — Matériel, NAND et mot de passe

Identifier la carte et sa NAND, créer une sauvegarde vérifiée, puis retrouver les identifiants autorisés nécessaires à la maintenance locale.

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
