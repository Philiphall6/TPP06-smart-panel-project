# Interface V5 — installée sur le panneau de référence

> Document historique. Pour la version actuelle, consulter le
> [guide de l’interface](interface.md) et la
> [dernière release](https://github.com/Philiphall6/TPP06-smart-panel-project/releases/latest).
> Les mentions « en préparation » ci-dessous décrivent des étapes passées.

Le 18 novembre 2026, le propriétaire a confirmé l’installation sans fil de la
V5, version de projet **0.1.5**, compilée dans Home Assistant. Les contrôles
directs après installation ont confirmé le binaire attendu, la version `0.1.5`
par API chiffrée, le Wi-Fi associé, l’état `esphome-healthy` et la politique
persistante conservée, sans processus graphique Tuya. Une capture réelle du
framebuffer confirme l’accueil, les icônes, l’heure et la date.

Le programme est un exécutable statique ARMv5TE / ARM926EJ-S, ABI soft-float.
Ce contrôle après installation n’est pas une mesure complète du transfert OTA
ni un essai prolongé de toutes les pages. Veille/réveil et bip restent à valider.
Pour commencer : [guide débutant](DEMARRER-ICI.md).

Évolution distincte en préparation : [Paramètres → Wi-Fi](17-wifi-depuis-ecran.md).
Cette fonction nécessite une mise en service du superviseur, pas seulement une OTA.

### Nouveau visuel V6 en préparation

Le modèle `esphome/tpp06-lvgl-modern.yaml`, version `0.1.6-glass.2-dev`,
reprend un style sombre à cartes dégradées : météo bleu ardoise, raccourcis
bleu et doré, navigation arrondie. Il conserve les commandes et paramètres.
Le pictogramme maison/arbre Home Assistant, en haut à gauche sans texte,
est dessiné par LVGL : pulsation bleue douce quand un client API se présentant
comme Home Assistant est connecté, gris et immobile sinon. La petite horloge
est à droite, près du Wi-Fi.
Un lecteur de journaux seul ne suffit pas. C'est une indication visuelle,
pas un contrôle d'authentification supplémentaire.
Le Wi-Fi figure uniquement dans la barre supérieure de l'accueil ; son état
de liaison détaillé reste consultable dans Diagnostics. Aucune batterie fictive.
Cette mise à jour d'interface ne réécrit ni le logo NAND ni le superviseur.
Les aperçus SVG sont des illustrations à données fictives, pas des captures
du panneau. La validation visuelle sur matériel reste nécessaire après OTA.

## Disponibilité dans le Builder

La configuration existante a été mise à jour, sans créer un second appareil.
Le YAML V4 a été sauvegardé ; identité, adresses, entités personnalisées,
clés API/OTA et pilotes déjà épinglés sont conservés. Le nouveau composant
`tpp06_backlight` a été fourni dans un dossier relatif au Builder pour le premier
essai. Il est désormais inclus dans `esphome-components` et référencé depuis
GitHub dans le modèle public. Ne pas supprimer les pilotes locaux d’une ancienne
installation sans les comparer ; aucun chemin du poste de développement n’est requis.

Pour les mises à jour d’un panneau déjà préparé : vérifier `0.1.5` dans le YAML,
conserver son précédent programme et contrôler l’espace disponible avant
**Installer → Sans fil**. Laisser la veille sur **Jamais** pour le premier essai.
Aucune réécriture du logo ou du superviseur n’est requise pour cette interface.

## Affichage et veille

- Navigation avec icônes **déjà incluses dans les polices LVGL**, sans police
  distante ni image plein écran ; accueil avec carte horloge/date contrastée.
- Paramètres → Ecran et sons : luminosité 10–100 %, veille jamais/30 s/1 min/
  2 min/5 min et visibilité de l'horloge. Préférences locales persistantes.
- La veille est **désactivée par défaut**. Tester d'abord le réveil sur place.
  LVGL se met en pause et le rétroéclairage s'éteint ; Linux, Wi-Fi, ADB, API,
  OTA et le superviseur restent actifs. Le relâchement du premier toucher
  réveille LVGL : ce toucher ne doit pas commander une lumière ou un volet.
- Le composant `tpp06_backlight` lit `max_brightness`, vérifie les droits et
  utilise uniquement `/sys/class/backlight/<nom>/brightness`. Pas d'export
  GPIO/PWM, d'accès relais, d'arrêt réseau ni de redémarrage.
- Si le périphérique manque, la veille n'est pas activée. En cas d'échec à
  l'extinction, retour immédiat au mode actif. Un arrêt ordonné restaure le
  niveau d'origine. Un processus tué brutalement ne peut pas exécuter ce
  nettoyage : le scénario de secours depuis la veille reste à valider.

Le nom du rétroéclairage est une substitution portable `backlight_device`.
L'indication Wi-Fi reste un état de liaison Linux, pas une mesure RSSI.

## Bip au toucher

Pas encore activé : les sorties nommées `BUZ_EN1` et `BUZ_EN2` ont été
identifiées en lecture seule et le firmware contient un générateur sonore.
Leur présence ne suffit pas à valider une séquence de commande sûre. La ligne
du menu indique explicitement « Indisponible : pilote a valider » ; ce n'est
pas un interrupteur factice. Aucun GPIO de buzzer n'a été modifié.

La [chaîne du clic Tuya a désormais été identifiée](15-bip-tactile.md) :
PWM à 4 750 Hz pendant 4 ms, sélection par les GPIO 8 et 18. Cela reste une
analyse en lecture seule, pas un essai sonore ni une activation dans ESPHome.

## Vrai logo de démarrage

La demande concerne le remplacement du **logo MOES initial**, pas un second
splash ESPHome. Aucun splash supplémentaire n'est ajouté au YAML.

Sur le matériel de référence, la partition nommée `logo` fait 512 Kio, avec
des blocs d'effacement de 128 Kio. Une sauvegarde privée a été vérifiée par
une seconde lecture ; le contenu de l'image est exactement le PNG MOES du
dump converti en pixels 16 bits, 320 × 480 (307 200 octets), suivi de `0xff`.
Le logo monochrome ne permet pas de distinguer RGB565 de BGR565. Le premier
choix BGR565 fondé sur les métadonnées était incorrect : une mire physique a
confirmé RGB565 et le logo a été corrigé dans ce format.

Le logo Home Assistant seul a été programmé sur le panneau de référence et
la relecture complète est identique au fichier préparé. Le contrôle visuel
des couleurs et de l'orientation reste à confirmer. Cette opération est
distincte de la V5 et de l'OTA ESPHome. Voir la [procédure et ses limites](12-logo-demarrage.md),
notamment l'incident d'outil incompatible et la restauration vérifiée de
l'original avant la programmation finale. Aucun binaire de flash ni script
d'effacement universel n'est distribué.

## Validation restante

1. Étendre la surveillance à l’endurance et aux mises à jour suivantes.
   Conserver le précédent programme et les sauvegardes ; recontrôler l’espace
   libre avant chaque OTA. La V5 est installée et vérifiée, pas seulement compilée.
2. Essai surveillé : réglage de luminosité, veille 30 s, toucher puis relâcher,
   absence d'action domotique au réveil, API et Wi-Fi continus.
3. Vérifier retour de secours et mise à jour OTA pendant la veille.
4. Valider séparément le pilote sonore puis seulement proposer le bip.
5. Confirmer visuellement le logo Home Assistant au démarrage. La sauvegarde
   MOES reste conservée hors du panneau ; ne pas répéter l'écriture NAND pour
   une simple mise à jour de l'interface.

Les secrets, les sauvegardes NAND et les paramètres propres à l'installation
restent privés. Aucun changement de démarrage permanent n'est nécessaire
pour modifier cette interface.

Références : [LVGL](https://github.com/lvgl/lvgl),
[polices, veille et réveil ESPHome](https://esphome.io/components/lvgl/),
[symboles LVGL](https://github.com/lvgl/lvgl/blob/v9.5.0/src/font/lv_symbol_def.h).
