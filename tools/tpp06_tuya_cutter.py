#!/usr/bin/env python3
"""Reversible installer and recovery tool for an owner-operated TPP06 panel.

The tool deliberately keeps the stock Tuya files. A permanent cut-over only
overrides S99tuya-app in the writable overlay and can therefore be reverted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import select
import shlex
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import NoReturn

from tpp06_authkey_reader import read_configuration
from tpp06_ota_uploader import upload as upload_adb_overlay


DEFAULT_ADB_PORT = 5555
DEFAULT_PRODUCT_TEST_PORT = 8090
DEFAULT_TRANSFER_PORT = 9001
REMOTE_BASE = "/data/tpp06-cutter"
REMOTE_TEST_BASE = "/tmp/tpp06-cutter"
TUYA_PROCESS = "voice_control_ak3760e"
SUPPORTED_ENGINES = ("openhasp", "esphome")
MODE_NAMES = ("tuya", *SUPPORTED_ENGINES)


class CutterError(RuntimeError):
    """A recoverable, user-facing cutter error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def derive_root_password(configuration: dict[str, object]) -> str:
    authkey = str(configuration.get("auzkey") or configuration.get("authkey") or "")
    if not authkey:
        raise CutterError("La réponse du panneau ne contient pas d'AUTHKEY.")
    return hashlib.md5(authkey.encode("utf-8")).hexdigest()[-8:]


def require_file(path: str | Path, label: str) -> Path:
    result = Path(path).expanduser().resolve()
    if not result.is_file():
        raise CutterError(f"{label} introuvable : {result}")
    return result


def confirm_exact(prompt: str, expected: str, assume_yes: bool) -> None:
    if assume_yes:
        return
    print(prompt)
    answer = input(f"Tapez {expected} pour continuer : ").strip()
    if answer != expected:
        raise CutterError("Opération annulée.")


def validate_backup_archive(path: Path) -> None:
    allowed_prefixes = (
        PurePosixPath("data/app"),
        PurePosixPath("data/customize"),
        PurePosixPath("data/etc/init.d"),
        PurePosixPath("data/tpp06-cutter"),
    )
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise CutterError("L'archive de sauvegarde est vide.")
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts:
                    raise CutterError(f"Chemin dangereux dans l'archive : {member.name}")
                if member.issym() or member.islnk():
                    raise CutterError(f"Lien refusé dans l'archive : {member.name}")
                if not any(name == prefix or prefix in name.parents for prefix in allowed_prefixes):
                    raise CutterError(f"Chemin hors périmètre dans l'archive : {member.name}")
    except (tarfile.TarError, OSError) as error:
        raise CutterError(f"Archive de sauvegarde invalide : {error}") from error


@dataclass
class CommandResult:
    stdout: str
    returncode: int


class PanelSession:
    def __init__(
        self,
        host: str,
        password: str,
        adb_port: int = DEFAULT_ADB_PORT,
        adb: str = "adb",
    ) -> None:
        self.host = host
        self.password = password
        self.adb_port = adb_port
        self.serial = f"{host}:{adb_port}"
        self.adb = adb

    def _adb(self, *arguments: str, timeout: float = 15) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                [self.adb, *arguments],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise CutterError("ADB est introuvable dans PATH.") from error
        except subprocess.TimeoutExpired as error:
            raise CutterError(f"ADB ne répond pas ({' '.join(arguments)}).") from error

    def connect(self) -> None:
        self._adb("connect", self.serial, timeout=12)
        devices = self._adb("devices", "-l").stdout.decode("utf-8", "replace")
        state = None
        for line in devices.splitlines():
            fields = line.split()
            if fields and fields[0] == self.serial:
                state = fields[1] if len(fields) > 1 else None
        if state != "device":
            raise CutterError(
                f"ADB {self.serial} indisponible (état : {state or 'absent'}). "
                "Activez l'overlay ADB par 8090 puis redémarrez le panneau."
            )

    def run_root(self, command: str, timeout: float = 30, check: bool = True) -> CommandResult:
        marker = f"__TPP06_CUTTER_{secrets.token_hex(8)}__"
        script = (
            "export LC_ALL=C\n"
            f"{command}\n"
            "tpp06_rc=$?\n"
            f"echo {marker}$tpp06_rc\n"
            "exit\n"
        ).encode()
        try:
            process = subprocess.Popen(
                [self.adb, "-s", self.serial, "shell"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except FileNotFoundError as error:
            raise CutterError("ADB est introuvable dans PATH.") from error
        output = bytearray()
        deadline = time.monotonic() + timeout

        def read_until(pattern: bytes) -> bool:
            expression = re.compile(pattern, re.IGNORECASE)
            while time.monotonic() < deadline:
                remaining = max(0.0, deadline - time.monotonic())
                readable, _, _ = select.select([process.stdout], [], [], remaining)
                if not readable:
                    break
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                output.extend(chunk)
                if expression.search(output):
                    return True
            return False

        try:
            # The TPP06 login program discards credentials sent before each
            # prompt, so credentials must be synchronised with the prompts.
            if not read_until(rb"login:\s*$"):
                raise CutterError("L'invite login du panneau ne répond pas.")
            process.stdin.write(b"root\n")
            process.stdin.flush()
            if not read_until(rb"password:\s*$"):
                raise CutterError("L'invite du mot de passe root ne répond pas.")
            process.stdin.write(self.password.encode() + b"\n")
            process.stdin.flush()
            if not read_until(rb"[#$]\s*$"):
                current = output.decode("utf-8", "replace").replace("\r", "")
                if "Login incorrect" in current:
                    raise CutterError("Le panneau a refusé le mot de passe root calculé.")
                raise CutterError("Le shell root du panneau ne répond pas après connexion.")
            process.stdin.write(script)
            process.stdin.flush()
            if not read_until(re.escape(marker.encode()) + rb"\d+"):
                raise CutterError("Impossible de confirmer l'exécution de la commande root.")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()
        text = bytes(output).decode("utf-8", "replace").replace("\r", "")
        match = re.search(re.escape(marker) + r"(\d+)", text)
        if not match:
            if "Login incorrect" in text:
                raise CutterError("Le panneau a refusé le mot de passe root calculé.")
            raise CutterError("Impossible de confirmer l'exécution de la commande root.")
        returncode = int(match.group(1))
        clean = text[: match.start()].strip()
        if check and returncode != 0:
            raise CutterError(f"Commande distante en échec ({returncode}) :\n{clean[-1200:]}")
        return CommandResult(clean, returncode)

    def remote_sha256(self, remote_path: str) -> str | None:
        result = self.run_root(
            f"sha256sum {shlex.quote(remote_path)} 2>/dev/null | awk '{{print $1}}'",
            check=False,
        )
        matches = re.findall(r"\b[0-9a-f]{64}\b", result.stdout)
        return matches[-1] if matches else None

    def remote_checksum(self, remote_path: str) -> tuple[str, str] | None:
        quoted = shlex.quote(remote_path)
        result = self.run_root(
            f"sha256sum {quoted} 2>/dev/null || md5sum {quoted} 2>/dev/null",
            check=False,
        )
        sha256_matches = re.findall(r"\b[0-9a-f]{64}\b", result.stdout)
        if sha256_matches:
            return "sha256", sha256_matches[-1]
        md5_matches = re.findall(r"\b[0-9a-f]{32}\b", result.stdout)
        if md5_matches:
            return "md5", md5_matches[-1]
        return None

    @staticmethod
    def _matches_local_checksum(local_path: Path, remote: tuple[str, str] | None) -> bool:
        if remote is None:
            return False
        algorithm, expected = remote
        actual = sha256_file(local_path) if algorithm == "sha256" else md5_file(local_path)
        return actual == expected

    def upload(self, local_path: Path, remote_path: str, port: int = DEFAULT_TRANSFER_PORT) -> None:
        pushed = self._adb(
            "-s", self.serial, "push", str(local_path), remote_path, timeout=60
        )
        if pushed.returncode == 0 and self._matches_local_checksum(
            local_path, self.remote_checksum(remote_path)
        ):
            return

        quoted = shlex.quote(remote_path)
        self.run_root(
            f"rm -f {quoted}; (nc -l -p {port} > {quoted}) >/tmp/tpp06-cutter-nc.log 2>&1 &",
        )
        deadline = time.monotonic() + 10
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((self.host, port), timeout=2) as connection:
                    with local_path.open("rb") as source:
                        while chunk := source.read(64 * 1024):
                            connection.sendall(chunk)
                    connection.shutdown(socket.SHUT_WR)
                break
            except OSError as error:
                last_error = error
                time.sleep(0.25)
        else:
            raise CutterError(f"Transfert réseau vers le panneau impossible : {last_error}")

        for _ in range(20):
            if self._matches_local_checksum(local_path, self.remote_checksum(remote_path)):
                return
            time.sleep(0.25)
        raise CutterError("La somme de contrôle du fichier transféré ne correspond pas.")

    def download(self, remote_path: str, local_path: Path, port: int = DEFAULT_TRANSFER_PORT) -> None:
        expected = self.remote_checksum(remote_path)
        if expected is None:
            raise CutterError(f"Fichier distant absent : {remote_path}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        pulled = self._adb(
            "-s", self.serial, "pull", remote_path, str(local_path), timeout=120
        )
        if (
            pulled.returncode != 0
            or not local_path.is_file()
            or not self._matches_local_checksum(local_path, expected)
        ):
            local_path.unlink(missing_ok=True)
            self.run_root(
                f"(nc -l -p {port} < {shlex.quote(remote_path)}) "
                ">/tmp/tpp06-cutter-nc.log 2>&1 &"
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    with socket.create_connection((self.host, port), timeout=3) as connection:
                        with local_path.open("wb") as destination:
                            while chunk := connection.recv(64 * 1024):
                                destination.write(chunk)
                    break
                except OSError:
                    time.sleep(0.25)
            else:
                raise CutterError("Téléchargement réseau de la sauvegarde impossible.")
        if not self._matches_local_checksum(local_path, expected):
            local_path.unlink(missing_ok=True)
            raise CutterError("La sauvegarde reçue est corrompue (somme de contrôle différente).")
        os.chmod(local_path, 0o600)


class TuyaCutter:
    def __init__(self, host: str, backup_dir: Path, adb: str = "adb") -> None:
        self.host = host
        self.backup_dir = backup_dir.expanduser().resolve()
        self.adb = adb
        self.configuration: dict[str, object] | None = None
        self.session: PanelSession | None = None

    def discover(self) -> PanelSession:
        try:
            configuration = read_configuration(
                self.host, DEFAULT_PRODUCT_TEST_PORT, 5.0
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise CutterError(f"Lecture AUTHKEY sur 8090 impossible : {error}") from error
        self.configuration = configuration
        password = derive_root_password(configuration)
        self.session = PanelSession(self.host, password, adb=self.adb)
        print(f"✓ Panneau détecté sur {self.host}:8090")
        print("✓ AUTHKEY lue et mot de passe root calculé en mémoire (valeurs masquées)")
        return self.session

    def connected_session(self) -> PanelSession:
        session = self.session or self.discover()
        session.connect()
        return session

    def status(self) -> None:
        session = self.session or self.discover()
        try:
            session.connect()
        except CutterError as error:
            print(f"! {error}")
            return
        result = session.run_root(
            "echo KERNEL=$(uname -r); "
            "echo MACHINE=$(uname -m); "
            "echo UI=$(pidof voice_control_ak3760e); "
            f"echo MODE=$(cat {REMOTE_BASE}/mode 2>/dev/null || echo tuya); "
            f"echo TEST=$(cat {REMOTE_TEST_BASE}/engine 2>/dev/null || echo none)"
        )
        print("✓ ADB et shell root opérationnels")
        for line in result.stdout.splitlines():
            if re.match(r"^(KERNEL|MACHINE|UI|MODE|TEST)=", line):
                print(f"  {line}")

    def enable_adb(self, overlay: Path, assume_yes: bool) -> None:
        overlay = require_file(overlay, "Paquet ADB")
        confirm_exact(
            "Cette opération remplace /data/app et /data/customize avec l'overlay ADB validé.",
            "INSTALLER-ADB",
            assume_yes,
        )
        upload_adb_overlay(self.host, DEFAULT_PRODUCT_TEST_PORT, 15.0, overlay)

    def backup(self, output: Path | None = None) -> Path:
        session = self.connected_session()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if output is None:
            output = self.backup_dir / f"tpp06-{self.host}-{timestamp}.tar.gz"
        output = output.expanduser().resolve()
        remote = f"/tmp/tpp06-cutter-backup-{timestamp}.tar.gz"
        command = (
            "set -- data/app data/customize data/etc/init.d; "
            f"[ -e {REMOTE_BASE} ] && set -- \"$@\" data/tpp06-cutter; "
            f"tar -czf {shlex.quote(remote)} -C / \"$@\""
        )
        session.run_root(command, timeout=120)
        session.download(remote, output)
        session.run_root(f"rm -f {shlex.quote(remote)}")
        validate_backup_archive(output)
        metadata = {
            "format": 1,
            "panel": self.host,
            "created_utc": timestamp,
            "sha256": sha256_file(output),
            "scope": ["/data/app", "/data/customize", "/data/etc/init.d", REMOTE_BASE],
        }
        metadata_path = output.with_suffix(output.suffix + ".json")
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        os.chmod(metadata_path, 0o600)
        print(f"✓ Sauvegarde vérifiée : {output}")
        print(f"  SHA-256 : {metadata['sha256']}")
        return output

    def restore(self, archive: Path, assume_yes: bool) -> None:
        archive = require_file(archive, "Sauvegarde")
        validate_backup_archive(archive)
        confirm_exact(
            "La restauration remplace l'overlay de données. Une coupure pendant l'écriture est dangereuse.",
            "RESTAURER",
            assume_yes,
        )
        self.backup()
        session = self.connected_session()
        remote = "/tmp/tpp06-cutter-restore.tar.gz"
        session.upload(archive, remote)
        if not session._matches_local_checksum(archive, session.remote_checksum(remote)):
            raise CutterError("La sauvegarde distante n'a pas la bonne somme de contrôle.")
        session.run_root(
            f"rm -rf {REMOTE_BASE}; "
            "rm -f /data/etc/init.d/S99tuya-app; "
            f"tar -xzf {remote} -C / && sync && rm -f {remote}",
            timeout=120,
        )
        print("✓ Sauvegarde restaurée. Redémarrez seulement après avoir vérifié l'alimentation.")

    def _stage_engine(
        self,
        engine: str,
        binary: Path,
        persistent: bool,
        config: Path | None,
        pages: Path | None,
    ) -> str:
        if engine not in SUPPORTED_ENGINES:
            raise CutterError(f"Moteur inconnu : {engine}")
        session = self.connected_session()
        root = f"{REMOTE_BASE}/{engine}" if persistent else f"{REMOTE_TEST_BASE}/{engine}"
        session.run_root(f"mkdir -p {root}")
        remote_tmp = f"/tmp/tpp06-cutter-{engine}-binary"
        session.upload(require_file(binary, "Binaire"), remote_tmp)
        session.run_root(
            f"mv {remote_tmp} {root}/{engine}; chmod 755 {root}/{engine}"
        )
        if engine == "openhasp":
            if config is not None:
                session.upload(require_file(config, "Configuration openHASP"), f"{root}/config.json")
            if pages is not None:
                session.upload(require_file(pages, "Pages openHASP"), f"{root}/pages.jsonl")
        return root

    def start_test(
        self,
        engine: str,
        binary: Path,
        config: Path | None,
        pages: Path | None,
    ) -> None:
        session = self.connected_session()
        self.stop_test(quiet=True)
        root = self._stage_engine(engine, binary, False, config, pages)
        executable = f"{root}/{engine}"
        arguments = f"-c {root}" if engine == "openhasp" else ""
        command = (
            f"mkdir -p {REMOTE_TEST_BASE}; "
            f"mkdir -p {REMOTE_TEST_BASE}/prefs; "
            f"ui_pid=$(pidof {TUYA_PROCESS}); echo \"$ui_pid\" > {REMOTE_TEST_BASE}/tuya.pid; "
            "[ -n \"$ui_pid\" ] && kill -STOP $ui_pid; "
            f"echo {engine} > {REMOTE_TEST_BASE}/engine; "
            f"ESPHOME_PREFDIR={REMOTE_TEST_BASE}/prefs "
            f"{executable} {arguments} > {REMOTE_TEST_BASE}/{engine}.log 2>&1 & "
            f"echo $! > {REMOTE_TEST_BASE}/engine.pid; sleep 2; "
            f"kill -0 $(cat {REMOTE_TEST_BASE}/engine.pid)"
        )
        try:
            session.run_root(command)
        except CutterError:
            self.stop_test(quiet=True)
            raise
        print(f"✓ Essai temporaire {engine} actif. Tuya est seulement suspendu.")
        print(f"  Arrêt sûr : {Path(sys.argv[0]).name} {self.host} stop-test")

    def stop_test(self, quiet: bool = False) -> None:
        session = self.connected_session()
        result = session.run_root(
            f"test_pid=$(cat {REMOTE_TEST_BASE}/engine.pid 2>/dev/null); "
            "[ -n \"$test_pid\" ] && kill $test_pid 2>/dev/null; sleep 1; "
            "[ -n \"$test_pid\" ] && kill -9 $test_pid 2>/dev/null; "
            f"ui_pid=$(cat {REMOTE_TEST_BASE}/tuya.pid 2>/dev/null); "
            "[ -n \"$ui_pid\" ] && kill -CONT $ui_pid 2>/dev/null; "
            f"rm -rf {REMOTE_TEST_BASE}",
            check=False,
        )
        if result.returncode != 0 and not quiet:
            raise CutterError("Impossible de terminer proprement l'essai temporaire.")
        if not quiet:
            print("✓ Essai arrêté et interface Tuya reprise.")

    @staticmethod
    def _launcher_script() -> bytes:
        return f"""#!/bin/sh
# TPP06_CUTTER_LAUNCHER
BASE={REMOTE_BASE}
MODE=$(cat "$BASE/mode" 2>/dev/null || echo tuya)

start_tuya() {{
    exec "$BASE/S99tuya-app.stock" start
}}

case "$1" in
  start)
    case "$MODE" in
      openhasp)
        ( "$BASE/openhasp/openhasp" -c "$BASE/openhasp" >>/tmp/openhasp.log 2>&1
          "$BASE/S99tuya-app.stock" start ) &
        ;;
      esphome)
        ( mkdir -p "$BASE/esphome/prefs"
          ESPHOME_PREFDIR="$BASE/esphome/prefs" "$BASE/esphome/esphome" >>/tmp/esphome-lvgl.log 2>&1
          "$BASE/S99tuya-app.stock" start ) &
        ;;
      *) start_tuya ;;
    esac
    ;;
  stop)
    killall openhasp esphome 2>/dev/null || true
    ;;
  restart)
    "$0" stop
    "$0" start
    ;;
  *) echo "Usage: $0 {{start|stop|restart}}"; exit 1 ;;
esac
""".encode()

    def install(
        self,
        engine: str,
        binary: Path,
        config: Path | None,
        pages: Path | None,
        assume_yes: bool,
    ) -> None:
        confirm_exact(
            "Installation permanente expérimentale. Tuya restera présent pour le retour arrière.",
            f"INSTALLER-{engine.upper()}",
            assume_yes,
        )
        backup = self.backup()
        root = self._stage_engine(engine, binary, True, config, pages)
        session = self.connected_session()
        with tempfile.NamedTemporaryFile(prefix="S99tpp06-", delete=False) as temporary:
            temporary.write(self._launcher_script())
            launcher = Path(temporary.name)
        try:
            session.upload(launcher, "/tmp/S99tuya-app.tpp06-cutter")
        finally:
            launcher.unlink(missing_ok=True)
        command = (
            f"mkdir -p {REMOTE_BASE} /data/etc/init.d; "
            f"if [ ! -f {REMOTE_BASE}/S99tuya-app.stock ]; then "
            "if grep -q TPP06_CUTTER_LAUNCHER /etc/init.d/S99tuya-app; then exit 42; fi; "
            f"cp /etc/init.d/S99tuya-app {REMOTE_BASE}/S99tuya-app.stock; fi; "
            f"chmod 755 {REMOTE_BASE}/S99tuya-app.stock {root}/{engine}; "
            "mv /tmp/S99tuya-app.tpp06-cutter /data/etc/init.d/S99tuya-app; "
            "chmod 755 /data/etc/init.d/S99tuya-app; "
            f"echo {engine} > {REMOTE_BASE}/mode; sync"
        )
        session.run_root(command)
        print(f"✓ {engine} préparé comme interface de démarrage.")
        print(f"✓ Sauvegarde de retour : {backup}")
        print("  Aucun redémarrage automatique n'a été envoyé.")

    def switch_mode(self, mode: str, assume_yes: bool) -> None:
        if mode not in MODE_NAMES:
            raise CutterError(f"Mode inconnu : {mode}")
        confirm_exact(
            f"Le prochain démarrage utilisera le mode {mode}.",
            f"MODE-{mode.upper()}",
            assume_yes,
        )
        session = self.connected_session()
        if mode != "tuya":
            check = session.run_root(
                f"test -x {REMOTE_BASE}/{mode}/{mode}", check=False
            )
            if check.returncode != 0:
                raise CutterError(f"Le moteur {mode} n'est pas installé.")
        session.run_root(f"echo {mode} > {REMOTE_BASE}/mode; sync")
        print(f"✓ Mode {mode} sélectionné pour le prochain démarrage.")

    def uninstall(self, assume_yes: bool) -> None:
        confirm_exact(
            "Le sélecteur sera retiré et le script Tuya original redeviendra visible.",
            "RESTAURER-TUYA",
            assume_yes,
        )
        backup = self.backup()
        session = self.connected_session()
        session.run_root(
            "rm -f /data/etc/init.d/S99tuya-app; "
            f"rm -rf {REMOTE_BASE}; sync"
        )
        print("✓ Sélecteur retiré. Tuya redémarrera au prochain cycle d'alimentation.")
        print(f"✓ Sauvegarde conservée : {backup}")


def add_engine_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("engine", choices=SUPPORTED_ENGINES)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--config", type=Path, help="config.json openHASP")
    parser.add_argument("--pages", type=Path, help="pages.jsonl openHASP")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TPP06 Tuya Cutter — sauvegarde et basculement local réversible"
    )
    parser.add_argument("host", help="Adresse IPv4 ou nom du TPP06")
    parser.add_argument(
        "--backup-dir", type=Path, default=Path("./tpp06-backups")
    )
    parser.add_argument("--adb", default="adb", help="Chemin de l'exécutable adb")
    parser.add_argument("--yes", action="store_true", help="Confirmer les écritures demandées")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Détecter le panneau et afficher son état")
    enable = subparsers.add_parser("enable-adb", help="Installer l'overlay ADB via 8090")
    enable.add_argument("overlay", type=Path)
    backup = subparsers.add_parser("backup", help="Créer une sauvegarde vérifiée")
    backup.add_argument("--output", type=Path)
    restore = subparsers.add_parser("restore", help="Restaurer une sauvegarde")
    restore.add_argument("archive", type=Path)
    test = subparsers.add_parser("test", help="Lancer temporairement une interface")
    add_engine_arguments(test)
    subparsers.add_parser("stop-test", help="Arrêter l'essai et reprendre Tuya")
    install = subparsers.add_parser("install", help="Préparer une interface au démarrage")
    add_engine_arguments(install)
    switch = subparsers.add_parser("switch", help="Choisir le mode du prochain démarrage")
    switch.add_argument("mode", choices=MODE_NAMES)
    subparsers.add_parser("uninstall", help="Retirer le sélecteur et restaurer Tuya")
    return parser


def interactive(cutter: TuyaCutter, assume_yes: bool) -> None:
    def ask_path(label: str, optional: bool = False) -> Path | None:
        suffix = " (Entrée pour ignorer)" if optional else ""
        while True:
            value = input(f"{label}{suffix} : ").strip()
            if optional and not value:
                return None
            if value:
                return Path(value).expanduser()

    def ask_engine() -> str:
        value = input("Moteur [openhasp/esphome] : ").strip().lower()
        if value not in SUPPORTED_ENGINES:
            raise CutterError("Moteur attendu : openhasp ou esphome.")
        return value

    def ask_engine_files(engine: str) -> tuple[Path, Path | None, Path | None]:
        binary = ask_path("Chemin du binaire")
        assert binary is not None
        if engine == "openhasp":
            config = ask_path("Chemin de config.json", optional=True)
            pages = ask_path("Chemin de pages.jsonl", optional=True)
        else:
            config = pages = None
        return binary, config, pages

    def test_engine() -> None:
        engine = ask_engine()
        binary, config, pages = ask_engine_files(engine)
        cutter.start_test(engine, binary, config, pages)

    def install_engine() -> None:
        engine = ask_engine()
        binary, config, pages = ask_engine_files(engine)
        cutter.install(engine, binary, config, pages, assume_yes)

    def restore_backup() -> None:
        archive = ask_path("Chemin de la sauvegarde .tar.gz")
        assert archive is not None
        cutter.restore(archive, assume_yes)

    def enable_adb() -> None:
        overlay = ask_path("Chemin de tpp06-adb-network-final.tar.gz")
        assert overlay is not None
        cutter.enable_adb(overlay, assume_yes)

    def select_mode() -> None:
        mode = input("Mode [tuya/openhasp/esphome] : ").strip().lower()
        cutter.switch_mode(mode, assume_yes)

    actions = {
        "1": ("État du panneau", lambda: cutter.status()),
        "2": ("Créer une sauvegarde", lambda: cutter.backup()),
        "3": ("Restaurer une sauvegarde", restore_backup),
        "4": ("Activer ADB par le port 8090", enable_adb),
        "5": ("Essayer openHASP ou ESPHome temporairement", test_engine),
        "6": ("Arrêter un essai temporaire", lambda: cutter.stop_test()),
        "7": ("Installer openHASP ou ESPHome au démarrage", install_engine),
        "8": ("Choisir le mode du prochain démarrage", select_mode),
        "9": ("Retirer le sélecteur et restaurer Tuya", lambda: cutter.uninstall(assume_yes)),
    }
    while True:
        print("\nTPP06 Tuya Cutter")
        for key, (label, _) in actions.items():
            print(f"  {key}. {label}")
        print("  0. Quitter")
        choice = input("Choix : ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if action is None:
            print("Choix inconnu.")
            continue
        try:
            action[1]()
        except CutterError as error:
            print(f"Erreur : {error}", file=sys.stderr)


def fail(message: str) -> NoReturn:
    print(f"Erreur : {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cutter = TuyaCutter(args.host, args.backup_dir, args.adb)
    try:
        if args.command is None:
            interactive(cutter, args.yes)
        elif args.command == "status":
            cutter.status()
        elif args.command == "enable-adb":
            cutter.enable_adb(args.overlay, args.yes)
        elif args.command == "backup":
            cutter.backup(args.output)
        elif args.command == "restore":
            cutter.restore(args.archive, args.yes)
        elif args.command == "test":
            cutter.start_test(args.engine, args.binary, args.config, args.pages)
        elif args.command == "stop-test":
            cutter.stop_test()
        elif args.command == "install":
            cutter.install(
                args.engine, args.binary, args.config, args.pages, args.yes
            )
        elif args.command == "switch":
            cutter.switch_mode(args.mode, args.yes)
        elif args.command == "uninstall":
            cutter.uninstall(args.yes)
        return 0
    except CutterError as error:
        fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
