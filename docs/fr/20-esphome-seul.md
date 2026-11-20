# ESPHome seul : désactiver le retour automatique à Tuya

Cette politique est réservée à un panneau déjà installé et validé en mode
ESPHome permanent, avec réseau Linux indépendant et récupération locale
disponible. Le parcours historique ne l’active pas par défaut pour une première
installation. Le nouvel [assistant graphique expérimental](21-assistant-ordinateur.md)
propose explicitement cette politique dans « Préparer ESPHome seul » ; son
parcours sur un panneau neuf reste à valider avec récupération locale.

Validation sur le panneau de référence : un redémarrage normal avec retour
de SSH, de l'API chiffrée et de la connexion HA ; interface visible confirmée
par l'utilisateur. Les chemins d'échec sont testés hors ligne : aucune panne
n'a été provoquée sur le panneau et aucune coupure électrique n'a été testée
dans cette validation. Ce résultat ne certifie pas les autres firmwares.

Le superviseur reconnaît la présence de
`/data/tpp06-cutter/no_stock_fallback`. Le marqueur seul ne suffit pas : il faut
le superviseur compatible, puis une réactivation contrôlée. Un superviseur
déjà en mémoire ne reçoit pas automatiquement les changements du fichier.

## Comportement

- ESPHome reste sélectionné au démarrage, même après un échec précédent.
- Le superviseur refuse de lancer l'application Tuya d'origine.
- Une erreur mène à `esphome-maintenance`, sans boucle de redémarrage ajoutée.
- Les services réseau existants ne sont pas arrêtés par le nettoyage du
  superviseur. Une tentative de démarrage du réseau est faite si nécessaire.
- Si installé, `/data/tpp06-ssh/service.sh` est appelé pour démarrer SSH.
- Le service local `tuya_factory` sur 8090 reste conservé ; ce n'est pas
  l'application Tuya Cloud. Ses ports et ADB restent des prérequis du
  superviseur actuel. Leur suppression est une modification distincte.
- Linux, pilotes, données d'origine et partitions NAND ne sont pas effacés.

Cette politique ne constitue pas un pare-feu anti-cloud et ne protège pas
contre une panne du noyau, du stockage, de l'alimentation ou du Wi-Fi. Si le
réseau est indisponible, SSH peut être inaccessible et une récupération UART
peut rester nécessaire. Une réinitialisation ou une mise à jour du système
d'origine pourrait également remplacer le superviseur.

## Mise en place accompagnée

### Continuer à commander les relais sans Wi-Fi

La suppression du retour Tuya ne suffit pas à rendre le panneau autonome.
Pour un panneau permanent dont les commandes locales ont été vérifiées,
le superviseur compatible peut lire `local_control_confirmed=yes` dans
`/data/tpp06-cutter/`. Il exige également `persistent_confirmed=yes`,
`boot_policy=persistent`, `network_mode=isolated` et une session non temporisée.

Ce marqueur est relu pendant la surveillance : si ce code est **déjà chargé**
dans le superviseur actif, son activation ne nécessite ni remplacement du
script, ni redémarrage, ni coupure réseau. Sauvegarder l'état précédent et
vérifier la version réellement installée avant de l'activer.

- Une perte d'association Wi-Fi ou de bail DHCP n'arrête plus ESPHome.
- Au prochain démarrage, après le lancement réussi de WPA/DHCP, l'absence
  de point d'accès n'empêche pas le lancement d'ESPHome. La recherche réseau
  continue en arrière-plan.
- Les contrôles du processus et des ports locaux API/secours restent actifs.
  Une panne du pilote ou un échec de lancement des services réseau n'est pas
  assimilé à une simple box éteinte.
- `api.reboot_timeout: 0s` reste nécessaire (idem pour MQTT si utilisé).
- L'écran et les relais locaux peuvent fonctionner, mais SSH et les commandes
  HA sont indisponibles tant que le réseau manque. Cela ne corrige pas un
  verrouillage indépendant du pilote des relais.

Les tests simulés couvrent une panne dépassant le seuil de surveillance, la
reconnexion, les contrôles locaux et l'activation dans un superviseur déjà
lancé. Ils ne remplacent pas les essais physiques sans point d'accès, à faire
sur place avec récupération possible ; ne pas couper le Wi-Fi à distance
pour les réaliser.

### Désactiver le retour automatique à Tuya

1. Sauvegarder le superviseur et les états de démarrage sur le PC.
2. Vérifier les clés SSH, le profil Wi-Fi indépendant et l'absence de transfert
   OTA. Ne pas modifier les clés API ni le firmware pendant cette opération.
3. Tester le candidat hors ligne et avec `sh -n` sur le panneau.
4. Installer atomiquement le superviseur compatible et le marqueur, sans
   tronquer le fichier actuellement exécuté.
5. Avec récupération sur place, demander un seul redémarrage normal.
6. Vérifier SSH, le même appareil via l'API chiffrée, l'état
   `esphome-healthy`, le choix `esphome` et l'absence de l'application/du
   moniteur Tuya. Confirmer séparément l'affichage et les commandes locales.

En cas d'échec, diagnostiquer par SSH/UART. La restauration du superviseur
sauvegardé et le retrait explicite du marqueur peuvent rétablir la politique
antérieure ; ce retour est manuel et peut permettre à Tuya Cloud de repartir.
Les sauvegardes privées ne doivent pas être publiées avec les sources.
