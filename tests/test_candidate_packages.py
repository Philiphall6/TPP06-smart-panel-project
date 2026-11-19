"""Candidate packages are local-only: no network, flashing or relay action."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    from esphome import yaml_util
    from esphome.config import validate_config
    from esphome.core import CORE
except ImportError:
    CORE = None


@unittest.skipIf(CORE is None, "ESPHome Python environment required")
class CandidateConfigTests(unittest.TestCase):
    def test_complete_release_entrypoint_without_remote_download(self):
        CORE.reset()
        self.addCleanup(CORE.reset)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            CORE.config_path = root / "complete.yaml"
            CORE.config_path.write_text((ROOT / "esphome/tpp06-lvgl-complete.yaml").read_text())
            (root / "secrets.yaml").write_text(
                "tpp06_api_encryption_key: MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=\n")
            config = yaml_util.load_yaml(CORE.config_path)
            release = config["packages"]["release"]
            self.assertEqual(release["ref"], "v0.1.7")
            packages = {}
            for index, name in enumerate(release["files"]):
                item = yaml_util.load_yaml(ROOT / name)
                for component in item.get("external_components", []):
                    self.assertEqual(component["source"]["ref"], release["ref"])
                    component["source"] = {"type": "local", "path": str(ROOT / "esphome-components")}
                packages[f"part{index}"] = item
            config["packages"] = packages
            config["external_components"][0]["source"] = {
                "type": "local", "path": str(ROOT / "esphome-components")}
            result = validate_config(config, {})
            self.assertFalse(result.errors, str(result.errors))
            self.assertFalse(result["tpp06_local_relays"]["control_enabled"])
            self.assertEqual(result["esphome"]["project"]["version"], "0.1.7")
            self.assertEqual(len(result["lvgl"][0]["pages"]), 14)
            CORE.config = result
            from esphome.__main__ import generate_cpp_contents
            generate_cpp_contents(result)
            for marker in ("panel_ble_proxy", "screen_brightness_control", "set_control_enabled(false)"):
                self.assertIn(marker, CORE.cpp_main_section)

    def test_complete_candidate_with_observation_and_no_relay_enable(self):
        CORE.reset()
        self.addCleanup(CORE.reset)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            CORE.config_path = root / "candidate.yaml"
            CORE.config_path.write_text((ROOT / "esphome/tpp06-lvgl-modern.yaml").read_text())
            (root / "secrets.yaml").write_text(
                "tpp06_api_encryption_key: MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=\n")
            config = yaml_util.load_yaml(CORE.config_path)
            config["external_components"][0]["source"] = {
                "type": "local", "path": str(ROOT / "esphome-components")}
            config["external_components"][0]["components"].extend(["tpp06_health", "tpp06_local_relays", "bluetooth_proxy"])
            names = ["local-relays-experimental", "runtime-health", "mute-input-observation", "local-controls-ui", "driver-diagnostics", "screen-controls", "linux-ble"]
            config["packages"] = {name: yaml_util.load_yaml(ROOT / f"esphome/packages/{name}.yaml") for name in names}
            result = validate_config(config, {})
            self.assertFalse(result.errors, str(result.errors))
            self.assertFalse(result["tpp06_local_relays"]["control_enabled"])
            CORE.config = result
            from esphome.__main__ import generate_cpp_contents
            generate_cpp_contents(result)
            cpp = CORE.cpp_main_section
            self.assertIn("set_heartbeat(true)", cpp)
            self.assertIn("set_wifi_signal_via_wpa(true)", cpp)
            self.assertIn("set_link(", cpp)
            self.assertIn("local_wifi_editor_health", cpp)
            self.assertIn("set_mute_sensor(", cpp)
            self.assertIn("control_available()", cpp)
            self.assertIn("quiet_hours(", cpp)
            self.assertIn("set_control_enabled(false)", cpp)
            self.assertIn("screen_brightness_control", cpp)
            self.assertIn("screen_sleep_control", cpp)
            self.assertIn("screen_wake_control", cpp)
            self.assertIn("is_paused()", cpp)
            self.assertIn("panel_ble_proxy", cpp)
            self.assertEqual(len(result["lvgl"][0]["pages"]), 14)
            self.assertEqual(result["api"]["reboot_timeout"].total_milliseconds, 0)
            # A slow polling interval must not accidentally arm a permanently
            # expired heartbeat when the Linux policy is commissioned later.
            from esphome.components.tpp06_health import CONFIG_SCHEMA
            import esphome.config_validation as cv
            for interval in ("100ms", "30s", "60s"):
                with self.assertRaises(cv.Invalid):
                    CONFIG_SCHEMA({"heartbeat": True, "update_interval": interval})
            CONFIG_SCHEMA({"heartbeat": False, "update_interval": "60s"})


class QuietHoursTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_boundaries_clock_invalid_and_overnight(self):
        code = r'''
#include "quiet_hours.h"
#include <cassert>
using esphome::tpp06_buzzer::quiet_hours;
int main() {
 assert(!quiet_hours(false,false,0,22,7));
 assert(quiet_hours(true,false,0,22,7));
 for(int minute=0;minute<1440;++minute) {
   assert(quiet_hours(true,true,minute,22,7)==(minute>=1320 || minute<420));
   assert(quiet_hours(true,true,minute,8,9)==(minute>=480 && minute<540));
   assert(quiet_hours(true,true,minute,8,8));
 }
 assert(quiet_hours(true,true,-1,22,7));
 assert(quiet_hours(true,true,1440,22,7));
 assert(quiet_hours(true,true,500,-1,7));
 assert(quiet_hours(true,true,500,22,24));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.cpp").write_text(code)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I",
                            str(ROOT / "esphome-components/tpp06_buzzer"), str(root / "test.cpp"),
                            "-o", str(root / "test")], check=True)
            subprocess.run([str(root / "test")], check=True, timeout=5)
