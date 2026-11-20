"""Controller identity must not match diagnostic command strings."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'esphome-components'


class ProcessIdentityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('g++'), 'native C++ compiler required')
    def test_generated_umbrella_can_include_both_component_headers(self):
        # ESPHome's generated esphome.h includes every component header in
        # main.cpp. pragma once alone only protects each *individual file*.
        for first, second in (('tpp06_buzzer', 'tpp06_local_relays'),
                              ('tpp06_local_relays', 'tpp06_buzzer')):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as folder:
                path = Path(folder)
                # Avoid GCC's optional identical-file pragma-once shortcut.
                # The headers are separate resources, as they are for Clang.
                for component in (first, second):
                    (path/component).mkdir()
                    (path/component/'process_identity.h').write_text(
                        (ROOT/component/'process_identity.h').read_text() +
                        '\n// Component resource: '+component+'\n')
                source = (f'#include "{first}/process_identity.h"\n'
                          f'#include "{second}/process_identity.h"\n'
                          f'#include "{first}/process_identity.h"\n'
                          '#include <cassert>\n'
                          'int main() {\n'
                          'assert(esphome::tpp06_process_identity::stock_cmdline('
                          '"voice_control_ak3760e", sizeof("voice_control_ak3760e")-1));\n'
                          'assert(!esphome::tpp06_process_identity::stock_cmdline('
                          '"esphome", 7));\n}\n')
                (path/'main.cpp').write_text(source)
                result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                         '-I'+str(path), str(path/'main.cpp'),
                                         '-o', str(path/'test')],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                subprocess.run([str(path/'test')], check=True, capture_output=True, timeout=5)

    def test_standalone_driver_headers_remain_identical(self):
        self.assertEqual((ROOT/'tpp06_local_relays/process_identity.h').read_bytes(),
                         (ROOT/'tpp06_buzzer/process_identity.h').read_bytes())

    @unittest.skipUnless(shutil.which('g++'), 'native C++ compiler required')
    def test_real_names_block_but_diagnostics_do_not(self):
        source = r'''
#include "process_identity.h"
#include <cassert>
#include <initializer_list>
#include <string>
using esphome::tpp06_process_identity::stock_cmdline;
static bool check(std::initializer_list<const char *> args) {
  std::string line;
  for (auto arg : args) { line += arg; line += '\0'; }
  return stock_cmdline(line.data(), line.size());
}
int main() {
  assert(check({"/tuya/app/voice_control_ak3760e", "--start"}));
  assert(check({"voice_control_ak3760e"}));
  assert(check({"/tuya/app/tuya_monitor.sh"}));
  assert(check({"sh", "/tuya/app/tuya_monitor.sh", "start"}));
  assert(check({"/bin/sh", "-e", "/tuya/app/tuya_monitor.sh"}));
  assert(check({"/bin/sh", "--", "/tuya/app/tuya_monitor.sh"}));
  assert(check({"/bin/sh", "-o", "errexit", "/tuya/app/tuya_monitor.sh"}));
  assert(check({"/bin/busybox", "sh", "/tuya/app/tuya_monitor.sh"}));
  assert(!check({"sh", "-c", "pidof voice_control_ak3760e; ps | grep tuya_monitor.sh"}));
  assert(!check({"sh", "-lc", "cat /tmp/tuya_monitor.sh"}));
  assert(!check({"sh", "-c", "tuya_monitor.sh"}));
  assert(!check({"pidof", "voice_control_ak3760e"}));
  assert(!check({"grep", "tuya_monitor.sh"}));
  assert(!check({"cat", "/tuya/app/tuya_monitor.sh"}));
  assert(!check({"sh", "/tmp/diagnostic.sh", "tuya_monitor.sh"}));
  assert(!check({"/bin/tuya_factory", "-p", "20480"}));
  assert(!check({"/data/esphome"}));
  assert(!check({"/tmp/voice_control_ak3760e.backup"}));
  assert(!check({"/tmp/not_tuya_monitor.sh"}));
  assert(!check({"sh", "--"}));
  assert(!check({"busybox"}));
  assert(!stock_cmdline("", 0));
  // Reading a 512-byte prefix of a long SSH command must not lock controls.
  std::string long_cmd("sh\0-c\0", 6);
  long_cmd += "pidof voice_control_ak3760e; ";
  long_cmd += std::string(600, 'x');
  assert(!stock_cmdline(long_cmd.data(), 511));
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'test.cpp').write_text(source)
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined',
                            '-I'+str(ROOT/'tpp06_local_relays'), str(path/'test.cpp'),
                            '-o', str(path/'test')], check=True, capture_output=True, timeout=30)
            subprocess.run([str(path/'test')], check=True, capture_output=True, timeout=5)
