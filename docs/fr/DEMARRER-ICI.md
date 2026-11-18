# Commencer ici — TPP06 avec Home Assistant, sans démontage

[English](../en/START-HERE.md) · [Accueil](../../README.md)

Ce guide distingue une **première préparation** d’une **mise à jour**.
Il n’est pas nécessaire d’ouvrir un panneau compatible pour utiliser la voie
réseau. Cela reste un projet expérimental : aucune garantie de récupération
à distance si le système ne démarre plus.

## 1. Comprendre les trois éléments

- **Le panneau** conserve son Linux Anyka et affiche une interface ESPHome/LVGL.
- **Home Assistant (HA)** fournit l’heure et les états de vos équipements.
- **ESPHome Device Builder**, installé dans HA, édite le YAML (fichier de
  configuration), compile votre programme puis envoie ses mises à jour.

Ajouter l’intégration ESPHome dans HA ne crée pas automatiquement un fichier
dans Builder. Un voyant « En ligne » ne prouve pas que l’API fonctionne : ouvrir
les journaux et rechercher une connexion suivie d’une authentification réussie.

**OTA** signifie mise à jour par le réseau. **ADB** est l’accès de maintenance
Linux utilisé pour la première préparation et les sauvegardes. **UART** est
une console filaire de secours, réservée à la récupération avancée.

Si ESPHome fonctionne déjà sur le panneau, **passer directement à l’étape 5**.
Ne pas réinstaller ADB, le superviseur ou le logo pour changer l’interface.

## 2. Préparer sans rien écrire sur le panneau

Il faut :

- son propre panneau TPP06 fonctionnel et connecté au Wi-Fi ;
- HA et un ordinateur sur un réseau local de confiance ;
- ESPHome Device Builder (référence testée : ESPHome **2026.10.2**) ;
- Python 3, Git et Android Platform Tools (`adb`) sur l’ordinateur pour les
  outils de préparation ; ils ne servent pas à compiler le firmware ;
- une alimentation stable et une récupération possible sur place.

La variante réseau testée est **TPP06/AK3761E**, identifiée `ak3761e_tpp06z`,
noyau `4.4.192V2.4`. Un boîtier ressemblant au TPP06 n’est pas une preuve de
compatibilité. Si vous ne pouvez pas confirmer le matériel/firmware à partir
de ses informations existantes, **ne pas envoyer l’overlay** : demander de l’aide.
Ne pas démonter juste pour suivre ce guide.

Depuis un terminal de l’ordinateur :

```bash
git clone https://github.com/Philiphall6/TPP06-smart-panel-project.git
cd TPP06-smart-panel-project
python3 --version
adb version
```

Sur Windows, utiliser `py -3` à la place de `python3` si nécessaire ; les
commandes `sha256sum` du guide avancé nécessitent un environnement compatible.
Les exemples ci-dessous utilisent **`192.0.2.1`**, une adresse fictive :
la remplacer par celle du panneau, trouvée dans les appareils connectés de
votre routeur. Ne pas utiliser l’adresse de Home Assistant.

```bash
python3 tools/tpp06_authkey_reader.py 192.0.2.1
```

Résultat attendu : réponse du panneau, AUTHKEY masquée et mot de passe root
calculé localement. C’est un diagnostic sans écriture persistante ni reboot.
Conserver le mot de passe en privé, ne pas publier la sortie. Si cela échoue,
vérifier IP, Wi-Fi et filtrage réseau ; **ne pas lancer une installation à l’aveugle**.
[Détail de la lecture réseau](00-acces-reseau-authkey.md).

## 3. Première préparation ADB et sauvegarde — point de vigilance

Si ADB fonctionne déjà, ne pas réinstaller son paquet. Sinon, lire entièrement
le [guide ADB sans UART](04-adb-wifi-sans-uart.md) et vérifier les sommes de
contrôle de la release indiquée avant toute écriture.

> [!WARNING]
> L’overlay ADB remplace `/data/app` et `/data/customize`. Ce n’est pas une
> simple lecture. Une sauvegarde Cutter réalisée **après** cette opération ne
> sauvegarde pas rétroactivement les personnalisations qui existaient avant.
> Si elles comptent pour vous et qu’aucun accès de sauvegarde n’est disponible,
> arrêter ici et demander un accompagnement. Ne pas confondre archive de retour
> ADB et sauvegarde complète de votre appareil.

Une fois l’accès ADB validé, depuis le dossier du dépôt :

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 status
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 backup
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 network-check
```

Le Cutter calcule l’accès en mémoire sans afficher les secrets. Attendre la
confirmation de sauvegarde vérifiée et conserver l’archive sur un autre
support privé. C’est une sauvegarde du périmètre du Cutter, **pas un dump NAND
complet**. Elle peut contenir les identifiants Wi-Fi.

`network-check` compare le profil Wi-Fi actif avec la copie de secours. Une
copie identique ne prouve pas que le réseau redémarrera sans Tuya. Un profil
absent, ambigu ou un état inconnu est un motif d’arrêt, pas une invitation à
inventer des paramètres Wi-Fi dans le YAML.

## 4. Préparer la V5 dans Device Builder

Une [procédure assistée expérimentale](13-installation-assistee.md) peut générer
la configuration privée et orchestrer la transition après compilation. Elle
est testée hors ligne seulement et nécessite encore un essai matériel accompagné.
Ce n'est pas une nouvelle étape à exécuter sur un panneau déjà sous ESPHome.

1. Sauvegarder les configurations existantes de HA/Builder.
2. Copier le contenu complet de
   [`esphome/tpp06-lvgl-mobile.yaml`](../../esphome/tpp06-lvgl-mobile.yaml)
   dans un fichier local du dossier `/config/esphome`, par exemple
   `mon-panneau.yaml`, avec l’éditeur de fichiers de HA. Le fichier apparaît
   ensuite dans Builder. Ne pas utiliser l’assistant pour créer un ESP32.
3. Ouvrir **Éditer** et adapter les variables en tête du fichier :

   | Variable | Ce que vous renseignez |
   | --- | --- |
   | `device_name` | Nom technique unique, par exemple `panneau-entree`, sans espaces |
   | `friendly_name` | Nom affiché, par exemple `Panneau entrée` |
   | `device_address` | IP actuelle pour la première connexion ; puis nom `.local` une fois mDNS vérifié |
   | `cover_entity` | Identifiant réel de votre volet, ou conserver l’exemple sans commander |
   | `cave_light_entity`, `bar_light_entity` | Identifiants réels de vos deux lumières ; noms historiques des variables, pas des pièces imposées |
   | Titres et couleurs `ui_*` | Vos libellés et votre palette |

   Trouver les identifiants dans **HA → Outils de développement → États**.
   Ne pas confondre le nom visible d’une lumière et son identifiant `light.…`.
   Pour un premier essai sans commande, garder les exemples fictifs.
4. Pour un **nouveau panneau uniquement**, créer une clé aléatoire privée avec
   `openssl rand -base64 32`, puis ajouter dans le `secrets.yaml` de Builder :

   ```yaml
   tpp06_api_encryption_key: "COLLER_ICI_VOTRE_CLE_PRIVEE"
   ```

   Cette valeur d’exemple n’est pas une clé utilisable. Ne pas la copier telle
   quelle. Avec plusieurs panneaux, utiliser une entrée distincte et adapter
   le `!secret` correspondant. Pour une mise à jour, **conserver la clé existante**.
5. Garder les blocs `api`, `ota`, `host`, `external_components` et
   `api.reboot_timeout: 0s`. Le modèle utilise le chiffrement OTA d’ESPHome
   2026.10.2 ; ne pas inventer un mot de passe OTA, ni remplacer la clé API par
   le mot de passe root. Ne pas ajouter un bloc `wifi:` ESP32 : Linux conserve
   son profil Wi-Fi via le superviseur.
6. **Valider**, puis lancer une **compilation/téléchargement manuel** dans HA,
   sans installation. Le résultat pour ce portage est un exécutable Linux
   `program`, pas un firmware ESP32 `.bin`. Le téléchargement initial des
   outils peut être long. Garder la fenêtre ouverte et lire le résultat final.

Le fichier utilise GitHub comme source de composants : il n’y a pas à ajouter
le dépôt dans les paramètres d’apparence de Builder. Aucun chemin du poste de développement
ou dossier privé d’un autre utilisateur ne doit être nécessaire. Les versions
ultérieures d’ESPHome ne sont pas automatiquement validées par ce guide.

### Arrêt avant la première activation autonome

**Une compilation réussie n’installe rien.** Le panneau d’origine n’écoute
pas encore l’OTA ESPHome. La première copie passe par le Cutter, pas par USB
comme un ESP32. Le message générique « première installation USB » du Builder
ne décrit pas ce portage Linux.

La procédure avancée est décrite dans [Tuya Cutter](07-tuya-cutter.md).
Un essai standard conserve Tuya et ne valide donc pas l’exclusivité de l’écran.
`install --experimental-multiboot --keep-stock` prépare sans sélectionner
ESPHome ; `install` ne confirme **jamais** automatiquement le démarrage
autonome permanent. Il faut vérifier le profil réseau, les sauvegardes, le
secours, l’essai borné puis l’API authentifiée avant confirmation séparée.

**Pour un novice : arrêter ici et demander une mise en service accompagnée.**
Le dépôt ne fournit pas encore un parcours universel en un clic pour cette
transition. Ne pas modifier manuellement `mode`, `network_mode` ou
`persistent_confirmed` en recopiant des valeurs trouvées dans un journal.
Une sélection réussie sur un autre panneau ne valide pas le vôtre.

## 5. Mettre à jour un panneau déjà sous ESPHome

1. Sauvegarder le YAML actuel, `secrets.yaml`, le dernier programme fonctionnel
   et la sauvegarde Cutter, hors GitHub. Ne pas renommer le panneau ou changer
   sa clé en même temps que l’interface.
2. Pour passer de V4 à V5, comparer votre YAML avec le modèle mobile V5 :
   conserver vos substitutions, clés et adresses ; reprendre aussi les nouveaux
   blocs V5 (`tpp06_backlight`, scripts, globales et automatismes), pas seulement
   `lvgl:`. Si un dossier local de composants issu des essais est encore
   référencé, ne pas le supprimer sans comparer avec les pilotes publiés.
3. Vérifier **version de projet `0.1.5`**, puis **Valider**. Laisser la veille
   sur **Jamais**. Ne pas installer un second appareil pour cette mise à jour.
4. Compiler/télécharger le candidat dans HA. Avec le programme téléchargé,
   vérifier l’espace disponible depuis l’ordinateur d’administration :

   ```bash
   python3 tools/tpp06_tuya_cutter.py 192.0.2.1 ota-space-check --binary /chemin/vers/program
   ```

   Respecter le résultat du contrôle ; prévoir le nouveau programme plus une
   marge (au moins 2 Mio dans l’essai de référence). Ne jamais effacer au hasard
   les données Tuya, le profil réseau ou les sauvegardes pour gagner de la place.
5. Dans Builder, cliquer **une seule fois sur Installer → Sans fil**. Choisir
   l’adresse actuelle du panneau si demandée. Ne pas lancer un deuxième envoi
   depuis une autre fenêtre et ne pas couper l’alimentation.
6. Attendre **Installation réussie**, pas simplement « Successfully compiled ».
   Ouvrir les journaux et vérifier connexion, authentification chiffrée et
   version `0.1.5`. Contrôler l’accueil, la date et le menu sans action domotique
   pour commencer. Une courte coupure API pendant le remplacement est possible ;
   elle ne prouve pas un redémarrage complet de Linux.

La configuration complète est une copie locale éditable : un changement sur
GitHub ne remplace pas automatiquement vos pages. L’absence de notification
« mise à jour » n’empêche donc pas ce parcours manuel. Pour reproduire un build,
noter la version ESPHome et le commit des composants ; `ref: main` suit le dépôt.

## 6. Relier Home Assistant et personnaliser

Dans **Paramètres → Appareils et services → ESPHome**, accepter la découverte
ou ajouter le nom/IP du panneau et **votre clé API**. Le mot de passe root n’est
pas la clé API. Une entrée existante doit conserver son identité ; en cas de
message « appareil différent / MAC différente », ne pas forcer une association
ni supprimer toutes les entités : vérifier l’ancien enregistrement et la vraie
MAC du panneau avant de migrer.

Pour autoriser les boutons à agir sur les lumières/volets, vérifier les entités
puis activer, dans les options de cette intégration, l’autorisation d’effectuer
des actions Home Assistant. Laisser cette permission désactivée pendant les
essais purement graphiques. Un état « connecté » peut aussi provenir du client
de journaux ; il ne prouve pas à lui seul la liaison fonctionnelle avec HA.

Modifier les pages et widgets dans `lvgl:` puis refaire validation, compilation
et OTA. La [V5](11-interface-v5.md) ajoute menu, diagnostics et luminosité.
La veille/réveil physique reste à tester sur place ; **bip indisponible**.
Le [logo initial MOES](12-logo-demarrage.md) est une autre opération, facultative
et risquée : une OTA de l’interface ne le modifie pas.

## 7. Si cela échoue

| Symptôme | Vérification sûre |
| --- | --- |
| Erreur de compilation | Télécharger le journal ; repérer la première erreur, pas seulement `build stopped`. Aucun nouvel envoi tant que cela ne compile pas. |
| Compilation réussie, installation échouée | Vérifier réseau, espace, adresse et clé ; ne pas reflasher l’overlay. |
| API refusée sur `6053` | Vérifier que l’application ESPHome tourne, pas seulement le Wi-Fi. Garder le secours et consulter `status`. |
| Connexion impossible avec clé | Utiliser la clé du programme réellement installé ; ne pas générer une nouvelle clé au hasard. |
| `.local` introuvable | Essayer l’IP connue ; vérifier mDNS/VLAN séparément. |
| Écran noir après veille | Ne pas multiplier les reboot ; récupération locale et analyse avant nouvel essai. |
| Boucle de démarrage / aucun réseau | Arrêter les tentatives OTA ; [récupération avancée](../archive/README.md). |

Le secours multiboot retourne à **Tuya d’origine**, pas à la V4 automatiquement.
Conserver les programmes précédents hors du panneau. Pour une restauration,
faire vérifier l’archive et le périmètre dans le [guide Cutter](07-tuya-cutter.md).

Ne pas exposer `8090`, ADB, API ou OTA sur Internet ; limiter l’accès de
maintenance au LAN de confiance. Le correctif ADB accepte le transport RSA
des clients du LAN : son isolation réseau est importante.

Documentation officielle complémentaire : [API et chiffrement](https://esphome.io/components/api/),
[OTA ESPHome](https://esphome.io/components/ota/esphome/),
[secrets YAML](https://esphome.io/guides/configuration-types/#secret).
