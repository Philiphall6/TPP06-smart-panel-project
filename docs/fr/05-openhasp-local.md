# Étape 5 — Interface locale openHASP sur le TPP06

Cette étape porte openHASP sur le Linux embarqué du TPP06 sans remplacer
immédiatement Tuya. Le premier jalon fonctionne depuis `/tmp` et disparaît au
redémarrage : il permet donc de valider l'écran, le tactile et MQTT avant toute
modification persistante.

## État vérifié

Les points suivants ont été testés sur un TPP06/AK3761E :

- processeur ARM926EJ-S, architecture `armv5tejl` et ABI soft-float ;
- Linux 4.4 et espace utilisateur Buildroot/uClibc ;
- framebuffer `/dev/fb0`, 320×480, 16 bits et stride de 640 octets ;
- format matériel BGR565 corrigé vers le RGB565 produit par LVGL ;
- tactile Goodix `/dev/input/event1`, plages multitouch 0–320 et 0–480 ;
- touches GPIO `/dev/input/event0` ;
- démarrage complet de LVGL et openHASP 0.7.2 sans crash.

Le rouge, le vert, le bleu et le blanc ont été contrôlés par une capture brute
du framebuffer. Tuya a été repris après chaque essai.

## Construire le portage

Le correctif repose sur le commit openHASP `c4fb5a7`.

```bash
git clone https://github.com/HASwitchPlate/openHASP.git
cd openHASP
git checkout c4fb5a7
git am /chemin/TPP06-smart-panel-project/openhasp/openhasp-tpp06.patch
```

Installer PlatformIO et un toolchain Bootlin ARMv5 EABI/uClibc, puis indiquer
leurs chemins si nécessaire :

```bash
export TPP06_TOOLCHAIN_DIR=/chemin/armv5-eabi--uclibc--stable-2018.02-2
export PIO=/chemin/vers/pio
./tpp06/build-openhasp.sh
```

Le résultat est `build-tpp06/openhasp-tpp06`. Le script vérifie que le fichier
est un exécutable ARM EABI5 soft-float et applique les deux adaptations
spécifiques : Goodix multitouch et BGR565.

## Premier essai réversible

Récupérer d'abord l'accès propre au panneau avec l'étape 0, puis activer ADB par
Wi-Fi avec l'étape 4. Copier le binaire, `pages.jsonl` et un `config.json`
contenant les paramètres MQTT dans un répertoire de test sous `/tmp`.

Créer d'abord `/tmp/openhasp` depuis le shell root du panneau, puis effectuer
les transferts depuis le PC :

```bash
adb connect ADRESSE_IP:5555
adb push build-tpp06/openhasp-tpp06 /tmp/openhasp-tpp06
adb push tpp06/runtime/pages.jsonl /tmp/openhasp/pages.jsonl
adb push tpp06/runtime/config.example.json /tmp/openhasp/config.json
```

Sur certains anciens serveurs ADB Tuya, `adb push` se termine prématurément.
Dans ce cas, utiliser temporairement le `nc` BusyBox du panneau ou un transfert
HTTP local, puis vérifier le SHA-256 du fichier reçu.

Depuis le shell root du panneau :

```sh
chmod +x /tmp/openhasp-tpp06
/tmp/openhasp-tpp06 -c /tmp/openhasp
```

Tuya et openHASP écrivent sinon tous deux dans le framebuffer. Pour une courte
validation visuelle, suspendre Tuya seulement avec un watchdog indépendant qui
le reprend automatiquement. Ne jamais désactiver son démarrage tant que le
tactile, MQTT et le retour arrière n'ont pas tous été validés.

## MQTT et Home Assistant

Copier `tpp06/runtime/config.example.json`, remplacer uniquement les champs
`CHANGE_ME` localement et ne jamais committer le vrai mot de passe MQTT. La
page d'exemple contient les commandes volet salle de bain, lumière cave et
luminosité ; leurs événements openHASP devront être reliés aux entités Home
Assistant réelles par MQTT ou automatisations.

## Reste à faire avant le remplacement de Tuya

1. Confirmer physiquement pression, relâchement et orientation du tactile.
2. Valider l'authentification MQTT et les événements Home Assistant.
3. Identifier le rétroéclairage, les relais, LED, buzzer et infrarouge.
4. Ajouter un superviseur avec watchdog et retour automatique vers Tuya.
5. Installer openHASP au démarrage seulement après plusieurs redémarrages de
   validation.

Le correctif ne contient aucune clé, aucun `AUTHKEY`, aucun mot de passe et
aucune donnée propre à un panneau.
