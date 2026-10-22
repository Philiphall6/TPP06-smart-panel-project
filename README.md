# TPP06

Notes de maintenance pour un panneau MOES / Tuya **TPP06**.

## État du projet

- Carte identifiée : `TPP06-Z-AK V1.0.2`
- Processeur : Anyka `AK3761EE128`
- Mémoire de démarrage : GigaDevice `GD5F1GM7UEYIG`, SPI NAND, WSON-8 8 × 6 mm, 3,3 V.
- Une sauvegarde NAND vérifiée existe hors du dépôt.
- Les dumps, mots de passe, clés et identifiants de l’appareil ne sont pas versionnés.

## Documentation

- [NAND et sauvegarde](docs/nand.md)
- [Journal de lecture NAND](docs/lecture-nand.md)
- [Carte et remontage](docs/remontage.md)
- [Récupération du mot de passe](docs/recuperation-mot-de-passe.md)
- [Console UART](docs/uart.md)
- [Matériel à identifier](docs/materiel.md)

## Règles de sécurité

Ne jamais utiliser `Erase` ou `Program` dans XGPro sans une raison précise et une sauvegarde validée. Débrancher le T48 avant de déplacer une puce, un adaptateur ou des fils.
