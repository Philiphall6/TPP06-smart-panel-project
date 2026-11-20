"""Regression checks for the native 320x480 Wi-Fi editor, no network access."""
from pathlib import Path
import unittest

import yaml


class ConfigLoader(yaml.SafeLoader):
    pass


ConfigLoader.add_multi_constructor('!', lambda loader, tag, node: loader.construct_scalar(node))


class WifiKeyboardTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'esphome/tpp06-lvgl-modern.yaml'
        self.config = yaml.load(path.read_text(), Loader=ConfigLoader)
        self.page = next(page for page in self.config['lvgl']['pages']
                         if page['id'] == 'page_wifi_settings')
        self.widgets = {config['id']: config for widget in self.page['widgets']
                        for config in widget.values() if 'id' in config}

    def test_keyboard_uses_top_origin_and_fits_above_navigation(self):
        keyboard = self.widgets['mobile_wifi_keyboard']
        # LVGL's keyboard constructor sets BOTTOM_MID, unlike ordinary objects.
        self.assertEqual(keyboard['align'], 'TOP_LEFT')
        self.assertGreaterEqual(keyboard['x'], 0)
        self.assertLessEqual(keyboard['x'] + keyboard['width'], 320)
        self.assertGreaterEqual(keyboard['y'], 276)  # Below the action buttons.
        nav_y = min(w['obj']['y'] for w in self.config['lvgl']['top_layer']['widgets']
                    if 'obj' in w and w['obj'].get('height') == 58)
        self.assertLessEqual(keyboard['y'] + keyboard['height'], nav_y)

    def test_both_fields_attach_keyboard_on_touch_and_focus(self):
        for field in ('mobile_wifi_ssid', 'mobile_wifi_password'):
            for event in ('on_click', 'on_focus'):
                actions = self.widgets[field][event]
                self.assertIn({'lvgl.keyboard.update': {
                    'id': 'mobile_wifi_keyboard', 'textarea': field}}, actions)

    def test_password_stays_masked_and_is_cleared_when_leaving(self):
        self.assertTrue(self.widgets['mobile_wifi_password']['password_mode'])
        self.assertIn({'lvgl.textarea.update': {
            'id': 'mobile_wifi_password', 'text': ''}}, self.page['on_unload'])
        # Showing the keyboard must not submit a Wi-Fi transaction.
        self.assertNotIn('panel_wifi_editor).start', str(self.page['on_load']))
