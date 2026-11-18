#!/usr/bin/env python3
"""Render the public mobile YAML as an approximate SVG design preview.

No ESPHome compilation, device connection, secret loading or action execution.
Browser fonts/rendering differ from LVGL: this is NOT a hardware screenshot.
"""
import argparse
import html
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]


class PublicLoader(yaml.SafeLoader):
    pass


PublicLoader.add_multi_constructor("!", lambda loader, tag, node: loader.construct_scalar(node))


def render(source: Path) -> str:
    config = yaml.load(source.read_text(), Loader=PublicLoader)
    substitutions = config["substitutions"]
    ui = config["lvgl"]
    styles = {s["id"]: s for s in ui["style_definitions"]}
    examples = {"mobile_clock": "09:41", "ha_status_label": "API CONNECTEE",
                "mobile_home_clock": "09:41", "mobile_home_greeting": "Bonjour",
                "mobile_home_date": "Mercredi 18 novembre 2026",
                "mobile_home_wifi": "Wi-Fi : liaison active",
                "mobile_diag_wifi": "Wi-Fi : liaison active",
                "mobile_diag_version": "ESPHome 2026.10.2",
                "mobile_diag_clock": "Horloge : valide",
                "mobile_diag_uptime": "Application : 42 min",
                "cover_state_label": "FERME", "cave_state_label": "ALLUMEE",
                "bar_state_label": "ETEINTE", "cave_brightness_value": "65 %",
                "bar_brightness_value": "-- %"}
    height = 76 + ((len(ui["pages"]) + 2) // 3) * 510
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1072" height="{height}" viewBox="0 0 1072 {height}">',
           f'<rect width="1072" height="{height}" fill="#111218"/>',
           '<g font-family="Montserrat, DejaVu Sans, sans-serif">',
           '<text x="24" y="28" font-size="18" fill="#F5F5F7">TPP06 / Mobile — interface LVGL native</text>',
           '<text x="24" y="51" font-size="12" fill="#989AA6">Apercu de conception, etats fictifs. Ce n’est pas une capture du panneau.</text>']

    def resolve(value):
        return re.sub(r"\$\{([^}]+)\}", lambda m: str(substitutions[m[1]]), str(value))

    def color(value):
        return f"#{value:06X}" if isinstance(value, int) else resolve(value).replace("0x", "#")

    def node(kind, widget, parent_width, parent_height, page_index):
        style = dict(ui.get("theme", {}).get(kind, {}))
        for name in ([widget["styles"]] if isinstance(widget.get("styles"), str) else widget.get("styles", [])):
            style.update(styles[name])
        style.update(widget)
        font_size = int(str(style.get("text_font", "montserrat_16")).rsplit("_", 1)[-1])
        text = resolve(examples.get(style.get("id"), style.get("text", "")))
        width = style.get("width", min(parent_width, len(text) * font_size * 0.62))
        height = style.get("height", font_size * 1.3)
        x, y = style.get("x", 0), style.get("y", 0)
        if str(style.get("align", "")).upper() == "CENTER":
            x += (parent_width - width) / 2
            y += (parent_height - height) / 2
        fill = color(style.get("bg_color", 0x1C1D24))
        if str(style.get("id", "")).startswith("mobile_nav_"):
            fill = color(substitutions["ui_accent"] if style["id"] == f"mobile_nav_{page_index}" else substitutions["ui_card"])
        out.append(f'<g transform="translate({x},{y})">')
        if kind in ("obj", "button"):
            radius = style.get("radius", 0)
            stroke = color(style.get("border_color", 0x2D2F38))
            border = style.get("border_width", 0)
            out.append(f'<rect width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{border}"/>')
        elif kind == "slider":
            fraction = 0.65 if style["id"] == "cave_brightness" else 0.01
            end = max(height / 2, min(width - height / 2, width * fraction))
            out.append(f'<rect width="{width}" height="{height}" rx="16" fill="{fill}"/>')
            out.append(f'<rect width="{end}" height="{height}" rx="16" fill="{color(substitutions["ui_accent"])}"/>')
            out.append(f'<circle cx="{end}" cy="{height/2}" r="{height/2+4}" fill="#F5F5F7"/>')
        elif kind == "label":
            text_color = color(style.get("text_color", substitutions["ui_text"]))
            if style.get("id") in ("ha_status_label", "cave_state_label"):
                text_color = "#30D158"
            anchor = {"CENTER": "middle", "RIGHT": "end"}.get(str(style.get("text_align", "")).upper(), "start")
            tx = width / 2 if anchor == "middle" else width if anchor == "end" else 0
            for line_index, line in enumerate(text.splitlines()):
                out.append(f'<text x="{tx}" y="{font_size + line_index * font_size * 1.2}" font-size="{font_size}" text-anchor="{anchor}" fill="{text_color}">{html.escape(line)}</text>')
        for child in widget.get("widgets", []):
            child_kind, value = next(iter(child.items()))
            node(child_kind, value, width, height, page_index)
        out.append('</g>')

    for i, page in enumerate(ui["pages"]):
        out.append(f'<g transform="translate({24+(i%3)*352},{76+(i//3)*510})">')
        out.append(f'<rect width="320" height="480" rx="26" fill="{color(substitutions["ui_background"])}" stroke="#343641"/>')
        for child in page["widgets"] + ui["top_layer"]["widgets"]:
            kind, value = next(iter(child.items()))
            active = {"page_home": 4, "page_sdb": 0, "page_cave": 1, "page_bar": 2}.get(page["id"], 3)
            node(kind, value, 320, 480, active)
        out.append('</g>')
    out.extend(['</g>', '</svg>'])
    return '\n'.join(out) + '\n'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(ROOT / "esphome/tpp06-lvgl-mobile.yaml"))
    print(f"Design preview only (not a hardware capture): {args.output}")
