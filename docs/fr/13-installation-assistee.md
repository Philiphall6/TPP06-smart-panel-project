# Première mise en service assistée — expérimental

[English](../en/13-assisted-setup.md) · [Guide débutant](DEMARRER-ICI.md)

**Statut : code et simulations hors ligne uniquement. Cette nouvelle procédure
complète n'a pas encore été exécutée sur un panneau.** Elle ne remplace pas
la validation sur matériel et n'est pas encore recommandée pour un novice seul.
Le panneau de référence déjà fonctionnel n'a pas été modifié pour ces tests.

L'outil [`tpp06_commission.py`](../../tools/tpp06_commission.py) automatise la
configuration privée, les précontrôles, la sauvegarde Cutter, la préparation,
un essai de démarrage et la confirmation du mode principal. **La compilation
reste dans Home Assistant.** Il ne prépare pas l'overlay ADB, ne flashe pas la
NAND et ne remplace pas le logo. Si ESPHome fonctionne déjà, utiliser l'OTA,
pas cet outil : la préparation refuse un panneau exécutant déjà ESPHome.

## Prérequis et limites

- Confirmer la variante compatible TPP06/AK3761E et son firmware ; les seuls
  contrôles de noyau/architecture ne prouvent pas la compatibilité matérielle.
- ADB réseau déjà opérationnel, Tuya d'origine seul actif, Wi-Fi associé.
- Ordinateur Linux, Python **3.11 ou plus**, `adb`, `readelf` (paquet binutils).
  Aucun Mint particulier n'est imposé ; cet ordinateur ne compile rien.
- Alimentation stable, présence sur place et récupération UART possible.
- Sauvegarde personnelle préalable ; la sauvegarde Cutter n'est pas une image
  NAND complète et peut contenir les identifiants Wi-Fi.
- Version ciblée : modèle V5/projet `0.1.5`, ESPHome `2026.10.2`.

Depuis la racine du dépôt, créer un environnement Python dédié :

```bash
python3 -m venv .venv-commission
.venv-commission/bin/pip install 'aioesphomeapi==46.12.0'
```

Les commandes ci-dessous utilisent des valeurs fictives : remplacer
`192.0.2.1` par l'IP du **panneau**, `/chemin/prive/panneau` par un nouveau
dossier hors Git dont le parent existe, et `panneau-entree` par un nom unique.
Utiliser le fuseau horaire de votre HA.

## 1. Générer puis compiler dans HA

```bash
.venv-commission/bin/python tools/tpp06_commission.py configure --directory /chemin/prive/panneau --name panneau-entree --address 192.0.2.1 --timezone Europe/Paris
```

Le dossier privé contient le YAML complet, `secrets.yaml`, `api-key.txt` et
`connection.json`. Il est créé avec des permissions privées ; aucun fichier
existant n'est remplacé. Copier le YAML dans `/config/esphome` de HA. **Fusionner
l'entrée secrète dans le `secrets.yaml` existant, sans remplacer ce dernier.**
Pour plusieurs panneaux, renommer l'entrée secrète et sa référence dans le
YAML afin de ne pas écraser la clé d'un autre appareil. Garder la même valeur
que dans `api-key.txt`. Ne publier ni ces fichiers ni le programme compilé.

Adapter les libellés et l'interface, mais garder le nom technique et la version
attendus, les sections réseau/API/OTA du modèle et `api.reboot_timeout: 0s`.
Laisser les entités fictives et ne pas autoriser les actions HA pendant l'essai.
Dans Builder : **Valider**, puis compiler/télécharger manuellement sans installer.
Copier l'exécutable Linux `program` dans le dossier privé. Ne pas utiliser de
firmware ESP32. Ne plus changer ce binaire au milieu de la procédure.

## 2. Contrôler, puis préparer sans reboot

```bash
.venv-commission/bin/python tools/tpp06_commission.py check --directory /chemin/prive/panneau --binary /chemin/prive/panneau/program
```

Cette commande ne modifie pas les fichiers du panneau. Elle vérifie notamment
l'architecture du programme, l'identité réseau, le profil Wi-Fi actif, les
accès de secours, le watchdog et l'espace disponible. Elle n'efface rien pour
faire de la place et ne garantit pas le démarrage futur.

Après examen des résultats, **uniquement en essai accompagné avec récupération
sur place**, préparer les fichiers :

```bash
.venv-commission/bin/python tools/tpp06_commission.py prepare --directory /chemin/prive/panneau --binary /chemin/prive/panneau/program --experimental --compatible-panel-confirmed --physical-recovery-ready
```

Cette étape **écrit sur le panneau** : sauvegarde préalable, installation du
programme et du superviseur, copie du profil Wi-Fi et contrôle des transferts.
Elle conserve la sélection Tuya et ne demande aucun redémarrage. Garder une
copie privée externe du dossier, notamment de `backups/` et `commission.json`.
Ces trois options sont une déclaration de l'opérateur, pas une preuve automatique
de compatibilité ou de présence physique.

## 3. Un essai, puis confirmation conditionnelle

```bash
.venv-commission/bin/python tools/tpp06_commission.py trial --directory /chemin/prive/panneau --binary /chemin/prive/panneau/program --experimental --compatible-panel-confirmed --physical-recovery-ready
```

L'outil demande **un seul redémarrage**, puis observe automatiquement le panneau.
Il exige au moins **120 secondes continues** avec le même processus ESPHome et
le même démarrage, sans interface Tuya, avec Wi-Fi, ADB, port de secours et API
chiffrée accessibles. Il compare MAC, nom et version et vérifie les sauvegardes.
Il ne commande ni lumière ni volet. Il confirme le mode principal seulement
après ces contrôles, puis vérifie le réarmement du superviseur et le désarmement
du garde. Aucun second redémarrage de validation n'est demandé.

Un garde indépendant sur le panneau prévoit le retour à Tuya et un reboot après
**10 minutes sans confirmation**, même si l'ordinateur se déconnecte. La fenêtre
de confirmation ferme à 8 minutes. Un redémarrage avant confirmation doit revenir
à Tuya grâce au marqueur d'essai consommé. **Ces protections sont testées en
simulation, pas encore matériellement avec ce nouvel assistant.** Elles ne
couvrent pas une panne du noyau, de la NAND ou de l'alimentation.

## En cas d'erreur ou de déconnexion

Ne pas relancer `trial`, supprimer le journal/verrou ou réinstaller à l'aveugle.
Si la demande de reboot a pu partir, seule cette commande reprend les contrôles
sans renvoyer de reboot :

```bash
.venv-commission/bin/python tools/tpp06_commission.py verify --directory /chemin/prive/panneau --binary /chemin/prive/panneau/program
```

Un essai déjà déclaré échoué n'est pas automatiquement réarmé. Laisser le garde
agir puis examiner l'état et les journaux privés avec un accompagnement. Les
phases ambiguës restent bloquées volontairement. Ne pas lancer une OTA en parallèle.

## Après une confirmation réussie

Ajouter le panneau dans l'intégration ESPHome de HA avec sa clé privée. Vérifier
physiquement affichage et tactile ; vérifier séparément mDNS avant de remplacer
l'IP initiale par le nom `.local`. Les mises à jour suivantes passent par Builder
et l'OTA, pas par cette première installation. Un arrêt électrique, l'endurance,
la veille/réveil, le bip et les commandes HA restent des validations distinctes.
Le secours conserve **Tuya d'origine**, pas la version précédente d'ESPHome.
