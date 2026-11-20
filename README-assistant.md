# Assistant TPP06 — 0.1.0-rc2

Installation et maintenance graphique pour la variante TPP06 / AK3761E,
Linux `4.4.192V2.4`. **Version expérimentale : simulations et interface testées
sur Mint ; parcours matériel complet sur panneau neuf et Windows réel non validés.**

1. Décompresser tout le dossier sur le PC. Python 3.11+ avec Tkinter et Android
   Platform Tools (`adb`) sont requis. Ne pas exécuter en administrateur/root.
2. Lancer `Installer-dependances.sh` sur Linux, ou `Installer-dependances.cmd`
   sur Windows. Cette étape installe seulement des bibliothèques Python sur le PC.
3. Ouvrir `Assistant-TPP06.sh` ou `Assistant-TPP06.cmd`.
4. Lire le [guide complet](docs/fr/21-assistant-ordinateur.md), puis choisir
   l’action souhaitée. Aucune action n’est exécutée au lancement.

Les huit actions : mot de passe d’origine, ADB réseau, acquisition NAND après ADB,
restauration d’une opération, changement de mot de passe, logo NAND, SSH et
première installation ESPHome seul. Le démarrage et sa vérification sont séparés.
Pas de dual boot automatique, pas de nettoyage permanent des fichiers Tuya.

Ce paquet contient **les sources de l’assistant**, pas un exécutable Windows
autonome, pas de firmware personnel ni de secret. Le programme ESPHome compilé
dans HA et les outils auxiliaires compatibles sont fournis séparément par
l’opérateur ; leurs prérequis et empreintes sont dans le guide. L’activation
ADB peut être activé **sans dump préalable**, en acceptant explicitement l’état
après déblocage comme référence souhaitée. Les personnalisations écrasées par
l’overlay ne seront pas récupérables à partir de cette référence.

La nouvelle acquisition copie toutes les partitions NAND exposées par Linux,
avec données et OOB, en deux passes comparées. Elle utilise seulement un tampon
en RAM sur le panneau, sans arrêt de service, écriture NAND ou reboot. Elle
refuse les blocs défectueux et erreurs ECC non pris en charge. **Une copie à
chaud n’est pas certifiée cohérente, ni équivalente à un dump physique intégral** :
les zones non exposées restent à identifier. La restauration NAND globale
reste non automatisée et non validée. Ne pas supprimer les anciens dumps.
L’archive partielle Cutter reste disponible séparément.

Pour un panneau déjà fonctionnel sous ESPHome, conserver les mises à jour OTA :
**ne pas relancer Première installation**. Garder les sauvegardes privées hors Git.
