#!/usr/bin/env python3
"""Build a lean user package from a fixed Git tag, never from private work files.

Tests, photos, historical notes and maintainer utilities remain in Git.
Runtime sources are copied unchanged. Omitted documentation links go online.
No connection to a panel, firmware build, cleanup or installation.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import subprocess
from urllib.parse import quote, unquote
import zipfile
from package_assistant import FILES as ASSISTANT_FILES

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/Philiphall6/TPP06-smart-panel-project"
ROOT_FILES = {"Assistant-TPP06.cmd", "Assistant-TPP06.sh", "Installer-dependances.cmd",
              "Installer-dependances.sh", "requirements-assistant.txt", "README-assistant.md"}
OMIT_TOOLS = {"package_assistant.py", "package_project.py", "render_mobile_preview.py", "render_boot_logo.py"}
ASSISTANT_RUNTIME = {name for name in ASSISTANT_FILES
                     if not name.startswith(("tests/", "docs/")) and Path(name).name not in OMIT_TOOLS}
INSTALL_GUIDES = {"docs/fr/21-assistant-ordinateur.md", "docs/en/21-assistant-ordinateur.md",
                  "docs/fr/19-ssh-dropbear.md"}


def include(name):
    return name in ASSISTANT_RUNTIME or name in INSTALL_GUIDES or name == "esphome/tpp06-lvgl-complete.yaml"


def rewrite_links(name, text, kept, tag):
    def resolve(target):
        if re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
            return target, False
        path, separator, fragment = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(path)))
        if resolved in kept:
            return target, False
        if resolved.startswith("../") or resolved.startswith("/"):
            raise ValueError("Documentation link outside repository: " + name)
        kind = "tree" if any(n.startswith(resolved.rstrip("/") + "/") for n in kept) else "blob"
        return f"{REPO}/{kind}/{tag}/{quote(resolved)}" + (separator + fragment if separator else ""), True

    def markdown(match):
        image, label, target = match.groups()
        url, externalized = resolve(target)
        if image and externalized:
            return f"[{label} (GitHub)]({url})"
        return f"{image}[{label}]({url})"

    text = re.sub(r"(!?)\[([^\]\n]*)\]\(([^\s)]+)\)", markdown, text)
    return re.sub(r'(\b(?:src|href)=\")([^\"]+)(\")',
                  lambda m: m[1] + resolve(m[2])[0] + m[3], text)


def readme(tag):
    return f"""# TPP06 HA Panel — {tag}

## Français — commencer ici

Ce paquet utilisateur contient l’assistant FR/EN, ses scripts Linux nécessaires,
un seul YAML ESPHome à importer et le logo Home Assistant. Aucun secret inclus.

1. Extraire **tout** ce dossier. Lire [README-assistant.md](README-assistant.md).
2. Installer les dépendances sur le PC avec `Installer-dependances.cmd` (Windows)
   ou `sh Installer-dependances.sh` (Linux).
3. Lancer `Assistant-TPP06.cmd` ou `sh Assistant-TPP06.sh`.
4. Copier uniquement `esphome/tpp06-lvgl-complete.yaml` dans la configuration
   ESPHome Device Builder / Home Assistant. Ajouter sa clé personnelle
   `tpp06_api_encryption_key` dans le `secrets.yaml` existant (sans l’écraser).
   Personnaliser le nom, l’adresse et les entités en tête du YAML.
5. Device Builder télécharge automatiquement les pages et pilotes depuis le tag
   {tag} de GitHub, puis compile pour le Linux ARMv5 du panneau. Internet est
   nécessaire au téléchargement initial. Aucun dossier `esphome-components`
   ou `packages` à copier dans Home Assistant, aucun serveur Mint requis.
6. Les relais restent en observation par défaut. Sur un panneau déjà validé,
   conserver sa clé, son identité et son réglage `control_enabled` existants.

[Guide assistant](docs/fr/21-assistant-ordinateur.md) ·
[YAML complet](esphome/tpp06-lvgl-complete.yaml) ·
[Logo et licence](assets/boot-logo/README.md)

**Expérimental** : parcours complet sur panneau neuf et Windows réel non validé.
La sauvegarde NAND à chaud ne certifie pas une restauration complète. Conserver
ses sauvegardes privées et respecter les confirmations/récupérations locales.
Le logo NAND n’est **pas** un firmware OTA. Un panneau déjà sous ESPHome ne doit
pas repasser par la première installation pour une simple mise à jour.

Les pilotes et pages ESPHome sont des sources externes GitHub épinglées ; ils
ne sont pas dupliqués dans ce ZIP. Les scripts `device/` sont utilisés par
l’assistant lors de la première installation Linux : ne pas les copier dans HA.
Le YAML seul ne convertit pas un panneau Tuya d’origine : préparer le premier
démarrage avec l’assistant. Une fois ESPHome installé, les compilations et OTA
se font dans Device Builder. Ne pas choisir un firmware ESP32.

Les tests, photos, archives et outils de développement sont conservés dans le
[dépôt au tag de cette version]({REPO}/tree/{tag}), pas dans ce ZIP.
Les liens vers les documents retirés du paquet s’ouvrent sur GitHub.
`PACKAGE-CONTENTS.json` indique la source Git et les empreintes des fichiers.

## English — start here

This lean user package includes one ESPHome YAML, the FR/EN assistant and its
required Linux scripts, and the Home Assistant boot logo. No private credentials.
Extract the whole folder, install PC dependencies with `Installer-dependances.cmd`
or `sh Installer-dependances.sh`, then run `Assistant-TPP06.cmd` or
`sh Assistant-TPP06.sh`. Copy only `esphome/tpp06-lvgl-complete.yaml` to Device
Builder. Add your own `tpp06_api_encryption_key` to the existing `secrets.yaml`
without replacing it. Customize the device name, address and entity substitutions.
ESPHome downloads pages/drivers pinned to {tag} from GitHub and builds locally
in Home Assistant. No driver/package folder to copy or Mint build server needed;
Internet is required for initial downloads. Keep commissioned relay settings,
identity and encryption key on an existing panel. New relay control defaults to
observation. YAML alone does not convert a stock Tuya panel: the assistant handles
first Linux preparation; subsequent builds and OTA use Device Builder.

[Assistant guide](docs/en/21-assistant-ordinateur.md) ·
[Logo license](assets/boot-logo/README.md)

Experimental: fresh-panel/real-Windows workflows and full NAND restoration remain
unvalidated. Preserve private backups. The NAND logo is not OTA firmware.
Tests, photos, historical documentation and maintainer tools remain in GitHub;
omitted document links open online. Runtime sources are unchanged.
"""


def build(directory, tag):
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", tag):
        raise ValueError("Provide an explicit version tag")
    commit = subprocess.check_output(["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(["git", "archive", "--format=zip", commit], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(raw)) as source:
        selected = {name: source.read(name) for name in source.namelist() if not name.endswith("/") and include(name)}
        modes = {name: source.getinfo(name).external_attr for name in selected}
    for required in ROOT_FILES | ASSISTANT_RUNTIME | INSTALL_GUIDES | {"esphome/tpp06-lvgl-complete.yaml"}:
        if required not in selected:
            raise ValueError("Missing required file: " + required)
    selected["README.md"] = readme(tag).encode()
    kept = set(selected)
    rewritten = []
    for name, data in list(selected.items()):
        if name.endswith(".md"):
            text = data.decode()
            if name == "assets/boot-logo/README.md":
                text += ("\nMaintainer note / Note développeur : the renderer is intentionally not included in this user ZIP. "
                         "Le script de reconstruction reste dans le "
                         f"[dépôt source]({REPO}/blob/{tag}/tools/render_boot_logo.py).\n")
            updated = rewrite_links(name, text, kept, tag).encode()
            if updated != data:
                rewritten.append(name)
            selected[name] = updated
    manifest = {"format": 1, "tag": tag, "source_commit": commit,
                "generated": ["README.md", "PACKAGE-CONTENTS.json"], "documentation_links_rewritten": rewritten,
                "omitted": ["tests", "media", "esphome-components", "esphome/packages", "other YAML templates", "docs/archive", "docs/releases", "legacy guides", "maintainer utilities"],
                "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(selected.items())}}
    selected["PACKAGE-CONTENTS.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"TPP06-HA-Panel-{tag}-package.zip"
    checksum = directory / f"TPP06-HA-Panel-{tag}-package-SHA256SUMS.txt"
    if archive.exists() or checksum.exists():
        raise ValueError("Output exists; choose another directory")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(selected.items()):
            entry = zipfile.ZipInfo(f"TPP06-HA-Panel-{tag}/" + name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = modes.get(name, 0o100644 << 16)
            output.writestr(entry, data)
    with zipfile.ZipFile(archive) as output:
        if output.testzip() is not None:
            raise ValueError("Invalid ZIP")
    with checksum.open("x", encoding="ascii") as stream:
        stream.write(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(build(args.output, args.tag))
