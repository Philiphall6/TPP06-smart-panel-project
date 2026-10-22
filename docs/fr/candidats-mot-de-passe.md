# Candidats de mot de passe à tester

Ces valeurs ont été partagées comme **candidats** pour la connexion locale du TPP06. Sur le panneau documenté ici, le mot de passe récupéré a correspondu à l’un des candidats publiés sur le forum Home Assistant. Elles restent néanmoins à tester sur chaque panneau : elles ne proviennent pas d’un dump publié dans ce dépôt.

À essayer uniquement sur un panneau dont l’accès est autorisé, **avant de démonter la NAND ou d’utiliser le XGecu** :

```text
6b7835db
80a69d0f
de8ba884
33a644d0
314b6d93
5bfd1d91
```

Si aucun candidat ne fonctionne, ne pas multiplier les essais : revenir aux journaux UART et à l’analyse locale du système. La lecture NAND avec le XGecu devient alors l’étape suivante pour créer une sauvegarde et comprendre le système. Ne publiez ni dump NAND, ni hash, ni identifiant propre à un appareil.

Source communautaire : [Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6).
