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
    def test_local_configuration_and_diagnostics(self):
        root = Path(__file__).resolve().parents[1]
        CORE.reset()
        self.addCleanup(CORE.reset)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        CORE.config_path = Path(temporary.name) / "tpp06-lvgl.yaml"
        CORE.config_path.write_text((root / "esphome/tpp06-lvgl.yaml").read_text())
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
