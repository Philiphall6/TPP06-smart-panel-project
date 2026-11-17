# Étape 6 — ESPHome + LVGL natif sur le TPP06

Cette voie exécute **ESPHome lui-même** sur le Linux Anyka du TPP06. Elle ne
remplace pas le processeur par un ESP32 et n'utilise pas ESPHome comme simple
passerelle : le moteur LVGL d'ESPHome dessine directement dans le framebuffer
et reçoit le tactile Goodix par `evdev`.

> **Validé sur matériel le 17 novembre 2026.** Le binaire ARMv5 statique démarre
> sur le TPP06, détecte le framebuffer 320×480 BGR565 et le tactile Goodix, puis
> termine correctement l'initialisation ESPHome. Le bouton LVGL répond au toucher
> et affiche bien `TACTILE OK`. L'installation au démarrage reste expérimentale :
> effectuer d'abord plusieurs essais depuis `/tmp`.

## Ce qui a été adapté

Le correctif [esphome-tpp06-lvgl.patch](../../esphome-lvgl/esphome-tpp06-lvgl.patch)
ajoute à ESPHome :

- un afficheur `fbdev` pour `/dev/fb0`, 320×480, 16 bits ;
- la détection automatique RGB565/BGR565 du framebuffer Anyka ;
- un tactile `evdev` pour `/dev/input/event1` ;
- la lecture explicite des événements Linux 32 bits de 16 octets, nécessaire
  avec le noyau 4.4 du panneau ;
- la compatibilité avec les anciens appels système ARM 32 bits de Linux 4.4
  (`clock_gettime`, `nanosleep` et `_newselect`) malgré la toolchain time64 ;
- le chargement explicite des vraies fonctions `pthread` de la libc statique ;
- un stockage des préférences dans un répertoire inscriptible choisi par
  `ESPHOME_PREFDIR` ;
- un exemple LVGL avec mire RVB et bouton tactile ;
- un script reproductible de compilation croisée ARMv5/uClibc.

Le binaire obtenu lors de la première compilation mesure environ 2,8 Mio. Son
SHA-256 de référence est :

```text
9d2d42251db95ff8564c90cb2d978cf398a214fecc04ed302f6717d78e726802
```

## Configuration portable dans Device Builder

Le dépôt fournit maintenant une couche de compatibilité sous forme de
`external_components`. Il n'est plus nécessaire de modifier le code source
d'ESPHome. Dans le Device Builder officiel, importer uniquement
[`esphome/tpp06-device-builder.yaml`](../../esphome/tpp06-device-builder.yaml).

Les éléments propres à une maison sont regroupés dans `substitutions` en tête
du fichier : nom, adresse MAC virtuelle et identifiants des trois entités Home
Assistant. Le reste de la configuration, l'interface LVGL et les pilotes Linux
sont téléchargés depuis ce dépôt. Une nouvelle installation ne demande donc
que la modification de ces variables.

Deux modes sont proposés :

- `tpp06-device-builder.yaml` reste lié au modèle GitHub et reçoit ses mises à
  jour ; il est adapté quand seules les substitutions changent ;
- `tpp06-lvgl.yaml` est le modèle complet et librement modifiable. Le mécanisme
  **Prendre le contrôle** utilise `import_full_config: true` et copie
  automatiquement ce fichier complet dans Device Builder. Les pages, widgets,
  styles, positions et actions deviennent alors locaux et éditables. Seuls les
  pilotes matériels `external_components` continuent à venir de GitHub.

Le TPP06 nécessite toujours une compilation croisée ARMv5, mais aucun serveur
extérieur n'est requis. Le composant `host` télécharge la toolchain Bootlin
directement dans le cache du Device Builder lors de la première compilation,
vérifie son SHA-256 puis la réutilise. Toutes les compilations suivantes sont
effectuées localement par le Device Builder de Home Assistant. Le premier
téléchargement représente environ 82 Mio.

Si le journal contient un chemin `.remote_builds/...`, la compilation est
encore déportée. Ouvrir **Paramètres → Envoyer les compilations**, supprimer ou
désactiver le serveur associé, puis nettoyer les fichiers de compilation de
l'appareil. Un chemin local normal commence par `/config/.esphome/build/...`.

Avant de compiler, remplacer `CHANGE_ME_BEFORE_INSTALL` dans la substitution
`ota_password` par un mot de passe propre à l'installation. Ne jamais publier
ce mot de passe dans un dépôt.

## Installation initiale et mises à jour OTA

Le bouton **Installer** de Device Builder ne peut pas installer directement le
premier binaire dans un système Tuya intact. La compilation est néanmoins
réussie lorsque le journal affiche `Successfully compiled program`. Télécharger
alors l'exécutable et effectuer le premier déploiement réversible avec Tuya
Cutter, comme décrit ci-dessous.

À partir de la version `0.1.3`, le binaire expose ensuite l'OTA ESPHome sur le
port `8082`. Les versions suivantes peuvent donc être installées directement
depuis Device Builder sur l'adresse IP du panneau, avec `ota_password`. Les
implémentations MD5 et SHA-256 portables incluses dans ce dépôt évitent la
dépendance OpenSSL absente du Linux Tuya.

## Compiler

Le correctif a été construit sur la révision ESPHome `9bf2bbc` (branche
`dev`, version `2026.12.0-dev`). ESPHome utilise C++20 ; l'ancien compilateur
GCC 6 du SDK Anyka ne suffit donc pas. Utiliser la toolchain officielle Bootlin
ARMv5 EABI/uClibc stable 2026.08-1, GCC 15.3.

```bash
git clone https://github.com/esphome/esphome.git
cd esphome
git checkout 9bf2bbc
git am /chemin/esphome-tpp06-lvgl.patch

export TPP06_TOOLCHAIN_PREFIX=/opt/armv5-eabi--uclibc--stable-2026.08-1/bin/arm-linux
export ESPHOME_PYTHON=/chemin/venv-esphome/bin/python
./tpp06/build.sh
```

Résultat :

```text
tpp06/.esphome/build/tpp06-lvgl/.pioenvs/tpp06-lvgl/program
```

Vérifier qu'il est statique et ARM EABI5 :

```bash
${TPP06_TOOLCHAIN_PREFIX}-readelf -h -l \
  tpp06/.esphome/build/tpp06-lvgl/.pioenvs/tpp06-lvgl/program
```

## Premier essai temporaire

La méthode recommandée utilise Tuya Cutter, qui suspend Tuya, place les
préférences dans `/tmp` et garantit le retour arrière :

```bash
python3 tools/tpp06_tuya_cutter.py --yes ADRESSE_IP_DU_PANNEAU \
  test esphome --binary \
  tpp06/.esphome/build/tpp06-lvgl/.pioenvs/tpp06-lvgl/program
```

Arrêt sûr et reprise immédiate de Tuya :

```bash
python3 tools/tpp06_tuya_cutter.py ADRESSE_IP_DU_PANNEAU stop-test
```

La procédure manuelle équivalente est détaillée ci-dessous.

1. Redémarrer le panneau pour retrouver ADB sur `5555`, puis se connecter selon
   l'[étape 4](04-adb-wifi-sans-uart.md).
2. Copier le programme uniquement dans `/tmp`. Si `adb push` ne fonctionne pas
   avec cet ancien démon, ouvrir un shell root sur le panneau et lancer :

   ```sh
   nc -l -p 9001 > /tmp/esphome-tpp06-lvgl
   ```

   Depuis le PC, dans un second terminal :

   ```bash
   nc ADRESSE_IP_DU_PANNEAU 9001 < \
     tpp06/.esphome/build/tpp06-lvgl/.pioenvs/tpp06-lvgl/program
   ```

3. Sur le panneau, rendre le fichier exécutable, vérifier sa somme, puis mettre
   temporairement l'interface Tuya en pause :

   ```sh
   chmod 755 /tmp/esphome-tpp06-lvgl
   sha256sum /tmp/esphome-tpp06-lvgl
   ui_pid=$(pidof voice_control_ak3760e)
   kill -STOP "$ui_pid"
   /tmp/esphome-tpp06-lvgl
   ```

4. Vérifier les trois bandes rouge, verte et bleue, puis le bouton `TOUCHER`.
   Après `Ctrl+C`, restaurer immédiatement Tuya :

   ```sh
   kill -CONT "$ui_pid"
   rm /tmp/esphome-tpp06-lvgl
   ```

Ne jamais créer de service permanent tant que l'orientation, les couleurs, le
tactile, la sortie du programme et le retour de l'interface Tuya n'ont pas été
validés plusieurs fois.

## Suite

La configuration portable contient déjà les pages Home Assistant pour le volet
et les deux éclairages. La suppression du cloud Tuya reste une opération
séparée et réversible.
