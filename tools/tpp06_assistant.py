#!/usr/bin/env python3
"""TPP06 desktop assistant. Every mutation requires a separate explicit form."""
from __future__ import annotations

import json
from pathlib import Path
import queue
import sys
import threading
import webbrowser

import tpp06_assistant_core as core


class Assistant:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        self.events = queue.Queue()
        self.busy = False
        self.buttons = []
        self.inputs = []
        self.host = tk.StringVar()
        self.password = tk.StringVar()
        self.adb = tk.StringVar(value="adb")
        self.status = tk.StringVar(value="Prêt — aucune connexion automatique")
        root.title("Assistant TPP06 · Installation et maintenance")
        root.geometry("960x760")
        root.minsize(780, 640)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", padding=(10, 8))
        style.configure("Title.TLabel", font=("TkDefaultFont", 20, "bold"))
        style.configure("Note.TLabel", foreground="#4b5563")

        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Votre panneau, étape par étape", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Expérimental · Aucune opération au lancement · Sauvegardes privées et confirmations avant écriture",
                  style="Note.TLabel").pack(anchor="w", pady=(6, 14))
        connection = ttk.LabelFrame(outer, text="Votre appareil — données conservées uniquement en mémoire", padding=10)
        connection.pack(fill="x")
        ttk.Label(connection, text="IP du panneau").grid(row=0, column=0, sticky="w")
        host_entry = ttk.Entry(connection, textvariable=self.host, width=20)
        host_entry.grid(row=0, column=1, padx=8)
        self.inputs.append(host_entry)
        ttk.Label(connection, text="Mot de passe root").grid(row=0, column=2, sticky="w")
        self.password_entry = ttk.Entry(connection, textvariable=self.password, show="•", width=24)
        self.password_entry.grid(row=0, column=3, padx=8)
        self.inputs.append(self.password_entry)
        self.visible = tk.BooleanVar()
        ttk.Checkbutton(connection, text="Afficher", variable=self.visible,
                        command=self.toggle_password).grid(row=0, column=4)
        ttk.Label(connection, text="Outil ADB").grid(row=1, column=0, sticky="w", pady=(10, 0))
        adb_entry = ttk.Entry(connection, textvariable=self.adb, width=46)
        adb_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=(10, 0))
        self.inputs.append(adb_entry)
        self.button(connection, "Choisir…", self.choose_adb).grid(row=1, column=4, pady=(10, 0))

        tabs = ttk.Notebook(outer, height=300)
        access = self.scroll_page(tabs, "1. Accès et diagnostic")
        files = self.scroll_page(tabs, "2. Sauvegarde et fichiers")
        installation = self.scroll_page(tabs, "3. Installer / administrer")
        recovery = self.scroll_page(tabs, "4. Reprendre / vérifier")

        self.row(access, "Vérifier cet ordinateur", "Python, ADB et dépendances ; aucun contact avec le panneau.", self.pc)
        self.row(access, "Vérifier les accès réseau", "Teste uniquement les cinq ports connus sur l’IP saisie.", self.ports)
        self.row(access, "Lire le mot de passe d’origine", "Demande confirmation ; le mot de passe reste masqué et n’est pas enregistré.", self.read_password)
        self.row(access, "Lire l’état Linux", "ADB déjà activé et mot de passe root requis. Ne touche pas aux relais.", self.diagnose)
        self.row(files, "Sauvegarde NAND après ADB", "Toutes les partitions exposées, données + OOB, deux lectures. Pas de restauration NAND automatique.", lambda: self.operation("nand"))
        self.row(files, "Contrôler une copie NAND", "Empreintes et tailles sur le PC ; ne certifie pas une restauration.", self.nand_archive)
        self.row(files, "Sauvegarde partielle Cutter", "Archive Cutter privée et contrôlée, PAS une image NAND complète.", self.backup)
        self.row(files, "Contrôler une sauvegarde", "Contrôle local du contenu et de la fiche SHA-256, sans extraction ni restauration.", self.archive)
        self.row(files, "Contrôler un programme ESPHome", "Vérifie le format ARMv5 sans l’exécuter. Ne compile et n’installe rien.", self.firmware)
        self.row(files, "Ouvrir le guide de l’assistant", "Fonctions disponibles, limites et prochaines étapes.",
                 lambda: self.guide("21-assistant-ordinateur.md"))

        ttk.Label(installation, text="Installation accompagnée — variante TPP06 / AK3761E uniquement", wraplength=800,
                  font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(installation, text="ADB → sauvegarde → SSH / mot de passe → préparer ESPHome → démarrer → vérifier.\n"
                  "Le logo est facultatif et distinct. Aucun choix de dual boot ; aucun nettoyage destructif.", wraplength=800).pack(anchor="w", pady=8)
        callbacks = (self.read_password, lambda: self.operation("adb"), lambda: self.operation("nand"),
                     lambda: self.operation("restore"), lambda: self.operation("password"),
                     lambda: self.operation("logo"), lambda: self.operation("ssh"), lambda: self.operation("esphome"))
        for action, callback in zip(core.ACTIONS, callbacks):
            self.row(installation, action.title, action.detail, callback)
        self.row(recovery, "Démarrer ESPHome préparé", "Un seul reboot, journal préalable ; refus si le démarrage a déjà été demandé.", lambda: self.operation("reboot"))
        self.row(recovery, "Vérifier / reprendre le premier boot", "Contrôle MAC, processus et API chiffrée pendant 120 secondes ; ne renvoie aucun reboot.", lambda: self.operation("verify"))
        self.row(recovery, "Réconcilier une écriture du logo", "Après une déconnexion : lire le résultat et comparer la NAND, jamais réécrire.", lambda: self.operation("logo-status"))
        self.row(recovery, "Inspecter un journal privé", "Vérifier les sauvegardes et afficher la phase sans relancer l’opération.", self.inspect_journal)
        self.row(recovery, "Guide et limites de récupération", "Si un intent reste ambigu, ne pas supprimer le verrou ni rejouer une installation.", lambda: self.guide("21-assistant-ordinateur.md"))

        log_frame = ttk.Frame(outer)
        log_frame.pack(side="bottom", fill="x")
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled", font=("TkFixedFont", 10))
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)
        ttk.Label(outer, textvariable=self.status).pack(side="bottom", anchor="w", pady=(0, 5))
        tabs.pack(fill="both", expand=True, pady=12)
        self.append("Aucune adresse, aucun secret prérempli. Aucun fichier de journal automatique.")
        self.timer = root.after(100, self.poll)
        self.host.trace_add("write", lambda *_: self.password.set(""))

    def scroll_page(self, tabs, title):
        shell = self.ttk.Frame(tabs)
        tabs.add(shell, text=title)
        canvas = self.tk.Canvas(shell, highlightthickness=0, height=300)
        scrollbar = self.ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        content = self.ttk.Frame(canvas, padding=12)
        window = canvas.create_window(0, 0, anchor="nw", window=content)
        content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        def wheel(event):
            # Bind at the toplevel but act only while the pointer is in this
            # page. No bind_all that steals scrolling from password dialogs.
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            while widget is not None:
                if widget is shell:
                    step = -1 if getattr(event, "num", 0) == 4 or event.delta > 0 else 1
                    canvas.yview_scroll(step * 3, "units")
                    break
                widget = getattr(widget, "master", None)
        for event_name in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind(event_name, wheel, add="+")
        return content

    def button(self, parent, text, command, enabled=True):
        button = self.ttk.Button(parent, text=text, command=command)
        button.configure(state="normal" if enabled else "disabled")
        self.buttons.append((button, enabled))
        return button

    def row(self, parent, title, detail, command, enabled=True):
        frame = self.ttk.Frame(parent)
        frame.pack(fill="x", pady=8)
        self.button(frame, title, command, enabled).pack(anchor="w")
        self.ttk.Label(frame, text=detail, wraplength=800, style="Note.TLabel").pack(anchor="w", pady=(4, 0))

    def toggle_password(self):
        self.password_entry.configure(show="" if self.visible.get() else "•")

    def append(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self, title, function, kind="report"):
        if self.busy:
            return
        self.busy = True
        self.status.set(title + "… Ne pas lancer d’OTA en parallèle.")
        for button, _ in self.buttons:
            button.configure(state="disabled")
        for entry in self.inputs:
            entry.configure(state="disabled")

        def worker():
            try:
                result = function()
                self.events.put((kind, title, result))
            except Exception as error:
                self.events.put(("error", title, core.safe_failure(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            kind, title, value = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            if kind == "progress":
                self.status.set(value)
                self.timer = self.root.after(100, self.poll)
                return
            self.busy = False
            for button, enabled in self.buttons:
                button.configure(state="normal" if enabled else "disabled")
            for entry in self.inputs:
                entry.configure(state="normal")
            self.status.set(title + (" — non terminé" if kind == "error" else " — terminé"))
            if kind == "password":
                self.visible.set(False)
                self.toggle_password()
                self.password.set(value)
                self.append("Mot de passe d’origine reçu et masqué. Il peut ne plus être valable s’il a été changé.")
            else:
                if kind == "password_changed":
                    value, new_password = value
                    self.password.set(new_password)
                    self.visible.set(False)
                    self.toggle_password()
                self.append(title + "\n" + (value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)))
        self.timer = self.root.after(100, self.poll)

    def values(self):
        # Snapshot Tk values in the main thread, never from a worker.
        return self.host.get(), self.password.get(), self.adb.get()

    def pc(self):
        adb = self.adb.get()
        self.start("Contrôle de l’ordinateur", lambda: core.check_pc(adb))

    def ports(self):
        host, _, adb = self.values()
        self.start("Accès réseau", lambda: core.probe_ports(host, adb))

    def read_password(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Lecture du mot de passe d’origine", "Uniquement sur votre propre panneau.\n\n"
                "Cette lecture entre dans le mode de test temporaire du service 8090. Elle ne change pas le mot de passe, "
                "n’écrit pas le firmware et ne redémarre pas l’appareil.\n\nContinuer ?", parent=self.root):
            return
        host = self.host.get()
        self.start("Lecture du mot de passe", lambda: core.factory_password(host), "password")

    def diagnose(self):
        values = self.values()
        self.start("Diagnostic Linux", lambda: core.device_report(core.connect_adb(*values)))

    def backup(self):
        from tkinter import filedialog, messagebox
        parent = filedialog.askdirectory(title="Dossier privé hors du dépôt Git", parent=self.root)
        if not parent:
            return
        if not messagebox.askyesno("Sauvegarde partielle — pas une NAND complète", "La sauvegarde peut contenir des secrets. "
                "Elle ne couvre pas tous les réglages Wi-Fi/SSH.\n\nUne archive temporaire sera créée puis supprimée dans /tmp "
                "du panneau après son téléchargement. Aucun reboot, relais ou fichier de démarrage n’est modifié. "
                "L’opération peut durer plusieurs minutes. Garder la fenêtre ouverte.\n\nContinuer ?", parent=self.root):
            return
        values = self.values()
        self.start("Sauvegarde du panneau", lambda: core.backup_panel(core.connect_adb(*values), parent))

    def archive(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Archive Cutter", filetypes=[("Archive gzip", "*.tar.gz"), ("Tous", "*")], parent=self.root)
        if path:
            self.start("Contrôle de sauvegarde", lambda: core.inspect_backup(path))

    def nand_archive(self):
        from tkinter import filedialog
        from tpp06_assistant_nand import inspect_reference
        path = filedialog.askopenfilename(title="Manifeste NAND privé", filetypes=[("Manifeste", "nand-manifest.json")], parent=self.root)
        if path:
            self.start("Contrôle NAND local", lambda: inspect_reference(path))

    def firmware(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Programme ARM compilé dans Home Assistant", parent=self.root)
        if path:
            self.start("Contrôle du programme", lambda: core.inspect_firmware(path))

    def choose_adb(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Exécutable adb / adb.exe", parent=self.root)
        if path:
            self.adb.set(path)

    def guide(self, name):
        path = core.PROJECT_ROOT / "docs" / "fr" / name
        # Local documentation: no automatic web fetch or upload.
        webbrowser.open(path.as_uri())

    def inspect_journal(self):
        from tkinter import filedialog
        from tpp06_assistant_jobs import inspect_job
        path = filedialog.askopenfilename(title="operation.json", filetypes=[("Journal", "*.json")], parent=self.root)
        if path:
            self.start("Journal privé", lambda: inspect_job(path))

    def operation_form(self, title, fields, warning, mutating=True):
        from tkinter import filedialog, messagebox
        window = self.tk.Toplevel(self.root)
        window.title(title)
        window.transient(self.root)
        window.grab_set()
        frame = self.ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        self.ttk.Label(frame, text=title, font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        self.ttk.Label(frame, text=warning, wraplength=660).grid(row=1, column=0, columnspan=3, pady=12, sticky="w")
        values = {}
        for row, (key, label, kind) in enumerate(fields, start=2):
            value = self.tk.StringVar()
            values[key] = value
            self.ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            self.ttk.Entry(frame, textvariable=value, width=44, show="•" if kind == "secret" else "").grid(row=row, column=1, padx=6, sticky="ew")
            if kind in ("file", "dir"):
                def browse(v=value, k=kind):
                    path = filedialog.askdirectory(parent=window) if k == "dir" else filedialog.askopenfilename(parent=window)
                    if path:
                        v.set(path)
                self.ttk.Button(frame, text="Choisir…", command=browse).grid(row=row, column=2)
        row = len(fields) + 2
        confirmation = self.tk.BooleanVar()
        if mutating:
            self.ttk.Checkbutton(frame, text="Je confirme la variante compatible, ma présence avec récupération UART possible,\n"
                                "l’alimentation stable et l’absence d’OTA / autre opération en parallèle.", variable=confirmation).grid(
                                    row=row, column=0, columnspan=3, sticky="w", pady=10)
            row += 1
        result = []

        def accept():
            data = {key: value.get() for key, value in values.items()}
            if any(not value for value in data.values()) or (mutating and not confirmation.get()):
                messagebox.showerror("Vérification requise", "Compléter tous les champs et les confirmations.", parent=window)
                return
            if "repeat" in data and data["new_password"] != data["repeat"]:
                messagebox.showerror("Mot de passe", "Les deux saisies sont différentes.", parent=window)
                return
            if mutating and not messagebox.askyesno("Confirmer cette opération uniquement", title + "\n\n" + warning, parent=window):
                return
            result.append(data)
            window.destroy()
        self.ttk.Button(frame, text="Annuler", command=window.destroy).grid(row=row, column=1, sticky="e", pady=8)
        self.ttk.Button(frame, text="Continuer", command=accept).grid(row=row, column=2, pady=8)
        self.root.wait_window(window)
        return result[0] if result else None

    def operation(self, action):
        import tpp06_assistant_jobs as jobs
        workspace = ("parent", "Dossier privé des opérations", "dir")
        artifacts = ("artifacts", "Dossier des outils compatibles", "dir")
        journal = ("journal", "Journal operation.json", "file")
        forms = {
            "adb": ("Activer ADB Wi-Fi — référence après déblocage", [workspace, artifacts],
                    "J’accepte l’état APRÈS ADB comme référence, pas l’état usine. L’overlay remplace /data/app et /data/customize : "
                    "sans dump antérieur, ces anciens fichiers ne pourront pas être récupérés. Sauvegarder après ADB avant les installations. "
                    "Le paquet de retour ADB n’est pas une sauvegarde complète. Aucun reboot automatique."),
            "nand": ("Sauvegarder les partitions NAND après ADB", [workspace, artifacts],
                     "Copie privée contenant des secrets. Lecture de toutes les partitions exposées avec OOB et deux passes identiques. "
                     "Seuls des fichiers temporaires en RAM sont créés, pas d’écriture NAND ni reboot. "
                     "Un système qui écrit pendant la copie peut rendre celle-ci incohérente : aucune restauration complète certifiée ici. "
                     "Ne lancer ni OTA ni autre opération ; l’acquisition peut être longue."),
            "ssh": ("Installer SSH / Dropbear", [workspace, artifacts],
                    "Première installation SSH uniquement. Binaire reconnu, clé unique, vérification d’authentification. "
                    "Ne jamais exposer le port 22 sur Internet. L’autostart est configuré après vérification de l’accès, sans reboot."),
            "password": ("Changer le mot de passe root", [workspace, ("new_password", "Nouveau mot de passe", "secret"), ("repeat", "Confirmer", "secret")],
                         "Ce firmware DES ne prend en compte que 8 caractères : choisir exactement 8 caractères ASCII aléatoires. "
                         "Les fichiers d’authentification sont sauvegardés ; une console de secours reste ouverte pendant le test du nouvel accès."),
            "esphome": ("Préparer ESPHome seul", [workspace, ("firmware", "Programme ARM compilé dans HA", "file")],
                        "Nouveau panneau sous Tuya uniquement. Sauvegarde du lanceur et du Wi-Fi, puis remplacement du démarrage. "
                        "Aucun retour automatique Tuya, aucun reboot ici. Ne pas couper l’alimentation pendant la préparation. "
                        "Conserver la clé API propre à ce programme pour l’étape Vérifier."),
            "logo": ("Remplacer uniquement le logo NAND", [workspace, artifacts, ("image", "Image RGB565 512 Kio / logo.before", "file")],
                     "Écriture NAND distincte de l’OTA : double lecture de l’original et sauvegarde PC, puis relecture après écriture. "
                     "Une coupure électrique reste dangereuse. Une seule tentative de restauration de l’original est prévue en cas d’échec. Aucun reboot."),
            "restore": ("Restaurer une opération sauvegardée", [workspace, journal],
                        "Restauration ciblée d’un journal complet de ce panneau, PAS d’un dump NAND ni d’une archive quelconque. "
                        "ESPHome : le lanceur d’origine prendra effet au prochain reboot manuel. SSH : le service sera arrêté et ses fichiers conservés."),
            "reboot": ("Demander le premier démarrage ESPHome", [journal],
                       "Un redémarrage Linux sera demandé. Réseau momentanément coupé ; les charges peuvent changer d’état au démarrage. "
                       "Pas de retour automatique vers Tuya. L’écriture de l’intention empêche d’envoyer deux fois le reboot."),
            "verify": ("Vérifier le premier démarrage", [journal, ("key", "Clé API chiffrée du programme", "secret")],
                       "Observation pendant cinq minutes maximum. Exige 120 secondes continues d’API chiffrée et de processus stable. Aucun reboot ni écriture de firmware."),
            "logo-status": ("Réconcilier la transaction du logo", [journal],
                            "Lecture du résultat et comparaison des octets. Ne renvoie ni effacement, ni écriture NAND, ni reboot."),
        }
        title, fields, warning = forms[action]
        data = self.operation_form(title, fields, warning, mutating=action not in ("verify", "logo-status"))
        if data is None:
            return
        if action == "restore":
            try:
                report = jobs.inspect_job(data["journal"])
            except Exception as error:
                self.append(core.safe_failure(error))
                return
            if report["operation"] == "password":
                extra = self.operation_form("Vérifier l’ancien mot de passe après restauration",
                    [("old_password", "Mot de passe de cette sauvegarde", "secret")],
                    "Il ne sera pas enregistré. La restauration ne sera conservée que si le login fonctionne.", mutating=False)
                if extra is None:
                    return
                data.update(extra)
        host, password, adb = self.values()

        def run():
            if action == "adb":
                return jobs.activate_adb(host, data["parent"], data["artifacts"], accept_post_adb_reference=True)
            if action == "verify":
                session = jobs.AssistantSession(core.validate_host(host), password, adb=adb)
                return jobs.verify_boot(session, data["journal"], data["key"],
                                       lambda message: self.events.put(("progress", title, message)))
            session = core.connect_adb(host, password, adb)
            if action == "nand":
                from tpp06_assistant_nand import capture_reference
                return capture_reference(session, data["parent"], data["artifacts"],
                                         lambda message: self.events.put(("progress", title, message)))
            if action == "password":
                return jobs.change_password(session, data["parent"], data["new_password"]), data["new_password"]
            if action == "ssh":
                return jobs.install_ssh(session, data["parent"], data["artifacts"])
            if action == "esphome":
                return jobs.prepare_esphome(session, data["parent"], data["firmware"])
            if action == "reboot":
                return jobs.reboot_prepared(session, data["journal"])
            if action == "logo":
                return jobs.change_logo(session, data["parent"], data["artifacts"], data["image"])
            if action == "logo-status":
                return jobs.reconcile_logo(session, data["journal"])
            if action == "restore":
                report = jobs.restore_operation(session, data["parent"], data["journal"], data.get("old_password", ""))
                return (report, session.password) if "old_password" in data else report
        kind = "password_changed" if action == "password" or "old_password" in data else "report"
        self.start(title, run, kind)

    def close(self):
        from tkinter import messagebox
        if self.busy:
            messagebox.showinfo("Opération en cours", "Attendre la fin du contrôle ou de la sauvegarde avant de fermer.", parent=self.root)
            return
        self.password.set("")
        self.root.after_cancel(self.timer)
        self.root.destroy()


def main():
    if sys.version_info < (3, 11):
        print("Python 3.11 ou plus récent est requis.")
        return 1
    try:
        import tkinter as tk
    except ImportError:
        print("Tkinter manque. Sur le PC Mint : installer python3-tk. Sous Windows : utiliser Python avec Tcl/Tk.")
        return 1
    try:
        root = tk.Tk()
    except tk.TclError:
        print("Ouvrir cet assistant depuis la session graphique du PC, pas une console SSH sans affichage.")
        return 1
    Assistant(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
