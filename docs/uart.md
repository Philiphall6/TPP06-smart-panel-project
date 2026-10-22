# Console UART

## Matériel

Un adaptateur USB–UART TTL est nécessaire. Le programmateur T48 ne sert pas de console série.

- Choisir une logique 1,8 V ou 3,3 V après mesure de la ligne TX0 au repos.
- Ne jamais connecter le VCC de l’adaptateur à la carte.
- Ne jamais injecter 5 V.

## Branchement

| Adaptateur USB–UART | Carte |
| --- | --- |
| GND | GND |
| RX | TX0 |
| TX | RX0 |
| VCC | Non connecté |

Commencer par GND et RX/TX0 pour observer le démarrage. Ajouter TX/RX0 seulement lorsque la tension logique est confirmée.

## Terminal

Ouvrir le terminal avant d’alimenter le panneau :

```text
115200 bauds, 8 bits, aucune parité, 1 stop bit, sans contrôle de flux
```
