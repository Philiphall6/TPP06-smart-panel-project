"""Relay tests use mocked files/events only. Never connect to a panel."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_fbdev_present import COMPONENT

ROOT = Path(__file__).resolve().parents[1]
SWITCH = r'''
#pragma once
namespace esphome::switch_ {
class Switch {
 public:
  virtual ~Switch() = default;
  void publish_state(bool value) { state = value; ++publications; }
  void turn_on() { write_state(true); }
  void turn_off() { write_state(false); }
  bool state = false;
  int publications = 0;
 protected:
  virtual void write_state(bool) = 0;
};
}
'''
PROGRAM = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstring>
#include <deque>
#include <dirent.h>
#include <fcntl.h>
#include <linux/input.h>
#include <map>
#include <string>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/utsname.h>
#include "local_relays.h"
#include "esphome/components/text_sensor/text_sensor.h"
using namespace esphome::tpp06_local_relays;
struct Event { int32_t sec, us; uint16_t type, code; int32_t value; };
struct File { std::string path; size_t offset; int flags; };
static std::map<std::string, std::string> fs;
static std::map<int, File> files;
static std::deque<Event> events;
static std::array<bool, 3> held{};
static uint32_t now = 0;
static int writes = 0, led_writes = 0, next_fd = 100;
static bool stock = false, stock_iter = false, bad_kernel = false, bad_keys = false;
static std::string process_command = "voice_control_ak3760e";
static bool short_write = false, wrong_readback = false, short_event = false, lock_busy = false;
static bool lock_read_only = false;
static bool mute_value = false, mute_supported = true;
namespace esphome { uint32_t millis() { return now; } }

extern "C" int __wrap_uname(struct utsname *u) {
  std::memset(u, 0, sizeof(*u));
  std::strcpy(u->release, bad_kernel ? "unknown" : "4.4.192V2.4");
  std::strcpy(u->machine, "armv5tejl"); return 0;
}
extern "C" DIR *__wrap_opendir(const char *p) {
  assert(std::string(p) == "/proc"); stock_iter = false; return reinterpret_cast<DIR*>(1);
}
extern "C" struct dirent *__wrap_readdir(DIR *) {
  static struct dirent entry{};
  if (!stock || stock_iter) return nullptr;
  stock_iter = true; std::strcpy(entry.d_name, "123"); return &entry;
}
extern "C" int __wrap_closedir(DIR *) { return 0; }
extern "C" int __wrap_open(const char *p, int flags, ...) {
  std::string path(p);
  if (path == "/dev/input/event0") { assert((flags & O_ACCMODE) == O_RDONLY); return 80; }
  assert(path != "/run/tpp06-local-relays.lock"); // Stock /run is read-only squashfs.
  if (path == "/var/run/tpp06-local-relays.lock") {
    if (lock_read_only) { errno = EROFS; return -1; }
    return 81;
  }
  if (path == "/proc/123/cmdline") fs[path] = process_command;
  if (!fs.count(path)) { errno = ENOENT; return -1; }
  if ((flags & O_ACCMODE) == O_WRONLY) {
    assert((path.find("/sys/class/gpio/KC_CTL") == 0 && path.substr(path.size()-6) == "/value") ||
           (path.find("/sys/class/leds/button") == 0 && path.substr(path.size()-11) == "/brightness"));
    assert(!(flags & (O_CREAT | O_TRUNC))); // No GPIO export/direction/LED/NAND writes.
  }
  int fd = next_fd++; files[fd] = {path, 0, flags}; return fd;
}
extern "C" int __wrap_close(int fd) { files.erase(fd); return 0; }
extern "C" int __wrap_flock(int fd, int op) {
  assert(fd == 81 && op == (LOCK_EX | LOCK_NB)); return lock_busy ? -1 : 0;
}
extern "C" ssize_t __wrap_read(int fd, void *buf, size_t count) {
  if (fd == 80) {
    assert(count == 16);
    if (short_event) return 8;
    if (events.empty()) { errno = EAGAIN; return -1; }
    std::memcpy(buf, &events.front(), 16); events.pop_front(); return 16;
  }
  assert(files.count(fd)); auto &f = files[fd]; auto &data = fs[f.path];
  size_t size = std::min(count, data.size() - f.offset);
  std::memcpy(buf, data.data() + f.offset, size); f.offset += size; return size;
}
extern "C" ssize_t __wrap_write(int fd, const void *buf, size_t size) {
  assert(files.count(fd) && (files[fd].flags & O_ACCMODE) == O_WRONLY);
  if (files[fd].path.find("/sys/class/leds/") == 0) {
    ++led_writes; fs[files[fd].path] = std::string(static_cast<const char*>(buf),size); return size;
  }
  assert(size == 2); std::string data(static_cast<const char*>(buf), size);
  assert(data == "0\n" || data == "1\n"); ++writes;
  if (!wrong_readback) fs[files[fd].path] = data;
  return short_write ? 1 : 2;
}
extern "C" int __wrap_ioctl(int fd, unsigned long request, ...) {
  assert(fd == 80);
  va_list ap; va_start(ap, request); void *arg = va_arg(ap, void*); va_end(ap);
  constexpr size_t n = (KEY_MAX+8)/8;
  constexpr size_t sw_n = (SW_MAX+8)/8;
  if (request == EVIOCGBIT(EV_SW,sw_n) || request == EVIOCGSW(sw_n)) {
    std::memset(arg, 0, sw_n);
    if (!mute_supported) return -1;
    if (request == EVIOCGBIT(EV_SW,sw_n) || mute_value)
      static_cast<unsigned char*>(arg)[SW_MUTE_DEVICE/8] |= 1U << (SW_MUTE_DEVICE%8);
    return sw_n;
  }
  if (request == EVIOCGNAME(64)) { std::strcpy(static_cast<char*>(arg), bad_keys ? "goodix-ts" : "gpiokeys"); return 9; }
  if (request == EVIOCGKEY(n) || request == EVIOCGBIT(EV_KEY,n)) {
    std::memset(arg, 0, n); auto *bits = static_cast<unsigned char*>(arg);
    for (int i=0; i<3; ++i) if (request == EVIOCGBIT(EV_KEY,n) || held[i])
      bits[(KEY_F1+i)/8] |= 1U << ((KEY_F1+i)%8);
    return n;
  }
  assert(false); return -1;
}
static std::string value_path(int i) { return "/sys/class/gpio/KC_CTL" + std::to_string(i+1) + "/value"; }
static void reset() {
  fs.clear(); files.clear(); events.clear(); held = {}; now = 0; writes = led_writes = 0;
  stock = bad_kernel = bad_keys = short_write = wrong_readback = short_event = lock_busy = false;
  process_command = "voice_control_ak3760e";
  for (int i=0; i<3; ++i) {
    std::string base = "/proc/device-tree/gpio_export/kc_ctl" + std::to_string(i+1);
    std::string gpio(12, '\0'); gpio[3] = 6; gpio[7] = 65+i; fs[base+"/gpios"] = gpio;
    fs[base+"/gpio-export,name"] = "KC_CTL" + std::to_string(i+1) + '\0';
    base = "/sys/class/gpio/KC_CTL" + std::to_string(i+1);
    fs[base+"/direction"] = "out\n"; fs[base+"/active_low"] = "0\n"; fs[base+"/value"] = "0\n";
    const int pins[] = {6,85,79}; gpio[7] = pins[i];
    base = "/proc/device-tree/leds/button" + std::to_string(i+1) + "_led";
    fs[base+"/gpios"] = gpio;
    base = "/sys/class/leds/button" + std::to_string(i+1) + "_led";
    fs[base+"/max_brightness"] = "255\n"; fs[base+"/brightness"] = "255\n";
  }
}
struct Fixture {
  LocalRelays hub; RelaySwitch relay[3];
  Fixture(bool enabled=true, uint32_t pulse=0) {
    for (int i=0; i<3; ++i) hub.set_relay(i, &relay[i]);
    hub.set_control_enabled(enabled); hub.set_pulse_duration(0,pulse);
  }
  ~Fixture() { hub.on_shutdown(); }
  void event(int code, int value) { events.push_back({0,0,EV_KEY,uint16_t(code),value}); hub.loop(); }
};
int main() {
  reset();
  { stock = true;
    const char diagnostic[] = "sh\0-c\0pidof voice_control_ak3760e; ps | grep tuya_monitor.sh";
    process_command.assign(diagnostic, sizeof(diagnostic));
    Fixture f; f.hub.setup(); assert(f.hub.control_available());
    now = 2000; f.hub.loop(); assert(f.hub.control_available());
    f.event(KEY_F1, 1); assert(writes == 1 && f.relay[0].state);
    process_command = "voice_control_ak3760e";
    now = 4000; f.hub.loop(); assert(!f.hub.control_available());
    f.event(KEY_F2, 1); assert(writes == 1);
  }
  reset();
  { Fixture f; esphome::text_sensor::TextSensor sensor; f.hub.set_mute_sensor(&sensor);
    f.hub.setup(); assert(sensor.state=="Inactif" && writes==0);
    events.push_back({0,0,EV_SW,SW_MUTE_DEVICE,1}); f.hub.loop();
    assert(sensor.state=="Actif" && writes==0);
    events.push_back({0,0,EV_SYN,SYN_DROPPED,0}); f.hub.loop();
    assert(sensor.state=="Indisponible");
    events.push_back({0,0,EV_SW,SW_MUTE_DEVICE,1}); f.hub.loop();
    assert(sensor.state=="Indisponible");
    events.push_back({0,0,EV_SYN,SYN_REPORT,0}); f.hub.loop();
    assert(sensor.state=="Inactif" && writes==0 && f.hub.control_available());
  }
  reset(); mute_supported=false;
  { Fixture f; esphome::text_sensor::TextSensor sensor; f.hub.set_mute_sensor(&sensor);
    f.hub.setup(); assert(sensor.state=="Indisponible" && f.hub.control_available());
    f.event(KEY_F1,1); assert(writes==1);
  }
  mute_supported=true;
  reset();
  {
    fs[value_path(1)] = "1\n";
    Fixture f; f.hub.setup(); assert(writes == 0 && f.relay[1].state);
    assert(led_writes==3 && fs["/sys/class/leds/button1_led/brightness"]=="0\n");
    events.push_back({0,0,EV_SW,SW_MUTE_DEVICE,1}); f.hub.loop(); assert(writes==0);
    f.event(KEY_F1,1); assert(writes == 1 && f.relay[0].state);
    assert(fs["/sys/class/leds/button1_led/brightness"]=="255\n");
    f.event(KEY_F1,1); f.event(KEY_F1,2); assert(writes == 1);
    f.event(KEY_F1,0); now=50; f.event(KEY_F1,1); assert(writes == 1); // bounce
    f.event(KEY_F1,0); now=200; f.event(KEY_F1,1); assert(writes == 2 && !f.relay[0].state);
    f.relay[0].turn_on(); assert(writes == 3 && f.relay[0].state);
    f.relay[0].turn_on(); assert(writes == 3);
    f.relay[0].turn_off(); assert(writes == 4 && !f.relay[0].state);
    f.hub.set_key_channel(2,1); f.event(KEY_F3,1); assert(writes == 5 && !f.relay[1].state);
    now=1000; f.hub.loop(); assert(writes == 5); // No network exists in this test.
    f.hub.on_shutdown(); assert(writes == 5);
    f.relay[2].turn_on(); assert(writes == 5);
  }
  reset();
  { Fixture f(false); f.hub.setup(); f.event(KEY_F1,1); f.relay[1].turn_on(); assert(writes==0 && led_writes==0); }
  reset();
  { Fixture f; f.hub.set_indicators_follow_relay(false); f.hub.setup(); f.relay[0].turn_on();
    assert(writes==1 && led_writes==3 && fs["/sys/class/leds/button1_led/brightness"]=="0\n"); }
  reset();
  { fs.erase("/sys/class/leds/button1_led/brightness"); Fixture f; f.hub.setup();
    f.relay[0].turn_on(); assert(writes==1 && !f.hub.warning); }
  for (int failure=0; failure<7; ++failure) {
    reset();
    if (failure==0) bad_kernel=true;
    if (failure==1) bad_keys=true;
    if (failure==2) fs[value_path(0)]="invalid";
    if (failure==3) stock=true;
    if (failure==4) lock_busy=true;
    if (failure==5) fs["/proc/device-tree/gpio_export/kc_ctl1/gpios"][7]=99;
    if (failure==6) lock_read_only=true;
    Fixture f; f.hub.setup(); f.relay[0].turn_on(); f.event(KEY_F1,1);
    assert(writes==0 && f.hub.warning);
    lock_read_only=false;
  }
  reset();
  { Fixture f; f.hub.setup(); stock=true; f.relay[0].turn_on(); stock=false;
    f.relay[0].turn_on(); assert(writes==0 && f.hub.warning); }
  reset();
  { Fixture f; f.hub.setup(); fs["/sys/class/gpio/KC_CTL1/active_low"]="1\n";
    f.relay[0].turn_on(); assert(writes==0 && f.hub.warning); }
  for (bool short_io : {false,true}) {
    reset(); Fixture f; f.hub.setup(); short_write=short_io; wrong_readback=!short_io;
    f.relay[0].turn_on(); assert(writes==1 && f.hub.warning);
    f.relay[0].turn_on(); assert(writes==1);
    assert(f.relay[0].state==short_io); // Report actual readback, never requested state.
  }
  reset();
  { held[0]=true; Fixture f; f.hub.setup(); f.event(KEY_F1,1); assert(writes==0);
    f.event(KEY_F1,0); f.event(KEY_F1,1); assert(writes==1); }
  reset();
  { Fixture f; f.hub.setup(); held[0]=true;
    events.push_back({0,0,EV_SYN,SYN_DROPPED,0});
    events.push_back({0,0,EV_KEY,KEY_F1,1});
    events.push_back({0,0,EV_SYN,SYN_REPORT,0}); f.hub.loop(); assert(writes==0);
    f.event(KEY_F1,1); assert(writes==0); f.event(KEY_F1,0); f.event(KEY_F1,1); assert(writes==1); }
  reset();
  { Fixture f; f.hub.setup(); short_event=true; f.hub.loop(); f.relay[0].turn_on(); assert(writes==0 && f.hub.warning); }
  reset();
  { Fixture f(true,500); f.hub.setup(); f.relay[0].turn_on(); assert(writes==1);
    now=400; f.relay[0].turn_on(); f.hub.loop(); assert(writes==1);
    now=500; f.hub.loop(); assert(writes==2 && !f.relay[0].state); }
  reset();
  { fs[value_path(0)]="1\n"; Fixture f(true,500); f.hub.setup(); now=1000; f.hub.loop();
    assert(writes==0 && f.relay[0].state); // Never switch inherited state implicitly.
    f.relay[0].turn_on(); now=1500; f.hub.loop(); assert(writes==1 && !f.relay[0].state); }
  reset();
  { Fixture f(true,500); f.hub.setup(); now=0xffffff00; f.relay[0].turn_on();
    now=244; f.hub.loop(); assert(writes==2 && !f.relay[0].state); }
  reset();
  { Fixture f; f.hub.setup(); now=0xfffffff0; f.event(KEY_F1,1); f.event(KEY_F1,0);
    now=10; f.event(KEY_F1,1); assert(writes==1); f.event(KEY_F1,0);
    now=200; f.event(KEY_F1,1); assert(writes==2); }
  reset();
  { Fixture f(true,500); f.hub.setup(); f.relay[0].turn_on();
    now=200; f.relay[0].turn_off(); now=900; f.hub.loop(); assert(writes==2); }
}
'''


class LocalRelayNativeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native g++ required for mocked test")
    def test_real_driver_with_mocked_sysfs_and_keys(self):
        with tempfile.TemporaryDirectory(prefix="tpp06-relays-test-") as folder:
            base = Path(folder)
            for name, content in {
                "esphome/core/component.h": COMPONENT,
                "esphome/components/switch/switch.h": SWITCH,
                "esphome/components/text_sensor/text_sensor.h": '#pragma once\n#include <string>\nnamespace esphome::text_sensor {class TextSensor {public:std::string state;void publish_state(const std::string &v){state=v;}};}\n',
                "esphome/core/hal.h": '#include <cstdint>\nnamespace esphome { uint32_t millis(); }\n',
                "esphome/core/log.h": '\n'.join('#define '+macro+'(...) ((void)0)' for macro in
                    ("ESP_LOGE", "ESP_LOGW", "ESP_LOGI", "ESP_LOGCONFIG"))+'\n',
                "test.cpp": PROGRAM,
            }.items():
                path = base/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
            driver = ROOT/"esphome-components/tpp06_local_relays"
            binary = base/"test"
            command = ["g++", "-std=c++17", "-DUSE_HOST", "-DUSE_TPP06_MUTE_INPUT", "-I"+str(base), "-I"+str(driver),
                       str(base/"test.cpp"), str(driver/"local_relays.cpp"), "-o", str(binary)]
            command += ["-Wl,--wrap="+name for name in (
                "uname", "opendir", "readdir", "closedir", "open", "close", "flock", "read", "write", "ioctl")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)


try:
    from esphome import yaml_util
    from esphome.config import validate_config
    from esphome.core import CORE
except ImportError:
    CORE = None


@unittest.skipIf(CORE is None, "ESPHome environment required")
class LocalRelayConfigTests(unittest.TestCase):
    def setUp(self):
        CORE.reset(); self.addCleanup(CORE.reset)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        CORE.config_path = Path(self.tmp.name)/"panel.yaml"
        CORE.config_path.write_text("esphome:\n  name: panel\n")
        self.config = yaml_util.load_yaml(ROOT/"esphome/packages/local-relays-experimental.yaml")
        self.config.update({"esphome": {"name": "panel"}, "host": {}, "external_components": [{
            "source": {"type": "local", "path": str(ROOT/"esphome-components")},
            "components": ["tpp06_local_relays", "host"],
        }]})

    def test_package_validates_and_generates_three_native_switches(self):
        result = validate_config(self.config, {})
        self.assertFalse(result.errors, str(result.errors))
        self.assertFalse(result["tpp06_local_relays"]["control_enabled"])
        self.assertTrue(all(s["pulse_duration"].total_milliseconds == 0 for s in result["switch"]))
        CORE.config = result
        from esphome.__main__ import generate_cpp_contents
        generate_cpp_contents(result)
        cpp = CORE.cpp_main_section
        self.assertIn("set_control_enabled(false)", cpp)
        self.assertEqual(cpp.count("tpp06_local_relays::RelaySwitch();"), 3)
        self.assertNotIn("homeassistant.service", cpp)

    def test_duplicate_channel_rejected(self):
        self.config["switch"][1]["channel"] = 1
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_invalid_key_mapping_rejected(self):
        self.config["tpp06_local_relays"]["key_map"] = [1, 1, 3]
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_automatic_restore_rejected(self):
        self.config["switch"][0]["restore_mode"] = "ALWAYS_ON"
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_pulse_duration_bound(self):
        self.config["switch"][0]["pulse_duration"] = "61s"
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_valid_inching(self):
        self.config["switch"][0]["pulse_duration"] = "500ms"
        result = validate_config(self.config, {})
        self.assertFalse(result.errors, str(result.errors))
        self.assertEqual(result["switch"][0]["pulse_duration"].total_milliseconds, 500)

    def test_api_disconnection_must_not_reboot_local_switches(self):
        self.config["api"]["reboot_timeout"] = "15min"
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_missing_channel_rejected(self):
        self.config["switch"].pop()
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_gpio_inversion_rejected(self):
        self.config["switch"][0]["inverted"] = True
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_invalid_indicator_mode_rejected(self):
        self.config["tpp06_local_relays"]["indicator_mode"] = "blink"
        self.assertTrue(validate_config(self.config, {}).errors)

    def test_package_merges_with_existing_ui_templates(self):
        for name in ("tpp06-lvgl-mobile.yaml", "tpp06-lvgl-modern.yaml"):
            with self.subTest(name=name):
                CORE.reset()
                CORE.config_path = Path(self.tmp.name)/"panel.yaml"
                CORE.config_path.write_text((ROOT/"esphome"/name).read_text())
                CORE.config_path.with_name("secrets.yaml").write_text(
                    "tpp06_api_encryption_key: MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=\n")
                config = yaml_util.load_yaml(CORE.config_path)
                config["external_components"][0]["source"] = {
                    "type": "local", "path": str(ROOT/"esphome-components")}
                config["external_components"][0]["components"].append("tpp06_local_relays")
                config["packages"] = {"local_relays": yaml_util.load_yaml(
                    ROOT/"esphome/packages/local-relays-experimental.yaml")}
                result = validate_config(config,{})
                self.assertFalse(result.errors, str(result.errors))
                switches = [s for s in result["switch"] if s["platform"] == "tpp06_local_relays"]
                self.assertEqual(len(switches), 3)
                self.assertIn("encryption", result["api"])
