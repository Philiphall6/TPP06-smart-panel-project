# Étape 3 — Suppression de Tuya et migration vers ESPHome

## But

Supprimer la dépendance à l’application et au cloud Tuya pour obtenir un contrôle local durable.

## Contrainte matérielle

La carte utilise un processeur Anyka `AK3761EE128`. ESPHome répertorie des microcontrôleurs pris en charge, mais pas cette famille Anyka. Il ne faut donc pas tenter de flasher ESPHome directement sur le processeur Anyka.

Référence : [microcontrôleurs pris en charge par ESPHome](https://esphome.io/components/).

## Deux voies à évaluer

### A. Remplacer le contrôleur par un ESP32 exécutant ESPHome

C’est la voie la plus directe pour supprimer Tuya. Elle demande :

1. Cartographier les boutons, voyants, écran, alimentation et sorties de la carte.
2. Définir les niveaux électriques et isolations nécessaires.
3. Tester d’abord les entrées, l’écran et les voyants sur établi.
4. Créer une configuration ESPHome minimale, puis ajouter les fonctions une par une.
5. Valider le contrôle local dans Home Assistant avant de retirer définitivement la logique Tuya.

### B. Conserver le processeur Anyka avec un logiciel local

Après l’accès UART, vérifier s’il est techniquement possible d’exécuter un service local sur le système Linux existant. Cette option peut éviter le remplacement matériel, mais elle n’est pas une installation ESPHome native et nécessite une analyse du système, de la mémoire disponible et de la chaîne de compilation.

## Critères de réussite

- Le panneau fonctionne sans compte Tuya ni accès cloud.
- Les commandes essentielles restent disponibles localement.
- Home Assistant contrôle le panneau en réseau local.
- Un schéma d’E/S, le câblage final et la configuration sont documentés.
- La sauvegarde NAND reste conservée hors GitHub.

## Sortie de l’étape

Une architecture locale validée : soit ESPHome sur contrôleur de remplacement, soit solution locale adaptée au système Anyka.
