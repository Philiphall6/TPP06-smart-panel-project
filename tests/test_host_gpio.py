"""Compile the host GPIO bridge against the installed ESPHome core headers.

Run with both 2026.10.2 and 2026.11.0. These are native contract tests only;
they do not build panel firmware or access Linux GPIO devices.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "esphome-components/host"


@unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
class HostGpioTests(unittest.TestCase):
    def test_main_thread_identity_across_translation_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "worker.cpp").write_text('''
#include "hal.h"
bool from_other_unit() { return esphome::is_main_loop_thread(); }
''')
            (root / "test.cpp").write_text('''
#include "hal.h"
#include <cassert>
bool from_other_unit();
void *worker(void *) {
  assert(!esphome::is_main_loop_thread());
  assert(!from_other_unit());
  return nullptr;
}
int main() {
  esphome::arch_init();
  assert(esphome::is_main_loop_thread() && from_other_unit());
  pthread_t thread;
  assert(pthread_create(&thread, nullptr, worker, nullptr) == 0);
  assert(pthread_join(thread, nullptr) == 0);
  assert(esphome::is_main_loop_thread() && from_other_unit());
}
''')
            subprocess.run(["g++", "-std=c++20", "-DUSE_HOST", "-pthread",
                            "-fno-threadsafe-statics", "-I", str(DRIVER),
                            str(root / "test.cpp"), str(root / "worker.cpp"),
                            "-o", str(root / "test")], check=True, timeout=30)
            subprocess.run([str(root / "test")], check=True, timeout=10)

    def test_real_core_contract_and_both_include_orders(self):
        try:
            import esphome
        except ImportError:
            self.skipTest("ESPHome core headers required")
        core = Path(esphome.__file__).parent / "core"
        for host_first in (False, True):
            with self.subTest(host_first=host_first), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                files = {
                    "esphome/core/gpio.h": (core / "gpio.h").read_text(),
                    "esphome/components/host/gpio.h": (DRIVER / "gpio.h").read_text(),
                    "esphome/components/host/gpio.cpp": (DRIVER / "gpio.cpp").read_text(),
                    "esphome/core/defines.h": "#pragma once\n",
                    "esphome/core/hal.h": '#pragma once\n#include "esphome/core/gpio.h"\n#define IRAM_ATTR\n',
                    "esphome/core/helpers.h": (
                        "#pragma once\n#include <cstddef>\n#include <cstdint>\n#include <cstdio>\n"
                        "#define ESPHOME_ALWAYS_INLINE __attribute__((always_inline))\n"
                    ),
                    "esphome/core/log.h": (
                        "#pragma once\n#define ESP_LOGD(...) ((void)0)\n"
                        "#define ESPHOME_LOG_LEVEL_CONFIG 0\n"
                        "namespace esphome {template<typename... T> void esp_log_printf_(T...) {}}\n"
                    ),
                }
                if (core / "gpio_pin.h").exists():
                    files["esphome/core/gpio_pin.h"] = (core / "gpio_pin.h").read_text()
                includes = ['#include "esphome/core/gpio.h"',
                            '#include "esphome/components/host/gpio.h"']
                if host_first:
                    includes.reverse()
                files["test.cpp"] = "\n".join(includes) + r'''
#include <cassert>
#include <cstring>
#include <type_traits>
void callback(int *) {}
int main() {
  static_assert(std::is_final_v<esphome::host::HostGPIOPin>);
  esphome::host::HostGPIOPin pin;
  pin.set_pin(7);
  pin.set_inverted(true);
  pin.set_flags(esphome::gpio::FLAG_OUTPUT);
  pin.setup();
  esphome::InternalGPIOPin *internal = &pin;
  esphome::GPIOPin *base = &pin;
  assert(base->is_internal() && internal->get_pin() == 7);
  assert(internal->is_inverted() && base->digital_read());
  assert(base->get_flags() == esphome::gpio::FLAG_OUTPUT);
  base->digital_write(false);
  char text[24];
  assert(base->dump_summary(text, sizeof(text)) == 5);
  assert(std::strcmp(text, "GPIO7") == 0);
  int value = 0;
  internal->attach_interrupt(callback, &value, esphome::gpio::INTERRUPT_ANY_EDGE);
  pin.attach_interrupt(callback, &value, esphome::gpio::INTERRUPT_ANY_EDGE);
  internal->detach_interrupt();
  auto isr = internal->to_isr();
  assert(isr.digital_read());
  isr.digital_write(false);
  isr.pin_mode(esphome::gpio::FLAG_INPUT);
  isr.clear_interrupt();
}
'''
                for name, text in files.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text)
                subprocess.run(["g++", "-std=c++20", "-DUSE_HOST", "-I", str(root),
                                str(root / "test.cpp"), str(root / "esphome/components/host/gpio.cpp"),
                                "-o", str(root / "test")], check=True, timeout=30)
                subprocess.run([str(root / "test")], check=True, timeout=10)
