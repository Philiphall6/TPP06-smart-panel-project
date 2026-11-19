#!/usr/bin/env python3
"""Add French navigation comments without changing any existing YAML line."""
import argparse
from pathlib import Path
import re

PREFIX = "# [TPP06] "
SECTIONS = {
    "substitutions": "01 — PERSONNALISATION : noms, entités HA, matériel et couleurs",
    "packages": "02 — MODULES : imports des fonctionnalités complémentaires",
    "esphome": "03 — APPLICATION : identité, démarrage et compilation",
    "external_components": "04 — PILOTES : sources et version des composants Linux",
    "tpp06_ui": "INTERFACE : pilote des fonctions tactiles",
    "tpp06_wifi": "RÉSEAU : pont vers le service Wi-Fi Linux",
    "tpp06_buzzer": "SON : pilote du bip local",
    "tpp06_backlight": "ÉCRAN : pilote du rétroéclairage",
    "tpp06_local_relays": "RELAIS LOCAUX : boutons physiques et sorties",
    "tpp06_health": "DIAGNOSTICS : mémoire, réseau et stockage OTA",
    "bluetooth_proxy": "BLUETOOTH : annonces BLE vers Home Assistant",
    "button": "COMMANDES HA : boutons, redémarrage logiciel et panneau",
    "switch": "RÉGLAGES HA : interrupteurs et préférences",
    "number": "RÉGLAGES HA : valeurs numériques",
    "select": "RÉGLAGES HA : listes de choix",
    "host": "LINUX : cible, interface réseau et compilation croisée",
    "tpp06_compat": "LINUX : compatibilité du noyau embarqué",
    "mdns": "DÉCOUVERTE : annonce du panneau sur le réseau local",
    "logger": "JOURNAUX : niveau des messages",
    "time": "HORLOGE : synchronisation avec Home Assistant",
    "api": "CONNEXION HA : API chiffrée et événements de connexion",
    "ota": "MISE À JOUR : transfert sans fil chiffré",
    "dashboard_import": "BUILDER : modèle public proposé à l'import",
    "text_sensor": "IMPORTS ET DIAGNOSTICS : textes, météo, lumières et volet HA",
    "sensor": "IMPORTS ET MESURES : température, humidité, position et luminosité",
    "binary_sensor": "ÉTATS : indicateurs binaires",
    "display": "AFFICHAGE : framebuffer Linux et format des couleurs",
    "touchscreen": "TACTILE : entrée, réveil et retour sonore",
    "globals": "PRÉFÉRENCES : réglages mémorisés et état de l'interface",
    "script": "LOGIQUE : actualisation des vues et actions locales",
    "interval": "ACTUALISATION : tâches périodiques",
    "lvgl": "INTERFACE : styles, navigation et pages tactiles",
}
PAGES = {
    "page_home": "VUE ACCUEIL : heure, date, météo et raccourcis",
    "page_sdb": "VUE VOLET : état importé et commandes HA",
    "page_cave": "VUE LUMIÈRE 1 : état importé et commandes HA",
    "page_bar": "VUE LUMIÈRE 2 : état importé et commandes HA",
    "page_menu": "VUE PARAMÈTRES : menu principal",
    "page_wifi_discovery": "VUE WI-FI : recherche et sélection du réseau",
    "page_wifi_settings": "VUE WI-FI : mot de passe et confirmation",
    "page_display_settings": "VUE ÉCRAN : luminosité, veille et horloge",
    "page_sound": "VUE SON : activation du bip tactile",
    "page_weather": "VUE MÉTÉO : détails des mesures HA",
    "page_diagnostics": "VUE DIAGNOSTICS : état et version du panneau",
    "page_local_controls": "VUE RELAIS : commandes locales indépendantes de HA",
    "page_quiet_hours": "VUE SILENCE : plage horaire du bip",
    "page_ble_settings": "VUE BLUETOOTH : détection et compteurs BLE",
}


def original_lines(text):
    return [line for line in text.splitlines(keepends=True)
            if not line.lstrip().startswith(PREFIX)]


def annotate(text):
    lines = original_lines(text)
    output = []
    for index, line in enumerate(lines):
        label = None
        match = re.match(r"^([a-z_]+):", line)
        if match:
            label = SECTIONS.get(match[1])
        page = re.match(r"^\s*- id: (page_\w+)\s*$", line)
        if page:
            label = PAGES.get(page[1], "VUE : " + page[1])
        if re.match(r"^\s*- platform: homeassistant\s*$", line):
            details = "".join(lines[index:index + 6])
            for key, title in (("cave_light_entity", "LUMIÈRE 1"),
                               ("bar_light_entity", "LUMIÈRE 2"),
                               ("cover_entity", "VOLET"), ("weather_entity", "MÉTÉO")):
                if key in details:
                    label = "IMPORT HOME ASSISTANT — " + title
                    break
        if label:
            indent = line[:len(line) - len(line.lstrip())]
            output.append(indent + PREFIX + label + "\n")
        output.append(line)
    result = "".join(output)
    if original_lines(result) != original_lines(text):
        raise ValueError("Refusing a change to existing configuration lines")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.files:
        before = path.read_text()
        after = annotate(before)
        if after != before:
            path.write_text(after)
        print(f"Commented: {path.name} (configuration unchanged)")


if __name__ == "__main__":
    main()
