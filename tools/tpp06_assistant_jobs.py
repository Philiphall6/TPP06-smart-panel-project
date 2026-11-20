"""Explicit, journalled maintenance actions for the verified TPP06 variant.

Never called at import/startup. Files remain local; hardware validation of this
new orchestration is pending. A journal with an intent is never replayed.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import redirect_stdout
import hashlib
import io
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time

from tpp06_assistant_core import AssistantError, PROJECT_ROOT, device_report, parse_fields, inspect_firmware
from tpp06_assistant_transport import AssistantSession
from tpp06_tuya_cutter import sha256_file

BASE = "/data/tpp06-cutter"
LAUNCHER = "/etc/init.d/S99tuya-app"  # Write THROUGH the mounted overlay, never its upperdir.
PINS = {
    "dropbearmulti": "81bb1b18b527971fbf4690a62a13ba5a055e98feff51cab5d4711c0986b59bc1",
    "nandtool": "514d3d76e49b9e1ef65fb1a3b3ab838925f026632329a057e2e369a99ca67c78",
    "adb-overlay.tar.gz": "16bbafe333380458bcae1362d9775a4492abc8bd2209dd41469958e6e6802ed7",
    "adb-rollback.tar.gz": "e3e6e98af9ac4bf7cd46681872efa121a99c910be9e6069cbb45d57a07ba98b1",
}


def require(condition, message):
    if not condition:
        raise AssistantError(message)


def dependency(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        raise AssistantError("Dépendance Python absente. Lancer Installer-dependances sur le PC, puis rouvrir l’assistant.") from None


def private_directory(parent):
    parent = Path(parent).expanduser().resolve(strict=True)
    require(parent.is_dir() and parent != PROJECT_ROOT and PROJECT_ROOT not in parent.parents,
            "Choisir un dossier privé hors du dépôt Git.")
    require(not any((p / ".git").exists() for p in (parent, *parent.parents)), "Conserver les sauvegardes hors de tout dépôt Git.")
    directory = Path(tempfile.mkdtemp(prefix="tpp06-operation-", dir=parent))
    if os.name == "nt":
        # chmod alone does not make a Windows directory private.
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10)
        sid = re.findall(r"S-1-5-(?:[0-9]+-)*[0-9]+", result.stdout)
        require(result.returncode == 0 and len(sid) == 1, "Identité Windows non vérifiée.")
        result = subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r", f"*{sid[0]}:(OI)(CI)F"],
                                capture_output=True, timeout=10)
        require(result.returncode == 0, "Impossible de protéger le dossier Windows ; aucun secret enregistré.")
    else:
        directory.chmod(0o700)
    return directory


def private_file(path, data):
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), "Fichier existant refusé.")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def identity(session):
    report = device_report(session)
    require(report["plateforme_connue"], "Plateforme non reconnue. Aucun changement autorisé.")
    fields = parse_fields(session.run_root("echo ASSIST_MAC=$(cat /sys/class/net/wlan0/address)\n"
                                          "echo ASSIST_BOOT=$(cat /proc/sys/kernel/random/boot_id)").stdout, {"MAC", "BOOT"})
    require(re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", fields["MAC"]) and
            fields["MAC"] not in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff") and
            re.fullmatch(r"[0-9a-f-]{36}", fields["BOOT"]), "Identité Linux invalide.")
    return dict(fields, **report)


def pinned_artifact(directory, name):
    path = Path(directory) / name
    require(name in PINS and path.is_file() and not path.is_symlink() and path.stat().st_size < 32 * 1024 * 1024,
            "Fichier auxiliaire requis absent ou invalide. Voir le guide du paquet local.")
    require(sha256_file(path) == PINS[name], "Fichier auxiliaire non reconnu pour ce noyau ; écriture refusée.")
    return path


def api_key_valid(key):
    try:
        require(len(base64.b64decode(key, validate=True)) == 32, "Clé API ESPHome invalide.")
    except ValueError:
        raise AssistantError("Clé API ESPHome invalide.") from None


async def probe_api(host, key, mac):
    from aioesphomeapi import APIClient
    client = APIClient(host, 6053, None, noise_psk=key)
    try:
        async with asyncio.timeout(15):
            await client.connect(login=True, log_errors=False)
            info = await client.device_info()
            require(info.mac_address.lower() == mac and info.project_name == "philiphall6.tpp06",
                    "L’API n’appartient pas au panneau/projet attendu.")
            await client.list_entities_services()
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), 5)
        except Exception:
            pass


def ssh_probe(session, public, port=22, password=None):
    import paramiko
    from paramiko.ssh_exception import AuthenticationException
    require(re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]+", public), "Clé publique SSH invalide.")
    key = paramiko.Ed25519Key(data=base64.b64decode(public.split()[1], validate=True))
    client = paramiko.SSHClient()
    host = session.host if port == 22 else f"[{session.host}]:{port}"
    client.get_host_keys().add(host, "ssh-ed25519", key)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(session.host, port=port, username="root", password=password or session.password,
                       allow_agent=False, look_for_keys=False, timeout=10, auth_timeout=10, banner_timeout=10)
        _, stdout, _ = client.exec_command("id -u", timeout=10)
        require(stdout.read(64).strip() == b"0", "Session SSH non root.")
        return True
    except AuthenticationException:
        return False
    finally:
        client.close()


def installed_ssh_key(session):
    output = session.run_root("if netstat -lnt | grep -q ':22 '; then\n"
                              "test -x /data/tpp06-ssh/dropbearmulti && test -s /data/tpp06-ssh/host_ed25519 || exit 1\n"
                              "/data/tpp06-ssh/dropbearmulti dropbearkey -y -f /data/tpp06-ssh/host_ed25519\n"
                              "else echo ASSIST_NO_SSH=yes; fi").stdout
    if re.search(r"^ASSIST_NO_SSH=yes\r?$", output, re.M):
        return None
    keys = re.findall(r"^ssh-ed25519 ([A-Za-z0-9+/=]+)(?: [^\r\n]*)?\r?$", output, re.M)
    require(len(keys) == 1, "SSH actif mais clé hôte non reconnue ; changement de mot de passe refusé.")
    dependency("paramiko")
    return "ssh-ed25519 " + keys[0]


class Job:
    def __init__(self, session, parent, action):
        self.session = session
        self.directory = private_directory(parent)
        self.record = {"format": 2, "action": action, "job": secrets.token_hex(12),
                       "host": session.host, "phase": "created", "before": identity(session), "backups": {}}
        self.remote = "/data/tpp06-assistant/" + self.record["job"]
        self.save()
        # mkdir is an exclusive device-wide claim. A stale lock is NOT removed
        # automatically after an interrupted destructive operation.
        session.run_root("set -e\numask 077\ntest ! -e /tmp/tpp06-nand.lock\ntest ! -L /data/tpp06-assistant\nmkdir /data/tpp06-assistant.lock\n"
                         "test ! -e /tmp/tpp06-nand.lock\n"
                         f"mkdir -p /data/tpp06-assistant\nmkdir {self.remote}")
        self.record["phase"] = "locked"
        self.save()

    @classmethod
    def resume(cls, session, path, verify_identity=True):
        path = Path(path).resolve(strict=True)
        require(path.name == "operation.json" and path.stat().st_size < 65536, "Journal invalide.")
        record = json.loads(path.read_text(encoding="utf-8"))
        require(record.get("format") == 2 and re.fullmatch(r"[0-9a-f]{24}", record.get("job", "")), "Journal invalide.")
        if verify_identity:
            require(identity(session)["MAC"] == record["before"]["MAC"], "Ce journal concerne un autre panneau.")
        job = cls.__new__(cls)
        job.session, job.directory, job.record = session, path.parent, record
        job.remote = "/data/tpp06-assistant/" + record["job"]
        return job

    def save(self):
        temporary = self.directory / (".journal-" + secrets.token_hex(8))
        private_file(temporary, (json.dumps(self.record, indent=2) + "\n").encode())
        os.replace(temporary, self.directory / "operation.json")
        if os.name != "nt":
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def phase(self, value):
        self.record["phase"] = value
        self.save()

    def backup(self, name, remote, mode=0o600):
        require(re.fullmatch(r"[a-z0-9_-]+", name), "Nom de sauvegarde invalide.")
        # Remote paths are always supplied by program constants or a validated
        # logo partition number, never the contents of a journal or ZIP.
        require(re.fullmatch(r"/[A-Za-z0-9_./-]+", remote), "Chemin de sauvegarde invalide.")
        copy = self.remote + "/" + name + ".before"
        self.session.run_root(f"set -e\numask 077\ntest ! -e {copy}\ncp {remote} {copy}\nchmod 600 {copy}")
        local = self.directory / (name + ".before")
        self.session.download(copy, local)
        self.record["backups"][name] = {"sha256": sha256_file(local), "target": remote, "mode": mode}
        self.save()
        return local

    def upload(self, source, name):
        require(re.fullmatch(r"[a-z0-9_.-]+", name), "Nom de transfert invalide.")
        # Freeze user-selected files before starting the transfer.
        local = self.directory / ("payload-" + name)
        private_file(local, Path(source).read_bytes())
        target = self.remote + "/" + name
        self.session.upload(local, target)
        return target

    def text(self, text, name):
        local = self.directory / ("source-" + name)
        private_file(local, text.encode("utf-8"))
        return self.upload(local, name)

    def finish(self, phase="complete"):
        self.phase(phase)
        self.session.run_root("rmdir /data/tpp06-assistant.lock")
        return {"etat": phase, "journal_prive": str(self.directory / "operation.json"), "redemarrage_envoye": False}


def install_ssh(session, parent, artifacts):
    binary = pinned_artifact(artifacts, "dropbearmulti")
    dependency("paramiko")  # Dependency checked before any device change.
    job = Job(session, parent, "ssh")
    session.run_root("set -e\ntest ! -e /data/tpp06-ssh\n! netstat -lnt | grep -Eq ':(22|2222) '")
    # Existing startup preserved off-device, even though this operation only
    # stages/starts the service. ESPHome supervisor starts it on future boots.
    job.backup("launcher", LAUNCHER, 0o755)
    hook = None
    if not job.record["before"]["esphome_actif"]:
        rc = job.backup("rc-local", "/etc/init.d/rc.local", 0o755).read_text()
        anchor = "/etc/init.d/S99tuya-app start"
        require(rc.splitlines().count(anchor) == 1 and "TPP06_ASSISTANT_SSH" not in rc,
                "Démarrage Linux non reconnu ; insertion SSH refusée.")
        insertion = ("# TPP06_ASSISTANT_SSH: optional, failure must not block the panel\n"
                     "if [ -x /data/tpp06-ssh/service.sh ]; then\n"
                     "    /data/tpp06-ssh/service.sh start >/tmp/tpp06-ssh-start.log 2>&1 || true\nfi\n")
        patched = "\n".join(insertion + line if line == anchor else line for line in rc.splitlines()) + "\n"
        hook = job.text(patched, "rc-local.sh")
        job.record["rc_hook_sha256"] = sha256_file(job.directory / "payload-rc-local.sh")
        job.save()
    remote = job.upload(binary, "dropbearmulti")
    service = job.upload(PROJECT_ROOT / "device/dropbear/service.sh", "service.sh")
    session.run_root(f"sh -n {service}")
    job.phase("ssh-install-intent")
    session.run_root(f"set -e\numask 077\nmkdir /data/tpp06-ssh\ncp {remote} /data/tpp06-ssh/dropbearmulti\n"
                     f"cp {service} /data/tpp06-ssh/service.sh\nchmod 700 /data/tpp06-ssh/dropbearmulti /data/tpp06-ssh/service.sh")
    for name in ("dropbearmulti", "service.sh"):
        require(session._matches_local_checksum(job.directory / ("payload-" + name), session.remote_checksum("/data/tpp06-ssh/" + name)),
                "Copie SSH installée non conforme ; aucun exécutable lancé.")
    session.run_root("set -e\numask 077\n/data/tpp06-ssh/dropbearmulti dropbearkey -t ed25519 -f /data/tpp06-ssh/host_ed25519 >/dev/null\n"
                     "/data/tpp06-ssh/service.sh start")
    output = session.run_root("/data/tpp06-ssh/dropbearmulti dropbearkey -y -f /data/tpp06-ssh/host_ed25519").stdout
    keys = re.findall(r"^ssh-ed25519 ([A-Za-z0-9+/=]+)(?: [^\r\n]*)?\r?$", output, re.M)
    require(len(keys) == 1, "Clé hôte SSH ambiguë.")
    public = "ssh-ed25519 " + keys[0]
    job.record["public_key"] = public
    job.save()
    require(ssh_probe(session, public), "Authentification SSH refusée ; ADB conservé.")
    require(not ssh_probe(session, public, password=secrets.token_hex(16)), "Un mauvais mot de passe SSH a été accepté.")
    if hook:
        staged = "/etc/init.d/rc.local.assistant-" + job.record["job"]
        session.run_root(f"set -e\ntest ! -e {staged}\ncp {hook} {staged}\nchmod 755 {staged}\n"
                         f"sh -n {staged}\nsync\nmv {staged} /etc/init.d/rc.local\nsync")
        require(session._matches_local_checksum(job.directory / "payload-rc-local.sh", session.remote_checksum("/etc/init.d/rc.local")),
                "Insertion SSH au démarrage non vérifiée. Ne pas redémarrer.")
    result = job.finish()
    result["ssh"] = "Clé hôte épinglée via ADB ; authentification root vérifiée."
    result["demarrage"] = "Démarrage SSH configuré ; sa persistance après reboot reste à confirmer sur le panneau. Aucun reboot envoyé."
    return result


def change_password(session, parent, new_password):
    # Old DES on this firmware: never pretend a long phrase offers >8 chars.
    require(re.fullmatch(r"[!-~]{8}", new_password) is not None and new_password != session.password,
            "Ce firmware utilise DES : choisir exactement 8 caractères ASCII imprimables, différents du mot de passe actuel.")
    public = installed_ssh_key(session)
    job = Job(session, parent, "password")
    job.backup("passwd", "/etc/passwd", 0o644)
    job.backup("shadow", "/etc/shadow")
    job.phase("password-change-intent")
    with session.console() as rescue:
        try:
            rescue.passwd(new_password)
            test = AssistantSession(session.host, new_password, adb=session.adb)
            test.connect()
            require(identity(test)["MAC"] == job.record["before"]["MAC"], "Nouvel accès non confirmé.")
            if public:
                require(ssh_probe(test, public), "Nouvel accès SSH non confirmé.")
        except Exception:
            # Keep the original authenticated console; interrupt a possible
            # passwd prompt before restoring the two exact authentication files.
            rescue.send(b"\x03\n")
            rescue.expect(rb"(?:^|\r?\n)[^\r\n]*[#$]\s*$", 10)
            rescue.command(f"set -e\ncp {job.remote}/passwd.before /etc/passwd\n"
                           f"cp {job.remote}/shadow.before /etc/shadow\nchmod 644 /etc/passwd\nchmod 600 /etc/shadow\nsync")
            identity(session)
            job.finish("password-rolled-back")
            raise AssistantError("Nouveau mot de passe non validé ; ancien accès restauré et vérifié.") from None
    session.password = new_password
    result = job.finish()
    result["authentification"] = "Nouveau login ADB vérifié ; SSH également s’il était actif. Secret non enregistré dans le journal."
    return result


def prepare_esphome(session, parent, firmware):
    artifact = inspect_firmware(firmware)
    before = identity(session)
    require(not before["esphome_actif"] and before["application_tuya_active"],
            "Première installation seulement. Pour un panneau déjà sous ESPHome, utiliser l’OTA.")
    require(before["stockage_libre_mio"] * 1048576 > Path(firmware).stat().st_size * 2 + 2 * 1048576,
            "Place insuffisante pour staging, sauvegarde et réserve OTA. Aucun nettoyage automatique.")
    job = Job(session, parent, "esphome")
    # Refuse an existing selector, uncertain overlay or partial prior install.
    session.run_root(f"set -e\ntest ! -e {BASE}\ntest -w /etc/init.d\n"
                     f"! grep -Eq 'TPP06_' {LAUNCHER}\n"
                     "test -c /dev/fb0\ntest -c /dev/input/event1\ntest -c /dev/watchdog\n"
                     "test -x /usr/share/udhcpc/default.script\n"
                     "for tool in wpa_supplicant wpa_cli udhcpc nohup netstat md5sum; do command -v $tool >/dev/null; done\n"
                     "owner=no\nfor pid in $(pidof ak_watchdog); do\n"
                     "for fd in /proc/$pid/fd/*; do\n"
                     "[ \"$(readlink \"$fd\" || true)\" != /dev/watchdog ] || owner=yes\ndone\ndone\n"
                     "test \"$owner\" = yes")
    job.backup("launcher", LAUNCHER, 0o755)
    # The profile helper selects the running supplicant's actual file, not a template.
    profile_helper = (PROJECT_ROOT / "device/tpp06-network-profile.sh").read_text()
    session.run_root(profile_helper + f"\nset -e\numask 077\nprofile=$(tpp06_active_wifi_profile)\n"
                     f"cp \"$profile\" {job.remote}/wifi.before\n"
                     f"tpp06_profiles_equal \"$profile\" {job.remote}/wifi.before")
    session.download(job.remote + "/wifi.before", job.directory / "wifi.before")
    job.record["wifi_sha256"] = sha256_file(job.directory / "wifi.before")
    job.save()
    program = job.upload(firmware, "esphome")
    require(sha256_file(job.directory / "payload-esphome") == artifact["sha256"], "Le programme a changé pendant la préparation.")
    supervisor = job.upload(PROJECT_ROOT / "device/tpp06-multiboot.sh", "supervisor.sh")
    wifi_edit = job.upload(PROJECT_ROOT / "device/tpp06-wifi-edit.sh", "wifi-edit.sh")
    job.phase("esphome-prepare-intent")
    session.run_root(f"set -e\numask 077\nmkdir {BASE}\nmkdir {BASE}/esphome {BASE}/network\n"
                     f"mv {program} {BASE}/esphome/esphome\nchmod 700 {BASE}/esphome/esphome\n"
                     f"cp {job.remote}/launcher.before {BASE}/S99tuya-app.stock\nchmod 755 {BASE}/S99tuya-app.stock\n"
                     f"cp {job.remote}/wifi.before {BASE}/network/wpa_supplicant.conf\n"
                     f"cp {wifi_edit} {BASE}/tpp06-wifi-edit.sh\n"
                     f"sh -n {supervisor}\nsh -n {BASE}/tpp06-wifi-edit.sh\n"
                     f"echo isolated > {BASE}/network_mode\necho persistent > {BASE}/boot_policy\n"
                     f"echo yes > {BASE}/persistent_confirmed\necho 0 > {BASE}/failure_count\n"
                     f"echo esphome > {BASE}/mode\necho owner-confirmed > {BASE}/no_stock_fallback\nsync")
    job.record["program_sha256"] = sha256_file(job.directory / "payload-esphome")
    job.record["supervisor_sha256"] = sha256_file(job.directory / "payload-supervisor.sh")
    for source, target in (("payload-esphome", BASE + "/esphome/esphome"),
                           ("wifi.before", BASE + "/network/wpa_supplicant.conf"),
                           ("payload-wifi-edit.sh", BASE + "/tpp06-wifi-edit.sh")):
        require(session._matches_local_checksum(job.directory / source, session.remote_checksum(target)),
                "Un fichier préparé est différent. Le lanceur ne sera pas remplacé.")
    # Final commit is an atomic rename through /etc, after all other files exist.
    job.phase("launcher-commit-intent")
    stage = LAUNCHER + ".assistant-" + job.record["job"]
    session.run_root(f"set -e\ntest ! -e {stage}\ncp {supervisor} {stage}\nchmod 755 {stage}\n"
                     f"sh -n {stage}\nsync\nmv {stage} {LAUNCHER}\nsync")
    require(session._matches_local_checksum(job.directory / "payload-supervisor.sh", session.remote_checksum(LAUNCHER)),
            "Lanceur monté non conforme ; ne pas redémarrer.")
    result = job.finish("prepared-no-reboot")
    result["suite"] = "Prêt pour un premier démarrage ESPHome seul, à demander séparément. Pas de retour automatique Tuya."
    result["controle_local"] = "Le fonctionnement sans Wi-Fi ne sera confirmé qu’après validation physique séparée."
    return result


def reboot_prepared(session, journal):
    job = Job.resume(session, journal)
    require(job.record["action"] == "esphome" and job.record["phase"] == "prepared-no-reboot",
            "Ce journal n’autorise pas un nouveau redémarrage. Utiliser Vérifier / reprendre.")
    require(identity(session)["BOOT"] == job.record["before"]["BOOT"],
            "Le panneau a déjà redémarré depuis la préparation. Utiliser Vérifier, pas un autre reboot.")
    for source, target in (("payload-supervisor.sh", LAUNCHER), ("payload-esphome", BASE + "/esphome/esphome")):
        require(session._matches_local_checksum(job.directory / source, session.remote_checksum(target)),
                "Fichier installé modifié depuis la préparation ; reboot refusé.")
    job.phase("reboot-intent")  # Persist BEFORE send; even a lost reply cannot resend.
    session.run_root("nohup sh -c 'sleep 3; /sbin/reboot' >/tmp/tpp06-assistant-reboot.log 2>&1 </dev/null &")
    return {"etat": "un_redemarrage_demande", "suite": "Utiliser Vérifier / reprendre avec la clé API du programme.",
            "journal_prive": str(job.directory / "operation.json")}


def verify_boot(session, journal, key, progress=lambda message: None, *, timeout=300, stable_seconds=120):
    api_key_valid(key)
    dependency("aioesphomeapi")
    job = Job.resume(session, journal, verify_identity=False)
    require(job.record["action"] == "esphome" and job.record["phase"] in ("prepared-no-reboot", "reboot-intent", "verifying", "verified"),
            "Pas de premier démarrage à vérifier dans ce journal.")
    deadline, since, previous = time.monotonic() + timeout, None, None
    while time.monotonic() < deadline:
        try:
            session.connect()
            now = identity(session)
            require(now["MAC"] == job.record["before"]["MAC"] and now["BOOT"] != job.record["before"]["BOOT"],
                    "Identité ou nouveau démarrage non confirmé.")
            require(now["esphome_actif"] and not now["application_tuya_active"], "ESPHome seul non confirmé.")
            state = parse_fields(session.run_root(f"echo ASSIST_PID=$(pidof esphome)\n"
                                                  f"echo ASSIST_ACTIVE=$(cat {BASE}/active_mode)").stdout, {"PID", "ACTIVE"})
            require(state["PID"].isdigit() and state["ACTIVE"] == "esphome-healthy", "Superviseur pas encore sain.")
            asyncio.run(probe_api(session.host, key, now["MAC"]))
            sample = (now["BOOT"], state["PID"])
            if previous is not None:
                require(sample == previous, "Redémarrage pendant la validation.")
        except Exception:
            since, previous = None, None
            progress("Attente du réseau et de l’API chiffrée ; aucun nouveau reboot envoyé.")
        else:
            if since is None:
                since, previous = time.monotonic(), sample
            job.phase("verifying")
            if time.monotonic() - since >= stable_seconds:
                job.phase("verified")
                return {"etat": "ESPHome seul et API chiffrée vérifiés", "stabilite_secondes": stable_seconds,
                        "limite": "Affichage, tactile, relais, bip et démarrage hors Wi-Fi restent des essais physiques distincts."}
            progress("API chiffrée et processus stables ; observation en cours.")
        time.sleep(5)
    raise AssistantError("Validation non obtenue dans le délai. Aucun reboot ni retour Tuya envoyé. Conserver le journal et diagnostiquer.")


def activate_adb(host, parent, artifacts, original_dump=None, *, accept_post_adb_reference=False):
    """One 8090 upload, journal intent first. No automatic power cycle/retry.

An original dump is optional only with explicit acknowledgement that overwritten
pre-ADB customizations are not recoverable from the subsequent reference.
"""
    from tpp06_assistant_core import validate_host
    from tpp06_authkey_reader import read_configuration
    from tpp06_ota_uploader import upload
    host = validate_host(host)
    overlay = pinned_artifact(artifacts, "adb-overlay.tar.gz")
    rollback = pinned_artifact(artifacts, "adb-rollback.tar.gz")
    dump = Path(original_dump) if original_dump else None
    if dump is not None:
        require(dump.is_file() and not dump.is_symlink() and dump.stat().st_size in (128 * 1024 * 1024, 136 * 1024 * 1024),
                "La NAND originale fournie doit être un fichier 128/136 Mio de CE panneau.")
    else:
        require(accept_post_adb_reference is True,
                "Confirmer explicitement l’état de référence APRÈS ADB et la perte possible des personnalisations antérieures.")
    folder = private_directory(parent)
    # Keep a private verified local copy of both the dump and rollback artifact.
    copies = [(rollback, "adb-rollback.tar.gz"), (overlay, "adb-overlay.tar.gz")]
    if dump is not None:
        copies.insert(0, (dump, "original-nand.bin"))
    for source, name in copies:
        require(shutil.disk_usage(folder).free > source.stat().st_size + 16 * 1048576, "Place insuffisante sur le PC.")
        destination = folder / name
        with source.open("rb") as src:
            fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as dst:
                shutil.copyfileobj(src, dst)
                dst.flush()
                os.fsync(dst.fileno())
        require(sha256_file(source) == sha256_file(destination), "Copie locale de sauvegarde non conforme.")
    configuration = read_configuration(host, 8090, 5)
    # Store a fingerprint, never AUTHKEY itself. This is not hardware attestation.
    factory = str(configuration.get("auzkey") or configuration.get("authkey") or "")
    require(factory, "Réponse usine non reconnue.")
    record = {"format": 1, "action": "adb", "host": host, "phase": "upload-intent",
              "factory_fingerprint": hashlib.sha256(factory.encode()).hexdigest(),
              "reference_policy": "pre-adb-dump-supplied" if dump is not None else "post-adb-reference-required",
              "original_sha256": sha256_file(folder / "original-nand.bin") if dump is not None else None,
              "backup_complete": False}
    private_file(folder / "adb-operation.json", json.dumps(record, indent=2).encode())
    # Never call again automatically on an exception: 8090 may have accepted it.
    with redirect_stdout(io.StringIO()):
        upload(host, 8090, 20, folder / "adb-overlay.tar.gz")
    private_file(folder / "upload-accepted.txt", b"Accepted by 8090. Power cycle remains manual.\n")
    return {"etat": "Overlay accepté par 8090", "dossier_prive": str(folder),
            "suite": "Couper/remettre l’alimentation uniquement après ce message, contrôler ADB puis effectuer la sauvegarde NAND après ADB avant toute installation. Aucun reboot envoyé."}


def inspect_job(path):
    """Offline journal inspection without displaying its address or identity."""
    path = Path(path)
    require(path.name == "operation.json" and path.stat().st_size < 65536, "Journal invalide.")
    record = json.loads(path.read_text(encoding="utf-8"))
    require(record.get("format") == 2, "Format de journal inconnu.")
    for name, item in record["backups"].items():
        require(re.fullmatch(r"[a-z0-9_-]+", name), "Nom de sauvegarde invalide.")
        require(sha256_file(path.parent / (name + ".before")) == item["sha256"], "Sauvegarde locale modifiée.")
    return {"operation": record["action"], "phase": record["phase"], "sauvegardes_verifiees": len(record["backups"]),
            "limite": "Aucune commande renvoyée. Un intent interrompu exige un diagnostic, pas une réinstallation."}


def restore_operation(session, parent, journal, old_password=""):
    inspect_job(journal)
    old = Job.resume(session, journal)
    require(old.record["phase"] in ("complete", "prepared-no-reboot", "verified"),
            "Journal incomplet : état ambigu. Ne pas restaurer à l’aveugle.")
    action = old.record["action"]
    require(action in ("esphome", "password", "ssh"),
            "Pour le logo, sélectionner logo.before comme candidat dans Remplacer le logo. Aucun restore NAND global.")
    if action == "password":
        require(bool(old_password) and all(32 <= ord(c) < 127 for c in old_password), "Ancien mot de passe requis pour vérifier le retour.")
    public = installed_ssh_key(session) if action == "password" else None
    job = Job(session, parent, "restore-" + action)
    if action == "ssh":
        for name in ("dropbearmulti", "service.sh"):
            require(session._matches_local_checksum(old.directory / ("payload-" + name), session.remote_checksum("/data/tpp06-ssh/" + name)),
                    "Installation SSH différente ; arrêt automatique refusé.")
        if "rc-local" in old.record["backups"]:
            require(session._matches_local_checksum(old.directory / "payload-rc-local.sh", session.remote_checksum("/etc/init.d/rc.local")),
                    "rc.local a été modifié depuis l’installation SSH ; restauration automatique refusée.")
            job.backup("rc-local", "/etc/init.d/rc.local", 0o755)
            hook = job.upload(old.directory / "rc-local.before", "restore-rc-local.sh")
            staged = "/etc/init.d/rc.local.assistant-" + job.record["job"]
            job.phase("restore-ssh-intent")
            session.run_root(f"set -e\ntest ! -e {staged}\ncp {hook} {staged}\nchmod 755 {staged}\n"
                             f"sh -n {staged}\nsync\nmv {staged} /etc/init.d/rc.local\nsync")
        job.phase("restore-ssh-intent")
        session.run_root(f"set -e\n/data/tpp06-ssh/service.sh stop\nmv /data/tpp06-ssh {job.remote}/ssh-preserved\nsync")
        result = job.finish()
        result["restauration"] = "SSH arrêté et déplacé dans le dossier privé de l’opération sur le panneau ; fichiers récupérables. ADB conservé."
        return result
    names = ("launcher",) if action == "esphome" else ("passwd", "shadow")
    targets = {"launcher": (LAUNCHER, "755"), "passwd": ("/etc/passwd", "644"), "shadow": ("/etc/shadow", "600")}
    for name in names:
        target, mode = targets[name]
        job.backup(name, target, int(mode, 8))
        job.upload(old.directory / (name + ".before"), "restore-" + name)
    script = "set -e\n"
    for name in names:
        target, mode = targets[name]
        stage = target + ".assistant-" + job.record["job"]
        script += f"test ! -e {stage}\ncp {job.remote}/restore-{name} {stage}\nchmod {mode} {stage}\n"
        if name == "launcher":
            script += f"sh -n {stage}\n"
        script += f"sync\nmv {stage} {target}\nsync\n"
    job.phase("restore-intent")
    if action == "password":
        with session.console() as rescue:
            rescue.command(script)
            test = AssistantSession(session.host, old_password, adb=session.adb)
            try:
                test.connect()
                require(identity(test)["MAC"] == job.record["before"]["MAC"], "Ancien accès non vérifié.")
                if public:
                    require(ssh_probe(test, public), "Accès SSH restauré non vérifié.")
            except Exception:
                rescue.command(f"set -e\ncp {job.remote}/passwd.before /etc/passwd\ncp {job.remote}/shadow.before /etc/shadow\n"
                               "chmod 644 /etc/passwd\nchmod 600 /etc/shadow\nsync")
                identity(session)
                job.finish("restore-rolled-back")
                raise AssistantError("Restauration d’accès non validée ; accès précédent conservé.") from None
        session.password = old_password
    else:
        session.run_root(script)
        require(session._matches_local_checksum(old.directory / "launcher.before", session.remote_checksum(LAUNCHER)),
                "Restauration du lanceur non vérifiée. Ne pas redémarrer.")
    result = job.finish()
    result["restauration"] = "Fichiers sauvegardés restaurés et contrôlés. Aucun fichier ESPHome effacé. Aucun reboot envoyé."
    if action == "esphome":
        result["suite"] = "Le lanceur d’origine prendra effet au prochain redémarrage manuel ; le processus actuel n’a pas été arrêté."
    return result


def change_logo(session, parent, artifacts, image):
    tool = pinned_artifact(artifacts, "nandtool")
    from tpp06_logo import decode
    image = Path(image)
    require(image.is_file() and image.stat().st_size == 524288, "Image logo 512 Kio requise, pas un PNG ni un firmware.")
    decode(image.read_bytes(), "RGB565")
    require(identity(session)["stockage_libre_mio"] * 1048576 > tool.stat().st_size + 4 * image.stat().st_size + 2 * 1048576,
            "Place insuffisante pour les copies du logo, l’outil et la marge. Aucun effacement autorisé.")
    job = Job(session, parent, "logo")
    geometry = """set -e
test "$(cat /sys/class/mtd/mtd3/name)" = logo
test "$(cat /sys/class/mtd/mtd3/type)" = nand
test "$(cat /sys/class/mtd/mtd3/size)" = 524288
test "$(cat /sys/class/mtd/mtd3/erasesize)" = 131072
test "$(cat /sys/class/mtd/mtd3/writesize)" = 2048
test "$(cat /sys/class/mtd/mtd3/bad_blocks)" = 0
test "$(cat /sys/class/mtd/mtd3/ecc_failures)" = 0
test "$(md5sum /bin/busybox | awk '{print $1}')" = fedb2a75c046de80ed5413cfb129387c
/bin/busybox --list | grep -qx flash_eraseall
"""
    session.run_root(geometry)
    # Two independent reads, both copied off-device, before allowing erase.
    original = job.backup("logo", "/dev/mtd3ro")
    second = job.backup("logo-second", "/dev/mtd3ro")
    require(original.stat().st_size == 524288 and original.read_bytes() == second.read_bytes(), "Lectures originales différentes ; aucun effacement.")
    candidate = job.upload(image, "candidate.bin")
    nandtool = job.upload(tool, "nandtool")
    session.run_root(f"chmod 700 {nandtool}\n{nandtool} --list | grep -qx nanddump\n{nandtool} --list | grep -qx nandwrite")
    original_md5 = hashlib.md5(original.read_bytes()).hexdigest()
    candidate_md5 = hashlib.md5((job.directory / "payload-candidate.bin").read_bytes()).hexdigest()
    script = (PROJECT_ROOT / "device/tpp06-assistant-logo.sh").read_text()
    script = script.replace("@STAGE@", job.remote).replace("@ORIGINAL@", original_md5).replace("@CANDIDATE@", candidate_md5)
    remote_script = job.text(script, "logo-write.sh")
    session.run_root(f"sh -n {remote_script}")
    job.phase("logo-write-intent")
    # Independent child transaction survives a PC/ADB disconnect. One claim
    # prevents replay. A failure attempts the known original once, never reboot.
    session.run_root(f"nohup sh {remote_script} >{job.remote}/logo-private.log 2>&1 </dev/null &")
    for _ in range(45):
        result = session.run_root(f"test ! -f {job.remote}/logo-result || cat {job.remote}/logo-result").stdout
        if re.search(r"^VERIFIED_CANDIDATE\r?$", result, re.M):
            session.download("/dev/mtd3ro", job.directory / "logo-readback.bin")
            require((job.directory / "logo-readback.bin").read_bytes() == (job.directory / "payload-candidate.bin").read_bytes(),
                    "Relecture locale différente. Ne pas redémarrer.")
            return job.finish()
        if re.search(r"^(RESTORED_ORIGINAL|RECOVERY_REQUIRED|PREFLIGHT_FAILED)\r?$", result, re.M):
            raise AssistantError("Logo non confirmé ; consulter le journal privé et conserver l’alimentation. Aucun reboot envoyé.")
        time.sleep(2)
    raise AssistantError("Transaction logo non réconciliée. Ne pas renvoyer l’écriture, ne pas redémarrer.")


def reconcile_logo(session, journal):
    job = Job.resume(session, journal)
    require(job.record["action"] == "logo" and job.record["phase"] == "logo-write-intent",
            "Aucune transaction logo interrompue à réconcilier.")
    result = session.run_root(f"test ! -f {job.remote}/logo-result || cat {job.remote}/logo-result").stdout
    matches = re.findall(r"^(VERIFIED_CANDIDATE|RESTORED_ORIGINAL|RECOVERY_REQUIRED|PREFLIGHT_FAILED)\r?$", result, re.M)
    require(len(matches) == 1, "Résultat absent ou ambigu. Ne pas réécrire ni redémarrer.")
    status = matches[0]
    require(status != "RECOVERY_REQUIRED", "La restauration du logo a échoué. Conserver l’alimentation et utiliser la récupération locale.")
    expected = job.directory / ("payload-candidate.bin" if status == "VERIFIED_CANDIDATE" else "logo.before")
    require(session._matches_local_checksum(expected, session.remote_checksum("/dev/mtd3ro")),
            "Logo réel différent du résultat annoncé. Aucun nouveau flash autorisé.")
    return job.finish("complete" if status == "VERIFIED_CANDIDATE" else "logo-original-preserved")
