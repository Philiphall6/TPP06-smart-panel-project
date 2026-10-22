# NAND

| Élément | Valeur |
| --- | --- |
| Modèle | GigaDevice GD5F1GM7UEYIG |
| Type | SPI NAND |
| Boîtier | WSON-8, 8 × 6 mm |
| Tension | 3,3 V |

## Brochage

Vue de dessus, repère en haut à gauche :

```text
 CS#   1 +----------+ 8 VCC 3,3 V
 IO1   2 |          | 7 IO3 / HOLD#
 IO2   3 |          | 6 CLK
 GND   4 +----------+ 5 IO0
```

## Lecture hors carte

Utiliser le support WSON/QFN-8 **8 × 6 mm**. Dans XGPro, sélectionner le circuit correspondant au modèle exact et vérifier l’identifiant avant toute lecture. Réaliser plusieurs lectures et les comparer localement. Les fichiers binaires restent hors Git.
