#!/usr/bin/env python3
"""Build a source-only desktop assistant package from an explicit allowlist.

No firmware, keys, dumps, host paths, private journals or venv are included.
"""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0-rc2"
FILES = [
    "Assistant-TPP06.sh", "Assistant-TPP06.cmd", "Installer-dependances.sh",
    "Installer-dependances.cmd", "requirements-assistant.txt", "README-assistant.md",
    "tools/tpp06_assistant.py", "tools/tpp06_assistant_core.py",
    "tools/tpp06_assistant_jobs.py", "tools/tpp06_assistant_transport.py", "tools/tpp06_assistant_elf.py",
    "tools/tpp06_assistant_nand.py",
    "tools/tpp06_tuya_cutter.py", "tools/tpp06_authkey_reader.py", "tools/tpp06_ota_uploader.py",
    "tools/tpp06_logo.py", "tools/package_assistant.py",
    "device/tpp06-multiboot.sh", "device/tpp06-network-profile.sh",
    "device/tpp06-wifi-edit.sh", "device/tpp06-assistant-logo.sh", "device/dropbear/service.sh",
    "device/dropbear/localoptions.h",
    "tests/test_tpp06_assistant.py", "tests/test_tpp06_assistant_gui.py",
    "tests/test_tpp06_assistant_jobs.py", "tests/test_tpp06_assistant_transport.py",
    "tests/test_tpp06_assistant_elf.py",
    "tests/test_tpp06_assistant_nand.py",
    "docs/fr/21-assistant-ordinateur.md", "docs/fr/19-ssh-dropbear.md",
    "docs/fr/12-logo-demarrage.md", "docs/fr/04-adb-wifi-sans-uart.md",
    "docs/fr/00-acces-reseau-authkey.md", "docs/fr/07-tuya-cutter.md",
    "docs/fr/20-esphome-seul.md",
]


def build(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"TPP06-Assistant-v{VERSION}-sources.zip"
    checksum = archive.with_suffix(".zip.sha256")
    if archive.exists() or checksum.exists():
        raise ValueError("Package already exists; choose another output directory.")
    for name in FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing or symlinked source: " + name)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name in FILES:
            target.write(ROOT / name, "TPP06-Assistant/" + name)
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None:
            raise ValueError("Invalid ZIP")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with checksum.open("x", encoding="ascii") as stream:
        stream.write(digest + "  " + archive.name + "\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(build(parser.parse_args().output))
