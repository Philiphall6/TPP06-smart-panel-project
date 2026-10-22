# Étape 0 — Mots de passe à essayer avant la NAND

## But

Essayer d’abord une petite liste de mots de passe partagés par la communauté, via un accès local ou UART autorisé, avant de démonter la NAND ou d’utiliser le XGecu.

## Origine de la liste

Ces candidats ne sont **pas calculés à partir du numéro de série** et n’ont pas de relation connue avec celui-ci. Il s’agit simplement de quelques valeurs partagées par la communauté. Une même valeur peut fonctionner sur plusieurs panneaux, mais ce n’est pas garanti.

Sur le panneau documenté dans ce dépôt, le mot de passe récupéré a correspondu à l’un des candidats du forum. La liste reste donc la voie la plus simple à tester en premier.

## Liste de candidats

```text
6b7835db
80a69d0f
de8ba884
33a644d0
314b6d93
5bfd1d91
```

Essayer cette liste uniquement sur un panneau dont l’accès est autorisé, sans multiplier les tentatives.

## Si aucun candidat ne fonctionne

Passer à l’[étape 1 — matériel et lecture NAND](01-materiel-nand-mot-de-passe.md) : créer une sauvegarde vérifiée avec le XGecu, puis rechercher les informations de connexion propres au panneau dans le dump local. Ne publiez ni dump NAND, ni hash, ni identifiant propre à un appareil.

## Source

[Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6), communauté Home Assistant.
