"""Build a scrollable settings page while preserving existing control actions.

Emits an apply_patch patch; never connects to a panel or changes its network.
"""
import copy
from pathlib import Path
import re
import sys
import yaml


def reorganize(page):
    result = copy.deepcopy(page)
    buttons = [copy.deepcopy(w['button']) for w in page['widgets'] if 'button' in w]
    if not buttons:
        raise ValueError('Expected the original flat settings menu')

    def destination(button):
        return next((a['lvgl.page.show'] for a in button.get('on_click', [])
                     if 'lvgl.page.show' in a), None)

    groups = [[], [], []]
    for button in buttons:
        target = destination(button)
        group = 1 if target in ('page_wifi_discovery', 'page_ble_settings') else (
            2 if target == 'page_diagnostics' else 0)
        button.pop('x', None)
        button.pop('y', None)
        button.update(width='100%', height=64, radius=16, scrollable=False)
        if target in ('page_wifi_discovery', 'page_ble_settings'):
            title, detail = ('Wi-Fi', 'Reseaux et mot de passe') if target == 'page_wifi_discovery' else (
                'Bluetooth BLE', 'Detection des appareils')
            button['widgets'] = [
                {'label': {'x': 16, 'y': 10, 'text_font': 'montserrat_16', 'text': title}},
                {'label': {'x': 16, 'y': 34, 'text_font': 'montserrat_12',
                           'text_color': '${ui_muted}', 'text': detail}},
                {'label': {'x': 252, 'y': 23, 'text': '>'}},
            ]
        else:
            for widget in button['widgets']:
                label = widget['label']
                if label.get('x') == 260:
                    label.update(x=252, y=23)
                else:
                    label['y'] = 10 if label.get('y', 0) < 20 else 34
                    label.update(width=224, height=22, long_mode='DOT')
        groups[group].append({'button': button})
    # Display controls first, then appearance and hour format.
    groups[0].sort(key=lambda w: w['button'].get('id') != 'mobile_setting_2')
    rows = []
    for title, group in zip(('ECRAN ET CONFORT', 'CONNEXIONS', 'SYSTEME'), groups):
        if not group:
            continue
        rows.append({'label': {'text': title, 'text_font': 'montserrat_12',
                              'text_color': '${ui_muted}', 'width': '100%', 'height': 24}})
        rows.extend(group)
    labels = [copy.deepcopy(w) for w in page['widgets'] if 'label' in w]
    labels[1]['label']['text'] = 'Faites glisser pour voir les options'
    result['scrollable'] = False
    result['widgets'] = labels + [{'obj': {
        'id': 'mobile_settings_list', 'align': 'TOP_LEFT',
        'x': 12, 'y': 122, 'width': 296, 'height': 282,
        'bg_opa': 'TRANSP', 'border_width': 0, 'radius': 0,
        'pad_left': 4, 'pad_right': 8, 'pad_top': 4, 'pad_bottom': 8,
        'scrollable': True, 'scroll_dir': 'VER', 'scrollbar_mode': 'AUTO',
        'layout': {'type': 'FLEX', 'flex_flow': 'COLUMN', 'pad_row': 8,
                   'flex_align_main': 'START', 'flex_align_cross': 'START'},
        'widgets': rows,
    }}]
    return result


def relocate_local(config):
    """Move an optional personal Local shortcut; leave its page/actions intact."""
    result = copy.deepcopy(config)
    ui = result['lvgl']
    matches = [w for w in ui['top_layer']['widgets'] if 'button' in w and
               {'lvgl.page.show': 'page_local_controls'} in w['button'].get('on_click', [])]
    if not matches:
        return result
    if len(matches) != 1 or not any(p['id'] == 'page_local_controls' for p in ui['pages']):
        raise ValueError('Ambiguous or missing local controls page')
    shortcut = matches[0]
    ui['top_layer']['widgets'].remove(shortcut)
    page = next(p for p in ui['pages'] if p['id'] == 'page_menu')
    rows = next(w['obj']['widgets'] for w in page['widgets'] if 'obj' in w)
    index = next(i for i, w in enumerate(rows) if w.get('label', {}).get('text') == 'SYSTEME') + 1
    rows.insert(index, {'button': {
        'id': 'mobile_settings_local', 'width': '100%', 'height': 64,
        'styles': 'mobile_card', 'radius': 16, 'scrollable': False,
        'widgets': [
            {'label': {'x': 16, 'y': 10, 'text_font': 'montserrat_16', 'text': 'Local'}},
            {'label': {'x': 16, 'y': 34, 'text_font': 'montserrat_12',
                       'text_color': '${ui_muted}', 'text': 'Relais et options du panneau'}},
            {'label': {'x': 252, 'y': 23, 'text': '>'}},
        ], 'on_click': copy.deepcopy(shortcut['button']['on_click']),
    }})
    return result


def patch(path):
    text = path.read_text()
    start = re.search(r'(?m)^( +)- id: page_menu\s*$', text)
    if not start:
        raise ValueError('Settings page not found')
    indent = start.group(1)
    end = re.search(r'(?m)^' + indent + r'# \[TPP06\] VUE WI-FI', text[start.end():])
    if not end:
        raise ValueError('Next section marker not found')
    stop = start.end() + end.start()
    old = text[start.start():stop].rstrip('\n')
    page = yaml.safe_load(old)[0]
    new = yaml.safe_dump([reorganize(page)], allow_unicode=True, sort_keys=False, width=100)
    new = '\n'.join(indent + line for line in new.rstrip().splitlines())
    return ('*** Begin Patch\n*** Update File: '+str(path.resolve())+'\n@@\n' +
            '\n'.join('-'+line for line in old.splitlines())+'\n'+
            '\n'.join('+'+line for line in new.splitlines())+'\n*** End Patch')


if __name__ == '__main__':
    print(patch(Path(sys.argv[1])))
