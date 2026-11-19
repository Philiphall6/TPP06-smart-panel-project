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

# Small code-native approximations for preview only. The panel uses LVGL's
# built-in FontAwesome glyphs, not these paths and not a downloaded font.
SYMBOLS = {
    "\uf015": '<path d="M3 11 12 3 21 11M6 9v12h12V9M10 21v-7h4v7"/>',
    "\uf0c9": '<path d="M4 5h16M4 12h16M4 19h16"/>',
    "\uf011": '<path d="M12 2v10M6 5a9 9 0 1 0 12 0"/>',
    "\uf043": '<path d="M12 2C10 6 5 12 5 16a7 7 0 0 0 14 0c0-4-5-10-7-14Z"/>',
    "\uf013": '<circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4M4 4l3 3m10 10 3 3M4 20l3-3M17 7l3-3"/>',
    "\uf1eb": '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M9 16a5 5 0 0 1 6 0"/><circle cx="12" cy="20" r="1"/>',
    "\uf070": '<path d="M2 12q10-14 20 0-10 14-20 0M3 3l18 18"/>',
    "\uf026": '<path d="M3 9h5l6-5v16l-6-5H3ZM18 9l4 6m0-6-4 6"/>',
    "\uf054": '<path d="m9 4 8 8-8 8"/>',
}


class PublicLoader(yaml.SafeLoader):
    pass


PublicLoader.add_multi_constructor("!", lambda loader, tag, node: loader.construct_scalar(node))


def render(source: Path, page_ids=None, ha_connected=True) -> str:
    config = yaml.load(source.read_text(), Loader=PublicLoader)
    substitutions = config["substitutions"]
    ui = config["lvgl"]
    # Detect the layout, not a release number that changes at publication.
    modern = any(page["id"] == "page_weather" for page in ui["pages"])
    version = "" if modern else "V5 "
    pages = [p for p in ui["pages"] if page_ids is None or p["id"] in page_ids]
    styles = {s["id"]: s for s in ui["style_definitions"]}
    examples = {"mobile_clock": "09:41", "ha_status_label": "API CONNECTEE",
                "mobile_home_clock": "09:41", "mobile_home_greeting": "Bonjour",
                "mobile_home_date": "Mercredi 18 novembre 2026",
                "mobile_home_wifi": "Wi-Fi : liaison active",
                "mobile_diag_wifi": "Wi-Fi : liaison active",
                "mobile_diag_version": "Interface V5 / ESPHome 2026.10.2",
                "mobile_diag_clock": "Horloge : valide",
                "mobile_diag_uptime": "Application : 42 min",
                "cover_state_label": "FERME", "cave_state_label": "ALLUMEE",
                "bar_state_label": "ETEINTE", "cave_brightness_value": "65 %",
                "bar_brightness_value": "-- %"}
    if modern:
        examples.update(mobile_home_date="Jeudi 19 novembre", mobile_home_clock="09:47",
                        mobile_clock="09:47", ha_status_label="HOME ASSISTANT\nCONNECTE",
                        mobile_weather_temp="11 °C", mobile_weather_detail_temp="11 °C",
                        mobile_weather_condition="Nuageux", mobile_weather_detail_condition="Nuageux",
                        mobile_weather_humidity_label="62 %", mobile_weather_wind_label="12 km/h",
                        mobile_weather_age="Recu il y a 4 min",
                        mobile_home_wifi="\uf1eb",
                        mobile_diag_version="Interface V6 / ESPHome 2026.10.2")
        if not ha_connected:
            examples['ha_status_label'] = 'HOME ASSISTANT\nNON CONNECTE'
    columns = max(1, min(3, len(pages)))
    width = 16 + columns * 352
    height = 76 + ((len(pages) + columns - 1) // columns) * 510
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{width}" height="{height}" fill="#111218"/>',
           '<g font-family="Montserrat, DejaVu Sans, sans-serif">',
           f'<text x="24" y="28" font-size="18" fill="#F5F5F7">TPP06 / Interface {version}— LVGL native</text>',
           '<text x="24" y="48" font-size="10" fill="#989AA6">Apercu de conception, etats fictifs.</text>',
           '<text x="24" y="62" font-size="10" fill="#989AA6">Ce n’est pas une capture du panneau.</text>']

    def resolve(value):
        return re.sub(r"\$\{([^}]+)\}", lambda m: str(substitutions[m[1]]), str(value))

    def color(value):
        return f"#{value:06X}" if isinstance(value, int) else resolve(value).replace("0x", "#")

    def opacity(value):
        if value == "TRANSP": return 0
        if value == "COVER": return 1
        return float(str(value).rstrip('%')) / (100 if str(value).endswith('%') else 255)

    decoration_id = 0

    def paint(style):
        nonlocal decoration_id
        fill = color(style.get("bg_color", 0x1C1D24))
        if style.get("bg_opa") == "TRANSP": return "none"
        if style.get("bg_grad_dir", "NONE") != "NONE":
            decoration_id += 1
            name = f"gradient{decoration_id}"
            horizontal = style["bg_grad_dir"] == "HOR"
            out.append(f'<defs><linearGradient id="{name}" x2="{1 if horizontal else 0}" y2="{0 if horizontal else 1}">'
                       f'<stop stop-color="{fill}"/><stop offset="1" stop-color="{color(style.get("bg_grad_color", 0))}"/>'
                       '</linearGradient></defs>')
            fill = f"url(#{name})"
        return fill

    def node(kind, widget, parent_width, parent_height, page_index):
        style = dict(ui.get("theme", {}).get(kind, {}))
        for name in ([widget["styles"]] if isinstance(widget.get("styles"), str) else widget.get("styles", [])):
            style.update(styles[name])
        style.update(widget)
        if modern and style.get('id') == 'mobile_weather_sun':
            style['bg_color'] = 0x7186A6  # The sample condition is cloudy, not sunny.
        font_size = int(str(style.get("text_font", "montserrat_16")).rsplit("_", 1)[-1])
        text = resolve(examples.get(style.get("id"), style.get("text", "")))
        width = style.get("width", min(parent_width, len(text) * font_size * 0.62))
        height = style.get("height", font_size * 1.3)
        x, y = style.get("x", 0), style.get("y", 0)
        if str(style.get("align", "")).upper() == "CENTER":
            x += (parent_width - width) / 2
            y += (parent_height - height) / 2
        if str(style.get("id", "")).startswith("mobile_nav_"):
            active = style["id"] == f"mobile_nav_{page_index}"
            style['bg_color'] = substitutions['ui_accent'] if active else substitutions['ui_card']
            if modern:
                style.update(bg_opa='COVER' if active else 'TRANSP', bg_grad_dir='VER',
                             bg_grad_color=0x25374E, border_width=1 if active else 0,
                             border_color=substitutions['ui_accent'], shadow_width=8 if active else 0,
                             shadow_color=substitutions['ui_accent'], shadow_opa='20%')
        fill = paint(style)
        out.append(f'<g transform="translate({x},{y})">')
        if kind in ("obj", "button"):
            radius = style.get("radius", 0)
            stroke = color(style.get("border_color", 0x2D2F38))
            border = style.get("border_width", 0)
            shadow = ''
            if style.get('shadow_width', 0):
                nonlocal decoration_id
                decoration_id += 1
                name = f'shadow{decoration_id}'
                out.append(f'<defs><filter id="{name}" x="-50%" y="-50%" width="200%" height="200%">'
                           f'<feDropShadow dx="{style.get("shadow_offset_x", 0)}" dy="{style.get("shadow_offset_y", 0)}" '
                           f'stdDeviation="{style["shadow_width"]/4}" flood-color="{color(style.get("shadow_color", 0))}" '
                           f'flood-opacity="{opacity(style.get("shadow_opa", "COVER"))}"/></filter></defs>')
                shadow = f' filter="url(#{name})"'
            out.append(f'<rect width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{border}"{shadow}/>')
            if style.get('id') == 'mobile_ha_logo':
                ink = '#18BCF2' if ha_connected else color(substitutions['ui_muted'])
                out.append(f'<path d="M2 12 14 1 26 12V26H2Z" fill="{ink}"/>')
                out.append('<path d="M14 26V10M14 22 8 17M14 19 20 14" fill="none" stroke="#1B2330" stroke-width="2"/>')
                for cx, cy in ((14, 10), (8, 17), (20, 14)):
                    out.append(f'<circle cx="{cx}" cy="{cy}" r="2" fill="#1B2330"/>')
        elif kind == "slider":
            minimum, maximum = style.get("min_value", 0), style.get("max_value", 100)
            value = 65 if style["id"] == "cave_brightness" else style.get("value", minimum)
            fraction = (value - minimum) / max(1, maximum - minimum)
            end = max(height / 2, min(width - height / 2, width * fraction))
            out.append(f'<rect width="{width}" height="{height}" rx="16" fill="{fill}"/>')
            out.append(f'<rect width="{end}" height="{height}" rx="16" fill="{color(substitutions["ui_accent"])}"/>')
            out.append(f'<circle cx="{end}" cy="{height/2}" r="{height/2+4}" fill="#F5F5F7"/>')
        elif kind == "label":
            if str(style.get("long_mode", "")).upper() == "DOT":
                limit = max(1, int(width / (font_size * 0.58)))
                if len(text) > limit:
                    text = text[:max(0, limit - 1)] + "…"
            text_color = color(style.get("text_color", substitutions["ui_text"]))
            if style.get("id") in ("ha_status_label", "cave_state_label"):
                text_color = "#45CEA2" if modern else "#30D158"
            if modern and style.get('id') == 'ha_status_label' and not ha_connected:
                text_color = color(substitutions['ui_muted'])
            if modern and style.get('id') == 'mobile_home_wifi':
                text_color = '#75B7FA'
            anchor = {"CENTER": "middle", "RIGHT": "end"}.get(str(style.get("text_align", "")).upper(), "start")
            tx = width / 2 if anchor == "middle" else width if anchor == "end" else 0
            for line_index, line in enumerate(text.splitlines()):
                baseline = font_size + line_index * font_size * 1.2
                line_tx = tx
                if line and line[0] in SYMBOLS:
                    symbol = SYMBOLS[line[0]]
                    icon_x = tx - font_size / 2 if anchor == "middle" else tx
                    out.append(f'<g transform="translate({icon_x},{baseline-font_size}) scale({font_size/24})" fill="none" stroke="{text_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{symbol}</g>')
                    line = line[1:].lstrip()
                    line_tx += font_size + 6
                if line:
                    out.append(f'<text x="{line_tx}" y="{baseline}" font-size="{font_size}" text-anchor="{anchor}" fill="{text_color}">{html.escape(line)}</text>')
        for child in widget.get("widgets", []):
            child_kind, value = next(iter(child.items()))
            if modern and str(style.get('id', '')).startswith('mobile_nav_') and child_kind == 'label':
                value = {**value, 'text_color': substitutions['ui_text'] if active else substitutions['ui_muted']}
            node(child_kind, value, width, height, page_index)
        out.append('</g>')

    for i, page in enumerate(pages):
        out.append(f'<g transform="translate({24+(i%columns)*352},{76+(i//columns)*510})">')
        background = paint({**ui, **page})
        out.append(f'<rect width="320" height="480" rx="26" fill="{background}" stroke="#343641"/>')
        for child in page["widgets"] + ui["top_layer"]["widgets"]:
            kind, value = next(iter(child.items()))
            active = {"page_home": 4, "page_weather": 4, "page_sdb": 0, "page_cave": 1, "page_bar": 2}.get(page["id"], 3)
            node(kind, value, 320, 480, active)
        out.append('</g>')
    out.extend(['</g>', '</svg>'])
    return '\n'.join(out) + '\n'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "esphome/tpp06-lvgl-mobile.yaml")
    parser.add_argument("--pages", nargs="+", help="Optional page IDs for a focused preview")
    parser.add_argument("--ha-disconnected", action="store_true", help="Preview grey HA logo; Wi-Fi remains independent")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(args.source, args.pages, ha_connected=not args.ha_disconnected))
    print(f"Design preview only (not a hardware capture): {args.output}")
