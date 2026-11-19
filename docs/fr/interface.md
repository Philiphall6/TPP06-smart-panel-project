# Interface actuelle — ESPHome + LVGL

[Dernière release](https://github.com/Philiphall6/TPP06-smart-panel-project/releases/latest) ·
[Guide débutant](DEMARRER-ICI.md) · [English](../en/interface.md)

Le modèle actuel est [`tpp06-lvgl-modern.yaml`](../../esphome/tpp06-lvgl-modern.yaml).
La version publiée et ses preuves de validation figurent dans les notes de
release, pas dans un numéro de génération du README. Les anciens modèles
restent disponibles pour consultation ; ne pas mélanger leurs blocs au hasard.

## Accueil

Fond sombre, cartes dégradées, heure, date, météo configurable et raccourcis
volet/lumières. Le logo Home Assistant en haut à gauche pulse en bleu lorsqu’un
client API se présente comme Home Assistant ; il devient gris et immobile sinon.
Un lecteur de journaux seul ne suffit pas. C’est une indication visuelle,
pas une preuve d’authentification supplémentaire ni de disponibilité de tous
les services HA. L’heure miniature est à droite, près du Wi-Fi.

Le Wi-Fi n’est pas répété sous la météo. Son icône reflète la liaison Linux,
pas la présence d’Internet. Aucune batterie fictive n’est affichée.
L’aperçu public utilise des données fictives ; ce n’est pas une capture du panneau.

## Paramètres et entités

- Luminosité et veille avec préférences mémorisées. Veille sur **Jamais** par
  défaut : valider le réveil sur place avant de l’activer.
- [Bip tactile local](15-bip-tactile.md), actif par défaut, désactivable et mémorisé.
  Un pilote indisponible est signalé, pas présenté comme fonctionnel.
- Diagnostics compacts : version, horloge, liaison réseau.
- Stockage disponible/total de `/data` en Mio, exposé dans l’appareil ESPHome
  de HA avec les relais ; valeur « Indisponible » si la lecture échoue.
- Boutons distincts **Redemarrer ESPHome** et **Redemarrer le panneau**.
  Le premier relance l’application ; le second coupe temporairement le réseau
  et peut modifier les relais au démarrage. Les contrôles de sécurité peuvent
  refuser la demande. Le test réel de ces boutons reste à effectuer.
- [Recherche et configuration Wi-Fi](17-wifi-depuis-ecran.md) : scan manuel,
  sélection, mot de passe masqué, essai borné, confirmation/annulation.
  Le service Linux optionnel doit être installé séparément. Son état au repos
  a été vérifié, **pas une migration réelle de réseau ni son retour arrière**.

Les [relais locaux](14-relais-locaux.md) sont des composants distincts des
pages qui commandent les entités HA. Les trois boutons physiques et voyants
ont été validés sur le matériel de référence. Le modèle public reste en
observation ; ne pas activer les sorties sans identifier les charges.
Le fonctionnement complet après perte Wi-Fi/HA ou coupure secteur reste à tester.

## Personnaliser et mettre à jour

Modifier les substitutions : noms, entités, `weather_entity`, libellés et couleurs.
Garder les clés dans `secrets.yaml`. Compiler dans HA puis suivre le
[parcours OTA](DEMARRER-ICI.md#5-mettre-à-jour-un-panneau-déjà-sous-esphome).
Les pilotes du modèle publié sont épinglés au tag de release ; une mise à jour
volontaire doit reprendre le modèle de la release suivante en conservant vos secrets.

L’OTA d’interface ne modifie ni le superviseur, ni le profil réseau, ni le
[logo NAND initial](12-logo-demarrage.md). Ne pas réinstaller le démarrage
pour une modification graphique. Pas de binaire personnel dans la release.
Voir aussi les [écarts avec Tuya](16-ecarts-tuya.md).
