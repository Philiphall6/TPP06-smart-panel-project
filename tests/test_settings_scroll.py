"""Settings stay within the viewport, with existing actions preserved."""
import copy
from pathlib import Path
import unittest
import yaml
from tools.settings_scroll import reorganize, relocate_local


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor('!', lambda loader, tag, node: loader.construct_scalar(node))


class SettingsScrollTests(unittest.TestCase):
    def test_list_overflows_vertically_but_stays_above_fixed_navigation(self):
        source = Path(__file__).resolve().parents[1]/'esphome/tpp06-lvgl-modern.yaml'
        config = yaml.load(source.read_text(), Loader=Loader)
        page = next(p for p in config['lvgl']['pages'] if p['id'] == 'page_menu')
        self.assertFalse(page['scrollable'])
        panel = next(w['obj'] for w in page['widgets'] if 'obj' in w)
        self.assertTrue(panel['scrollable'])
        self.assertEqual(panel['scroll_dir'], 'VER')
        self.assertEqual(panel['layout']['flex_flow'], 'COLUMN')
        self.assertLessEqual(panel['y']+panel['height'], 410)
        rows = [next(iter(w.values())) for w in panel['widgets']]
        self.assertGreater(sum(w['height'] for w in rows), panel['height'])
        for row in rows:
            self.assertNotIn('y', row)
            self.assertEqual(row['width'], '100%')
        labels = [w['label']['text'] for w in panel['widgets'] if 'label' in w]
        self.assertEqual(labels, ['ECRAN ET CONFORT', 'CONNEXIONS', 'SYSTEME'])

    def test_personal_bluetooth_shortcut_and_all_actions_are_preserved(self):
        widgets = [{'label': {'text': 'Parametres'}}, {'label': {'text': 'old'}}]
        for target in ('page_ble_settings', 'page_wifi_discovery', 'page_diagnostics',
                       'page_display_settings'):
            widgets.append({'button': {'x': 232, 'y': 60, 'height': 36, 'width': 72,
                                      'widgets': [{'label': {'text': target}}],
                                      'on_click': [{'lvgl.page.show': target}]}})
        original = {'id': 'page_menu', 'on_load': [{'script.execute': 'refresh'}], 'widgets': widgets}
        saved = copy.deepcopy(original)
        result = reorganize(original)
        self.assertEqual(original, saved)
        self.assertEqual(result['on_load'], original['on_load'])
        rows = result['widgets'][-1]['obj']['widgets']
        actions = [w['button']['on_click'] for w in rows if 'button' in w]
        expected = [w['button']['on_click'] for w in widgets if 'button' in w]
        self.assertCountEqual(actions, expected)
        self.assertIn('Bluetooth BLE', str(rows))

    def test_local_moves_to_system_without_changing_its_controls(self):
        shortcut = {'button': {'on_click': [{'lvgl.page.show': 'page_local_controls'}]}}
        controls = {'id': 'page_local_controls', 'widgets': [{'label': {'text': 'Relays'}}]}
        menu = {'id': 'page_menu', 'widgets': [{'obj': {'widgets': [
            {'label': {'text': 'SYSTEME'}}]}}]}
        config = {'lvgl': {'top_layer': {'widgets': [shortcut]}, 'pages': [menu, controls]}}
        result = relocate_local(config)
        self.assertEqual(result['lvgl']['top_layer']['widgets'], [])
        self.assertEqual(result['lvgl']['pages'][1], controls)
        row = result['lvgl']['pages'][0]['widgets'][0]['obj']['widgets'][1]['button']
        self.assertEqual(row['on_click'], shortcut['button']['on_click'])
        self.assertEqual(relocate_local(result), result)
