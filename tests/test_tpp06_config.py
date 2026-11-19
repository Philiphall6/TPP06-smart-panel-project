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
        self.assertEqual(config["display"][0]["pixel_format"], "RGB565")
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

    def test_framebuffer_pixel_format_schema(self):
        self.test_local_configuration_and_diagnostics()
        from esphome.components.fbdev.display import CONFIG_SCHEMA
        import esphome.config_validation as cv
        for pixel_format in ("AUTO", "RGB565", "BGR565", "rgb565"):
            result = CONFIG_SCHEMA({"id": "format_test", "pixel_format": pixel_format})
            self.assertEqual(result["pixel_format"], pixel_format.upper())
        self.assertEqual(CONFIG_SCHEMA({"id": "format_default"})["pixel_format"], "AUTO")
        with self.assertRaises(cv.Invalid):
            CONFIG_SCHEMA({"id": "format_invalid", "pixel_format": "RGB888"})

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
    PAGE_COUNT = 7
    UI_VERSION = "0.1.5"
    IMPORT_MARKER = "mobile"

    def test_mobile_cpp_generation_without_compiling(self):
        self.test_local_configuration_and_diagnostics()
        # Exercise LVGL action/lambda code generation only: no compiler, device,
        # build installation or toolchain download is invoked.
        from esphome.__main__ import generate_cpp_contents
        generate_cpp_contents(CORE.config)
        code = CORE.cpp_main_section
        self.assertIn("set_pixel_format(fbdev::PixelFormat::RGB565)", code)
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
        self.assertEqual(len(ui["pages"]), self.PAGE_COUNT)
        self.assertEqual(ui["pages"][0]["id"], "page_home")
        self.assertEqual(ui["buffer_size"], "25%")
        self.assertIn(self.IMPORT_MARKER, config["dashboard_import"]["package_import_url"])
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
            self.assertEqual(len(page["on_load"]), 3 if page["id"] == "page_wifi_settings" else 2)
        ids = [value["id"] for _, value in widgets if "id" in value]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("mobile_ha_logo" if self.CONFIG_FILE == "tpp06-lvgl-modern.yaml" else "ha_status_label", ids)
        for required in ("mobile_clock", "cover_state_label",
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
            if page["id"] in ("page_home", "page_menu", "page_diagnostics", "page_display_settings"):
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

    def test_screen_sleep_is_opt_in_and_does_not_stop_network(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        self.assertEqual(config["esphome"]["project"]["version"], self.UI_VERSION)
        ui = config["lvgl"]
        prefs = {x["id"]: x for x in config["globals"]}
        self.assertEqual(str(prefs["mobile_sleep_choice"]["initial_value"]), "0")
        self.assertTrue(prefs["mobile_sleep_choice"]["restore_value"])
        self.assertTrue(prefs["mobile_brightness"]["restore_value"])
        self.assertTrue(ui["resume_on_input"])
        self.assertIn("available()", str(ui["on_idle"]))
        self.assertIn("lvgl.pause", str(ui["on_idle"]))
        self.assertIn("set_paused(false, false)", str(ui["on_pause"]))
        self.assertIn("wake()", str(ui["on_resume"]))
        for hook in ("on_idle", "on_pause", "on_resume"):
            for forbidden in ("homeassistant.action", "reboot", "system(", "exec(", "wifi.disable"):
                self.assertNotIn(forbidden, str(ui[hook]))
        self.assertIn("tpp06_backlight", config["external_components"][0]["components"])
        # No false sound control, no guessed GPIO access, no extra boot splash.
        self.assertNotIn("mobile_boot_splash", str(ui))
        self.assertNotIn("/sys/class/gpio", str(config))
        from esphome.components.tpp06_backlight import backlight_name
        import esphome.config_validation as cv
        self.assertEqual(backlight_name("backlight"), "backlight")
        for invalid in ("../gpio", "", "/dev/mtd3", "backlight;reboot", "a/b"):
            with self.assertRaises(cv.Invalid):
                backlight_name(invalid)


class ModernConfigTests(MobileConfigTests):
    CONFIG_FILE = "tpp06-lvgl-modern.yaml"
    PAGE_COUNT = 11
    UI_VERSION = "0.1.6-glass.2-dev"
    IMPORT_MARKER = "modern"

    def test_release_sources_are_pinned_together(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        self.assertEqual(config["external_components"][0]["source"]["ref"], "v0.1.6")
        self.assertTrue(config["dashboard_import"]["package_import_url"].endswith("@v0.1.6"))

    def test_glass_status_and_weather_layout(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        ui = config['lvgl']
        home = next(p for p in ui['pages'] if p['id'] == 'page_home')
        top = ui['top_layer']['widgets']
        wifi = next(w['label'] for w in top if w.get('label', {}).get('id') == 'mobile_home_wifi')
        self.assertEqual(wifi['text'], '\uf1eb')
        self.assertLess(wifi['y'], 20)
        self.assertNotIn('mobile_home_wifi', str(home))
        self.assertNotIn('Wi-Fi', str(home))
        script = next(s for s in config['script'] if s['id'] == 'tpp06_refresh_connection')
        self.assertIn('active_clients()', str(script))
        self.assertIn('Home Assistant ', str(script))
        self.assertIn('0x18BCF2', str(script))
        self.assertIn('${ui_muted}', str(script))
        self.assertNotIn('ha_status_label', str(config))
        self.assertIn('connected && !was_connected', str(script))
        self.assertIn('lv_anim_start', str(script))
        self.assertIn('lv_anim_delete', str(script))
        clock = next(w['label'] for w in top if w.get('label', {}).get('id') == 'mobile_clock')
        self.assertEqual(clock['text_align'], 'RIGHT')
        self.assertGreater(clock['x'], 160)
        self.assertLess(clock['x'] + clock['width'], wifi['x'])
        logo = str(config['esphome']['on_boot']['then'][0])
        self.assertIn('lv_event_get_target_obj', logo)
        self.assertIn('lv_event_get_layer', logo)
        self.assertIn('lv_draw_triangle_dsc_init', logo)
        self.assertNotIn('lv_event_get_draw_ctx', logo)  # Removed in LVGL 9.
        for name in ('mobile_home_cover_card', 'mobile_home_lights_card', 'mobile_weather_card'):
            card = next(w['button'] for w in home['widgets'] if w.get('button', {}).get('id') == name)
            self.assertLessEqual(card['y'] + card['height'], 400)
            self.assertIn('lvgl.page.show', str(card['on_click']))

    def test_wifi_editor_is_local_masked_and_not_automatic(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        page = next(p for p in config["lvgl"]["pages"] if p["id"] == "page_wifi_settings")
        password = next(w["textarea"] for w in page["widgets"] if
                        w.get("textarea", {}).get("id") == "mobile_wifi_password")
        self.assertTrue(password["password_mode"])
        self.assertNotIn("text", password)
        self.assertIn("mobile_wifi_password", str(page["on_unload"]))
        self.assertNotIn("homeassistant.action", str(page))
        self.assertNotIn("panel_wifi_editor", str(config["esphome"]["on_boot"]))
        self.assertNotIn("wifi", config)
        self.assertNotIn("text", config)  # No HA credential entities.

    def test_wifi_discovery_requires_tap_and_keeps_manual_entry(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        page = next(p for p in config["lvgl"]["pages"] if p["id"] == "page_wifi_discovery")
        self.assertNotIn("request_scan", str(page["on_load"]))
        self.assertNotIn("request_scan", str(config["interval"]))
        buttons = [w["button"] for w in page["widgets"] if "button" in w]
        selections = [b for b in buttons if "tpp06_select_wifi" in str(b)]
        self.assertEqual(len(selections), 4)
        self.assertTrue(any("request_scan" in str(b) for b in buttons))
        self.assertTrue(any("Saisie manuelle" in str(b) for b in buttons))
        select = next(s for s in config["script"] if s["id"] == "tpp06_select_wifi")
        self.assertIn("mobile_wifi_password", str(select))
        self.assertNotIn(".start(", str(select))  # Selecting does not switch Wi-Fi.
        for button in buttons:
            self.assertLessEqual(button["y"] + button["height"], 406)
        menu = next(p for p in config["lvgl"]["pages"] if p["id"] == "page_menu")
        rows = sorted((w["button"] for w in menu["widgets"] if "button" in w), key=lambda b: b["y"])
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertGreaterEqual(row["height"], 44)
            self.assertLessEqual(row["y"] + row["height"], 406)
        for previous, following in zip(rows, rows[1:]):
            self.assertLess(previous["y"] + previous["height"], following["y"])

    def test_storage_and_restart_are_native_same_device_entities(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        storage = next(s for s in config["text_sensor"] if s.get("id") == "panel_storage")
        restart = next(b for b in config["button"] if b.get("id") == "panel_restart")
        device = next(b for b in config["button"] if b.get("id") == "panel_device_restart")
        self.assertEqual(restart["mode"], "application")
        self.assertEqual(device["mode"], "device")
        self.assertEqual(storage["platform"], "tpp06_system")
        self.assertEqual(storage["update_interval"], "60s")
        self.assertNotIn("internal", storage)
        self.assertNotIn("entity_category", storage)
        self.assertEqual(restart["platform"], "tpp06_system")
        self.assertNotIn("internal", restart)
        self.assertNotIn("entity_category", restart)
        self.assertNotIn("button.press", str(config["esphome"]["on_boot"]))

    def test_diagnostics_version_is_short_and_height_bounded(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        version = next(x for x in config["text_sensor"] if x.get("id") == "mobile_version")
        self.assertTrue(version["hide_hash"])
        self.assertTrue(version["hide_timestamp"])
        def labels(node):
            if isinstance(node, dict):
                if node.get("id") == "mobile_diag_version" and "height" in node:
                    yield node
                for value in node.values():
                    yield from labels(value)
            elif isinstance(node, list):
                for value in node:
                    yield from labels(value)
        label, = list(labels(config["lvgl"]))
        self.assertEqual(label["long_mode"], "DOT")
        self.assertLessEqual(label["y"] + label["height"], 52)

    def test_weather_is_private_optional_read_only_and_unit_aware(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        self.assertEqual(config["substitutions"]["weather_entity"], "weather.tpp06_example")
        values = [x for section in ("sensor", "text_sensor") for x in config[section]
                  if str(x.get("entity_id", "")) == "${weather_entity}"]
        self.assertEqual(len(values), 6)
        self.assertTrue(all(x["internal"] for x in values))
        self.assertNotIn("homeassistant.action", str(values))
        attrs = {x.get("attribute") for x in values}
        self.assertEqual(attrs, {None, "temperature", "temperature_unit", "humidity",
                                 "wind_speed", "wind_speed_unit"})
        weather = next(x for x in config["script"] if x["id"] == "tpp06_refresh_weather")
        self.assertIn("fresh(", str(weather))
        self.assertIn("Donnees anciennes", str(weather))
        self.assertIn("has_state()", str(weather))
        self.assertNotIn("http_request", config)
        self.assertNotIn("api_key", config["substitutions"])

    def test_sound_setting_controls_real_driver_and_preserves_user_choice(self):
        self.test_local_configuration_and_diagnostics()
        config = yaml_util.load_yaml(CORE.config_path)
        sound = next(p for p in config["lvgl"]["pages"] if p["id"] == "page_sound")
        button = next(x["button"] for x in sound["widgets"] if "button" in x
                      and x["button"].get("id") == "mobile_beep_enable")
        self.assertIn("on_click", button)
        self.assertIn("touch_beep", str(button["on_click"]))
        setting = next(s for s in config["switch"] if s["id"] == "touch_beep")
        self.assertEqual(setting["restore_mode"], "RESTORE_DEFAULT_ON")
        self.assertIn("set_enabled(true)", str(setting["turn_on_action"]))
        self.assertIn("set_enabled(false)", str(setting["turn_off_action"]))
        self.assertIn("enabled()", str(setting["lambda"]))
        self.assertIn("panel_buzzer).click()", str(config["touchscreen"][0]["on_touch"]))
        self.assertNotIn("on_update", config["touchscreen"][0])
        self.assertNotIn("click()", str(config["esphome"]["on_boot"]))
        self.assertNotIn("/sys/class/pwm", str(config))
        self.assertNotIn("/sys/class/gpio", str(config))
        self.assertNotIn("homeassistant.action", str(sound))
