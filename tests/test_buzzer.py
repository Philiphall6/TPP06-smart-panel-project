"""Native simulated sound tests. No panel connection, sysfs write or firmware build."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_fbdev_present import COMPONENT

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "esphome-components/tpp06_buzzer"
PROGRAM = r'''
#include <cassert>
#include <string>
#include <vector>
#include "pulse.h"
using namespace esphome::tpp06_buzzer;
struct Fake : PulseIO {
  std::atomic<bool> enabled{true};
  std::vector<std::string> events;
  int count=0, fail_at=-1, cancel_at=-1, waits=0;
  bool refuse_claim=false, refuse_export=false, refuse_stop=false;
  bool output=false, released=false, removed=false;
  int gate1=0, gate2=0;
  int period=0, duty=0;
  bool step(std::string name) {
    events.push_back(name); ++count;
    if (count==cancel_at) enabled.store(false);
    return count!=fail_at;
  }
  bool claim() override { events.push_back("claim"); return !refuse_claim; }
  bool export_channel() override { events.push_back("export"); return !refuse_export; }
  bool read_pwm(const char *key, int &value) override {
    if (!step(std::string("read:")+key)) return false;
    value=std::string(key)=="period"?period:duty; return true;
  }
  bool pwm(const char *key,int value) override {
    bool ok=step(std::string(key)+"="+std::to_string(value));
    // Linux 4.4 pwm_config rejects even duty=0 when period is zero.
    if (std::string(key)=="duty_cycle") {
      if (period<=0 || value<0 || value>period) return false;
      if (ok) duty=value;
    }
    if (std::string(key)=="period") {
      if (value<=0 || duty>value) return false;
      if (ok) period=value;
    }
    if (std::string(key)=="enable") {
      if (!value && refuse_stop && output) return false;
      if (ok) output=value;
    }
    return ok;
  }
  bool gate(unsigned channel,int value) override {
    bool ok=step("gate"+std::to_string(channel)+"="+std::to_string(value));
    if (ok) (channel==1?gate1:gate2)=value;
    return ok;
  }
  bool pause_500us() override { ++waits; return step("wait"); }
  bool unexport_channel() override { assert(!output); removed=true; return step("unexport"); }
  void release() override { events.push_back("release"); released=true; }
};
int main() {
  Fake normal;
  assert(play_click(normal,normal.enabled));
  assert(normal.waits==8 && normal.removed && normal.released);
  assert(!normal.output && !normal.gate1 && !normal.gate2);
  const std::vector<std::string> prefix={"claim","export","enable=0","read:period","read:duty_cycle",
    "period=210526","duty_cycle=105250","gate1=0","gate2=1","enable=1"};
  assert(std::vector<std::string>(normal.events.begin(),normal.events.begin()+prefix.size())==prefix);
  assert(play_click(normal,normal.enabled)); // Retained state after unexport/re-export.
  Fake old_sequence;
  assert(!old_sequence.pwm("duty_cycle",0)); // Regression: previous implementation fails.
  Fake retained; retained.period=1000000; retained.duty=500000;
  assert(play_click(retained,retained.enabled));
  assert(retained.events[5]=="duty_cycle=105250" && retained.events[6]=="period=210526");
  Fake invalid; invalid.period=0; invalid.duty=1;
  assert(!play_click(invalid,invalid.enabled) && invalid.removed && !invalid.output);
  Fake disabled; disabled.enabled=false;
  assert(play_click(disabled,disabled.enabled) && disabled.events.empty());
  Fake busy; busy.refuse_claim=true;
  assert(!play_click(busy,busy.enabled) && busy.events.size()==1);
  Fake no_export; no_export.refuse_export=true;
  assert(!play_click(no_export,no_export.enabled) && no_export.released && no_export.count==0);
  // Each programming or waiting failure still reaches the stop/gate cleanup.
  for (int failure=1;failure<=16;++failure) {
    Fake f; f.fail_at=failure;
    assert(!play_click(f,f.enabled));
    assert(!f.output && !f.gate1 && !f.gate2 && f.released && f.removed);
  }
  // Cancellation during configuration or playback never queues another sound.
  for (int cancel=1;cancel<=16;++cancel) {
    Fake f; f.cancel_at=cancel;
    assert(play_click(f,f.enabled));
    assert(!f.output && !f.gate1 && !f.gate2 && f.released);
    assert(f.waits<=8);
  }
  Fake retry_stop; retry_stop.fail_at=17;
  assert(play_click(retry_stop,retry_stop.enabled));
  assert(!retry_stop.output && !retry_stop.gate2 && retry_stop.removed);
  // Failures in cleanup are reported, but must not skip subsequent cleanup.
  for (int failure=18;failure<=20;++failure) {
    Fake f; f.fail_at=failure;
    assert(!play_click(f,f.enabled));
    assert(!f.output && f.released);
    assert(f.events.back()=="release");
  }
  Fake stuck; stuck.refuse_stop=true;
  assert(!play_click(stuck,stuck.enabled));
  assert(stuck.output && !stuck.gate1 && !stuck.gate2 && stuck.released && !stuck.removed);
  int stops=0; for (auto &event:stuck.events) if(event=="enable=0") ++stops;
  assert(stops==4); // Initial disable plus three cleanup retries.
}
'''


class BuzzerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_pulse_success_cancellation_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "test.cpp"
            source.write_text(PROGRAM)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(DRIVER), str(source), "-o", str(root / "test")], check=True)
            subprocess.run([str(root / "test")], check=True, timeout=5)

    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_native_driver_compiles_without_running_hardware_io(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / "esphome/core"
            core.mkdir(parents=True)
            # ESPHome Component does not have a virtual destructor. Match that
            # contract so a stub cannot hide an invalid destructor override.
            component = COMPONENT.replace("virtual ~Component()", "~Component()")
            (core / "component.h").write_text(component)
            (core / "hal.h").write_text('#pragma once\n#include <cstdint>\nnamespace esphome { uint32_t millis(); }\n')
            (core / "log.h").write_text('#pragma once\n#define ESP_LOGCONFIG(...) ((void)0)\n#define ESP_LOGE(...) ((void)0)\n#define YESNO(x) ((x)?"yes":"no")\n')
            subprocess.run(["g++", "-std=c++17", "-DUSE_HOST", "-pthread", "-Wall", "-Wextra",
                            "-I", str(root), "-I", str(DRIVER), "-c", str(DRIVER / "buzzer.cpp"),
                            "-o", str(root / "buzzer.o")], check=True)

    def test_only_buzzer_paths_and_no_shell_or_network(self):
        source = (DRIVER / "buzzer.cpp").read_text()
        for forbidden in ("KC_CTL", "system(", "popen(", "socket(", "pwmchip3", "/dev/mtd"):
            self.assertNotIn(forbidden, source)
        setup = source.split("void Buzzer::setup() {")[1].split("void Buzzer::dump_config")[0]
        self.assertNotIn("put(", setup)
        self.assertNotIn("play_click(", setup)
        self.assertIn("< 200", source)
        self.assertIn("joinable_", source)
