from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from tools.render_mobile_preview import render


class MobilePreviewTests(unittest.TestCase):
    def test_preview_is_valid_and_explicitly_not_a_capture(self):
        source = Path(__file__).resolve().parents[1] / "esphome/tpp06-lvgl-mobile.yaml"
        svg = render(source)
        document = ET.fromstring(svg)
        self.assertEqual(document.attrib["width"], "1072")
        self.assertEqual(document.attrib["height"], "1606")
        self.assertIn("Interface V5", svg)
        self.assertIn("Ce n’est pas une capture du panneau", svg)
        self.assertNotIn("!secret", svg)
        self.assertNotIn("\uf015", svg)
        self.assertNotIn("\uf070", svg)

    def test_brightness_preview_respects_default_and_sample_values(self):
        source = Path(__file__).resolve().parents[1] / "esphome/tpp06-lvgl-mobile.yaml"
        svg = render(source)
        # 240 px slider, 100% default brightness, knob constrained by 10 px radius.
        self.assertIn('<circle cx="230.0" cy="10.0"', svg)
        self.assertIn("Luminosite : 100 %", svg)
        self.assertIn("65 %", svg)
