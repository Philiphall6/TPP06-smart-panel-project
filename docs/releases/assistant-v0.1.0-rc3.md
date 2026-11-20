# Assistant 0.1.0-rc3 — Français / English, logo inclus et dossiers guidés

**Mise à jour du logiciel PC, pas une OTA du panneau.** Aucun changement du
firmware ESPHome ni de ses références de version. Préversion expérimentale :
le parcours complet sur un panneau neuf et Windows réel reste à valider.

## Téléchargement et démarrage

Télécharger `TPP06-Assistant-v0.1.0-rc3-sources.zip` et son fichier `.sha256`,
extraire **tout** le dossier, puis ouvrir `README-assistant.md`.
Le paquet est lançable avec Python, ce n’est pas un EXE autonome.

- [Python 3.11+ avec Tcl/Tk](https://www.python.org/downloads/) : installateur classique,
  pas le paquet Windows embeddable.
- [Android Platform Tools / ADB](https://developer.android.com/tools/releases/platform-tools) :
  extraire le ZIP complet, choisir `platform-tools/adb.exe` ou `adb`.
- Lancer `Installer-dependances.cmd` sur Windows ou `sh Installer-dependances.sh`
  sur Linux, puis `Assistant-TPP06.cmd` ou `sh Assistant-TPP06.sh`.
  Le module `elftools` absent sur la capture est fourni par `pyelftools`.

## Nouveautés

- Boutons **Français / English**, sans perte de l’adresse, des saisies ou du masquage
  du mot de passe. Libellés et confirmations traduits ; certains rapports techniques
  gardent leur langue d’origine. Guide débutant anglais inclus.
- Onglet **Logiciels et aide**, liens officiels et explications des prérequis.
- **Sauvegardes sur cet ordinateur** : `TPP06-Backups` proposé dans le dossier utilisateur.
  Les sous-dossiers privés contiennent les partitions et les journaux de récupération.
- **Outils TPP06 sur cet ordinateur** : `TPP06-Tools` proposé. Préparation explicite
  des outils NAND et ADB par HTTPS, vérification SHA-256, refus des fichiers inconnus
  sans écrasement. Ce téléchargement ne contacte pas le panneau et n’exécute rien.
  Dropbear reste à préparer selon le guide SSH ; aucun binaire arbitraire n’est accepté.
- Formulaires défilants avec boutons de confirmation visibles en bas.
- Logo Home Assistant **bleu** inclus : aperçu PNG, image RGB565 320 × 480 / 512 Kio,
  SHA-256, SVG public, attribution et licence CC BY-NC-SA 4.0. Choisi par défaut dans
  l’action Logo. **Jamais à envoyer comme firmware OTA.** Aucun dump privé utilisé.

## Contrôles et limites

**343 tests passent**, dont **89 tests propres à l’assistant**, avec interface Tk
sur Mint. Les téléchargements réels des outils NAND et ADB ont également été
comparés aux empreintes attendues. Les tests des opérations matérielles sont
simulés ; ils ne certifient pas l’installation sur un panneau neuf ni une restauration.
Aucun panneau n’a été modifié pour cette publication.

La sauvegarde NAND couvre les partitions exposées par Linux avec deux passes,
données et OOB. Elle ne certifie ni la cohérence d’une copie à chaud ni les zones
physiques cachées. **Pas de restauration NAND globale automatique ou validée.**
Les sauvegardes restent privées, hors Git et hors dossiers partagés/cloud.
Le remplacement du logo reste une écriture NAND séparée, avec sauvegarde,
contrôles et récupération locale requise ; une coupure électrique reste dangereuse.

## English summary

PC-only experimental update; no panel OTA or firmware version change. FR/EN
controls, official software links, explained default backup/tool folders, explicit
HTTPS downloads with pinned SHA-256, scrollable forms and the public blue Home
Assistant boot logo are included. Dropbear still needs compatible manual preparation.
Extract the full ZIP and follow `docs/en/21-assistant-ordinateur.md`.
The logo is **not OTA firmware**. Live NAND backup does not certify full restoration.
No device changes or personal data are included in this release.
