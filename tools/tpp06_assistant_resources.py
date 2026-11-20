"""PC-only setup helpers. Explicit downloads, pinned files, no device execution."""
from pathlib import Path
import hashlib
import os
import shutil
import tempfile
import urllib.request

from tpp06_assistant_core import AssistantError, PROJECT_ROOT
from tpp06_assistant_jobs import PINS

SOFTWARE = {
    "python": "https://www.python.org/downloads/",
    "adb": "https://developer.android.com/tools/releases/platform-tools",
    "dropbear": "https://github.com/Philiphall6/TPP06-smart-panel-project/blob/main/docs/fr/19-ssh-dropbear.md",
}
DOWNLOADS = {
    "nandtool": "https://busybox.net/downloads/binaries/1.21.1/busybox-armv5l",
    "adb-overlay.tar.gz": "https://github.com/Philiphall6/TPP06-smart-panel-project/releases/download/v0.1.0/tpp06-adb-network-final.tar.gz",
    "adb-rollback.tar.gz": "https://github.com/Philiphall6/TPP06-smart-panel-project/releases/download/v0.1.0/tpp06-adb-rollback.tar.gz",
}
REQUIRED = {"adb": ("adb-overlay.tar.gz", "adb-rollback.tar.gz"), "nand": ("nandtool",),
            "logo": ("nandtool",), "ssh": ("dropbearmulti",)}
LOGO_NAME = "home-assistant-320x480-rgb565.bin"


def default_backups():
    return Path.home() / "TPP06-Backups"


def default_tools():
    return Path.home() / "TPP06-Tools"


def default_adb():
    found = shutil.which("adb")
    if found:
        return found
    name = "adb.exe" if os.name == "nt" else "adb"
    # Resolve only well-known locations; never recursively search personal files.
    for parent in (PROJECT_ROOT, Path.home() / "Downloads", default_tools()):
        path = parent / "platform-tools" / name
        if path.is_file():
            return str(path)
    return "adb"


def tool_status(directory, action):
    result = {}
    for name in REQUIRED.get(action, ()):
        path = Path(directory) / name
        if not path.is_file() or path.is_symlink():
            result[name] = "missing"
        elif path.stat().st_size > 32 * 1048576:
            result[name] = "invalid"
        else:
            result[name] = "ready" if hashlib.sha256(path.read_bytes()).hexdigest() == PINS[name] else "invalid"
    return result


def prepare_tools(directory, action, opener=urllib.request.urlopen):
    """Download only known artifacts after an explicit GUI confirmation.

Do not run ARM binaries on the PC, unpack archives, or contact the panel.
Unknown existing files are preserved and refused, never silently replaced.
"""
    names = REQUIRED.get(action)
    if not names:
        raise AssistantError("Aucun outil à télécharger pour cette opération.")
    directory = Path(directory).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, state in tool_status(directory, action).items():
        if state == "ready":
            results[name] = "ready"
            continue
        if state == "invalid" or (directory / name).exists() or (directory / name).is_symlink():
            raise AssistantError("Un outil existant est différent : conservé sans remplacement. Choisir un autre dossier.")
        if name not in DOWNLOADS:
            raise AssistantError("Dropbear compatible non distribué automatiquement. Consulter le guide SSH ; ne pas utiliser un binaire ARM quelconque.")
        fd, temporary = tempfile.mkstemp(prefix=".tpp06-download-", dir=directory)
        try:
            digest = hashlib.sha256()
            total = 0
            with os.fdopen(fd, "wb") as dst, opener(DOWNLOADS[name], timeout=30) as response:
                if not response.geturl().startswith("https://"):
                    raise AssistantError("Téléchargement HTTPS requis.")
                while block := response.read(65536):
                    total += len(block)
                    if total > 32 * 1048576:
                        raise AssistantError("Téléchargement trop volumineux ; fichier refusé.")
                    digest.update(block)
                    dst.write(block)
                dst.flush()
                os.fsync(dst.fileno())
            if digest.hexdigest() != PINS[name]:
                raise AssistantError("Empreinte SHA-256 différente : outil refusé, ne pas poursuivre.")
            # Exclusive destination: do not clobber a file created during download.
            with open(directory / name, "xb") as dst, open(temporary, "rb") as src:
                shutil.copyfileobj(src, dst)
            results[name] = "ready"
        finally:
            Path(temporary).unlink(missing_ok=True)
    return {"outils": results, "limite": "Téléchargement sur le PC uniquement. Aucun outil exécuté, aucune connexion au panneau."}


def bundled_logo():
    path = PROJECT_ROOT / "assets" / "boot-logo" / LOGO_NAME
    return str(path) if path.is_file() else ""
