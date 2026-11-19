# Étape 4 — Activer ADB par Wi-Fi sans UART

Cette procédure installe, par le service de production TCP `8090`, un petit
overlay persistant qui lance `adbd` sur le port TCP `5555`. Elle a été validée
sur un panneau TPP06 équipé de l'Anyka `AK3761E`, identifié comme
`ak3761e_tpp06z`, avec le noyau `4.4.192V2.4` daté du 13 décembre 2024.

> **Expérimental — lire avant d'agir.** Le type de mise à jour `bootpicture`
> efface puis remplace `/data/app` et `/data/customize`. Une variante de
> matériel ou de firmware différente peut ne plus démarrer. Ne pas utiliser ce
> paquet sur un autre modèle et ne jamais couper l'alimentation pendant le
> transfert.

## Résultat obtenu

Après redémarrage :

```text
192.0.2.1:5555 device product:occam model:Nexus_4 device:mako
uid=0(root) gid=0(root)
Linux Tuya 4.4.192V2.4 ... armv5tejl GNU/Linux
```

Le réglage survit à un redémarrage normal. Une réinitialisation usine ou une
mise à jour Tuya peut cependant supprimer ou remplacer l'overlay.

### Capture de la console validée

Les anciennes captures de console ne sont plus distribuées pour préserver
les adresses d'installation. Utiliser l'adresse de son panneau ; ne publier
ni mot de passe, ni `AUTHKEY`, ni capture brute de sa session.

## Prérequis

- le panneau et l'ordinateur sur le même réseau local de confiance ;
- Python 3 ;
- Android Platform Tools (`adb`) ;
- le mot de passe `root` propre au panneau, obtenu avec l'[étape 0](00-acces-reseau-authkey.md) ;
- les trois fichiers de la release :
  - `tpp06-adb-network-final.tar.gz` ;
  - `tpp06-adb-rollback.tar.gz` ;
  - `SHA256SUMS`.

Vérifier d'abord que le service de production répond :

```bash
nc -vz ADRESSE_IP_DU_PANNEAU 8090
python3 tools/tpp06_authkey_reader.py ADRESSE_IP_DU_PANNEAU
```

Puis vérifier les téléchargements depuis le dossier qui les contient :

```bash
sha256sum -c SHA256SUMS
```

## Installation

Depuis la racine du dépôt :

```bash
python3 tools/tpp06_ota_uploader.py \
  ADRESSE_IP_DU_PANNEAU \
  tpp06-adb-network-final.tar.gz \
  --i-understand-this-overwrites-customization
```

Attendre impérativement le message suivant :

```text
Upload accepted by ...
Now power-cycle the panel.
```

Couper puis remettre l'alimentation du panneau. Attendre environ une minute,
puis se connecter :

```bash
adb kill-server
adb connect ADRESSE_IP_DU_PANNEAU:5555
adb devices -l
adb shell
```

Dans le shell, saisir :

```text
Tuya login: root
Password: MOT_DE_PASSE_CALCULE_A_L_ETAPE_0
```

Le mot de passe ne s'affiche pas pendant la frappe. Vérifier ensuite :

```sh
id
uname -a
```

## Ce que fait le paquet

Le paquet ne modifie pas les partitions système d'origine. Il ajoute dans la
partition de données :

- une copie corrigée de l'ancien binaire `adbd` ;
- `/data/etc/init.d/S50adbd`, qui évite la création du transport USB
  FunctionFS et laisse `adbd` utiliser son transport TCP de secours ;
- un superviseur qui relance `adbd` s'il quitte après une connexion TCP
  incomplète ;
- des fichiers de clé **publique** ADB, sans clé privée ni mot de passe.

Le vérificateur de signature RSA de cette version d'`adbd` provoquait un
`Segmentation fault`. Dans la copie installée, la fonction de vérification à
l'adresse virtuelle `0x1bab4` (offset fichier `0xbab4`) renvoie succès. Le
binaire original de la partition système reste intact.

## Avertissement de sécurité

Le correctif RSA signifie que **tout client présent sur le LAN peut établir le
transport ADB**. Le shell Tuya demande toujours `root` et le mot de passe propre
au panneau, mais le port `5555` ne doit jamais être exposé sur Internet.

Recommandations :

- ne créer aucune redirection NAT vers `5555` ou `8090` ;
- placer le panneau sur un VLAN/SSID IoT isolé ;
- filtrer `5555` et `8090` pour n'autoriser que l'ordinateur d'administration ;
- arrêter ADB ou appliquer le retour arrière lorsque le diagnostic est terminé.

## Retour arrière

Le paquet de retour arrière restaure le script de démarrage `S50adbd` d'origine
et désactive donc l'ADB réseau au redémarrage :

```bash
python3 tools/tpp06_ota_uploader.py \
  ADRESSE_IP_DU_PANNEAU \
  tpp06-adb-rollback.tar.gz \
  --i-understand-this-overwrites-customization
```

Attendre la confirmation complète, puis couper et remettre l'alimentation. Le
retour arrière peut laisser quelques fichiers de clés publiques inoffensifs
dans l'overlay, mais aucun service ADB réseau ne les utilise alors.

## Dépannage

- `Connection refused` sur `8090` : vérifier l'adresse IP, le même réseau et
  l'absence de filtrage local.
- `Connection refused` sur `5555` : attendre une minute, puis refaire
  `adb connect`. Ne pas tester `5555` avec `nc` : une trame non-ADB peut faire
  quitter cet ancien démon avant que son superviseur ne le relance.
- `unauthorized` : exécuter `adb kill-server`, puis recommencer. Le paquet
  validé accepte le transport sans confirmation RSA à l'écran.
- panneau qui ne redémarre plus : utiliser l'UART comme voie de récupération ;
  la procédure réseau ne peut plus agir si le système ou le port `8090` ne
  démarre pas.
