# Logo de démarrage — distinct de l'interface OTA

Le logo MOES affiché par le chargeur de démarrage est dans la partition NAND
nommée `logo`. Il ne fait pas partie du programme ESPHome. Une mise à jour
OTA normale peut modifier les pages LVGL, les icônes, les menus et la veille,
mais ne remplace pas ce logo initial.

État au 18 novembre 2026 : le premier logo Home Assistant démarrait mais
apparaissait jaune. Les métadonnées vidéo BGR565 étaient trompeuses : une
mire physique a confirmé un affichage RGB565. Le même visuel a été réencodé
en RGB565, programmé dans la seule partition `logo`, puis relu intégralement
avec comparaison octet par octet et vérification d'empreinte. Aucun redémarrage
n'a été lancé après cette correction : **la confirmation visuelle du logo bleu
reste à faire**. Le programme ESPHome, le lanceur et les partitions de démarrage
contrôlées sont restés inchangés ; l'API et le superviseur sont restés sains.

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
- **RGB565**, confirmé par une mire rouge/verte/bleue visible sur le panneau,
  malgré les métadonnées BGR565 du pilote. Le logo MOES monochrome seul ne
  permet pas de distinguer RGB de BGR.

Ces dimensions ne sont **pas une règle pour tous les appareils**.

## Préparation hors ligne

Le paquet de l’assistant inclut désormais le [PNG et l’image RGB565 publics](../../assets/boot-logo/README.md),
avec attribution, licence et SHA-256. Le formulaire Logo les propose directement.
Ils ne proviennent pas d’un dump d’appareil et ne contiennent aucune donnée personnelle.

Après rendu du SVG en PNG opaque 320 × 480, avec Python et Pillow :

```sh
python tools/tpp06_logo.py logo-320x480.png logo-candidate.bin --pixel-order RGB565
```

Ce convertisseur ne se connecte à aucun panneau. Il refuse les chemins de
sortie sous `/dev`, les liens symboliques et les fichiers existants. Il
n'efface, ne programme et ne redémarre rien. **Ne pas envoyer ce fichier
comme firmware OTA ESPHome.**

## Précautions de programmation

L’action Logo de l’[assistant expérimental](21-assistant-ordinateur.md) est liée
au matériel vérifié, pas à tous les panneaux similaires. Elle exige une confirmation
distincte, une récupération locale et les contrôles de sauvegarde/compatibilité.
Le convertisseur hors ligne, lui, ne programme rien.

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
