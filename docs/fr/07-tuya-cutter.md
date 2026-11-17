# Étape 7 — TPP06 Tuya Cutter

`tpp06_tuya_cutter.py` rassemble les opérations du projet dans un installateur
réversible. On lui donne l'adresse IP du panneau ; il lit l'`AUTHKEY` par le
port `8090`, calcule le mot de passe root uniquement en mémoire, se connecte à
ADB et propose sauvegarde, restauration et basculement d'interface.

> **Version de développement.** La logique locale et la validation des
> archives sont testées automatiquement. Les opérations ADB doivent encore être
> validées de bout en bout sur le panneau après son prochain redémarrage. Ne pas
> utiliser le mode permanent avant les essais temporaires.

## Principes de sécurité

- l'`AUTHKEY` et le mot de passe ne sont ni affichés ni enregistrés ;
- les sauvegardes locales sont créées en mode `0600` et ignorées par Git ;
- une restauration refuse chemins absolus, `..`, liens symboliques et fichiers
  extérieurs au périmètre autorisé ;
- une installation permanente crée automatiquement une sauvegarde préalable ;
- les binaires Tuya d'origine ne sont jamais effacés ;
- le « retrait de Tuya » est un **basculement réversible** du script
  `S99tuya-app`, pas une suppression des partitions d'origine ;
- aucun redémarrage n'est envoyé automatiquement.

## Prérequis

- Python 3.10 ou plus récent ;
- Android Platform Tools (`adb`) ;
- panneau et ordinateur sur le même réseau local isolé ;
- overlay ADB de l'étape 4 si le port `5555` n'est pas encore actif ;
- binaire openHASP ou ESPHome-LVGL compilé selon les étapes 5 et 6.

## Assistant interactif

Depuis la racine du dépôt :

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52
```

Le menu permet de :

1. vérifier le panneau et le mode actif ;
2. créer une sauvegarde ;
3. restaurer une sauvegarde ;
4. envoyer l'overlay ADB par `8090` ;
5. essayer openHASP ou ESPHome temporairement ;
6. arrêter l'essai et reprendre Tuya ;
7. préparer une interface permanente ;
8. sélectionner `tuya`, `openhasp` ou `esphome` pour le prochain démarrage ;
9. retirer le sélecteur et retrouver le démarrage Tuya d'origine.

## Commandes non interactives

### État et sauvegarde

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 status
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 backup
```

Les archives sont placées par défaut dans `./tpp06-backups/`, accompagnées
d'un manifeste JSON et d'une somme SHA-256.

### Activer ADB par 8090

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 enable-adb \
  /chemin/tpp06-adb-network-final.tar.gz
```

Cette action conserve la règle de l'étape 4 : une coupure/remise sous tension
est nécessaire après l'envoi du paquet.

### Essai temporaire openHASP

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 test openhasp \
  --binary /chemin/openhasp-tpp06 \
  --config /chemin/config.json \
  --pages /chemin/pages.jsonl
```

### Essai temporaire ESPHome + LVGL

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 test esphome \
  --binary /chemin/esphome-lvgl-program
```

Pendant un essai, le processus Tuya est suspendu avec `SIGSTOP`, pas tué. Le
programme est copié sous `/tmp/tpp06-cutter`, donc disparaît au redémarrage.
Pour revenir immédiatement :

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 stop-test
```

### Installation permanente réversible

Après plusieurs essais réussis :

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 install esphome \
  --binary /chemin/esphome-lvgl-program
```

Ou pour openHASP :

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 install openhasp \
  --binary /chemin/openhasp-tpp06 \
  --config /chemin/config.json \
  --pages /chemin/pages.jsonl
```

Le Cutter installe les fichiers sous `/data/tpp06-cutter`, conserve une copie
du script Tuya d'origine et place un sélecteur dans l'overlay
`/data/etc/init.d/S99tuya-app`. Le mode choisi prend effet seulement au prochain
redémarrage électrique.

Changer de mode :

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 switch tuya
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 switch openhasp
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 switch esphome
```

### Restaurer ou désinstaller

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52 restore \
  tpp06-backups/tpp06-192.168.1.52-DATE.tar.gz

python3 tools/tpp06_tuya_cutter.py 192.168.1.52 uninstall
```

Une restauration crée elle-même une sauvegarde de l'état qu'elle va remplacer.
`uninstall` retire uniquement le sélecteur et les programmes ajoutés par le
Cutter ; la couche inférieure d'origine redevient alors visible.

## Transferts

Le Cutter essaie `adb push`/`adb pull`, vérifie systématiquement SHA-256, puis
utilise automatiquement un port `nc` temporaire du panneau si l'ancien démon
ADB Tuya interrompt le protocole de transfert. Aucun serveur permanent n'est
laissé actif.
