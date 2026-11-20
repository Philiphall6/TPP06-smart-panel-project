"""Conservative desktop-assistant backend. No installation or reboot entrypoint.

Network diagnostics are read-only. Reading the factory password separately
enters the existing temporary product-test mode. Backup is an explicit action:
it creates an archive in /tmp, downloads it, then removes that temporary file.
No credentials, raw shell output or configuration are returned in reports.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import socket
import sys
import tarfile
import tempfile

from tpp06_authkey_reader import read_configuration
from tpp06_tuya_cutter import PanelSession, PROJECT_ROOT, derive_root_password
from tpp06_assistant_transport import AssistantSession


class AssistantError(ValueError):
    """Only static, user-safe messages belong in this exception."""


@dataclass(frozen=True)
class Action:
    title: str
    available: bool
    detail: str
    guide: str


# This catalogue is also used by the GUI: unavailable actions have no handler.
ACTIONS = (
    Action("1 · Mot de passe d’origine", True,
           "Lecture locale via 8090 ; ne retrouve pas un mot de passe changé.", "00-acces-reseau-authkey.md"),
    Action("2 · Activer ADB Wi-Fi", True,
           "Paquet reconnu ; état après ADB accepté comme référence, avec confirmation explicite.", "04-adb-wifi-sans-uart.md"),
    Action("3 · Sauvegarder", True,
           "Copie des partitions NAND après ADB ; cohérence et restauration restent à qualifier.", "21-assistant-ordinateur.md"),
    Action("4 · Restaurer une opération", True,
           "Retour d’une opération journalisée, pas une restauration NAND globale.", "21-assistant-ordinateur.md"),
    Action("5 · Changer le mot de passe", True,
           "Nouvelle connexion vérifiée ; console de secours conservée.", "19-ssh-dropbear.md"),
    Action("6 · Changer le logo", True,
           "Image 512 Kio, outils reconnus, double sauvegarde et relecture NAND.", "12-logo-demarrage.md"),
    Action("7 · Installer SSH / Dropbear", True,
           "Clé hôte unique et vérifiée via ADB ; binaire noyau connu requis.", "19-ssh-dropbear.md"),
    Action("8 · Installer ESPHome seul", True,
           "Première installation uniquement, programme ARM compilé dans HA à fournir.", "20-esphome-seul.md"),
)

PORTS = {22: "SSH", 5555: "ADB", 6053: "API ESPHome", 8082: "OTA", 8090: "Maintenance"}


def validate_host(value: str) -> str:
    try:
        address = ipaddress.IPv4Address(value.strip())
    except ipaddress.AddressValueError:
        raise AssistantError("Saisir l’adresse IPv4 du panneau, pas celle de Home Assistant.") from None
    if address.is_loopback or address.is_multicast or address.is_unspecified or int(address) == 0xffffffff:
        raise AssistantError("Adresse du panneau invalide.")
    return str(address)


def check_pc(adb: str = "adb") -> dict:
    return {
        "python": sys.version.split()[0],
        "system": sys.platform,
        "adb": "présent" if shutil.which(adb) else "absent",
        "readelf": "présent" if shutil.which("readelf") else "absent",
        "dependances": {name: "présente" if importlib.util.find_spec(name) else "absente"
                        for name in ("paramiko", "aioesphomeapi", "elftools")},
        "diagnostic_adb_et_sauvegarde": "transport portable, ADB requis",
        "installation": "parcours expérimental, fichiers compatibles et confirmations requis",
    }


def probe_ports(host: str, adb="adb") -> dict:
    host = validate_host(host)
    found = {}
    for port, name in PORTS.items():
        if port == 5555:
            # A raw TCP probe can crash the old adbd. Use its own client only.
            if not shutil.which(adb):
                found["ADB (5555)"] = "non testé : outil adb absent"
            else:
                try:
                    AssistantSession(host, "", adb=adb).connect()
                    found["ADB (5555)"] = "transport ADB accessible, login root non testé"
                except Exception:
                    found["ADB (5555)"] = "transport ADB non confirmé"
            continue
        try:
            with socket.create_connection((host, port), timeout=2):
                found[f"{name} ({port})"] = "accessible"
        except OSError:
            found[f"{name} ({port})"] = "non accessible"
    return {"acces": found, "limite": "Un port ouvert ne prouve ni l’identité ni la compatibilité du panneau."}


def factory_password(host: str) -> str:
    host = validate_host(host)
    try:
        config = read_configuration(host, 8090, 5.0)
        return derive_root_password(config)
    except Exception:
        raise AssistantError("Lecture du mot de passe d’origine impossible. Vérifier l’adresse et l’accès 8090.") from None


def connect_adb(host: str, password: str, adb: str = "adb") -> PanelSession:
    host = validate_host(host)
    if not password or len(password) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise AssistantError("Saisir un mot de passe root valide, sans retour à la ligne.")
    if not shutil.which(adb):
        raise AssistantError("ADB est absent : installer Android Platform Tools sur cet ordinateur.")
    session = AssistantSession(host, password, adb=adb)
    session.connect()
    return session


# Keep the stock executable name split: old relay drivers incorrectly scan
# diagnostic command strings as well as real process names and lock themselves.
DIAGNOSTIC = """echo ASSIST_ARCH=$(uname -m)
echo ASSIST_KERNEL=$(uname -r)
echo ASSIST_DATA=$(readlink -f /data)
echo ASSIST_FREE=$(df -Pk /data | awk 'END {print $4}')
echo ASSIST_TOTAL=$(df -Pk /data | awk 'END {print $2}')
stock_name=voice_control_ak3760
stock_name=${stock_name}e
if pidof "$stock_name" >/dev/null; then echo ASSIST_STOCK=yes; else echo ASSIST_STOCK=no; fi
if pidof esphome >/dev/null; then echo ASSIST_ESP=yes; else echo ASSIST_ESP=no; fi
"""


def parse_fields(output: str, allowed: set[str]) -> dict:
    if len(output) > 131072:
        raise AssistantError("Réponse du panneau trop longue.")
    result = {}
    for key, value in re.findall(r"^ASSIST_([A-Z_]+)=([^\r\n]*)\r?$", output, re.M):
        if key not in allowed or key in result:
            raise AssistantError("Diagnostic ambigu ; aucune suite automatique.")
        result[key] = value
    if set(result) != allowed:
        raise AssistantError("Diagnostic incomplet ; aucune suite automatique.")
    return result


def device_report(session: PanelSession) -> dict:
    fields = parse_fields(session.run_root(DIAGNOSTIC).stdout,
                          {"ARCH", "KERNEL", "DATA", "FREE", "TOTAL", "STOCK", "ESP"})
    if not all(fields[k].isdigit() for k in ("FREE", "TOTAL")) or not all(
            fields[k] in ("yes", "no") for k in ("STOCK", "ESP")):
        raise AssistantError("Diagnostic invalide.")
    recognized = (fields["ARCH"] == "armv5tejl" and fields["KERNEL"] == "4.4.192V2.4"
                  and fields["DATA"] in ("/data", "/tuya/data"))
    return {
        "plateforme_connue": recognized,
        "stockage_libre_mio": round(int(fields["FREE"]) / 1024, 1),
        "stockage_total_mio": round(int(fields["TOTAL"]) / 1024, 1),
        "esphome_actif": fields["ESP"] == "yes",
        "application_tuya_active": fields["STOCK"] == "yes",
        "limite": "Lecture seule. La plateforme reconnue ne valide pas à elle seule la variante matérielle.",
    }


def inspect_firmware(path: str) -> dict:
    if not Path(path).is_file():
        raise AssistantError("Choisir un fichier programme normal, pas un périphérique ou un dossier.")
    from tpp06_assistant_elf import inspect
    report = inspect(path)
    return dict(report, architecture="ARMv5TE statique, soft-float",
                limite="Format ELF seulement ; pilotes, noyau, API et démarrage restent à valider. Aucune installation.")


def inspect_backup(path: str | Path) -> dict:
    """Never extract; bound work and reject special entries, links and duplicates."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 512 * 1024 * 1024:
        raise AssistantError("Archive absente ou trop volumineuse (limite 512 Mio).")
    prefixes = tuple(PurePosixPath(p) for p in
                     ("data/app", "data/customize", "data/etc/init.d", "data/tpp06-cutter"))
    names, size = set(), 0
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            size += member.size
            if (name.is_absolute() or ".." in name.parts or "\\" in member.name
                    or not (member.isfile() or member.isdir()) or name in names
                    or not any(name == p or p in name.parents for p in prefixes)
                    or size > 512 * 1024 * 1024 or len(names) >= 20000):
                raise AssistantError("Archive hors périmètre ou dangereuse ; aucune extraction.")
            names.add(name)
            if member.isfile():
                with archive.extractfile(member) as source:
                    read = 0
                    while chunk := source.read(65536):
                        read += len(chunk)
                    if read != member.size:
                        raise AssistantError("Archive tronquée.")
    if not names:
        raise AssistantError("Archive vide.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(65536):
            digest.update(chunk)
    checksum = digest.hexdigest()
    metadata = path.with_suffix(path.suffix + ".json")
    checked = False
    if metadata.exists():
        if metadata.stat().st_size > 16384:
            raise AssistantError("Métadonnées trop volumineuses.")
        info = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(info, dict) or info.get("format") != 1 or info.get("sha256") != checksum:
            raise AssistantError("L’archive ne correspond pas à sa fiche SHA-256.")
        checked = True
    return {"entrees": len(names), "octets_decompresses": size, "sha256": checksum,
            "fiche_sha256_identique": checked,
            "limite": "Archive Cutter, pas une NAND complète. Ce contrôle ne prouve ni sa provenance ni une restauration réussie."}


BACKUP_SPACE = """set --
for path in /data/app /data/customize /data/etc/init.d /data/tpp06-cutter; do
[ ! -e "$path" ] || set -- "$@" "$path"
done
[ "$#" -gt 0 ] || exit 3
echo ASSIST_SIZE=$(du -sk "$@" | awk '{n+=$1} END {print n}')
echo ASSIST_TMP=$(df -Pk /tmp | awk 'END {print $4}')
"""


def backup_panel(session: PanelSession, parent: str | Path) -> dict:
    """Cutter-scope backup, without the legacy netcat fallback.

No restoration or installation is chained on success. Partial local evidence
is retained on failure, never automatically deleted or published.
"""
    parent = Path(parent).expanduser().resolve(strict=True)
    if not parent.is_dir() or parent == PROJECT_ROOT or PROJECT_ROOT in parent.parents:
        raise AssistantError("Choisir un dossier privé existant hors du dépôt Git.")
    report = device_report(session)
    if not report["plateforme_connue"]:
        raise AssistantError("Plateforme non reconnue ; sauvegarde automatique refusée.")
    fields = parse_fields(session.run_root(BACKUP_SPACE).stdout, {"SIZE", "TMP"})
    if not all(v.isdigit() for v in fields.values()) or int(fields["SIZE"]) <= 0:
        raise AssistantError("Impossible d’estimer l’espace de sauvegarde.")
    needed = int(fields["SIZE"]) * 2048 + 16 * 1024 * 1024
    if int(fields["TMP"]) * 1024 < needed or shutil.disk_usage(parent).free < needed:
        raise AssistantError("Marge insuffisante dans /tmp ou sur le PC. Aucun nettoyage automatique.")
    # New directory (0700) protects even a partial download and avoids clobbers.
    from tpp06_assistant_jobs import private_directory
    folder = private_directory(parent)
    archive = folder / "sauvegarde.tar.gz"
    remote_dir = "/tmp/tpp06-assistant-" + secrets.token_hex(12)
    remote = remote_dir + "/sauvegarde.tar.gz"
    # mkdir fails on an existing directory; do not reuse or clean that directory.
    session.run_root(f"umask 077\nmkdir {remote_dir}")
    cleaned = False
    try:
        session.run_root("umask 077\nset --\n"
                         "for path in data/app data/customize data/etc/init.d data/tpp06-cutter; do\n"
                         "[ ! -e /$path ] || set -- \"$@\" \"$path\"\ndone\n"
                         "[ \"$#\" -gt 0 ] || exit 3\n"
                         f"tar -czf {remote} -C / \"$@\"", timeout=600)
        checksum = session.remote_checksum(remote)
        if checksum is None:
            raise AssistantError("Somme de contrôle distante indisponible ; transfert refusé.")
        pulled = session._adb("-s", session.serial, "pull", remote, str(archive), timeout=180)
        if pulled.returncode != 0 or not archive.is_file() or not session._matches_local_checksum(archive, checksum):
            raise AssistantError("Téléchargement ADB incomplet ou différent. Copie partielle conservée dans le dossier privé ; aucun repli vers un port non authentifié.")
        os.chmod(archive, 0o600)
        result = inspect_backup(archive)
        metadata = {"format": 1, "sha256": result["sha256"], "scope": "cutter_partial_not_nand"}
        fd = os.open(archive.with_suffix(".gz.json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(metadata, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        result = inspect_backup(archive)
    finally:
        try:
            session.run_root(f"rm -f {remote} && rmdir {remote_dir}")
            cleaned = True
        except Exception:
            # Preserve the original failure if any; never hide a cleanup failure
            # behind a success result either. No broad recursive removal.
            pass
    result["dossier_prive"] = str(folder)
    result["archive_temporaire_supprimee"] = cleaned
    if not cleaned:
        result["attention"] = "Le fichier temporaire privé reste dans /tmp du panneau ; nettoyage à contrôler."
    result["limite"] += " Les réglages Wi-Fi/SSH hors périmètre Cutter ne sont pas tous inclus."
    return result


def safe_failure(error: Exception) -> str:
    # Raw errors from the legacy transport may echo commands and credentials.
    if isinstance(error, AssistantError):
        return str(error)
    return "Opération non terminée. Vérifier les prérequis, les fichiers et l’accès. Aucun redémarrage automatique ; ne pas relancer à l’aveugle."
