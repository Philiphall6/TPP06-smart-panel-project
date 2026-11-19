"""Exercise the actual YAML lambdas without hardware, HA or firmware upload."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

try:
    from esphome import yaml_util
except ImportError:
    yaml_util = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(yaml_util is None, "ESPHome Python environment required")
class ScreenControlsTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml_util.load_yaml(ROOT / "esphome/packages/screen-controls.yaml")

    def test_no_competing_restore_or_startup_actions(self):
        self.assertNotIn("esphome", self.config)
        self.assertNotIn("globals", self.config)
        for kind in ("number", "select"):
            for entity in self.config[kind]:
                self.assertNotIn("restore_value", entity)
                self.assertNotIn("optimistic", entity)
                self.assertEqual(str(entity["update_interval"]), "1s")
        self.assertEqual(self.config["number"][0]["min_value"], 10)
        self.assertEqual(self.config["number"][0]["max_value"], 100)
        wake = self.config["button"][0]["on_press"][0]["if"]
        self.assertIn("available()", str(wake["condition"]["lambda"]))
        self.assertEqual(wake["then"], [{"lvgl.resume": None}])

    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_real_lambdas_sync_and_reject_failed_commands(self):
        number = self.config["number"][0]
        select = self.config["select"][0]
        state = self.config["binary_sensor"][0]
        code = r'''
#include <cassert>
#include <cmath>
#include <limits>
#include <optional>
#include <string>
#define id(name) name
struct Backlight {
  bool present = true, write_ok = true, sleeping = false;
  int last = 100, writes = 0;
  bool available() const { return present; }
  bool set_percent(int value) {
    ++writes;
    if (!write_ok) return false;
    last = value;
    return true;
  }
} panel_backlight;
struct UI { bool paused = false; bool is_paused() const { return paused; } } mobile_ui;
int mobile_brightness = 100, mobile_sleep_choice = 0;
struct Number { int published = -1; void publish_state(int n) { published = n; } } screen_brightness_control;
struct Select { std::string published; void publish_state(const std::string &s) { published = s; } } screen_sleep_control;
'''
        code += "\nfloat read_brightness() {\n" + str(number["lambda"]) + "\n}\n"
        code += "void set_brightness(float x) {\n" + str(number["set_action"][0]["lambda"]) + "\n}\n"
        code += "std::optional<std::string> read_sleep() {\n" + str(select["lambda"]) + "\n}\n"
        code += "void set_sleep(const std::string &x) {\n" + str(select["set_action"][0]["lambda"]) + "\n}\n"
        code += "std::optional<bool> read_state() {\n" + str(state["lambda"]) + "\n}\n"
        code += r'''
int main() {
  assert(read_brightness() == 100);
  set_brightness(40);
  assert(mobile_brightness == 40 && screen_brightness_control.published == 40);
  mobile_brightness = 65; // Change from the panel's own settings.
  assert(read_brightness() == 65);
  int writes = panel_backlight.writes;
  for (float value : {NAN, INFINITY, -INFINITY, 0.0f, 9.0f, 101.0f}) set_brightness(value);
  assert(panel_backlight.writes == writes && mobile_brightness == 65);
  panel_backlight.write_ok = false;
  set_brightness(80);
  assert(mobile_brightness == 65 && screen_brightness_control.published == 40);
  panel_backlight.write_ok = true;
  panel_backlight.sleeping = true;
  set_brightness(30);
  assert(panel_backlight.sleeping && mobile_brightness == 30);
  const char *options[] = {"Jamais", "30 secondes", "1 minute", "2 minutes", "5 minutes"};
  for (int i = 0; i < 5; ++i) {
    set_sleep(options[i]);
    assert(mobile_sleep_choice == i && read_sleep().value() == options[i]);
    assert(screen_sleep_control.published == options[i]);
  }
  set_sleep("invalid");
  assert(mobile_sleep_choice == 4);
  mobile_sleep_choice = 2; // Local UI change is visible without another restore.
  assert(read_sleep().value() == "1 minute");
  mobile_sleep_choice = 5;
  assert(!read_sleep().has_value());
  mobile_sleep_choice = -1;
  assert(!read_sleep().has_value());
  assert(read_state().has_value() && !read_state().value());
  mobile_ui.paused = true;
  assert(read_state().value());
  panel_backlight.present = false;
  assert(std::isnan(read_brightness()) && !read_state().has_value());
  writes = panel_backlight.writes;
  set_brightness(60);
  assert(panel_backlight.writes == writes && mobile_brightness == 30);
  set_sleep("Jamais");
  assert(mobile_sleep_choice == 0);
  set_sleep("30 secondes");
  assert(mobile_sleep_choice == 0);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "test.cpp").write_text(code)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(folder / "test.cpp"), "-o", str(folder / "test")], check=True)
            subprocess.run([str(folder / "test")], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
