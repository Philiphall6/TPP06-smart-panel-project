# Logo de démarrage — distinct de l'interface OTA

Le logo MOES affiché par le chargeur de démarrage est dans la partition NAND
nommée `logo`. Il ne fait pas partie du programme ESPHome. Une mise à jour
OTA normale peut modifier les pages LVGL, les icônes, les menus et la veille,
mais ne remplace pas ce logo initial.

État du panneau de référence : logo Home Assistant programmé et relu
intégralement, puis un redémarrage logiciel réussi et plus de deux minutes
de contrôles API chiffrés sans changement de processus ni nouveau démarrage.
Le superviseur a confirmé `esphome-healthy`, avec Wi-Fi et accès de secours
disponibles. Le rendu visuel, les couleurs et l'orientation restent à confirmer
sur place. Lors de cet essai de logo, l’interface était la V4 ; la
[V5](11-interface-v5.md) a ensuite été installée et vérifiée séparément.

## Image et format

L'[image préparée](../images/tpp06-home-assistant-boot.svg) utilise uniquement
le symbole officiel Home Assistant, centré sur fond noir, sans logo ESPHome.
Source : [home-assistant/assets](https://github.com/home-assistant/assets/tree/8d4090f492d60841a0db4b3b26585184b29333ba),
archive `logo/home-assistant-logo.zip`, fichier
`home-assistant-logomark-color-on-light.svg`. Les tracés sont conservés ; seule
une mise à l'échelle uniforme et un fond noir sont ajoutés. Marque de l'Open
Home Foundation, ressource sous CC BY-NC-SA 4.0. Ce projet communautaire n'est
pas un produit officiel ou certifié Home Assistant.

Sur le panneau de référence uniquement :

- image 320 × 480, pixels 16 bits little-endian, 307 200 octets ;
- partition 512 Kio, reste rempli par `0xff`, blocs 128 Kio, pages 2 Kio ;
- le logo d'origine correspond exactement au PNG MOES du dump converti ;
- BGR565 est retenu à partir du format LCD du DT vivant et du pilote vidéo.
  Le logo MOES monochrome seul ne permet pas de distinguer RGB de BGR.

Ces dimensions ne sont **pas une règle pour tous les appareils**.

## Préparation hors ligne

Après rendu du SVG en PNG opaque 320 × 480, avec Python et Pillow :

```sh
python tools/tpp06_logo.py logo-320x480.png logo-candidate.bin --pixel-order BGR565
```

Ce convertisseur ne se connecte à aucun panneau. Il refuse les chemins de
sortie sous `/dev`, les liens symboliques et les fichiers existants. Il
n'efface, ne programme et ne redémarre rien. **Ne pas envoyer ce fichier
comme firmware OTA ESPHome.**

## Précautions de programmation

La procédure privée est liée au matériel vérifié, pas un installateur
universel. Aucun script d'effacement automatique n'est fourni ici.

Avant une programmation, résoudre la partition par son **nom**, contrôler
sa géométrie et les compteurs ECC/blocs défectueux, conserver deux lectures
identiques de l'original hors du panneau, vérifier les outils et les fichiers,
disposer d'une alimentation stable et d'une récupération locale. Programmer
uniquement la partition du logo avec la gestion NAND/ECC adaptée ; relire
l'intégralité et comparer les octets avant tout redémarrage.

**Retour d'expérience important :** un binaire `armv5l` peut contenir des
instructions de calcul flottant absentes du SoC. L'aide, la lecture NAND et
un essai QEMU réussis ne prouvent pas que le chemin d'écriture fonctionne.
Lors de cet essai, un outil hard-float a échoué après effacement ; le logo
MOES a été restauré avec un outil compatible puis relu intégralement, sans
redémarrer. Les fichiers de démarrage, le programme ESPHome et les partitions
SPL/U-Boot/DTB contrôlées étaient inchangés. Ne pas réutiliser l'outil rejeté.

Le secours multiboot de l'application ne protège pas contre une mauvaise
écriture NAND, une coupure pendant l'effacement ou une modification du
chargeur de démarrage. Les sauvegardes et journaux matériels restent privés.
