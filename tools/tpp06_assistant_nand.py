"""Post-ADB NAND acquisition, never NAND restoration.

Only the pinned BusyBox 1.21.1 nanddump is supported: -o INCLUDES OOB
(unlike some mtd-utils versions). Reads use /dev/mtdNro, never mtdblock.
Two matching passes prove repeatability, NOT filesystem consistency.
All exposed partitions are retained; unexposed chip areas are not invented.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil

from tpp06_assistant_jobs import identity, pinned_artifact, private_directory, private_file, require
from tpp06_tuya_cutter import sha256_file

CHUNK = 1024 * 1024
FIELDS = ("size", "erasesize", "writesize", "oobsize", "bad_blocks", "ecc_failures")


def read_file(session, path):
    # Paths are generated internally, never taken from a device label.
    require(re.fullmatch(r"/[a-zA-Z0-9_./-]+", path), "Chemin de diagnostic invalide.")
    tag = "NAND_" + secrets.token_hex(12)
    output = session.run_root(f"set -e\nprintf '\\n{tag}_BEGIN\\n'\ncat {path}\nprintf '\\n{tag}_END\\n'").stdout
    match = re.search(r"^" + tag + r"_BEGIN\r?\n(.*?)\r?\n" + tag + r"_END\r?$", output, re.M | re.S)
    require(match is not None, "Lecture de l’inventaire NAND incomplète.")
    return match[1].replace("\r\n", "\n")


def parse_mtd(text):
    lines = text.strip().splitlines()
    require(lines and re.fullmatch(r"dev:\s+size\s+erasesize\s+name", lines[0]), "Table MTD invalide.")
    parts = []
    for line in lines[1:]:
        match = re.fullmatch(r'mtd([0-9]{1,2}): ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) "([^"\x00-\x1f]{1,80})"', line)
        require(match is not None, "Entrée MTD non reconnue.")
        index, size, erase, name = match.groups()
        size, erase = int(size, 16), int(erase, 16)
        require(0 < erase <= size <= 128 * 1048576 and size % erase == 0, "Géométrie MTD invalide.")
        parts.append({"index": int(index), "name": name, "size": size, "erasesize": erase})
    require(1 <= len(parts) <= 32 and len({p["index"] for p in parts}) == len(parts), "Table MTD vide ou dupliquée.")
    require(sum(p["size"] for p in parts) <= 256 * 1048576, "Taille MTD hors profil pris en charge.")
    return sorted(parts, key=lambda p: p["index"])


def inventory(session):
    result = {"mtd": read_file(session, "/proc/mtd"), "mounts": read_file(session, "/proc/mounts"),
              "cmdline": read_file(session, "/proc/cmdline"), "partitions": []}
    for part in parse_mtd(result["mtd"]):
        prefix = f'/sys/class/mtd/mtd{part["index"]}/'
        require(read_file(session, prefix + "type").strip() == "nand", "Une partition n’est pas une NAND.")
        for key in FIELDS:
            value = read_file(session, prefix + key).strip()
            require(value.isdigit(), "Compteur ou géométrie NAND absent.")
            value = int(value)
            require(key not in part or part[key] == value, "Géométrie sysfs différente de /proc/mtd.")
            part[key] = value
        require(part["writesize"] == 2048 and part["oobsize"] == 64 and part["erasesize"] == 131072,
                "Géométrie NAND non prise en charge par ce lecteur.")
        require(part["bad_blocks"] == 0, "Blocs défectueux présents : acquisition spécialisée requise, aucun bloc ne sera masqué.")
        require(part["ecc_failures"] == 0, "Erreurs ECC non corrigibles : acquisition spécialisée requise.")
        result["partitions"].append(part)
    mounts = [line.split() for line in result["mounts"].splitlines()]
    require(any(len(m) >= 4 and m[1] == "/tmp" and m[2] == "tmpfs" and "rw" in m[3].split(",") for m in mounts),
            "/tmp n’est pas un tmpfs accessible en écriture : aucune copie temporaire sur NAND autorisée.")
    # Conservative: any writable persistent/overlay mount precludes an offline snapshot claim.
    result["persistent_rw"] = any(len(m) >= 4 and "rw" in m[3].split(",") and
                                  m[2] not in {"tmpfs", "proc", "sysfs", "devpts", "devtmpfs", "debugfs"}
                                  for m in mounts)
    return result


def save_manifest(folder, record):
    pending = folder / "manifest.pending"
    private_file(pending, json.dumps(record, indent=2, ensure_ascii=False).encode())
    os.replace(pending, folder / "nand-manifest.json")


def capture_reference(session, parent, artifacts, progress=lambda message: None):
    """Acquire all exposed partitions twice, using only bounded RAM staging.

Never stop services/remount/reboot or erase/write MTD. A live acquisition is
explicitly NOT certified as a consistent or restore-tested reference.
"""
    tool = pinned_artifact(artifacts, "nandtool")
    device = identity(session)
    before = inventory(session)
    folder = private_directory(parent)
    total = sum(p["size"] for p in before["partitions"])
    require(shutil.disk_usage(folder).free > total * 3 + 32 * 1048576, "Place PC insuffisante pour données, OOB et contrôles.")
    record = {"format": "tpp06-nand-reference-1", "baseline": "post-adb-current-state",
              "phase": "acquiring", "device": device, "inventory": before,
              "scope": "all-linux-exposed-mtd-partitions-not-certified-full-chip",
              "restore_validated": False, "consistency_validated": False,
              "files": [], "chunks": []}
    save_manifest(folder, record)
    remote = "/tmp/tpp06-nand-" + secrets.token_hex(12)
    # Both backup and mutation entrypoints respect this RAM-only exclusive lock.
    session.run_root("set -e\numask 077\ntest ! -e /data/tpp06-assistant.lock\nmkdir /tmp/tpp06-nand.lock")
    stage_created = False
    completed = False
    cleanup_ok = False
    try:
        session.run_root("test ! -e /data/tpp06-assistant.lock")
        session.run_root(f"set -e\numask 077\nmkdir {remote}")
        stage_created = True
        free = read_file(session, "/proc/meminfo")
        match = re.search(r"^MemAvailable:\s+([0-9]+) kB$", free, re.M)
        if match is None:
            match = re.search(r"^MemFree:\s+([0-9]+) kB$", free, re.M)
        require(match is not None and int(match[1]) >= 16 * 1024, "Marge RAM insuffisante ; aucun service ne sera arrêté.")
        session.upload(tool, remote + "/nandtool")
        require(session._matches_local_checksum(tool, session.remote_checksum(remote + "/nandtool")), "Outil transféré différent.")
        session.run_root(f"set -e\nchmod 700 {remote}/nandtool\n{remote}/nandtool --list | grep -qx nanddump")
        for pass_number in (1, 2):
            for part in before["partitions"]:
                index, size = part["index"], part["size"]
                progress(f"Lecture NAND {pass_number}/2 · partition {index}")
                data_path = folder / f"mtd{index}.data.bin"
                oob_path = folder / f"mtd{index}.data-oob.bin"
                if pass_number == 1:
                    private_file(data_path, b"")
                    private_file(oob_path, b"")
                for offset in range(0, size, CHUNK):
                    length = min(CHUNK, size - offset)
                    # -o INCLUDES OOB on this exact pinned BusyBox. Never -b.
                    session.run_root(f"set -e\numask 077\n{remote}/nandtool nanddump -o -s {offset} -l {length} -f {remote}/chunk /dev/mtd{index}ro", timeout=120)
                    local = folder / "chunk.partial"
                    session.download(remote + "/chunk", local)
                    require(local.stat().st_size == length // 2048 * 2112, "Lecture NAND tronquée ou format OOB inattendu.")
                    digest = sha256_file(local)
                    if pass_number == 1:
                        with local.open("rb") as src, data_path.open("ab") as data, oob_path.open("ab") as raw:
                            while page := src.read(2112):
                                raw.write(page)
                                data.write(page[:2048])
                            for dst in (data, raw):
                                dst.flush()
                                os.fsync(dst.fileno())
                        record["chunks"].append({"partition": index, "offset": offset, "length": length, "sha256": digest})
                    else:
                        expected = next(c for c in record["chunks"] if c["partition"] == index and c["offset"] == offset)
                        require(digest == expected["sha256"], "La NAND a changé entre les deux lectures. Copie conservée, référence NON validée.")
                    local.unlink()  # Only this owned, verified staging file; full first-pass copies remain.
                    session.run_root(f"rm -f {remote}/chunk")
                if pass_number == 1:
                    for path in (data_path, oob_path):
                        record["files"].append({"name": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)})
                    save_manifest(folder, record)
            after = inventory(session)
            require(after == before, "Inventaire, montages ou compteurs ECC modifiés pendant la lecture.")
            after_device = identity(session)
            require(all(after_device[k] == device[k] for k in ("MAC", "BOOT")), "Panneau ou démarrage modifié pendant la sauvegarde.")
        record["phase"] = "captured-two-matching-passes"
        record["acquisition"] = "live" if before["persistent_rw"] else "no-writable-persistent-mount-observed"
        # Even matching reads with RO mounts are not a proof of whole-chip coverage or tested restoration.
        save_manifest(folder, record)
        completed = True
    finally:
        if not completed:
            record["phase"] = "incomplete-not-a-reference"
            save_manifest(folder, record)
        try:
            if stage_created:
                session.run_root(f"set -e\nrm -f {remote}/chunk {remote}/nandtool\nrmdir {remote}")
            session.run_root("rmdir /tmp/tpp06-nand.lock")
            cleanup_ok = True
        except Exception:
            pass  # The lock is never removed by another attempt; report uncertainty.
    report = inspect_reference(folder / "nand-manifest.json")
    report.update(dossier_prive=str(folder), nettoyage_temporaire=cleanup_ok)
    return report


def inspect_reference(path):
    path = Path(path)
    require(path.name == "nand-manifest.json" and not path.is_symlink() and path.stat().st_size <= 2 * 1048576,
            "Manifeste NAND invalide.")
    record = json.loads(path.read_text(encoding="utf-8"))
    require(record.get("format") == "tpp06-nand-reference-1" and record.get("phase") == "captured-two-matching-passes",
            "Acquisition NAND incomplète ; ne pas utiliser comme référence.")
    parts = parse_mtd(record["inventory"]["mtd"])
    expected = {f'mtd{p["index"]}.{suffix}.bin': p["size"] * (2112 if suffix == "data-oob" else 2048) // 2048
                for p in parts for suffix in ("data", "data-oob")}
    files = record["files"]
    require(len(files) == len(expected) and {f["name"] for f in files} == set(expected), "Liste des partitions sauvegardées incomplète.")
    for entry in files:
        file = path.parent / entry["name"]
        require(file.is_file() and not file.is_symlink() and file.stat().st_size == entry["size"] == expected[entry["name"]],
                "Taille ou type d’un fichier NAND invalide.")
        require(sha256_file(file) == entry["sha256"], "Empreinte d’un fichier NAND différente.")
    return {"etat": "Toutes les partitions MTD exposées copiées et contrôlées",
            "partitions": len(parts), "reference": "État courant après ADB, pas état usine",
            "limite": "Intégrité des fichiers contrôlée, pas une preuve de cohérence système ni de couverture des zones NAND non exposées. Restauration complète non validée ; ne pas flasher ces fichiers à l’aveugle."}
