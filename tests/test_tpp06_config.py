"""Validate the portable YAML using local drivers, without downloading/building."""
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock, patch

try:
    from esphome import yaml_util
    from esphome.config import validate_config
    from esphome.core import CORE
except ImportError:
    CORE = None


@unittest.skipIf(CORE is None, "run inside an ESPHome Python environment")
class PortableConfigTests(unittest.TestCase):
    CONFIG_FILE = "tpp06-lvgl.yaml"

    def test_local_configuration_and_diagnostics(self):
        root = Path(__file__).resolve().parents[1]
        CORE.reset()
        self.addCleanup(CORE.reset)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        CORE.config_path = Path(temporary.name) / "tpp06-lvgl.yaml"
        CORE.config_path.write_text((root / "esphome" / self.CONFIG_FILE).read_text())
        # Public deterministic test fixture only; never use this key on a device.
        CORE.config_path.with_name("secrets.yaml").write_text(
            "tpp06_api_encryption_key: MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=\n"
        )
        config = yaml_util.load_yaml(CORE.config_path)
        config["external_components"][0]["source"] = {
            "type": "local", "path": str(root / "esphome-components"),
        }
        self.assertEqual(config["api"]["reboot_timeout"], "0s")
        self.assertIn("-Wl,--strip-all", config["esphome"]["build_flags"])
        self.assertTrue(any(x["platform"] == "version" for x in config["text_sensor"]))
        self.assertTrue(any(x["platform"] == "uptime" for x in config["sensor"]))
        self.assertEqual(len(config["time"]), 1)
        clock = config["time"][0]
        self.assertEqual(clock["platform"], "homeassistant")
        self.assertEqual(clock["id"], "tpp06_ha_time")
        # Do not bake the developer's locale or a public NTP service into a
        # portable installation. HA supplies time over the existing API.
        self.assertNotIn("timezone", clock)
        self.assertNotIn("servers", clock)
        self.assertIn("on_time_sync", clock)
        result = validate_config(config, {})
        self.assertFalse(result.errors, str(result.errors))
        CORE.config = result
        self.assertEqual(CORE.address, "tpp06-lvgl.local")
        self.assertFalse(result["mdns"]["disabled"])
        self.assertEqual(result["host"]["network_interface"], "wlan0")
        self.assertNotIn("mac_address", result["host"])
        self.assertIn("encryption", result["api"])
        self.assertIn("encryption", result["ota"][0])
        from esphome.storage_json import StorageJSON
        metadata = StorageJSON.from_esphome_core(CORE, None, claim_build=False)
        self.assertEqual(metadata.address, "tpp06-lvgl.local")
        self.assertFalse(metadata.no_mdns)
        self.assertIsNone(metadata.firmware_bin_path)

    def test_linux_identity_and_mdns_guards(self):
        # Initialize the external component imports using the full config test.
        self.test_local_configuration_and_diagnostics()
        from esphome.components.host import validate_identity, validate_network_interface
        import esphome.config_validation as cv
        self.assertEqual(validate_network_interface("wlan0"), "wlan0")
        for invalid in ("", "../wlan0", "a" * 16, "wlan0;reboot", "wlan 0"):
            with self.assertRaises(cv.Invalid):
                validate_network_interface(invalid)
        with self.assertRaises(cv.Invalid):
            validate_identity({"mac_address": "02:00:00:00:06:01", "network_interface": "wlan0"})
        self.assertNotIn("mac_address", validate_identity({"network_interface": "wlan0"}))

    def test_mdns_requires_enabled_matching_interface(self):
        self.test_local_configuration_and_diagnostics()
        from esphome.components.tpp06_mdns import final_validate
        import esphome.config_validation as cv
        import esphome.final_validate as fv
        config = {"network_interface": "wlan0"}
        with patch.object(fv, "full_config") as full:
            full.get.return_value = {"host": config, "mdns": {"disabled": True}}
            with self.assertRaises(cv.Invalid):
                final_validate(config)
            full.get.return_value = {"host": {"network_interface": "eth0"}, "mdns": {"disabled": False}}
            with self.assertRaises(cv.Invalid):
                final_validate(config)
            full.get.return_value = {"host": config, "mdns": {"disabled": False}}
            final_validate(config)

    def test_address_bridge_is_idempotent_and_does_not_affect_other_platforms(self):
        import importlib.util
        from esphome.core import EsphomeCore
        path = Path(__file__).resolve().parents[1] / "esphome-components/host/address.py"
        spec = importlib.util.spec_from_file_location("test_host_address_bridge", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = EsphomeCore.address
        self.addCleanup(setattr, EsphomeCore, "address", original)
        module.install_address_bridge()
        installed = EsphomeCore.address
        module.install_address_bridge()
        self.assertIs(EsphomeCore.address, installed)
        core = EsphomeCore()
        core.config = {"host": {"use_address": "192.0.2.20"}}
        self.assertEqual(core.address, "192.0.2.20")
        core.config = {"wifi": {"use_address": "example.local"}}
        self.assertEqual(core.address, "example.local")
        core.config = {"host": {}}
        self.assertIsNone(core.address)
        core.config = None
        with self.assertRaises(ValueError):
            _ = core.address

    def test_host_cache_cannot_bypass_address_bridge(self):
        import importlib.util
        from esphome import compiled_config, writer
        path = Path(__file__).resolve().parents[1] / "esphome-components/host/address.py"
        spec = importlib.util.spec_from_file_location("test_host_cache_bridge", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "device.validated.json"
            cache.write_text("{}")
            CORE.config_path = Path(directory) / "device.yaml"
            self.addCleanup(CORE.reset)
            original = Mock()
            with patch.object(compiled_config, "save_compiled_config", original), \
                 patch.object(writer, "save_compiled_config", original), \
                 patch.object(compiled_config, "compiled_config_path", return_value=cache):
                module._disable_host_fast_cache()
                self.assertIs(writer.save_compiled_config, compiled_config.save_compiled_config)
                compiled_config.save_compiled_config({"host": {"use_address": "192.0.2.1"}})
                self.assertFalse(cache.exists())
                original.assert_not_called()
                wifi = {"wifi": {"use_address": "example.local"}}
                compiled_config.save_compiled_config(wifi)
                original.assert_called_once_with(wifi)


class MobileConfigTests(PortableConfigTests):
    CONFIG_FILE = "tpp06-lvgl-mobile.yaml"

    def test_mobile_cpp_generation_without_compiling(self):
        self.test_local_configuration_and_diagnostics()
        # Exercise LVGL action/lambda code generation only: no compiler, device,
        # build installation or toolchain download is invoked.
        from esphome.__main__ import generate_cpp_contents
        generate_cpp_contents(CORE.config)
        code = CORE.cpp_main_section
        self.assertIn("/sys/class/net/wlan0/carrier", code)
        self.assertIn("mobile_home_date", code)
        self.assertIn("mobile_clock_visible", code)
        self.assertIn("LV_OBJ_FLAG_HIDDEN", code)
        # LVGL inlines single-return text lambdas, then calls .c_str(). A
        # ternary between string literals yields const char*, not std::string.
        # Code generation alone accepts that invalid C++; check each regression.
        for widget in ("mobile_format_value", "mobile_visibility_value",
                       "mobile_accent_value", "mobile_diag_clock"):
            self.assertTrue(
                f"lv_label_set_text({widget}, (std::string(" in
                (CORE.cpp_global_section + code),
                f"{widget}: inline text expression must construct std::string",
            )
        self.assertNotIn('system("', code)

    def test_mobile_navigation_clock_and_touch_targets(self):
        # Resolve !secret in the same throwaway environment as the schema test.
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        ui = config["lvgl"]
        self.assertEqual(len(ui["pages"]), 6)
        self.assertEqual(ui["pages"][0]["id"], "page_home")
        self.assertEqual(ui["buffer_size"], "25%")
        self.assertIn("mobile", config["dashboard_import"]["package_import_url"])
        self.assertEqual(config["external_components"][0]["source"]["url"],
                         "https://github.com/Philiphall6/TPP06-smart-panel-project")
        self.assertNotIn("image", config)
        self.assertNotIn("font", config)  # Built-in LVGL fonts, no external downloads.
        widgets = []

        def visit(items):
            for item in items:
                kind, value = next(iter(item.items()))
                widgets.append((kind, value))
                visit(value.get("widgets", []))

        visit(ui["top_layer"]["widgets"])
        for page in ui["pages"]:
            visit(page["widgets"])
            self.assertEqual(len(page["on_load"]), 2)
        ids = [value["id"] for _, value in widgets if "id" in value]
        self.assertEqual(len(ids), len(set(ids)))
        for required in ("ha_status_label", "mobile_clock", "cover_state_label",
                         "cave_brightness_value", "bar_brightness_value",
                         "mobile_home_clock", "mobile_home_date", "mobile_home_wifi",
                         "mobile_nav_4", "mobile_format_value", "mobile_visibility_value",
                         "mobile_accent_value", "mobile_diag_wifi", "mobile_diag_uptime"):
            self.assertIn(required, ids)
        for kind, value in widgets:
            if kind == "button":
                self.assertGreaterEqual(value["width"], 44)
                self.assertGreaterEqual(value["height"], 44)
        brightness = [x for x in config["sensor"] if x.get("attribute") == "brightness"]
        self.assertEqual(len(brightness), 2)
        self.assertTrue(all(x.get("internal") for x in brightness))
        # Remote state updates must never trigger household actions themselves.
        self.assertNotIn("homeassistant.action", str(brightness))
        prefs = {x["id"]: x for x in config["globals"]}
        for key in ("mobile_clock_12h", "mobile_clock_visible", "mobile_purple_accent"):
            self.assertTrue(prefs[key]["restore_value"])
        self.assertFalse(prefs["mobile_active_nav"]["restore_value"])
        self.assertEqual(str(prefs["mobile_active_nav"]["initial_value"]), "4")
        wifi = next(x for x in config["text_sensor"] if x.get("id") == "mobile_wifi_state")
        self.assertTrue(wifi["internal"])
        self.assertIn("/carrier", str(wifi["lambda"]))
        self.assertIn("inconnu", str(wifi["lambda"]))
        for page in ui["pages"]:
            if page["id"] in ("page_home", "page_menu", "page_diagnostics"):
                self.assertNotIn("homeassistant.action", str(page))
                self.assertNotIn("reboot", str(page))
        clock = next(x for x in config["script"] if x["id"] == "tpp06_refresh_clock")
        self.assertIn("is_valid()", str(clock))
        self.assertIn("%I:%M %p", str(clock))
        self.assertIn("day_of_week", str(clock))

        def check_bounds(items, parent_width, parent_height):
            for item in items:
                _, value = next(iter(item.items()))
                width, height = value.get("width"), value.get("height")
                if str(value.get("align", "")).upper() != "CENTER":
                    if isinstance(width, int):
                        self.assertLessEqual(value.get("x", 0) + width, parent_width)
                    if isinstance(height, int):
                        self.assertLessEqual(value.get("y", 0) + height, parent_height)
                if value.get("widgets"):
                    check_bounds(value["widgets"], width, height)
        check_bounds(ui["top_layer"]["widgets"], 320, 480)
        for page in ui["pages"]:
            check_bounds(page["widgets"], 320, 480)
