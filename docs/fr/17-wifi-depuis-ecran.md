# Wi-Fi depuis Paramètres — liaison Linux activée sur le panneau de référence

Le modèle de développement `0.1.6-wifi.2-dev` ajoute **Paramètres → Wi-Fi** :
recherche de réseaux, sélection tactile du nom, clavier, mot de passe masqué,
**Essayer**, **Confirmer** et **Annuler**. Le réseau actif du panneau de référence n'a pas été modifié.
Ne pas lancer une OTA en supposant que cette fonction est déjà validée.

## Fonctionnement prévu

1. Ouvrir **Paramètres → Wi-Fi → Rechercher les réseaux**. Attendre environ
   20 secondes, toucher le réseau souhaité, puis saisir sa clé sur le clavier.
   Le nom est prérempli et le clavier vise le mot de passe masqué. Toucher
   un résultat ne lance pas la connexion. **Saisie manuelle** reste disponible
   pour les réseaux masqués ou absents de la liste.
2. **Essayer** demande au superviseur Linux de conserver le profil actuel,
   puis d'essayer le nouveau. L'API et l'accès distant peuvent être coupés.
3. Le superviseur attend l'association au réseau demandé, la disparition de
   l'ancien bail puis une adresse IPv4 et 20 secondes de stabilité.
4. **Confirmer** sur le panneau conserve le nouveau profil. L'ancien reste
   dans un fichier privé pour une récupération manuelle.
5. Sans confirmation, ou avec **Annuler**, il restaure l'ancien profil.
   Le délai d'essai est de 120 secondes, vérifié à chaque passage du
   superviseur (normalement 10 secondes) ; la reconnexion prend du temps.

Le retour rétablit une **configuration**, pas une garantie de connexion si
l'ancien point d'accès a disparu. Une panne du pilote Wi-Fi ou du système peut
nécessiter une récupération sur place. Une connexion Wi-Fi ne prouve pas
l'accès à Internet ou à Home Assistant ; aucun de ces services n'est requis
pour confirmer depuis l'écran.

## Découverte locale

La recherche n'est déclenchée ni au démarrage ni à l'ouverture de la page.
Elle utilise `SCAN`, puis lit `SCAN_RESULTS` au passage suivant du superviseur.
Ces résultats peuvent provenir du cache du pilote : l'interface le signale,
sans prétendre avoir reçu l'événement de fin d'un nouveau scan. Si la liste
est ancienne ou vide, attendre puis relancer, ou saisir le nom manuellement.

- Quatre résultats par page, bouton **Suite**, au plus 24 noms/profils distincts.
  Les doublons de même nom et catégorie de sécurité sont regroupés ; tri par
  signal décroissant lorsque le pilote fournit un niveau dBm négatif.
- Les réseaux non compatibles sont indiqués **Non pris en charge** et ne
  peuvent pas être sélectionnés. La découverte ne garantit pas une connexion.
- La liste expire après deux minutes ; une nouvelle recherche est limitée à
  une fois toutes les 30 secondes. Aucun scan automatique en boucle.
- Les résultats sont limités à 12 000 octets, privés et non journalisés.
  Les noms masqués, malformés, caractères de contrôle et lignes tronquées
  sont ignorés. Les noms UTF-8 valides sont conservés sans commande shell.
- Le scan est refusé pendant un essai Wi-Fi, sa restauration, une OTA repérée
  par le superviseur ou si les processus réseau ne lui appartiennent pas.
  Il ne change pas le profil ni le bail DHCP, mais un scan radio peut provoquer
  une brève latence. Le comportement réel du pilote reste à tester sur place.

## Protection et limites

- Wi-Fi Linux `wlan0`, pas le composant ESP32 `wifi:`.
- WPA/WPA2 personnel seulement dans cette première version. Pas de WPA3 seul,
  réseau ouvert, entreprise, portail captif ou configuration IP statique.
- SSID de 1 à 32 octets UTF-8. Clé de 8 à 63 caractères ASCII imprimables,
  sans guillemet double, ou PSK de 64 chiffres hexadécimaux. Les guillemets
  sont refusés pour éviter une ambiguïté du parseur de configuration WPA.
- Saisie manuelle disponible, y compris pour un SSID masqué ; pas encore
  d'import de fichier ou de bibliothèque multi-profils.
- Pas d'entité Home Assistant contenant la clé. Champ effacé après l'envoi
  et à la sortie de la page. Aucun journal du composant ne contient la clé.
- Répertoire temporaire privé `0700`, fichiers `0600`. Les profils persistants
  restent des secrets locaux lisibles par root, **pas des fichiers chiffrés**.
  Ne jamais publier ces profils ni leurs sauvegardes sur GitHub.
- Pas de commande relais, de reboot ou d'écriture de partition firmware.
  Seule la vérification de liaison Wi-Fi est suspendue pendant l'essai ;
  les vérifications de processus, API locale et services de secours restent.
- Pour changer de box quand l'ancien réseau a déjà disparu, il faut aussi
  avoir validé et activé la politique locale hors ligne du superviseur
  (`local_control_confirmed`). Elle n'est pas activée par cette interface.
  Avec cette politique, un retour au profil précédent sans point d'accès
  laisse l'écran disponible pour corriger la saisie ; sans elle l'essai
  depuis une connexion déjà perdue est refusé.
- Une interruption avant confirmation laisse un journal persistant. Le
  superviseur restaure l'ancien profil avant son prochain démarrage réseau
  ou son retour vers le logiciel d'origine.
- Le profil réseau du logiciel Tuya d'origine n'est pas réécrit. Après une
  migration confirmée, ce secours peut donc nécessiter l'ancien point d'accès.
- Une nouvelle IP peut nécessiter une mise à jour côté HA si mDNS ne traverse
  pas le réseau. La clé API, l'identité et les entités ne sont pas remplacées.

## Deux parties, pas une simple OTA

Le composant `tpp06_wifi` ne commande jamais le réseau lui-même. Il échange
des fichiers privés avec `device/tpp06-wifi-edit.sh`, chargé **par le nouveau
superviseur**. Un marqueur récent, émis par le processus en cours, autorise
la saisie effective ; un ancien superviseur ou un helper absent laisse la
fonction indisponible. L'OTA de l'interface n'active pas ce mécanisme.

L'activation reste un travail de mise en service séparé : sauvegarder le
superviseur et le profil réellement actifs, vérifier les binaires et le
secours, installer les deux scripts ensemble et faire reprendre le nouveau
superviseur lors d'un redémarrage surveillé. Le fichier d'autorisation
`wifi_editor_enabled` n'est **pas créé automatiquement**. Ne pas copier un
script sur le superviseur en train de s'exécuter, ni supprimer le journal
`network/wifi-trial/pending` pour forcer un état « prêt ».

Avant activation utilisateur, avec une personne sur place et un secours UART :

1. Compiler l'interface dans HA et vérifier la taille, l'ABI et la réserve OTA.
2. Vérifier le rendu de la liste et du clavier, la sélection du bon SSID,
   la confidentialité de la saisie et le tactile. Tester une liste vide,
   les doublons, plusieurs pages, les noms accentués et la saisie masquée.
3. Essayer un mot de passe faux, l'annulation et l'expiration sans client HA.
4. Essayer un second point d'accès réel, le renouvellement DHCP, la confirmation
   et la découverte mDNS depuis HA.
5. Tester l'interruption du programme et le redémarrage avant confirmation.
6. Vérifier les relais locaux pendant l'absence de réseau et l'accès de secours
   après retour au profil précédent. Ne pas déclarer la fonction validée avant.
   Vérifier également la saisie d'un nouveau réseau lorsque l'ancien point
   d'accès est éteint, après validation de la politique locale hors ligne.

### Préparer sans activer

Le contrôle `device/tpp06-wifi-preflight.sh` peut examiner les candidats
**sans les charger** et sans modifier le réseau. Sur le panneau, lui passer
les chemins des deux scripts placés dans un dossier de préparation privé :

```sh
sh /chemin/prive/tpp06-wifi-preflight.sh \
  /chemin/prive/tpp06-multiboot.sh /chemin/prive/tpp06-wifi-edit.sh
```

Il contrôle la syntaxe avec le shell du panneau, la politique de démarrage,
le profil privé, le lanceur de secours, l'absence d'OTA/transaction en cours,
l'appartenance des processus WPA/DHCP et la réponse du service Wi-Fi.
Il n'affiche ni nom de réseau ni clé. Un résultat positif signifie seulement
que ces prérequis sont satisfaits : **aucune activation et aucune migration
réseau n'ont été testées**. La limite de remplacement d'une box déjà absente
est signalée si la politique locale hors ligne n'a pas été confirmée.

Conserver le superviseur actif, le secours et le profil réseau en sauvegarde
privée, puis comparer leurs empreintes après préparation. Ne pas remplacer
le lanceur actif, créer `wifi_editor_enabled` ou redémarrer à distance sans
la mise en service surveillée décrite ci-dessus. Les fichiers placés dans
un dossier de préparation ne sont pas chargés automatiquement.

Les tests automatiques couvrent la machine d'états avec WPA/DHCP simulés,
la récupération du journal, la découverte simulée (tri, doublons, expiration,
sécurité, temporisation), les refus de données invalides, les permissions
des fichiers, la génération C++ LVGL et la validation YAML. **Ils ne remplacent
pas ces essais matériels.** Un candidat `0.1.6-wifi.2-dev` a maintenant été
compilé dans HA et contrôlé comme exécutable ARMv5TE statique, soft-float.
La réserve de stockage OTA a été vérifiée sur le panneau de référence ; elle
doit être recalculée sur chaque installation. Ce contrôle ne valide pas le
changement de réseau : le service Linux était alors absent/non activé sur ce panneau.
L'installation du candidat a ensuite été constatée et vérifiée par son empreinte
et son API chiffrée, sans renvoyer une seconde OTA. Observation de 120 secondes :
processus stable, aucun redémarrage Linux, quatre états d'interrupteurs reçus,
deux boutons de redémarrage et stockage présents. Aucun relais n'a été actionné.
Cela ne remplace ni le contrôle visuel/tactile ni les essais réseau sur place.
L'installation de l'interface seule laisse la gestion Wi-Fi indisponible.

La liaison Linux a ensuite été installée séparément sur le panneau de référence,
après confirmation d'une récupération sur place. Un seul redémarrage a été
demandé. Après le démarrage, une observation de 120 secondes a confirmé la
stabilité du processus ; l'API chiffrée et les accès de secours répondaient.
Le démarrage permanent a été réarmé, puis le marqueur de disponibilité du
service Wi-Fi a été vérifié récent, avec état `idle` et sans transaction.
Le profil Wi-Fi et le lanceur Tuya de secours ont conservé leurs empreintes.
**Cela valide la liaison logicielle au repos, pas une migration réseau.**
La recherche tactile, le changement de point d'accès et le retour arrière
réel restent à tester. La politique locale hors ligne n'a pas été activée.
Cette activation sur un panneau ne rend pas automatiquement les autres
installations compatibles : chacune nécessite les mêmes contrôles.

Référence technique : [interface de contrôle wpa_supplicant](https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html).
