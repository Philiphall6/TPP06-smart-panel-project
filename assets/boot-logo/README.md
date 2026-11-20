# Home Assistant boot logo / Logo de démarrage

Provided files / fichiers fournis :

- `home-assistant-320x480.png` — preview / aperçu, 320 × 480, black background / fond noir.
- `home-assistant-320x480-rgb565.bin` — RGB565 little-endian, 524288 bytes / octets,
  307200 image bytes, remaining bytes `FF`. **Not an ESPHome OTA firmware.**
- `SHA256SUMS.txt` — integrity checks / empreintes de contrôle.

Only for the verified TPP06/AK3761E logo partition geometry. Use the assistant's
separate Logo operation, with original backup, compatibility checks and local
UART recovery. Power loss during a NAND erase/write can require recovery.
No device dump or personal data was used to create these assets.

Uniquement pour la géométrie logo TPP06/AK3761E vérifiée. Utiliser l’action Logo
distincte de l’assistant, avec sauvegarde, contrôles et récupération UART sur place.
Une coupure pendant l’écriture NAND reste dangereuse. Ces fichiers proviennent
du SVG public, jamais d’un dump d’appareil ou de données personnelles.

## Attribution and license / Attribution et licence

Home Assistant logomark © Open Home Foundation. Source:
[home-assistant/assets](https://github.com/home-assistant/assets/tree/8d4090f492d60841a0db4b3b26585184b29333ba),
`logo/home-assistant-logo.zip`, `home-assistant-logomark-color-on-light.svg`.
Licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
Changes: uniform scaling, centered black background, rasterization and RGB565
encoding. The adapted images are distributed under the same license.
Home Assistant is an Open Home Foundation trademark; this community project is
not an official or certified Home Assistant product.

Logo Home Assistant, marque de l’Open Home Foundation ; ressource sous CC BY-NC-SA
4.0. Modifications : mise à l’échelle uniforme, fond noir, rastérisation et encodage
RGB565. Les images adaptées gardent la même licence. Projet communautaire non
officiel et non certifié Home Assistant.

Public source: [SVG](../../docs/images/tpp06-home-assistant-boot.svg).
Rebuild on Linux with librsvg, Cairo and Pillow, to a **new** output directory:

```sh
python3 tools/render_boot_logo.py OUTPUT_DIRECTORY
```

The renderer and codec do not contact or write to a panel.
Le rendu et le convertisseur ne contactent et ne modifient aucun panneau.
