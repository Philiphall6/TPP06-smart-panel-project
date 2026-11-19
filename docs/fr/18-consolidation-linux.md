# Consolidation Linux : suivi des 22 domaines

Travail du 19 novembre 2026, inclus dans les sources de la release **v0.1.7**.
L'application a été installée par OTA sur le panneau de référence ; le nouveau
superviseur Linux n'a pas été déployé et reste expérimental. Les modèles sont
épinglés au même tag que les pilotes. Les lots successifs ci-dessous conservent
leurs résultats propres ; voir aussi [BLE, écran et YAML](20-ble-ecran-yaml.md).

L'inventaire en lecture seule a été exécuté sur le panneau de référence. Les
tests logiciels utilisent des fichiers temporaires et des appels système
simulés : ils ne valident pas un fonctionnement matériel après coupure.
Aucun redémarrage Linux, changement de Wi-Fi, commande de relais, émission IR,
appairage Bluetooth ou chargement de module n'a été effectué pour ce travail.

Validation du candidat : **200 tests logiciels réussis**, compilation complète
dans Home Assistant et contrôle du binaire ARMv5TE statique, little-endian,
soft-float. Le programme de référence mesure 10 221 608 octets ; sa réserve
après staging a été vérifiée supérieure à 2 Mio avant transfert.
Une seule OTA chiffrée a ensuite installé l'application : version et checksum
vérifiés, API et heartbeat stables pendant 180 secondes, états des trois relais
inchangés, aucun reboot Linux et chemins de secours conservés. Une capture du
framebuffer confirme l'accueil et l'entrée Local ; elle ne valide pas tous les
gestes tactiles. Les deux copies des nouvelles préférences sont présentes.
Le YAML privé du Builder correspond maintenant à l'application installée ;
l'ancien YAML est sauvegardé et la copie de compilation est archivée hors du Builder.
Ces résultats ne remplacent pas les essais hors ligne, de coupure ou de
persistance après redémarrage. Aucun firmware privé n'est publié.

Après installation, le diagnostic a correctement signalé une réserve insuffisante
pour une prochaine OTA de même taille avec 2 Mio de marge. Un nettoyage demandé
ensuite a archivé sur l'ordinateur 19 anciens journaux Tuya compressés, vérifié
chaque copie puis supprimé uniquement ces fichiers fermés. Les deux archives
les plus récentes, les journaux actifs et les sauvegardes de secours sont conservés.
Résultat sur le panneau de référence : 3,40 Mio libérés, 15,02 Mio disponibles
sur 38,50 Mio et 5,28 Mio de réserve après une OTA de même taille. Les fichiers
retirés sont récupérables depuis la sauvegarde privée ; aucun reboot Linux ni
changement des relais n'a été observé. Recalculer la marge avant chaque OTA.
Dans ce premier candidat installé, le signal Wi-Fi est déclaré indisponible
plutôt que d'inventer une valeur dBm. Voir le lot diagnostic ci-dessous.

## Lot réseau et pilotes (OTA vérifiée sur le panneau de référence)

Le contrôle en lecture seule montre que `/proc/net/wireless` fournit un niveau
positif non exploitable comme RSSI dBm, tandis que `wpa_supplicant` renvoie un
RSSI signé par `SIGNAL_POLL`. Le composant propose donc `wifi_signal_via_wpa`
(désactivé par défaut dans le composant, activé dans le package candidat).
Il interroge uniquement le socket local `/var/run/wpa_supplicant/<interface>` :
aucun scan, processus externe, changement de profil ni trafic Internet.
La réception est non bloquante et expire après une seconde. Réponse invalide,
tronquée ou service absent donnent « Indisponible », sans conversion inventée.
Le socket client abstrait disparaît à sa fermeture, sans fichier à nettoyer.

Le nouveau diagnostic de liaison lit `operstate` et `carrier` dans sysfs.
« Liaison active » ne valide ni DHCP, ni DNS, ni Internet, ni la connexion HA.
Le package `driver-diagnostics.yaml` expose en plus la disponibilité déclarée
par les pilotes relais, bip, rétroéclairage et service de configuration Wi-Fi.
Ce sont des lectures d'état logiciel, **pas des essais physiques** ; un service
Wi-Fi occupé n'est pas nécessairement défaillant. Aucun relais n'est commandé.

Validation logicielle de ce lot : **206 tests réussis**, dont requêtes sur socket
Unix simulé, silence du service, réponses invalides, expiration et débordement
de l'horloge. La compilation HA distincte a réussi : programme de 10 237 224
octets, ARMv5TE statique little-endian soft-float vérifié, réserve après staging
de 5,26 Mio lors du contrôle. L'API chiffrée et les accès de secours restent
disponibles ; boot Linux, PID, états des relais et checksums du superviseur/secours
sont inchangés pendant la compilation. Une seule OTA chiffrée a ensuite installé
ce lot : version et checksum vérifiés, API et heartbeat stables pendant 180 s,
aucun redémarrage Linux ni changement des relais ou des réglages d'interrupteurs.
Le RSSI signé est reçu et les quatre diagnostics déclarent les pilotes/services
disponibles. Cela ne valide pas physiquement les sorties : aucune charge n'a été
commandée. La capture en lecture seule confirme l'accueil normal. Le Builder
est aligné sur l'application installée, avec sauvegarde de l'ancien YAML et
archivage privé du candidat pour éviter un doublon. Le superviseur reste inchangé.
Une surveillance prolongée et les essais hors ligne restent à réaliser.

Références : [interface de contrôle wpa_supplicant](https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html),
[sockets Unix Linux](https://man7.org/linux/man-pages/man7/unix.7.html),
[conversion des unités dans Linux 4.4](https://github.com/torvalds/linux/blob/v4.4/net/wireless/wext-proc.c).

## Changements préparés

- Préférences : écriture temporaire, contrôles d'erreur, synchronisation,
  remplacement atomique, checksum et copie précédente. Import de l'ancien
  format sans l'écraser ; refus d'une lecture partielle et limitation de taille.
- Journaux ESPHome/openHASP, Wi-Fi et service de secours : rétention contrôlée
  pendant le fonctionnement, en conservant les descripteurs ouverts des processus.
- Nouveau composant `tpp06_health` : RAM disponible/totale, signal Wi-Fi Linux,
  état du superviseur et estimation de la marge OTA, avec état indisponible.
- Signal de vie émis depuis la boucle ESPHome dans `/tmp`, basé sur l'horloge
  monotone. Vérification facultative par le superviseur, non armée par défaut.
- Page tactile des trois relais : commandes locales, sans service HA, refusées
  si le pilote est désactivé ou en défaut. Libellés personnalisables.
- Plages de silence : réglables à l'écran et dans HA, sans écraser le réglage
  habituel du bip et sans modifier l'éclairage. Désactivées par défaut.
- Observation de `SW_MUTE_DEVICE` dans HA, avec resynchronisation après perte
  d'événements. **Aucune action Power ou microphone ne lui est attribuée.**
- Outil d'inventaire reproductible, filtré pour ne pas publier les informations
  d'installation. Il n'ouvre pas les périphériques matériels.

## Suivi exhaustif

« Préparé » signifie code/test logiciel, pas installation ni validation réelle.

| Domaine | Traitement de ce lot | Condition restante |
| --- | --- | --- |
| 1. Autonomie hors réseau | Commandes locales préservées ; confirmation hors ligne visible dans le diagnostic | Essais séparés sans HA, sans point d'accès, puis démarrage à froid hors réseau avant activation de la politique |
| 2. Préférences | Sauvegarde atomique et secours préparés ; pannes d'écriture simulées ; compilation cible réussie | Essai de persistance/récupération sur le panneau |
| 3. Journaux et flash | Rétention en fonctionnement préparée ; marge OTA exposée | Observer les volumes réels et la réserve pendant une OTA |
| 4. Santé de l'application | Heartbeat monotone préparé et testé | Observation prolongée, puis essais de blocage et d'OTA avant de le rendre obligatoire |
| 5. Affichage/tactile | Pilotes existants conservés ; pages candidates sans changement de framebuffer | Réveil au premier toucher sans commande, OTA et secours en veille |
| 6. Relais/voyants | Page de trois relais préparée ; états réels et `restore_mode: DISABLED` conservés | Valider cette page ; décider explicitement de la politique après coupure et tester l'inching |
| 7. Entrée supérieure | Capteur texte d'observation préparé | Corréler un appui physique avec `SW_MUTE_DEVICE`, puis décider d'une action ; pas de reboot implicite |
| 8. Bip | Plages horaires locales préparées | Confirmer les horaires et le silence réel ; aucun changement du pilote PWM validé |
| 9. Wi-Fi modifiable | Pont existant conservé, présent dans l'inventaire | Mauvais mot de passe, annulation, coupure pendant essai, retour arrière et ancien routeur absent |
| 10. Diagnostic réseau | RSSI signé via socket wpa_supplicant et état de liaison installés et observés pendant 180 s, sans SSID/clé ; mDNS conservé | DHCP/DNS distincts, changement de sous-réseau et reconnexion HA ; IPv6 non ajouté |
| 11. Heure/RTC | Module RTC présent, aucun `/dev/rtc0` ; inventaire reproductible | Revue puis activation supervisée du pilote, preuve de rétention électrique ; pas d'heure fictive |
| 12. Infrarouge | Nœud et pilote émetteur détectés, aucune émission | Vérification des capacités puis essai sur récepteur choisi ; apprentissage non établi |
| 13. Bluetooth | Annonces BLE transmises à HA par Linux MGMT ; marche/arrêt vérifié depuis HA et 181 s d'observation | Endurance et reprise après coupure ; pas de GATT, audio ni appairage |
| 14. Audio/micro/Assist | Module présent, périphérique audio absent | Preuve matérielle et pilote audio fonctionnel avant portage |
| 15. Lumière/proximité | Aucun périphérique IIO observé | Identification du capteur ou preuve sur carte ; aucun balayage I²C aveugle |
| 16. Autres capteurs | Absence constatée dans les interfaces inventoriées | Distinguer mesures HA et capteurs locaux ; ne pas inventer de température |
| 17. USB/UART | Console et liaison Bluetooth conservées | Aucun UART réaffecté, rôle USB hôte non établi |
| 18. Watchdog/démarrage | Contrat d'initialisation conservé, heartbeat séparé | Ne pas supprimer `rc.local`, les modules stock ni `ak_watchdog` ; pas de second alimentateur watchdog |
| 19. OTA/secours | Diagnostic de réserve et compatibilité séparée application/superviseur | Durcissement du backend OTA, retour automatique au dernier ESPHome et validation des coupures encore à réaliser |
| 20. Diagnostics HA | RAM, superviseur, marge OTA, entrée mute et états déclarés des pilotes relais/bip/rétroéclairage et service Wi-Fi installés ; nouveaux états reçus sur l'API chiffrée | Version des services, motif de boot et vérification matérielle des pilotes à compléter |
| 21. Maintenance | Inventaire filtré ; ports de secours laissés en place | Politique d'accès LAN et mode maintenance avant toute fermeture de port |
| 22. Fonctions d'interface | Relais locaux et plages de silence préparés | Économiseurs, alarmes, langues, verrouillage, éditeur de cartes et export de réglages non implémentés dans ce lot |

Les ressources communes Tuya ne prouvent pas la présence de toutes ces fonctions
sur chaque modèle. Le projet ne réactive pas implicitement le cloud Tuya.

## Préférences : compatibilité et limites

Les fichiers sont propres à l'installation, dans `ESPHOME_PREFDIR` :

- `<nom>.prefs` : ancienne copie conservée, jamais écrasée par ce candidat ;
- `<nom>.prefs.v2` : format checksummé, mode 0600, taille maximale 1 Mio ;
- `<nom>.prefs.v2.bak` : dernière copie valide précédente.

Au premier démarrage, import de l'ancienne copie seulement si les deux fichiers
nouveaux sont absents. Une corruption du nouveau format ne ressuscite pas les
anciens réglages : récupération du backup valide, sinon valeurs par défaut et
avertissement. Une écriture inchangée n'est pas répétée. Un échec laisse le
réglage en attente d'une nouvelle synchronisation.

Un retour à un ancien firmware retrouvera **les réglages d'avant migration**,
pas les derniers réglages du candidat. Ce mécanisme ne constitue ni un backup
Wi-Fi ni un backup NAND. Un checksum n'est pas du chiffrement. Les coupures
électriques réelles et les garanties du système de fichiers restent à tester.

## Journaux et surveillance

Le superviseur vérifie les tailles à ses passages : 1 Mio pour chaque journal
ESPHome/openHASP, 256 Kio pour Wi-Fi/secours. Au dépassement, les derniers 64 Kio
sont conservés dans `.previous` et le fichier courant est tronqué sur place.
Tous les producteurs utilisent l'ajout (`O_APPEND`). Cela évite qu'un renommage
laisse le processus écrire indéfiniment dans un ancien fichier ouvert.

Ce n'est **pas un quota strict** entre deux passages ni une réduction de tous
les accès flash. Des lignes concurrentes peuvent être perdues pendant la
rotation. Les dumps, sauvegardes, configurations et fichiers inconnus sont
laissés intacts. Le nettoyage ponctuel décrit plus haut ne déploie pas cette
nouvelle politique de rétention : le superviseur installé reste inchangé.

Le heartbeat utilise le protocole `1 PID secondes_monotones` et un fichier
privé `/tmp/tpp06-health/heartbeat`, renouvelé toutes les 5 s par défaut. Ce
signal établit une progression de la boucle principale, pas le bon état de
chaque périphérique. Aucun accès à `/dev/watchdog` n'est ajouté.

L'absence de `heartbeat_policy` conserve le comportement existant. La valeur
`observe` n'ajoute aucun motif de secours. **Ne pas écrire `required-v1` avant
commissionnement** : ce mode exige PID correspondant et âge ≤ 25 s ; le
superviseur conserve sa règle de trois défauts persistants. Un blocage pendant
OTA pourrait autrement provoquer un secours intempestif. Les essais OTA font
donc partie du prérequis d'activation.

La marge OTA est une **estimation** : taille du programme en cours + 2 Mio de
réserve, pas une garantie pour un futur fichier plus gros ni pour deux slots.
L'outil existant `ota-space-check` reste nécessaire avec le fichier exact.

## Assembler le candidat sans toucher au panneau

Sur une copie privée du YAML moderne, remplacer la source `external_components`
par une source **locale** pointant vers `esphome-components` de ce même checkout.
Ajouter `tpp06_health` et `tpp06_local_relays` à la liste des composants.
Inclure les packages de ce checkout :

1. `esphome/packages/local-relays-experimental.yaml` ;
2. `esphome/packages/runtime-health.yaml` ;
3. `esphome/packages/mute-input-observation.yaml` ;
4. `esphome/packages/local-controls-ui.yaml` ;
5. `esphome/packages/driver-diagnostics.yaml` (interface moderne et pilotes locaux requis).

Les tests fusionnent ces cinq packages et génèrent le C++ avec ESPHome. La
compilation ARMv5TE statique dans HA et les contrôles de taille/ABI des deux
lots ont réussi sur des copies privées de référence. Un essai borné du lot
réseau/pilotes a été validé sur le panneau de référence ; il reste nécessaire sur
chaque autre installation, ainsi que
ces contrôles pour chaque autre configuration. Ne pas remplacer une configuration privée existante
ni dupliquer ses relais : conserver ses identifiants, secrets et choix validés.

L'entrée **Local** ouvre les trois commandes puis les plages de silence. La
plage traverse minuit si nécessaire ; début = fin signifie silence permanent.
Heure inconnue + plage activée = silence. Le choix du bip reste mémorisé à part.
Ce n'est pas un mode Ne pas déranger global : notifications et luminosité ne
sont pas modifiées.

Le package expérimental laisse le contrôle des relais **désactivé**. L'ajout de
la page ne remplace pas leur commissionnement. Il ne change ni les GPIO au boot,
ni les voyants, ni les paramètres Wi-Fi, ni les règles de démarrage Linux.

## Inventaire sûr et validation progressive

Avec l'environnement Python du projet et l'accès de maintenance déjà configuré :

```sh
python3 tools/tpp06_capabilities.py --host 192.0.2.1 --backup-dir /chemin/prive/sauvegardes
```

L'adresse est un exemple. `--adb` permet de choisir le transport ADB local.
Le rapport ne contient ni IP, MAC, nom Wi-Fi, clé, nom de charge ni dump. Le
transport de maintenance s'authentifie normalement ; le script d'inventaire
n'effectue que des lectures de métadonnées. Ne jamais exposer les ports de
maintenance sur Internet.

Ordre de validation :

1. Vérifier sauvegarde, identité, binaire, place et accès de récupération.
2. Compiler/tester le candidat ; ne pas remplacer en même temps l'application
   et le superviseur. Observer d'abord le heartbeat sans l'armer.
3. Vérifier affichage, veille/réveil, pages, bip et diagnostics, puis OTA.
4. Sur place, surveiller les charges : perte HA, perte du point d'accès,
   retour réseau puis boot hors ligne. Aucun essai de coupure réseau automatique.
5. Valider séparément Wi-Fi temporaire et rollback avec un second point d'accès.
6. Ensuite seulement, activer les politiques confirmées. Aborder RTC, IR,
   Bluetooth et audio comme des essais indépendants et réversibles.

Voir [l'inventaire Tuya](16-ecarts-tuya.md),
[les relais](14-relais-locaux.md) et [le pont Wi-Fi](17-wifi-depuis-ecran.md).
