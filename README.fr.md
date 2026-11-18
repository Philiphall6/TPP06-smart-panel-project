# TPP06 — documentation française

**[Guide débutant : commencer ici, sans démontage](docs/fr/DEMARRER-ICI.md)**

[Accueil du projet](README.md) · [English](README.en.md)

## Le boîtier TPP06

<p align="center">
  <img src="media/visuels-produit/01-panneau-blanc.png" alt="TPP06 avec commandes blanches" width="300">
  &nbsp;&nbsp;
  <img src="media/visuels-produit/02-panneau-noir.png" alt="TPP06 avec commandes noires" width="300">
</p>

*Visuels de référence des deux variantes du boîtier. L’apparence seule ne garantit pas la compatibilité du firmware.*

## Ce qui fonctionne sur le panneau de référence

La **V5 / `0.1.5`** est installée : binaire vérifié, API chiffrée accessible,
Wi-Fi connecté, superviseur sain et démarrage permanent conservé. Une capture
réelle confirme l’accueil LVGL avec icônes, date et heure. Compilation dans
Home Assistant et mise à jour sans fil ; aucun poste Mint imposé.

Le logiciel est ESPHome natif sur **Linux Anyka ARMv5**, pas un firmware ESP32.
Le YAML reste librement éditable dans Device Builder. Les pilotes sont fournis
par ce dépôt ; les noms, entités et secrets appartiennent à chaque installation.

> [!WARNING]
> Première installation expérimentale : compatibilité à contrôler, sauvegarde
> obligatoire, récupération physique possible. Le démarrage permanent a été
> vérifié par redémarrages logiciels, pas par coupure électrique. Le secours
> logiciel ne garantit pas la récupération en cas de panne du noyau ou de NAND.

## Parcours normal

Un [assistant expérimental](docs/fr/13-installation-assistee.md) prépare la
transition vers ESPHome principal. Tests hors ligne uniquement : sa procédure
complète reste à valider sur matériel avant un usage novice autonome.

1. [Identifier son cas et préparer HA](docs/fr/DEMARRER-ICI.md).
2. [Obtenir l’accès par le réseau](docs/fr/00-acces-reseau-authkey.md).
3. [Préparer ADB si nécessaire](docs/fr/04-adb-wifi-sans-uart.md), puis
   [sauvegarder avec le Cutter](docs/fr/07-tuya-cutter.md).
4. Personnaliser et compiler le [YAML V5](esphome/tpp06-lvgl-mobile.yaml)
   dans Device Builder ; première mise en service encadrée.
5. Si ESPHome fonctionne déjà, utiliser **Installer → Sans fil**, sans
   réinstaller l’overlay ni le superviseur.

## Fonctions et limites

- [V5 : accueil, icônes, paramètres, luminosité et veille](docs/fr/11-interface-v5.md).
  Laisser la veille sur **Jamais** jusqu’au test de réveil sur place ; bip indisponible.
- [Détails ESPHome / historique](docs/fr/06-esphome-lvgl-natif.md).
- [Multiboot, sauvegarde et retour Tuya](docs/fr/07-tuya-cutter.md).
- [openHASP, voie distincte](docs/fr/05-openhasp-local.md).
- [Logo Home Assistant à la place de MOES](docs/fr/12-logo-demarrage.md) :
  facultatif, écriture NAND distincte de l’OTA, réservé à une intervention avancée.

## Archives matérielles

Le démontage, le dessoudage NAND, l’UART et la recherche historique de mots de
passe sont regroupés dans les **[archives](docs/archive/README.md)**. Ils ne
sont pas nécessaires au parcours réseau compatible. Les anciens liens restent
accessibles ; ne pas suivre leurs états historiques comme la procédure actuelle.

## Confidentialité et contributions

Créer une clé privée différente pour chaque panneau. Ne publier ni YAML
personnel, ni secrets, ni binaire compilé personnel, ni dump/sauvegarde.
Les exemples d’adresses et d’entités sont fictifs.

Crédit à [t0m1o1](https://github.com/t0m1o1), auteur de TPPwned, pour la
découverte de l’accès AUTHKEY réseau. Voir les [remerciements](README.md#remerciements).
