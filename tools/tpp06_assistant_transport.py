"""Windows/Linux ADB login transport. No shell=True, select-on-pipes or netcat.

The console stays open for credential changes and their independent checks.
All public errors are static: neither password nor echoed shell text escapes.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import queue
import re
import secrets
import subprocess
import threading
import time

from tpp06_tuya_cutter import CommandResult, PanelSession


class TransportError(RuntimeError):
    pass


class Console:
    def __init__(self, process, password, timeout=15):
        self.process = process
        self.events = queue.Queue()
        self.buffer = bytearray()
        self.closed = False
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.expect(rb"login:\s*$", timeout)
            self.send(b"root\n")
            self.expect(rb"password:\s*$", timeout)
            self.send(password.encode("utf-8") + b"\n")
            self.expect(rb"(?:^|\r?\n)[^\r\n]*[#$]\s*$", timeout)
            self.command("export LC_ALL=C\nunalias mv cp rm 2>/dev/null || true", timeout=10)
        except Exception:
            self.close()
            raise TransportError("Connexion root impossible.") from None

    def _read(self):
        try:
            while True:
                chunk = self.process.stdout.read1(4096)
                if not chunk:
                    break
                self.events.put(chunk)
        except (OSError, ValueError):
            pass
        finally:
            self.events.put(None)

    def send(self, data):
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise TransportError("Console interrompue ; état à vérifier avant toute nouvelle écriture.") from None

    def expect(self, pattern, timeout):
        pattern = re.compile(pattern, re.I | re.M)
        deadline = time.monotonic() + timeout
        while True:
            match = pattern.search(self.buffer)
            if match:
                result = bytes(self.buffer[:match.end()])
                del self.buffer[:match.end()]
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("Délai console dépassé ; état à vérifier.")
            try:
                chunk = self.events.get(timeout=remaining)
            except queue.Empty:
                raise TransportError("Délai console dépassé ; état à vérifier.") from None
            if chunk is None:
                raise TransportError("Console fermée avant confirmation.")
            self.buffer.extend(chunk)
            if len(self.buffer) > 1024 * 1024:
                raise TransportError("Réponse console trop longue.")

    def command(self, command, timeout=30, check=True):
        if max(map(len, command.splitlines()), default=0) > 480:
            raise TransportError("Ligne trop longue pour la console embarquée.")
        marker = "__ASSIST_" + secrets.token_hex(12)
        # A child shell contains exit/set -e so they cannot close the root
        # rescue session. Single-quoted delimiter prevents host interpolation.
        delimiter = "ASSIST_SCRIPT_" + secrets.token_hex(12)
        self.send((f"sh <<'{delimiter}'\n{command}\n{delimiter}\n"
                   f"printf '\\n{marker}%s\\n' \"$?\"\n").encode("utf-8"))
        output = self.expect(rb"^" + marker.encode() + rb"[0-9]+\r?$", timeout)
        match = re.search(rb"^" + marker.encode() + rb"([0-9]+)\r?$", output, re.M)
        result = CommandResult(output[:match.start()].decode("utf-8", "replace"), int(match[1]))
        if check and result.returncode:
            raise TransportError("La commande distante a échoué ; aucune relance automatique.")
        return result

    def passwd(self, password):
        # This is an interactive program, not a password in shell argv/history.
        self.send(b"passwd root\n")
        self.expect(rb"(?:new password|enter new password):\s*$", 15)
        self.send(password.encode("ascii") + b"\n")
        self.expect(rb"(?:retype password|retype new password|repeat password):\s*$", 15)
        self.send(password.encode("ascii") + b"\n")
        self.expect(rb"(?:^|\r?\n)[^\r\n]*[#$]\s*$", 15)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.send(b"exit\n")
            self.process.stdin.close()
            self.process.wait(timeout=2)
        except (OSError, ValueError, subprocess.TimeoutExpired, TransportError):
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=3)
        finally:
            self.reader.join(timeout=1)
            self.process.stdout.close()


class AssistantSession(PanelSession):
    @contextmanager
    def console(self):
        process = subprocess.Popen([self.adb, "-s", self.serial, "shell"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        console = Console(process, self.password)
        try:
            yield console
        finally:
            console.close()

    def run_root(self, command, timeout=30, check=True):
        with self.console() as console:
            return console.command(command, timeout, check)

    def upload(self, local_path, remote_path, **unused):
        result = self._adb("-s", self.serial, "push", str(local_path), remote_path, timeout=180)
        if result.returncode or not self._matches_local_checksum(Path(local_path), self.remote_checksum(remote_path)):
            raise TransportError("Envoi ADB non vérifié. Aucun transfert anonyme de secours.")

    def download(self, remote_path, local_path, **unused):
        local_path = Path(local_path)
        if local_path.exists() or local_path.is_symlink():
            raise TransportError("Destination existante refusée.")
        checksum = self.remote_checksum(remote_path)
        if not checksum:
            raise TransportError("Somme distante absente.")
        result = self._adb("-s", self.serial, "pull", remote_path, str(local_path), timeout=180)
        if result.returncode or not local_path.is_file() or not self._matches_local_checksum(local_path, checksum):
            raise TransportError("Copie ADB incomplète ; conserver les fichiers pour diagnostic.")
        os.chmod(local_path, 0o600)
