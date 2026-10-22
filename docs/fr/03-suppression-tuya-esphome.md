# Étape 3 — Suppression de Tuya et accès local via ESPHome

## But

Conserver la carte TPP06 et son processeur Anyka, mais modifier le logiciel existant pour supprimer la dépendance à l’application et au cloud Tuya. Le résultat doit être accessible localement depuis ESPHome.

Aucun remplacement de contrôleur n’est prévu et ESPHome ne doit pas être flashé directement sur le processeur Anyka.

## Pré-requis

- Sauvegarde NAND locale vérifiée.
- Accès UART fonctionnel.
- Identification du compte autorisé et connexion système établie.
- Journaux de démarrage et inventaire des services sauvegardés sans secrets.

## Plan de travail

1. Identifier les services Tuya, les scripts de démarrage, les interfaces réseau et les processus qui commandent l’écran, les boutons et les sorties.
2. Cartographier les mécanismes locaux déjà présents : sockets Unix, ports réseau, commandes, fichiers de configuration et bus matériels.
3. Créer ou adapter un service local qui commande le panneau sans cloud Tuya.
4. Exposer ce service à ESPHome avec une interface documentée et locale. Le protocole sera choisi après l’inventaire : API ESPHome si elle est réalisable sur le système, ou composant/adaptateur ESPHome vers l’interface locale du panneau.
5. Désactiver le démarrage et les communications Tuya seulement après validation complète du contrôle local.
6. Vérifier que les boutons, l’écran et les automatisations locales fonctionnent sans Internet.

## Critères de réussite

- Le panneau démarre et reste fonctionnel sans compte Tuya ni accès au cloud.
- Les commandes locales du panneau restent opérationnelles.
- ESPHome peut lire l’état et commander les fonctions utiles sur le réseau local.
- La modification est réversible grâce à la sauvegarde NAND conservée hors GitHub.
- La documentation décrit les services modifiés, l’interface locale et la procédure de retour arrière, sans publier de mot de passe ni de clé.

## Sortie de l’étape

Un logiciel TPP06 localisé, sans service Tuya actif, et une intégration ESPHome documentée.
