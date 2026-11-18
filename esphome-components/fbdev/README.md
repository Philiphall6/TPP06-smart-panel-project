# Anyka framebuffer presentation / Présentation de l'image

## Français

Un logo de démarrage encore visible ne signifie pas forcément que Linux est
bloqué. Sur le panneau étudié, ESPHome, son API et le tactile fonctionnaient ;
la mémoire `/dev/fb0` contenait déjà l'interface, mais le contrôleur affichait
encore l'image de démarrage.

Le pilote noyau `ak-lcd` a besoin d'une présentation via `FBIOPAN_DISPLAY`
pour sélectionner la mémoire vidéo Linux. Une présentation avec les offsets
inchangés a rétabli l'interface, confirmée visuellement, sans redémarrage ni
écriture NAND.

Le correctif du pilote ESPHome présente les pixels modifiés, regroupe les
copies LVGL par tour de boucle et limite les nouvelles tentatives à une par
seconde en cas d'erreur. Il conserve les paramètres vidéo existants et ne
s'applique qu'à `ak-lcd`, avec offsets nuls. Il ne modifie ni le logo enregistré,
ni sa couleur, ni le démarrage de secours.

Validation : récupération ponctuelle confirmée sur matériel, tests C++ avec
appels système simulés, puis correctif durable compilé dans Home Assistant et
installé par OTA sur le panneau de référence, dont l'interface est visible.
Une mise à jour du dépôt ne modifie pas à elle seule le programme installé.

## English

A boot logo remaining on screen does not necessarily mean Linux is stuck.
On the inspected panel, ESPHome, its API and touch input were running, and
`/dev/fb0` already contained the UI while the LCD still displayed the boot image.

The `ak-lcd` kernel driver requires `FBIOPAN_DISPLAY` to select the Linux
framebuffer. Presenting with unchanged offsets restored the UI, visually
confirmed without reboot or NAND writes.

The ESPHome driver fix presents dirty pixels, batches LVGL copies per loop,
and retries failed presentations at most once per second. It preserves video
parameters and applies only to `ak-lcd` with zero offsets. It does not change
the stored logo, its colours, or recovery boot settings.

Validation: one-off recovery confirmed on hardware, C++ tests with mocked
system calls, then the durable fix built in Home Assistant and installed by
OTA on the reference panel with a visible interface. Updating the repository
alone does not update the running program.

## Couleurs / Colours

Sur le TPP06 testé, une mire envoyée directement en RGB565 little-endian
(`0xf800`, `0x07e0`, `0x001f`) affiche bien rouge, vert, bleu. Pourtant les
champs du pilote noyau annoncent BGR565. Suivre ces champs échange donc à tort
le rouge et le bleu : l'accent `#0A84FF` devient `#FF840A`.

Les exemples TPP06 sélectionnent maintenant `pixel_format: RGB565` dans le
bloc `display` de plateforme `fbdev`. Le pilote accepte aussi `AUTO` (défaut,
respecte les métadonnées noyau) et `BGR565` pour les autres matériels. Ne pas
changer les couleurs du thème pour compenser cette erreur. Cela ne modifie ni
le logo stocké en NAND ni les relais. La correction nécessite une compilation
puis une installation OTA ; la mire seule ne corrige pas le programme installé.

La version `0.1.5-colors.1` a été installée par OTA et ses couleurs confirmées
par le propriétaire. Le logo de démarrage a une correction séparée : voir le
[suivi NAND](../../docs/fr/12-logo-demarrage.md), dont le contrôle visuel reste à faire.

On the tested TPP06, raw little-endian RGB565 red/green/blue bars display in
the correct order despite BGR565 kernel metadata. The TPP06 examples explicitly
set `pixel_format: RGB565`; generic framebuffer users retain the `AUTO` default
or may select `BGR565`. Both single-pixel and LVGL bulk writes use this setting.
This changes neither the NAND boot logo nor relay control. Compile and install
the updated application via OTA, then visually verify its colours.

`0.1.5-colors.1` was installed by OTA and its UI colours confirmed by the owner.
The separate [NAND logo correction](../../docs/en/12-boot-logo.md) still awaits
visual confirmation at boot.

## Reference links

Linux 4.4's [`store_pan`](https://github.com/torvalds/linux/blob/v4.4/drivers/video/fbdev/core/fbsysfs.c)
passes the current video parameters with the requested offsets to
`fb_pan_display`. The inspected vendor driver then calls `ak_lcdc_rgb_display`.
Do not blindly apply presentation operations to unknown framebuffer drivers.
