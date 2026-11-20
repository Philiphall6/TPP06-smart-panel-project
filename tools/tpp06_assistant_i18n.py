"""Small offline FR/EN catalogue; language changes never reconnect a device."""
import weakref

EN = {
    "Téléchargement en cours… Le résultat détaillé apparaîtra dans le journal de la fenêtre principale.": "Downloading… Detailed results will appear in the main window's log.",
    "Impossible de lire ce dossier sur le PC.": "Cannot read this folder on the PC.",
    "Impossible de créer le dossier de sauvegarde sur ce PC.": "Cannot create the backup folder on this PC.",
    "Outils manquants ou non reconnus. Utiliser Préparer les outils, puis Vérifier les outils.": "Missing or unrecognized tools. Use Prepare tools, then Check tools.",
    "Lancer Installer-dependances.cmd (Windows) ou Installer-dependances.sh (Linux), puis rouvrir l’assistant. Le module elftools est fourni par pyelftools.": "Run Installer-dependances.cmd (Windows) or Installer-dependances.sh (Linux), then reopen the assistant. The elftools module is provided by pyelftools.",
    "Assistant TPP06 · Installation et maintenance": "TPP06 Assistant · Setup and maintenance",
    "Votre panneau, étape par étape": "Your panel, step by step",
    "Expérimental · Aucune opération au lancement · Sauvegardes privées et confirmations avant écriture": "Experimental · No operation at startup · Private backups and confirmation before changes",
    "Votre appareil — données conservées uniquement en mémoire": "Your device — details kept in memory only",
    "IP du panneau": "Panel IP address", "Mot de passe root": "Root password", "Afficher": "Show",
    "Outil ADB": "ADB program", "Choisir…": "Browse…",
    "0. Logiciels et aide": "0. Software and help",
    "1. Accès et diagnostic": "1. Access and diagnostics",
    "2. Sauvegarde et fichiers": "2. Backups and files",
    "3. Installer / administrer": "3. Setup / administration",
    "4. Reprendre / vérifier": "4. Resume / verify",
    "Vérifier cet ordinateur": "Check this computer",
    "Python, ADB et dépendances ; aucun contact avec le panneau.": "Python, ADB and dependencies; no contact with the panel.",
    "Vérifier les accès réseau": "Check network access",
    "Teste uniquement les cinq ports connus sur l’IP saisie.": "Checks only the five known ports at the entered IP address.",
    "Lire le mot de passe d’origine": "Read the original password",
    "Demande confirmation ; le mot de passe reste masqué et n’est pas enregistré.": "Requires confirmation; the password stays hidden and is not saved.",
    "Lire l’état Linux": "Read Linux status",
    "ADB déjà activé et mot de passe root requis. Ne touche pas aux relais.": "Requires enabled ADB and the root password. Does not operate relays.",
    "Sauvegarde NAND après ADB": "NAND backup after ADB",
    "Toutes les partitions exposées, données + OOB, deux lectures. Pas de restauration NAND automatique.": "All exposed partitions, data + OOB, two reads. No automatic NAND restoration.",
    "Contrôler une copie NAND": "Check a NAND copy",
    "Empreintes et tailles sur le PC ; ne certifie pas une restauration.": "Checks hashes and sizes on this PC; does not certify restoration.",
    "Sauvegarde partielle Cutter": "Partial Cutter backup",
    "Archive Cutter privée et contrôlée, PAS une image NAND complète.": "Private, checked Cutter archive, NOT a full NAND image.",
    "Contrôler une sauvegarde": "Check a backup",
    "Contrôle local du contenu et de la fiche SHA-256, sans extraction ni restauration.": "Local content and SHA-256 checks, without extraction or restoration.",
    "Contrôler un programme ESPHome": "Check an ESPHome program",
    "Vérifie le format ARMv5 sans l’exécuter. Ne compile et n’installe rien.": "Checks the ARMv5 format without running it. Does not build or install anything.",
    "Ouvrir le guide de l’assistant": "Open the assistant guide",
    "Fonctions disponibles, limites et prochaines étapes.": "Available features, limitations and next steps.",
    "Installation accompagnée — variante TPP06 / AK3761E uniquement": "Guided setup — TPP06 / AK3761E variant only",
    "ADB → sauvegarde → SSH / mot de passe → préparer ESPHome → démarrer → vérifier.": "ADB → backup → SSH / password → prepare ESPHome → boot → verify.",
    "Le logo est facultatif et distinct. Aucun choix de dual boot ; aucun nettoyage destructif.": "The logo is optional and separate. No dual-boot choice or destructive cleanup.",
    "Démarrer ESPHome préparé": "Start prepared ESPHome",
    "Un seul reboot, journal préalable ; refus si le démarrage a déjà été demandé.": "One reboot, recorded first; refused if startup was already requested.",
    "Vérifier / reprendre le premier boot": "Verify / resume the first boot",
    "Contrôle MAC, processus et API chiffrée pendant 120 secondes ; ne renvoie aucun reboot.": "Checks MAC, processes and encrypted API for 120 seconds; does not send another reboot.",
    "Réconcilier une écriture du logo": "Check an interrupted logo write",
    "Après une déconnexion : lire le résultat et comparer la NAND, jamais réécrire.": "After a disconnect: read the result and compare NAND; never rewrite.",
    "Inspecter un journal privé": "Inspect a private operation record",
    "Vérifier les sauvegardes et afficher la phase sans relancer l’opération.": "Checks backups and displays the stage without repeating the operation.",
    "Guide et limites de récupération": "Recovery guide and limitations",
    "Si un intent reste ambigu, ne pas supprimer le verrou ni rejouer une installation.": "If an operation's outcome is unclear, do not remove its lock or repeat installation.",
    "Prêt — aucune connexion automatique": "Ready — no automatic connection",
    "Aucune adresse, aucun secret prérempli. Aucun fichier de journal automatique.": "No prefilled address or secret. No automatic log file.",
    "… Ne pas lancer d’OTA en parallèle.": "… Do not run OTA at the same time.",
    " — non terminé": " — not completed", " — terminé": " — completed",
    "Mot de passe d’origine reçu et masqué. Il peut ne plus être valable s’il a été changé.": "Original password received and hidden. It may no longer work if it was changed.",
    "Contrôle de l’ordinateur": "Computer check", "Accès réseau": "Network access",
    "Lecture du mot de passe d’origine": "Read original password", "Lecture du mot de passe": "Read password",
    "Uniquement sur votre propre panneau.": "Only on your own panel.",
    "Cette lecture entre dans le mode de test temporaire du service 8090. Elle ne change pas le mot de passe, n’écrit pas le firmware et ne redémarre pas l’appareil.": "This enters service 8090's temporary test mode. It does not change the password, write firmware or reboot the device.",
    "Continuer ?": "Continue?", "Diagnostic Linux": "Linux diagnostics",
    "Dossier privé hors du dépôt Git": "Backup folder on this PC, outside the Git repository",
    "Sauvegarde partielle — pas une NAND complète": "Partial backup — not a full NAND image",
    "La sauvegarde peut contenir des secrets. Elle ne couvre pas tous les réglages Wi-Fi/SSH.": "The backup may contain secrets. It does not cover all Wi-Fi/SSH settings.",
    "Une archive temporaire sera créée puis supprimée dans /tmp du panneau après son téléchargement. Aucun reboot, relais ou fichier de démarrage n’est modifié. L’opération peut durer plusieurs minutes. Garder la fenêtre ouverte.": "A temporary archive will be created in the panel's /tmp and removed after download. No reboot, relay or boot-file change. This may take several minutes; keep this window open.",
    "Sauvegarde du panneau": "Panel backup", "Archive Cutter": "Cutter archive", "Archive gzip": "Gzip archive",
    "Tous": "All", "Contrôle de sauvegarde": "Backup check", "Manifeste NAND privé": "Private NAND manifest",
    "Manifeste": "Manifest", "Contrôle NAND local": "Local NAND check",
    "Programme ARM compilé dans Home Assistant": "ARM program built in Home Assistant",
    "Contrôle du programme": "Program check", "Exécutable adb / adb.exe": "adb / adb.exe executable",
    "Journal privé": "Private operation record", "Journal": "Operation record",
    "Je confirme la variante compatible, ma présence avec récupération UART possible,": "I confirm the compatible variant, that I am on site with UART recovery available,",
    "l’alimentation stable et l’absence d’OTA / autre opération en parallèle.": "stable power, and no OTA / other operation running at the same time.",
    "Vérification requise": "Check required", "Compléter tous les champs et les confirmations.": "Complete all fields and confirmations.",
    "Mot de passe": "Password", "Les deux saisies sont différentes.": "The two passwords do not match.",
    "Confirmer cette opération uniquement": "Confirm this operation only", "Annuler": "Cancel", "Continuer": "Continue",
    "Sauvegardes sur cet ordinateur": "Backups on this computer",
    "Outils TPP06 sur cet ordinateur": "TPP06 tools on this computer",
    "Journal operation.json": "operation.json record",
    "Activer ADB Wi-Fi — référence après déblocage": "Enable Wi-Fi ADB — post-unlock reference",
    "J’accepte l’état APRÈS ADB comme référence, pas l’état usine. L’overlay remplace /data/app et /data/customize : sans dump antérieur, ces anciens fichiers ne pourront pas être récupérés. Sauvegarder après ADB avant les installations. Le paquet de retour ADB n’est pas une sauvegarde complète. Aucun reboot automatique.": "I accept the state AFTER ADB as the reference, not the factory state. The overlay replaces /data/app and /data/customize: without an earlier dump, those old files cannot be recovered. Back up after ADB before installing. The ADB rollback package is not a complete backup. No automatic reboot.",
    "Sauvegarder les partitions NAND après ADB": "Back up NAND partitions after ADB",
    "Copie privée contenant des secrets. Lecture de toutes les partitions exposées avec OOB et deux passes identiques. Seuls des fichiers temporaires en RAM sont créés, pas d’écriture NAND ni reboot. Un système qui écrit pendant la copie peut rendre celle-ci incohérente : aucune restauration complète certifiée ici. Ne lancer ni OTA ni autre opération ; l’acquisition peut être longue.": "Private copy containing secrets. Reads all exposed partitions with OOB and two matching passes. Only temporary RAM files are created; no NAND writes or reboot. A system writing during the copy may make it inconsistent: full restoration is NOT certified. Do not run OTA or another operation; acquisition may take a while.",
    "Installer SSH / Dropbear": "Install SSH / Dropbear",
    "Première installation SSH uniquement. Binaire reconnu, clé unique, vérification d’authentification. Ne jamais exposer le port 22 sur Internet. L’autostart est configuré après vérification de l’accès, sans reboot.": "First SSH installation only. Recognized binary, unique host key and authentication checks. Never expose port 22 to the Internet. Autostart is configured after access verification, without rebooting.",
    "Changer le mot de passe root": "Change root password", "Nouveau mot de passe": "New password", "Confirmer": "Confirm",
    "Ce firmware DES ne prend en compte que 8 caractères : choisir exactement 8 caractères ASCII aléatoires. Les fichiers d’authentification sont sauvegardés ; une console de secours reste ouverte pendant le test du nouvel accès.": "This DES firmware only uses 8 characters: choose exactly 8 random ASCII characters. Authentication files are backed up; a rescue console stays open while the new login is tested.",
    "Préparer ESPHome seul": "Prepare ESPHome-only mode", "Programme ARM compilé dans HA": "ARM program built in HA",
    "Nouveau panneau sous Tuya uniquement. Sauvegarde du lanceur et du Wi-Fi, puis remplacement du démarrage. Aucun retour automatique Tuya, aucun reboot ici. Ne pas couper l’alimentation pendant la préparation. Conserver la clé API propre à ce programme pour l’étape Vérifier.": "New panel running Tuya only. Backs up the launcher and Wi-Fi, then replaces startup. No automatic Tuya fallback and no reboot here. Do not disconnect power during preparation. Keep this program's API key for the Verify step.",
    "Remplacer uniquement le logo NAND": "Replace only the NAND boot logo",
    "Logo Home Assistant fourni / autre image compatible": "Included Home Assistant logo / other compatible image",
    "Écriture NAND distincte de l’OTA : double lecture de l’original et sauvegarde PC, puis relecture après écriture. Une coupure électrique reste dangereuse. Une seule tentative de restauration de l’original est prévue en cas d’échec. Aucun reboot.": "NAND write separate from OTA: two reads of the original and a PC backup, then read-back verification. Power loss remains dangerous. One attempt to restore the original is provided on failure. No reboot.",
    "Restaurer une opération sauvegardée": "Restore a saved operation",
    "Restauration ciblée d’un journal complet de ce panneau, PAS d’un dump NAND ni d’une archive quelconque. ESPHome : le lanceur d’origine prendra effet au prochain reboot manuel. SSH : le service sera arrêté et ses fichiers conservés.": "Targeted restoration from a completed record for this panel, NOT a NAND dump or arbitrary archive. ESPHome: the original launcher takes effect at the next manual reboot. SSH: the service is stopped and its files retained.",
    "Demander le premier démarrage ESPHome": "Request the first ESPHome boot",
    "Un redémarrage Linux sera demandé. Réseau momentanément coupé ; les charges peuvent changer d’état au démarrage. Pas de retour automatique vers Tuya. L’écriture de l’intention empêche d’envoyer deux fois le reboot.": "Requests a Linux reboot. Network access will briefly stop; connected loads may change state at startup. No automatic Tuya fallback. Recording the intent prevents sending the reboot twice.",
    "Vérifier le premier démarrage": "Verify the first boot", "Clé API chiffrée du programme": "Program's API encryption key",
    "Observation pendant cinq minutes maximum. Exige 120 secondes continues d’API chiffrée et de processus stable. Aucun reboot ni écriture de firmware.": "Observes for up to five minutes. Requires 120 continuous seconds of encrypted API and process stability. No reboot or firmware write.",
    "Réconcilier la transaction du logo": "Reconcile the logo transaction",
    "Lecture du résultat et comparaison des octets. Ne renvoie ni effacement, ni écriture NAND, ni reboot.": "Reads the result and compares bytes. Does not repeat erasure, NAND writes or reboot.",
    "Vérifier l’ancien mot de passe après restauration": "Verify the old password after restoration",
    "Mot de passe de cette sauvegarde": "Password for this backup",
    "Il ne sera pas enregistré. La restauration ne sera conservée que si le login fonctionne.": "It will not be saved. Restoration is retained only if login succeeds.",
    "Opération en cours": "Operation in progress",
    "Attendre la fin du contrôle ou de la sauvegarde avant de fermer.": "Wait for the check or backup to finish before closing.",
    "1 · Mot de passe d’origine": "1 · Original password",
    "Lecture locale via 8090 ; ne retrouve pas un mot de passe changé.": "Local read through 8090; does not recover a changed password.",
    "2 · Activer ADB Wi-Fi": "2 · Enable Wi-Fi ADB",
    "Paquet reconnu ; état après ADB accepté comme référence, avec confirmation explicite.": "Recognized package; post-ADB state explicitly accepted as the reference.",
    "3 · Sauvegarder": "3 · Back up",
    "Copie des partitions NAND après ADB ; cohérence et restauration restent à qualifier.": "Copies NAND partitions after ADB; consistency and restoration still need validation.",
    "4 · Restaurer une opération": "4 · Restore an operation",
    "Retour d’une opération journalisée, pas une restauration NAND globale.": "Rolls back a recorded operation, not the entire NAND.",
    "5 · Changer le mot de passe": "5 · Change password",
    "Nouvelle connexion vérifiée ; console de secours conservée.": "Verifies a new login while keeping a rescue console open.",
    "6 · Changer le logo": "6 · Change boot logo",
    "Image 512 Kio, outils reconnus, double sauvegarde et relecture NAND.": "512 KiB image, recognized tools, two backups and NAND read-back.",
    "7 · Installer SSH / Dropbear": "7 · Install SSH / Dropbear",
    "Clé hôte unique et vérifiée via ADB ; binaire noyau connu requis.": "Unique host key verified via ADB; requires a kernel-compatible binary.",
    "8 · Installer ESPHome seul": "8 · Install ESPHome-only mode",
    "Première installation uniquement, programme ARM compilé dans HA à fournir.": "First installation only; provide the ARM program built in HA.",
    "Logiciels nécessaires sur le PC": "Software needed on the PC",
    "Python — site officiel": "Python — official website",
    "Installer Python 3.11 ou plus récent avec Tcl/Tk. Ne pas choisir le paquet embeddable Windows.": "Install Python 3.11 or newer with Tcl/Tk. Do not choose the Windows embeddable package.",
    "ADB — Android Platform Tools": "ADB — Android Platform Tools",
    "Télécharger pour Windows ou Linux, extraire le ZIP entier, puis choisir platform-tools/adb.exe (Windows) ou adb (Linux). Android Studio n’est pas nécessaire.": "Download for Windows or Linux, extract the entire ZIP, then select platform-tools/adb.exe (Windows) or adb (Linux). Android Studio is not required.",
    "Installer les dépendances Python": "Install Python dependencies",
    "Sur Windows : fermer l’assistant, lancer Installer-dependances.cmd, puis relancer Assistant-TPP06.cmd. Sur Linux : sh Installer-dependances.sh. Le module elftools est fourni par pyelftools ; ne pas l’installer sur le panneau.": "Windows: close the assistant, run Installer-dependances.cmd, then reopen Assistant-TPP06.cmd. Linux: sh Installer-dependances.sh. pyelftools provides the elftools module; do not install it on the panel.",
    "Voir le logo Home Assistant fourni": "View the included Home Assistant logo",
    "Logo 320 × 480 sur fond noir, RGB565, 512 Kio. Réservé à la partition logo compatible ; jamais comme firmware OTA.": "320 × 480 logo on black, RGB565, 512 KiB. Only for the compatible logo partition; never use as OTA firmware.",
    "Comprendre les dossiers": "Understanding the folders",
    "Les deux dossiers sont sur cet ordinateur, pas dans Home Assistant ni dans le panneau.": "Both folders are on this computer, not in Home Assistant or on the panel.",
    "Sauvegardes : copies et journaux de récupération. Choisir un emplacement personnel, hors Git et hors dossier partagé/cloud. Le sous-dossier privé sera créé automatiquement.": "Backups: copies and recovery records. Choose a personal location outside Git and shared/cloud folders. The private subfolder is created automatically.",
    "Outils : fichiers techniques pour ADB, NAND ou SSH, différents du programme adb.exe. Le bouton Préparer les outils télécharge les fichiers disponibles et contrôle leur SHA-256, sans les exécuter.": "Tools: technical files for ADB, NAND or SSH, different from adb.exe. Prepare tools downloads available files and checks SHA-256 without running them.",
    "Préparer les outils": "Prepare tools", "Téléchargement des outils": "Tool download",
    "Télécharger les outils reconnus sur cet ordinateur ? Aucune connexion au panneau, aucune installation ni exécution. Les fichiers existants non reconnus seront conservés et refusés.": "Download recognized tools to this computer? No panel connection, installation or execution. Unrecognized existing files are preserved and refused.",
    "Vérifier les outils": "Check tools", "Outils manquants ou invalides": "Missing or invalid tools",
    "Préparer les outils ou choisir un dossier contenant les fichiers reconnus avant de continuer.": "Prepare tools or choose a folder containing the recognized files before continuing.",
    "prêt": "ready", "manquant": "missing", "empreinte incorrecte": "incorrect checksum",
    "Guide SSH / Dropbear": "SSH / Dropbear guide",
    "Dropbear compatible doit être préparé selon le guide SSH. Aucun binaire ARM arbitraire n’est accepté.": "Compatible Dropbear must be prepared following the SSH guide. Arbitrary ARM binaries are not accepted.",
    "Attendre la fin du téléchargement avant de continuer.": "Wait for the download to finish before continuing.",
    "Les dossiers proposés seront créés uniquement après confirmation. Aucun mot de passe n’y est prérempli.": "Suggested folders are created only after confirmation. No password is prefilled.",
    "Saisir l’adresse IPv4 du panneau, pas celle de Home Assistant.": "Enter the panel's IPv4 address, not Home Assistant's address.",
    "Adresse du panneau invalide.": "Invalid panel address.",
    "Opération non terminée. Vérifier les prérequis, les fichiers et l’accès. Aucun redémarrage automatique ; ne pas relancer à l’aveugle.": "Operation not completed. Check prerequisites, files and access. No automatic reboot; do not retry blindly.",
    "Fichier auxiliaire requis absent ou invalide. Voir le guide du paquet local.": "Required tool file is missing or invalid. See the local package guide.",
    "Fichier auxiliaire non reconnu pour ce noyau ; écriture refusée.": "Tool not recognized for this kernel; write refused.",
    "Empreinte SHA-256 différente : outil refusé, ne pas poursuivre.": "SHA-256 mismatch: tool refused; do not continue.",
    "Un outil existant est différent : conservé sans remplacement. Choisir un autre dossier.": "An existing tool differs: kept without replacement. Choose another folder.",
    "Dropbear compatible non distribué automatiquement. Consulter le guide SSH ; ne pas utiliser un binaire ARM quelconque.": "Compatible Dropbear is not automatically distributed. Read the SSH guide; do not use an arbitrary ARM binary.",
    "Dépendance Python absente. Lancer Installer-dependances sur le PC, puis rouvrir l’assistant.": "Missing Python dependency. Run Installer-dependances on this PC, then reopen the assistant.",
    "Certains diagnostics techniques restent dans leur langue d’origine ; les confirmations sont traduites.": "Some technical diagnostics remain in their original language; confirmations are translated.",
}


class Language:
    def __init__(self):
        self.code = "fr"
        self.widgets = []

    def text(self, text):
        if self.code == "fr" or not isinstance(text, str):
            return text
        if text in EN:
            return EN[text]
        # Composed paragraphs and operation titles retain exact catalogue entries.
        return "\n".join(EN.get(line, line) for line in text.split("\n"))

    def remember(self, widget, source):
        self.widgets.append((weakref.ref(widget), source))

    def refresh(self):
        alive = []
        for reference, source in self.widgets:
            widget = reference()
            if widget is not None and widget.winfo_exists():
                widget.configure(text=self.text(source))
                alive.append((reference, source))
        self.widgets = alive


class Widgets:
    def __init__(self, module, language):
        self.module, self.language = module, language

    def __getattr__(self, name):
        factory = getattr(self.module, name)
        def create(*args, **kwargs):
            source = kwargs.get("text")
            if source is not None:
                kwargs["text"] = self.language.text(source)
            widget = factory(*args, **kwargs)
            if source is not None:
                self.language.remember(widget, source)
            return widget
        return create


class Dialogs:
    def __init__(self, module, language):
        self.module, self.language = module, language

    def __getattr__(self, name):
        def call(*args, **kwargs):
            args = tuple(self.language.text(value) if index < 2 else value for index, value in enumerate(args))
            for key in ("title", "message"):
                if key in kwargs:
                    kwargs[key] = self.language.text(kwargs[key])
            if "filetypes" in kwargs:
                kwargs["filetypes"] = [(self.language.text(label), pattern) for label, pattern in kwargs["filetypes"]]
            return getattr(self.module, name)(*args, **kwargs)
        return call
