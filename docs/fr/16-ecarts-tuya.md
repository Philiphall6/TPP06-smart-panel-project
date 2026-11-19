# Fonctions Tuya : écarts et vérifications restantes

Mise à jour : voir le [suivi des 22 domaines et les correctifs candidats](18-consolidation-linux.md).
Ce document conserve l'état de l'inventaire initial ; « préparé » ne signifie
pas installé ou validé sur le matériel.

Inventaire du 18 novembre 2026, à partir du firmware sauvegardé, du code du
projet et de lectures du panneau de référence. Aucun test usine, émission IR,
commande Bluetooth, son, changement de relais ou redémarrage pour cet audit.

**Attention : la bibliothèque Tuya contient du code pour plusieurs familles
de panneaux. Un symbole ou une traduction ne prouve pas qu'une fonction était
disponible sur ce modèle, ni que son capteur est monté.** Cet inventaire n'est
pas une certification de parité complète.

## Ce qui fonctionne déjà

- Interface ESPHome/LVGL et tactile ; correction des couleurs validée par
  une mire physique puis par l'utilisateur.
- Trois boutons de façade, trois relais et leurs voyants, validés sur le
  panneau de référence ; états/commandes exposés dans Home Assistant.
- API chiffrée, OTA et identité réseau réelle déjà vérifiées sur cette
  installation. Cela ne valide pas toutes les conditions de perte réseau.
- Démarrage de l'application ESPHome avec mécanisme de secours Tuya. Ce
  secours ne protège pas d'une mauvaise écriture NAND.

## Écarts prioritaires

| Fonction | État du portage / travail restant |
| --- | --- |
| Commande locale sans HA, Wi-Fi ou Internet | Les boutons commandent directement le pilote local. Il reste à valider séparément perte HA, perte Wi-Fi et démarrage à froid sans réseau. La politique hors ligne du superviseur est préparée mais pas activée sur la cible. |
| État des relais après coupure | Ne pas supposer une restauration : le composant évite de restaurer d'anciennes préférences. Définir et tester une politique explicite par relais. Tuya contient `tuya_cc_get_relay_last_status`, sans preuve ici d'un réglage utilisateur équivalent. |
| Relais dans l'interface tactile | Les commandes physiques et HA fonctionnent ; les pages d'éclairage existantes ne constituent pas encore une page générique des trois relais locaux. |
| Mode impulsion / inching | Chemin logiciel préparé et tests simulés ; durée réelle, interruption et retour après panne restent à valider sur le matériel. Le mode switch reste celui validé. |
| Bouton supérieur « Power » | Pas d'action ajoutée. Une entrée de type mute est candidate, mais sa correspondance physique n'est pas confirmée. Ne pas la transformer en arrêt système sur supposition. |
| Veille et réveil | Réglages présents ; vérifier veille réelle, réveil sans action involontaire, OTA et secours pendant la veille. |
| Bip tactile | Correctif `0.1.6-buzzer.1` installé et fonctionnement confirmé par le propriétaire. Voir [le diagnostic et les limites](15-bip-tactile.md). |
| Météo | V6 installée, affichage confirmé sur le panneau. Garder un état indisponible explicite lorsque HA ou les données manquent. |
| Stockage | `0.1.6-system.2` ajoute une entité texte « Stockage disponible et total » au même appareil ESPHome que les relais. Lecture de `/data` toutes les 60 s, disponible/total en Mio ; en cas d'erreur, « Indisponible », sans conserver une valeur périmée. Validation après OTA à faire. |
| Redémarrage ESPHome | « Redemarrer ESPHome » relance seulement l'application, après les hooks d'arrêt. Refus si OTA présente, binaire remplacé ou superviseur non sain. Pas de reboot Linux. Essai réel encore à faire. |
| Redémarrage complet | « Redemarrer le panneau » demande `/sbin/reboot` sans forçage, à l'init BusyBox vérifié. Contrôle supplémentaire du secours, du mode permanent confirmé, du profil Wi-Fi et de 2 Mio libres. Les deux boutons s'excluent mutuellement ; aucune relance automatique après demande Linux acceptée. Le réseau sera interrompu et les relais peuvent changer au démarrage. Essai réel encore à faire. |
| Wi-Fi configurable à l'écran | Scan/sélection/mot de passe et essai borné disponibles dans le code ; service Linux vérifié au repos. Aucune migration réelle ni retour arrière réseau validé. Voir [les limites et la mise en service séparée](17-wifi-depuis-ecran.md). |
| Heure après démarrage sans HA | Synchronisation HA présente ; démarrage à froid hors réseau et source de temps de secours non validés. Aucun RTC exposé dans `/sys/class/rtc` lors de l'inventaire. |

## Fonctions repérées dans Tuya, non portées

| Fonction | Preuve et limites |
| --- | --- |
| Luminosité automatique | `gui_ctrl_get_bright_auto`, `gui_ctrl_set_bright_auto`, `tuya_sensor_light_get`. Luminosité manuelle disponible côté ESPHome ; capteur ambiant non identifié sur la cible. |
| Réveil par proximité | `gui_ctrl_proximity_*`, `tuya_sensor_distance_get`. Aucun capteur identifié dans l'inventaire standard IIO/I²C ; un pilote spécifique reste possible. |
| Mode nuit / Ne pas déranger | Fonctions `gui_ctrl_dnd_*` et traductions de plages horaires, notifications et appels. Pas de politique globale équivalente pour luminosité/bip/notifications. |
| Économiseurs d'écran | Sélection de type et ressources d'horloge dans Tuya. Une veille seule ne remplace pas les différents cadrans et fonds. |
| Verrouillage par code | Fonctions `gui_ctrl_set_passwd_enable` et `gui_ctrl_set_passwd`. Pas de verrouillage local porté ; il ne doit pas empêcher une commande locale nécessaire. |
| Réveil / alarme | Traductions `settings_alarm_clock_*` dans les ressources communes. À confirmer pour ce modèle avant d'en faire une fonction manquante certaine. |
| Cartes, scènes, notifications | Ressources de configuration des cartes et fonctions de notifications présentes. Le portage est modifiable en YAML, pas encore par un éditeur complet sur l'écran. |
| Infrarouge | `/dev/lirc0` présent ; `tuya_ir_code_learn` et fonctions d'émission dans la bibliothèque. Ni émission, ni réception, ni apprentissage testés. |
| Bluetooth | Contrôleur `hci0` présent et fonctions/réglages Bluetooth dans Tuya. Aucun appairage, audio ou rôle proxy HA validé ; présence du contrôleur ≠ compatibilité proxy. |
| Voix, microphone, audio | Fonctions mute, volume et reconnaissance vocale dans la bibliothèque commune. Matériel et services disponibles sur ce panneau non établis ; ne pas promettre Assist sur cette seule base. |

Les fonctions Tuya Cloud ne sont pas à réactiver automatiquement : le projet
vise le contrôle local. Les scènes et notifications peuvent être redéfinies
côté HA, avec un comportement explicite quand HA est absent.

## Trace des vérifications

- Bibliothèque privée `libtuya_app.so`, SHA-256 :
  `f940aeee4a70e6ccb7f12eda075b40c7a3577484f1a460c327d9055d5d8477f7`.
- Ressources communes `pkg_res/dgnzk_3.5/default_language.json` ; les autres
  familles dans le dump expliquent la prudence sur les fonctions annoncées.
- Lectures système : contrôleur I²C `ak-i2c`, périphérique `gt1x`, entrées
  `gpio-keys` et `goodix-ts`, Bluetooth `hci0`, infrarouge `/dev/lirc0`.
  IIO n'exposait que `iio_sysfs_trigger`, sans capteur `iio:device`.
- Voir aussi [les relais](14-relais-locaux.md),
  [la V5](11-interface-v5.md) et [le logo](12-logo-demarrage.md).

## Ordre proposé

1. Consolider l'autonomie locale et les états de relais après panne.
2. Valider veille/réveil, identifier le bouton supérieur, puis tester le bip.
3. Valider les états météo indisponibles/périmés et compléter les réglages.
4. Identifier les capteurs éventuels ; seulement ensuite envisager proximité
   et luminosité automatique.
5. Explorer IR/Bluetooth séparément, sans mélanger ces essais avec les sorties
   secteur ou le démarrage de secours.

Les identifiants d'installation, noms des charges, adresses réseau, secrets et
dumps restent hors du dépôt. Aucun binaire Tuya n'est distribué ici.
