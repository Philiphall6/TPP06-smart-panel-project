# Bluetooth BLE, écran et organisation du YAML

Le [modèle complet](../../esphome/tpp06-lvgl-complete.yaml) réunit l'interface,
les relais, les diagnostics Linux, le rétroéclairage et les annonces BLE. Ses
imports sont figés sur la même release. Le [modèle d'interface détaillé](../../esphome/tpp06-lvgl-modern.yaml)
reste disponible pour modifier les cartes, les widgets et les actions.

## Personnaliser les entités

Dans `substitutions`, remplacer uniquement les exemples par ses propres entités :

- `cover_entity` : volet Home Assistant ;
- `cave_light_entity` : première lumière Home Assistant ;
- `bar_light_entity` : deuxième lumière Home Assistant ;
- `weather_entity` : météo Home Assistant ;
- `local_relay_1_label`, `local_relay_2_label`, `local_relay_3_label` : noms
  affichés pour les trois sorties physiques, distinctes des lumières importées.

Les noms historiques des deux variables de lumière sont conservés pour la
compatibilité ; ils n'imposent aucune pièce. Le nom du panneau, ses clés et
ses entités doivent rester privés. Créer sa propre clé dans `secrets.yaml` ;
ne jamais utiliser une clé de test provenant du dépôt.

Les commentaires `[TPP06]` repèrent la personnalisation, les imports HA, les
pilotes, la logique et chaque vue : accueil, volet, lumières, paramètres,
Wi-Fi, écran, son, météo et diagnostics. Les vues supplémentaires sont dans
`esphome/packages/`. La commande suivante ajoute les mêmes repères sans
modifier les lignes de configuration existantes :

```sh
python3 tools/tpp06_yaml_sections.py /chemin/prive/mon-panneau.yaml
```

Conserver une sauvegarde privée avant toute édition. Cet outil ajoute des
commentaires ; il ne remplace pas une validation ESPHome et ne lance pas d'OTA.

## Détecter les annonces BLE

Dans **Paramètres → BLE**, ou dans HA avec **Détection Bluetooth BLE**, activer
la détection. Le réglage est mémorisé. Dans le modèle public, il est désactivé
par défaut. Un client HA abonné aux annonces BLE est nécessaire pour lancer
le scan ; une simple connexion aux journaux ne suffit pas.

Le composant Linux transmet les annonces par l'API ESPHome chiffrée, sans
daemon BlueZ ni cloud Tuya. Les intégrations HA compatibles peuvent alors
exploiter ces annonces. Les compteurs représentent des **annonces**, pas un
nombre d'appareils distincts ni un nombre d'appairages.

Limites : scan LE actif uniquement ; aucun GATT, appairage, audio, connexion
Bluetooth ou proxy ESP32 complet. Désactiver la détection arrête le scan
possédé par ce composant, pas l'alimentation de toute la radio. Le contrôleur
doit déjà être exposé par Linux ; l'OTA ne charge aucun pilote noyau manquant.
La fonction reste expérimentale et propre au matériel compatible.

## Régler le rétroéclairage

Les paramètres de l'écran et HA utilisent les mêmes valeurs mémorisées :

- **Luminosité écran** : 10 à 100 % ;
- **Veille automatique écran** : jamais, 30 secondes, 1, 2 ou 5 minutes ;
- **Réveiller écran** : bouton d'action ;
- **Écran en veille** : diagnostic de pause de l'interface.

Ces réglages ne commandent ni l'éclairage de la pièce ni les relais. Un pilote
indisponible ne doit pas être présenté comme un réglage réussi.

## Mettre à jour sans modifier le démarrage

Pour une installation déjà fonctionnelle, conserver son YAML privé, son nom,
ses clés, ses correspondances de boutons et son réglage `control_enabled`.
Ne pas remplacer aveuglément ce fichier par le modèle public : celui-ci met
les relais en **observation** avant leur validation sur place. Les packages
et tous leurs pilotes doivent provenir du même tag.

Valider et compiler dans Device Builder sur HA, vérifier la place pour le
nouveau programme et sa marge de sécurité, puis envoyer une seule OTA.
Une mise à jour de ces fonctions ne nécessite ni changement de Wi-Fi, ni
réinstallation du superviseur, ni écriture du logo NAND. Les modifications
optionnelles du superviseur restent une opération séparée, non validée sur
le matériel pour cette release.

## Ce qui a été vérifié

Le programme de référence `0.1.7-dev.3` a été compilé dans HA, installé par
une OTA chiffrée et surveillé pendant 181 secondes : annonces reçues et
transmises, huit nouvelles entités présentes dans HA, arrêt/reprise du scan
depuis HA, maintien des valeurs luminosité/veille et réveil réel du rétroéclairage.
Linux et les états des relais n'ont pas changé. Cela ne prouve pas l'endurance,
la reprise après coupure ni la compatibilité avec tous les appareils BLE.
Le numéro public de release ne remplace pas une nouvelle validation matérielle.

Références : [interface Linux MGMT](https://github.com/bluez/bluez/wiki/MGMT),
[intégration Bluetooth HA](https://www.home-assistant.io/integrations/bluetooth/).
