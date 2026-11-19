# TPP06 · ESPHome + LVGL, en local

Une interface tactile personnalisable pour le panneau **MOES / Tuya TPP06**,
reliée à Home Assistant. ESPHome fonctionne sur le **Linux Anyka d’origine** :
ce n’est pas un ESP32 et il ne faut pas lui envoyer un firmware ESP32.

**[Dernière release : version, nouveautés et limites](https://github.com/Philiphall6/TPP06-smart-panel-project/releases/latest)** ·
[Historique des releases](https://github.com/Philiphall6/TPP06-smart-panel-project/releases)

**[Commencer ici — guide débutant français](docs/fr/DEMARRER-ICI.md)** ·
**[Start here — English beginner guide](docs/en/START-HERE.md)**

[Documentation FR](README.fr.md) · [English documentation](README.en.md) ·
[Archives démontage / NAND / UART](docs/archive/README.md)

## Le boîtier TPP06

<p align="center">
  <img src="media/visuels-produit/01-panneau-blanc.png" alt="TPP06 blanc / white" width="300">
  &nbsp;&nbsp;
  <img src="media/visuels-produit/02-panneau-noir.png" alt="TPP06 noir / black" width="300">
</p>

*L’apparence seule ne garantit pas la compatibilité du firmware.*

## Interface et fonctions

- Accueil sombre à cartes arrondies, heure, date et météo Home Assistant.
- Logo Home Assistant bleu animé lorsqu’un client HA est connecté, gris sinon ;
  petite horloge et Wi-Fi uniquement dans la barre supérieure de l’accueil.
- Pages volet et lumières, paramètres, luminosité, veille et diagnostics.
- Bip tactile local, actif par défaut et désactivable avec choix mémorisé.
- Trois relais locaux avec boutons physiques et voyants, exposés dans HA.
  Le modèle public reste en **observation par défaut** avant validation du matériel.
- Stockage disponible/total et deux commandes distinctes : relancer ESPHome
  ou redémarrer Linux, avec contrôles préalables.
- Paramètres Wi-Fi : recherche, sélection et mot de passe. Cette fonction
  nécessite aussi le service Linux optionnel ; **le changement réel de réseau
  et son retour arrière restent à valider sur matériel**.

![Aperçu illustratif avec données fictives, pas une capture personnelle](docs/images/tpp06-interface-preview.svg)

Les [notes de la dernière release](https://github.com/Philiphall6/TPP06-smart-panel-project/releases/latest)
font foi pour la version, les essais réalisés et les limites. La branche `main`
peut contenir des travaux plus récents. Consulter les [détails de l’interface](docs/fr/interface.md).

## Installation et mises à jour

Compilation dans **ESPHome Device Builder sur Home Assistant**, sans poste Mint
ni serveur de compilation externe obligatoire. Le [YAML complet](esphome/tpp06-lvgl-modern.yaml)
reste éditable : pages, titres, couleurs et entités. Pour une installation
reproductible, prendre les sources du tag indiqué dans la dernière release,
pas une copie arbitraire de `main`.

| Votre situation | Prochaine étape |
| --- | --- |
| ESPHome fonctionne déjà | [Mise à jour OTA](docs/fr/DEMARRER-ICI.md#5-mettre-à-jour-un-panneau-déjà-sous-esphome), sans réinstaller le démarrage |
| Panneau encore d’origine | [Compatibilité, accès réseau, sauvegarde et préparation](docs/fr/DEMARRER-ICI.md) |
| Plus de démarrage ou de réseau | [Récupération avancée](docs/archive/README.md) |

Le parcours courant est **réseau → ADB → sauvegarde → compilation HA → essai
encadré → OTA**. Le démontage et l’UART restent dans les archives de récupération.
L’[assistant de première mise en service](docs/fr/13-installation-assistee.md)
est testé hors ligne ; son parcours complet n’est pas validé pour un novice seul.

> [!WARNING]
> Projet expérimental, spécifique au matériel testé, pas un installateur universel.
> La première préparation écrit un overlay. Sauvegardes et récupération locale
> sont nécessaires. Le secours revient à **Tuya d’origine**, pas automatiquement
> au précédent programme ESPHome ; il ne protège pas d’une panne NAND ou du noyau.
> Veille/réveil, coupure électrique, perte réseau et endurance restent à tester
> selon votre installation. Ne pas ouvrir un panneau sous tension ni exposer ses ports sur Internet.

Une OTA d’interface ne remplace ni le superviseur Linux ni le logo de démarrage.
Le [logo Home Assistant au démarrage](docs/fr/12-logo-demarrage.md) est une
opération NAND distincte, facultative et avancée.

## Documentation et confidentialité

- [Interface, fonctions et limites](docs/fr/interface.md)
- [Relais locaux](docs/fr/14-relais-locaux.md) · [Bip tactile](docs/fr/15-bip-tactile.md)
- [Wi-Fi depuis les paramètres](docs/fr/17-wifi-depuis-ecran.md)
- [Fonctions Tuya restantes](docs/fr/16-ecarts-tuya.md)
- [Accès réseau](docs/fr/00-acces-reseau-authkey.md) · [Tuya Cutter](docs/fr/07-tuya-cutter.md)
- [Portage ESPHome et historique](docs/fr/06-esphome-lvgl-natif.md)
- [openHASP — autre voie expérimentale](docs/fr/05-openhasp-local.md)

La release de l’interface distribue les **sources**, pas un programme personnel
prêt à flasher. Les anciennes releases ADB ne sont pas des firmwares ESPHome.
Compiler chez soi : les clés et paramètres privés restent dans votre installation.
Ne publier ni `secrets.yaml`, YAML personnel, programme compilé personnel,
capture privée, dump ou sauvegarde. Les exemples publics sont fictifs.

## Remerciements

Merci à [t0m1o1](https://github.com/t0m1o1), auteur de **TPPwned**, pour la
découverte de l’extraction réseau de l’AUTHKEY et du calcul du mot de passe,
ainsi qu’aux participants du [sujet Home Assistant](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516).

Projet communautaire indépendant, sans affiliation avec MOES, Tuya,
Home Assistant, ESPHome ou LVGL.
