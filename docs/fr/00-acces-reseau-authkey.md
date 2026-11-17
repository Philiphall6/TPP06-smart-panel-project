# Étape 0 — Récupérer le mot de passe par le réseau

## But

Récupérer l'`AUTHKEY` propre au panneau par son service de test local, puis calculer son mot de passe `root`/ADB, sans ouvrir le boîtier, sans UART et sans dessouder la NAND.

Cette méthode a été découverte et publiée dans le projet **TPPwned** par [t0m1o1](https://github.com/t0m1o1). L'implémentation de ce dépôt a été reconstruite et vérifiée sur notre propre TPP06 à partir du protocole du firmware.

N'utiliser cet outil que sur un panneau qui vous appartient ou pour lequel vous avez une autorisation explicite.

## Fonctionnement

Le panneau expose son service de test de production sur le port TCP `8090`. Le protocole utilise les trames suivantes :

```text
55 AA | version | commande | longueur (2 octets) | données | somme de contrôle
```

La somme de contrôle est la somme des octets précédents limitée à un octet.

Deux commandes en lecture sont utilisées :

1. `0x00` avec `{"action":"enter"}` active temporairement le contexte de test en mémoire ;
2. `0x04` demande la configuration contenant l'`AUTHKEY`.

L'activation temporaire est perdue au redémarrage. Le script n'envoie ni écriture persistante, ni redémarrage, ni mise à jour OTA.

Le mot de passe est calculé ainsi :

```text
mot_de_passe_root = 8 derniers caractères hexadécimaux de MD5(AUTHKEY)
```

## Utilisation

Vérifier d'abord l'adresse du panneau et le port :

```bash
ping 192.168.1.52
nc -vz 192.168.1.52 8090
```

Exécuter ensuite l'outil depuis la racine du dépôt :

```bash
python3 tools/tpp06_authkey_reader.py 192.168.1.52
```

Exemple de sortie :

```text
Panel: 192.168.1.52:8090
AUTHKEY: abcd…wxyz
Root/ADB password: 1234abcd
No persistent write or reboot was requested.
```

L'`AUTHKEY` est masquée par défaut. Pour une intervention locale uniquement, sa valeur complète peut être affichée avec :

```bash
python3 tools/tpp06_authkey_reader.py 192.168.1.52 --show-authkey
```

## Sécurité

La réponse brute peut également contenir `uuid`, `pskKey`, `ap_ssid` et `ap_pwd`. Le script ne les affiche jamais. Ne jamais publier une capture brute, une `AUTHKEY`, un mot de passe, un dump ou des identifiants Wi-Fi dans une issue ou un commit.

Si le port `8090` est inaccessible, vérifier que l'adresse IP est correcte, que le panneau est sur le même réseau local et que son firmware expose encore le service de test.
