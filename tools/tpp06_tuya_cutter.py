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
REMOTE_DIAGNOSTIC_BASE = f"{REMOTE_BASE}/diagnostics"
ESPHOME_TEST_SECONDS = 60
PERSISTENT_FREE_RESERVE = 2 * 1024 * 1024
TUYA_PROCESS = "voice_control_ak3760e"
SUPPORTED_ENGINES = ("openhasp", "esphome")
MODE_NAMES = ("tuya", *SUPPORTED_ENGINES)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MULTIBOOT_SCRIPT = PROJECT_ROOT / "device" / "tpp06-multiboot.sh"
NETWORK_PROFILE_HELPER = PROJECT_ROOT / "device" / "tpp06-network-profile.sh"


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


def persistent_install_fits(
    available_bytes: int,
    reclaimable_bytes: int,
    payload_bytes: int,
    reserve_bytes: int = PERSISTENT_FREE_RESERVE,
) -> bool:
    """Return whether replacing an existing engine leaves a safety reserve."""
    return available_bytes + reclaimable_bytes >= payload_bytes + reserve_bytes


def ota_install_fits(
    available_bytes: int,
    payload_bytes: int,
    reserve_bytes: int = PERSISTENT_FREE_RESERVE,
) -> bool:
    """OTA keeps the running executable: its size is NOT reclaimable space."""
    return (
        available_bytes >= 0
        and payload_bytes > 0
        and reserve_bytes >= 0
        and available_bytes >= payload_bytes + reserve_bytes
    )


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
    except (tarfile.TarError, OSError, EOFError) as error:
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
            # The stock login profile aliases these commands to interactive
            # variants (-i). A prompt would consume subsequent script lines.
            "unalias mv cp rm 2>/dev/null || true\n"
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
            # The command script already contains `exit`.  Let the tiny Tuya
            # login service consume it and close cleanly; killing adb as soon
            # as the result marker appears leaves the next shell without a
            # login prompt for several seconds.
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout is not None:
                process.stdout.close()
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
            f"echo ACTIVE=$(cat {REMOTE_BASE}/active_mode 2>/dev/null || echo unknown); "
            f"echo FAILURES=$(cat {REMOTE_BASE}/failure_count 2>/dev/null || echo 0); "
            f"echo NETWORK=$(cat {REMOTE_BASE}/network_mode 2>/dev/null || echo unavailable); "
            f"test -f {REMOTE_BASE}/boot_pending && echo PENDING=yes || echo PENDING=no; "
            f"echo TEST=$(cat {REMOTE_TEST_BASE}/engine 2>/dev/null || echo none)"
        )
        print("✓ ADB et shell root opérationnels")
        for line in result.stdout.splitlines():
            if re.match(
                r"^(KERNEL|MACHINE|UI|MODE|ACTIVE|FAILURES|NETWORK|PENDING|TEST)=",
                line,
            ):
                print(f"  {line}")

    def network_check(self) -> None:
        """Read-only comparison; never claims autonomous Wi-Fi is validated."""
        helper = NETWORK_PROFILE_HELPER.read_text(encoding="utf-8")
        command = helper + "\n" + (
            "if profile=$(tpp06_active_wifi_profile); then\n"
            "echo CHECK_ACTIVE_PROFILE=recognized\n"
            f"if tpp06_profiles_equal \"$profile\" {REMOTE_BASE}/network/wpa_supplicant.conf; then\n"
            "echo CHECK_SAVED_PROFILE=identical\n"
            "else comparison=$?\n"
            "if [ \"$comparison\" = 1 ]; then echo CHECK_SAVED_PROFILE=different_or_missing\n"
            "else echo CHECK_SAVED_PROFILE=unavailable; fi; fi\n"
            "else echo CHECK_ACTIVE_PROFILE=unknown\n"
            "echo CHECK_SAVED_PROFILE=not_checked; fi\n"
            "echo CHECK_AUTONOMOUS_WIFI=not_verified\n"
        )
        result = self.connected_session().run_root(command)
        # Whitelist complete values; never print the shell echo, path or secrets.
        expected = {
            "ACTIVE_PROFILE": {"recognized", "unknown"},
            "SAVED_PROFILE": {"identical", "different_or_missing", "not_checked", "unavailable"},
            "AUTONOMOUS_WIFI": {"not_verified"},
        }
        found = {}
        for line in result.stdout.splitlines():
            match = re.fullmatch(r"CHECK_([A-Z_]+)=([a-z_]+)", line)
            if match and match[1] in expected and match[2] in expected[match[1]]:
                found[match[1]] = match[2]
        if found.keys() != expected.keys():
            raise CutterError("Diagnostic réseau incomplet ; aucune bascule autorisée.")
        for key, value in found.items():
            print(f"{key}={value}")
        print("Aucun changement réseau. Un profil identique ne valide pas le Wi-Fi sans Tuya.")

    def reboot_check(self) -> None:
        """Read-only gate that must pass before a user-initiated reboot."""
        session = self.connected_session()
        result = session.run_root(
            f"mode=$(sed -n '1p' {REMOTE_BASE}/mode 2>/dev/null || echo tuya)\n"
            "case \"$mode\" in tuya|openhasp|esphome) mode_ok=yes;; *) mode_ok=no;; esac\n"
            "echo CHECK_mode=$mode_ok:$mode\n"
            f"test -x {REMOTE_BASE}/S99tuya-app.stock && echo CHECK_stock=yes || echo CHECK_stock=no\n"
            "grep -q TPP06_MULTIBOOT_V1 /data/etc/init.d/S99tuya-app 2>/dev/null "
            "&& echo CHECK_supervisor=yes || echo CHECK_supervisor=no\n"
            f"test ! -f {REMOTE_BASE}/boot_pending && echo CHECK_pending=yes || echo CHECK_pending=no\n"
            f"if [ \"$mode\" = tuya ]; then echo CHECK_engine=yes\n"
            f"else test -x {REMOTE_BASE}/$mode/$mode && echo CHECK_engine=yes || echo CHECK_engine=no; fi\n"
            "if [ \"$mode\" = esphome ]; then\n"
            f"test -s {REMOTE_BASE}/network/wpa_supplicant.conf && "
            f"grep -q 'network[[:space:]]*={{' {REMOTE_BASE}/network/wpa_supplicant.conf && "
            f"grep -q 'ssid[[:space:]]*=' {REMOTE_BASE}/network/wpa_supplicant.conf "
            "&& echo CHECK_wifi=yes || echo CHECK_wifi=no\n"
            "else echo CHECK_wifi=yes; fi\n"
            "free_kib=$(df -k /data 2>/dev/null | awk 'NR==2 {print $4}')\n"
            "test \"${free_kib:-0}\" -ge 2048 && echo CHECK_space=yes || echo CHECK_space=no"
        )
        checks: dict[str, str] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^CHECK_([a-z]+)=(.+)$", line)
            if match:
                checks[match.group(1)] = match.group(2)
        required = ("mode", "stock", "supervisor", "pending", "engine", "wifi", "space")
        print("Contrôle avant redémarrage (lecture seule) :")
        for name in required:
            value = checks.get(name, "missing")
            passed = value == "yes" or (name == "mode" and value.startswith("yes:"))
            print(f"  {'✓' if passed else '✗'} {name}: {value}")
        failed = [
            name
            for name in required
            if not (
                checks.get(name) == "yes"
                or (name == "mode" and checks.get(name, "").startswith("yes:"))
            )
        ]
        if failed:
            raise CutterError(
                "Redémarrage refusé par le précontrôle : " + ", ".join(failed)
            )
        print("✓ Précontrôle réussi. Aucun redémarrage n'a été envoyé.")

    def ota_space_check(self, binary: Path) -> None:
        """Check the installed flash target without uploading or deleting files.

        This is a storage gate, not proof of binary compatibility or OTA health.
        Like status(), authentication may read AUTHKEY through factory port 8090.
        """
        binary = require_file(binary, "Binaire OTA")
        payload_bytes = binary.stat().st_size
        if payload_bytes == 0:
            raise CutterError("Le binaire OTA est vide.")
        session = self.connected_session()
        target = f"{REMOTE_BASE}/esphome/esphome"
        result = session.run_root(
            f"test -f {target} || exit 2\n"
            "echo CHECK_DATA=$(readlink -f /data)\n"
            f"echo CHECK_TARGET=$(readlink -f {target})\n"
            "free_kib=$(df -Pk /data 2>/dev/null | awk 'END {print $4}')\n"
            "echo CHECK_FREE_KIB=$free_kib\n"
            "engine_pids=$(pidof esphome)\n"
            "if [ -z \"$engine_pids\" ]; then echo CHECK_RUNNING=stopped\n"
            "else\n"
            "for engine_pid in $engine_pids; do\n"
            "echo CHECK_RUNNING=$(readlink /proc/$engine_pid/exe)\n"
            "done\n"
            "fi"
        )
        targets = re.findall(r"^CHECK_TARGET=(.*)$", result.stdout, re.M)
        data_roots = re.findall(r"^CHECK_DATA=(/[^\n]+)$", result.stdout, re.M)
        free = re.findall(r"^CHECK_FREE_KIB=(\d+)$", result.stdout, re.M)
        running = re.findall(r"^CHECK_RUNNING=(.*)$", result.stdout, re.M)
        canonical = (
            data_roots[0].rstrip("/") + "/tpp06-cutter/esphome/esphome"
            if len(data_roots) == 1 else None
        )
        if canonical is None or targets != [canonical] or len(free) != 1:
            raise CutterError("Cible OTA ou espace /data non confirmé : contrôle refusé.")
        if len(running) != 1 or running[0] not in ("stopped", canonical):
            raise CutterError(
                "Le programme actif n'est pas l'unique cible flash attendue. "
                "Ne pas faire d'OTA pendant cet essai."
            )
        available_bytes = int(free[0]) * 1024
        print(f"Espace libre : {available_bytes} octets")
        print(f"Nouveau programme : {payload_bytes} octets")
        print(f"Réserve minimale : {PERSISTENT_FREE_RESERVE} octets")
        if not ota_install_fits(available_bytes, payload_bytes):
            missing = max(0, payload_bytes + PERSISTENT_FREE_RESERVE - available_bytes)
            raise CutterError(
                f"OTA déconseillée : il manque {missing} octets pour conserver la réserve. "
                "L'ancien programme ne peut pas être décompté avant le transfert. "
                "Aucun fichier n'a été modifié."
            )
        print("✓ Espace suffisant pour le staging OTA avec réserve.")
        if running[0] == "stopped":
            print("ESPHome est arrêté : aucun service OTA actif n'a été validé.")
        print("Contrôle stockage seulement : compatibilité, sauvegarde et transfert restent à valider.")

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
        # The writable YAFFS layout differs between TPP06 firmware revisions.
        # In particular, untouched panels may have no /data/app or
        # /data/customize at all. Archive only paths that actually exist; the
        # read-only SquashFS application remains untouched and needs no copy.
        command = (
            "set --; "
            "for path in data/app data/customize data/etc/init.d data/tpp06-cutter; do "
            "[ -e /$path ] && set -- \"$@\" \"$path\"; "
            "done; "
            "[ \"$#\" -gt 0 ] || exit 3; "
            f"tar -czf {shlex.quote(remote)} -C / \"$@\""
        )
        # gzip on the ARMv5 panel can exceed two minutes for a 20 MiB ELF.
        session.run_root(command, timeout=600)
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
            "/data/etc/init.d/S99tuya-app stop 2>/dev/null || true; "
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
        binary = require_file(binary, "Binaire")
        session = self.connected_session()
        root = f"{REMOTE_BASE}/{engine}" if persistent else f"{REMOTE_TEST_BASE}/{engine}"
        target = f"{root}/{engine}"
        installed = f"{REMOTE_BASE}/{engine}/{engine}"
        if session._matches_local_checksum(binary, session.remote_checksum(installed)):
            if not persistent:
                session.run_root(
                    f"mkdir -p {root} && ln -sf {installed} {target}"
                )
            if engine == "esphome":
                # Reuse the verified flash copy instead of consuming scarce
                # tmpfs RAM with another identical executable during a trial.
                return root
        if persistent:
            payload_size = binary.stat().st_size
            for optional in (config, pages):
                if optional is not None:
                    payload_size += require_file(optional, "Fichier de configuration").stat().st_size
            capacity = session.run_root(
                "available=$(df -k /data 2>/dev/null | awk 'NR==2 {print $4}'); "
                f"existing=$(wc -c < {shlex.quote(target)} 2>/dev/null || echo 0); "
                "echo TPP06_SPACE=${available:-0}:${existing:-0}"
            )
            match = re.findall(r"TPP06_SPACE=(\d+):(\d+)", capacity.stdout)
            if not match:
                raise CutterError("Impossible de mesurer l'espace libre de /data.")
            available_kib, reclaimable = (int(value) for value in match[-1])
            if not persistent_install_fits(
                available_kib * 1024, reclaimable, payload_size
            ):
                required_mib = (payload_size + PERSISTENT_FREE_RESERVE + 1048575) // 1048576
                usable_mib = (available_kib * 1024 + reclaimable) // 1048576
                raise CutterError(
                    "Espace /data insuffisant pour une installation sûre : "
                    f"{usable_mib} Mio réutilisables, {required_mib} Mio requis "
                    "avec la réserve de sécurité."
                )
        session.run_root(f"mkdir -p {root}")
        remote_tmp = f"/tmp/tpp06-cutter-{engine}-binary"
        session.upload(binary, remote_tmp)
        # upload() has already verified the checksum.  In persistent mode the
        # previous engine can now be removed safely: install() first forces
        # the next boot to stock and has produced a verified backup.
        remove_previous = f"rm -f {target}; " if persistent else ""
        session.run_root(
            f"{remove_previous}mv {remote_tmp} {target}; chmod 755 {target}"
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
        if engine == "esphome":
            # Keep the stock Tuya process alive: on the TPP06 it also owns the
            # Wi-Fi setup.  The test is deliberately non-persistent and a
            # detached watchdog always terminates it after a short window.
            log = f"{REMOTE_DIAGNOSTIC_BASE}/esphome-test.log"
            command = (
                f"mkdir -p {REMOTE_TEST_BASE} {REMOTE_DIAGNOSTIC_BASE} "
                f"{REMOTE_BASE}/esphome-test-prefs; "
                f"[ -f {log} ] && cp {log} {log}.previous; "
                f"echo 'TPP06 ESPHome temporary test' > {log}; "
                f"echo esphome > {REMOTE_TEST_BASE}/engine; "
                f"ESPHOME_PREFDIR={REMOTE_BASE}/esphome-test-prefs "
                f"{executable} >> {log} 2>&1 & "
                f"echo $! > {REMOTE_TEST_BASE}/engine.pid; "
                f"( sleep {ESPHOME_TEST_SECONDS}; "
                f"test_pid=$(cat {REMOTE_TEST_BASE}/engine.pid 2>/dev/null); "
                "[ -n \"$test_pid\" ] && kill $test_pid 2>/dev/null; sleep 2; "
                "[ -n \"$test_pid\" ] && kill -9 $test_pid 2>/dev/null; "
                f"echo 'AUTO_STOP after {ESPHOME_TEST_SECONDS}s' >> {log}; "
                f"rm -f {REMOTE_TEST_BASE}/engine.pid {REMOTE_TEST_BASE}/engine "
                f") >/dev/null 2>&1 & echo $! > {REMOTE_TEST_BASE}/watchdog.pid; "
                f"sleep 2; kill -0 $(cat {REMOTE_TEST_BASE}/engine.pid)"
            )
        else:
            command = (
                f"mkdir -p {REMOTE_TEST_BASE}; "
                f"mkdir -p {REMOTE_TEST_BASE}/prefs; "
                f"ui_pid=$(pidof {TUYA_PROCESS}); echo \"$ui_pid\" > {REMOTE_TEST_BASE}/tuya.pid; "
                "[ -n \"$ui_pid\" ] && kill -STOP $ui_pid; "
                f"echo {engine} > {REMOTE_TEST_BASE}/engine; "
                f"{executable} {arguments} > {REMOTE_TEST_BASE}/{engine}.log 2>&1 & "
                f"echo $! > {REMOTE_TEST_BASE}/engine.pid; sleep 2; "
                f"kill -0 $(cat {REMOTE_TEST_BASE}/engine.pid)"
            )
        try:
            # The device's interactive ash input truncates long physical lines.
            # Keep complete shell statements short, especially the auto-stop.
            session.run_root(command.replace("; ", ";\n"))
        except CutterError:
            self.stop_test(quiet=True)
            raise
        if engine == "esphome":
            print(f"✓ Essai temporaire {engine} actif avec Tuya conservé.")
            print(f"  Arrêt automatique dans {ESPHOME_TEST_SECONDS} secondes.")
            print(f"  Journal persistant : {REMOTE_DIAGNOSTIC_BASE}/esphome-test.log")
        else:
            print(f"✓ Essai temporaire {engine} actif. Tuya est seulement suspendu.")
        print(f"  Arrêt sûr : {Path(sys.argv[0]).name} {self.host} stop-test")

    def stop_test(self, quiet: bool = False) -> None:
        session = self.connected_session()
        result = session.run_root(
            f"watchdog_pid=$(cat {REMOTE_TEST_BASE}/watchdog.pid 2>/dev/null); "
            "[ -n \"$watchdog_pid\" ] && kill $watchdog_pid 2>/dev/null; "
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
        try:
            return MULTIBOOT_SCRIPT.read_bytes()
        except OSError as error:
            raise CutterError(f"Superviseur multiboot introuvable : {error}") from error

    def install(
        self,
        engine: str,
        binary: Path,
        config: Path | None,
        pages: Path | None,
        assume_yes: bool,
        experimental_multiboot: bool = False,
        keep_stock: bool = False,
    ) -> None:
        if engine == "esphome" and not experimental_multiboot:
            raise CutterError(
                "Installation permanente ESPHome encore expérimentale. Relancez "
                "avec --experimental-multiboot seulement après un essai temporaire "
                "réussi et une sauvegarde vérifiée."
            )
        confirm_exact(
            "Installation permanente expérimentale. Tuya restera présent pour le retour arrière.",
            f"INSTALLER-{engine.upper()}",
            assume_yes,
        )
        backup = self.backup()
        # If staging is interrupted, the already installed launcher must boot
        # stock rather than attempting a missing or only partly copied engine.
        self.connected_session().run_root(
            f"mkdir -p {REMOTE_BASE}; echo tuya > {REMOTE_BASE}/mode; sync"
        )
        root = self._stage_engine(engine, binary, True, config, pages)
        session = self.connected_session()
        with tempfile.NamedTemporaryFile(prefix="S99tpp06-", delete=False) as temporary:
            temporary.write(self._launcher_script())
            launcher = Path(temporary.name)
        try:
            session.upload(launcher, "/tmp/S99tuya-app.tpp06-cutter")
        finally:
            launcher.unlink(missing_ok=True)
        next_mode = "tuya" if keep_stock else engine
        command = (
            "set -e; "
            f"mkdir -p {REMOTE_BASE} /data/etc/init.d; "
            f"if [ ! -f {REMOTE_BASE}/S99tuya-app.stock ]; then "
            "if grep -Eq 'TPP06_CUTTER_LAUNCHER|TPP06_MULTIBOOT_V1' "
            "/etc/init.d/S99tuya-app; then exit 42; fi; "
            f"cp /etc/init.d/S99tuya-app {REMOTE_BASE}/S99tuya-app.stock; fi; "
            f"chmod 755 {REMOTE_BASE}/S99tuya-app.stock {root}/{engine}; "
            "sh -n /tmp/S99tuya-app.tpp06-cutter; "
            "cp /tmp/S99tuya-app.tpp06-cutter /data/etc/init.d/.S99tuya-app.staged; "
            "chmod 755 /data/etc/init.d/.S99tuya-app.staged; "
            "sync; "
            "mv /data/etc/init.d/.S99tuya-app.staged /data/etc/init.d/S99tuya-app; "
            f"echo 0 > {REMOTE_BASE}/failure_count; "
            f"mkdir -p {REMOTE_BASE}/network; umask 077; "
            f"echo one-shot > {REMOTE_BASE}/boot_policy; "
            f"echo no > {REMOTE_BASE}/persistent_confirmed; "
            "if profile=$(tpp06_active_wifi_profile); then "
            f"cp \"$profile\" {REMOTE_BASE}/network/wpa_supplicant.conf.staged; "
            f"chmod 600 {REMOTE_BASE}/network/wpa_supplicant.conf.staged; "
            f"tpp06_profiles_equal \"$profile\" {REMOTE_BASE}/network/wpa_supplicant.conf.staged; "
            f"mv {REMOTE_BASE}/network/wpa_supplicant.conf.staged "
            f"{REMOTE_BASE}/network/wpa_supplicant.conf; "
            f"echo learning > {REMOTE_BASE}/network_mode; "
            f"else echo unavailable > {REMOTE_BASE}/network_mode; fi; "
            f"rm -f {REMOTE_BASE}/boot_pending {REMOTE_BASE}/engine.pid "
            f"{REMOTE_BASE}/supervisor.pid; "
            f"echo {next_mode} > {REMOTE_BASE}/mode.tmp; "
            f"mv {REMOTE_BASE}/mode.tmp {REMOTE_BASE}/mode; sync"
        )
        session.run_root(NETWORK_PROFILE_HELPER.read_text(encoding="utf-8") + "\n" +
                         command.replace("; ", ";\n"))
        print(f"✓ {engine} installé ; prochain démarrage : {next_mode}.")
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
                f"test -x {REMOTE_BASE}/{mode}/{mode} && "
                "grep -q TPP06_MULTIBOOT_V1 /data/etc/init.d/S99tuya-app",
                check=False,
            )
            if check.returncode != 0:
                raise CutterError(
                    f"Le moteur {mode} ou le superviseur multiboot V1 n'est pas installé."
                )
        session.run_root(
            f"echo {mode} > {REMOTE_BASE}/mode; "
            f"echo 0 > {REMOTE_BASE}/failure_count; "
            f"rm -f {REMOTE_BASE}/boot_pending; sync"
        )
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
            "/data/etc/init.d/S99tuya-app stop 2>/dev/null || true; "
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
    subparsers.add_parser("network-check", help="Comparer le profil Wi-Fi actif au secours, sans modification")
    subparsers.add_parser(
        "reboot-check", help="Vérifier sans écriture que le prochain démarrage est sûr"
    )
    ota_check = subparsers.add_parser(
        "ota-space-check", help="Contrôler l'espace de staging OTA, sans transfert ni suppression"
    )
    ota_check.add_argument("--binary", type=Path, required=True)
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
    install.add_argument(
        "--keep-stock", action="store_true",
        help="Installer les fichiers en conservant Tuya au prochain démarrage",
    )
    install.add_argument(
        "--experimental-multiboot",
        action="store_true",
        help="Autoriser ESPHome avec le superviseur de repli automatique",
    )
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
        elif args.command == "reboot-check":
            cutter.reboot_check()
        elif args.command == "network-check":
            cutter.network_check()
        elif args.command == "ota-space-check":
            cutter.ota_space_check(args.binary)
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
                args.engine,
                args.binary,
                args.config,
                args.pages,
                args.yes,
                args.experimental_multiboot,
                args.keep_stock,
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
