"""Candidate liveness, bounded retention, diagnostics; no network or hardware."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "device/tpp06-multiboot.sh"


class SupervisorHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "base"
        self.base.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        (self.proc / "uptime").write_text("1234.25 100.00\n")
        self.heartbeat = self.root / "heartbeat"
        self.functions = SCRIPT.read_text().rsplit('\ncase "$1" in', 1)[0]
        self.env = {**os.environ, "TPP06_BASE": str(self.base),
                    "TPP06_PROC_ROOT": str(self.proc), "TPP06_HEARTBEAT_FILE": str(self.heartbeat)}

    def shell(self, script):
        return subprocess.run(["sh"], input=self.functions + "\n" + script,
                              env=self.env, text=True, capture_output=True, timeout=5)

    def test_observation_is_backward_compatible(self):
        self.assertEqual(self.shell("engine_pid=42; heartbeat_ready").returncode, 0)

    def test_required_heartbeat_rejects_stale_wrong_pid_missing_and_malformed(self):
        (self.base / "heartbeat_policy").write_text("required-v1\n")
        self.assertNotEqual(self.shell("engine_pid=42; heartbeat_ready").returncode, 0)
        for body, ok in [("1 42 1234\n", True), ("1 42 1209\n", True),
                         ("1 42 1208\n", False), ("1 42 1235\n", False),
                         ("1 43 1234\n", False), ("2 42 1234\n", False),
                         ("1 42 01234\n", False), ("1 42 -1\n", False),
                         ("1 42 999999999999\n", False), ("1 42 1234 extra\n", False),
                         ("1 42 1234", False), ("1 42 x[$(false)]\n", False),
                         ("1 42 0\n", False), ("1 42 " + "1" * 200 + "\n", False)]:
            with self.subTest(body=body):
                self.heartbeat.write_text(body)
                self.assertEqual(self.shell("engine_pid=42; heartbeat_ready").returncode == 0, ok)
        self.heartbeat.unlink()
        self.heartbeat.symlink_to(self.proc / "uptime")
        self.assertNotEqual(self.shell("engine_pid=42; heartbeat_ready").returncode, 0)

    def test_invalid_policy_fails_closed(self):
        (self.base / "heartbeat_policy").write_text("required-v2\n")
        self.assertNotEqual(self.shell("engine_pid=42; heartbeat_ready").returncode, 0)

    def test_log_cap_preserves_live_append_descriptor_and_only_touches_known_logs(self):
        directory = self.base / "diagnostics"
        directory.mkdir()
        log = directory / "esphome.log"
        marker = directory / "owner-backup"
        marker.write_text("keep")
        log.write_bytes(b"x" * (1048576 + 7))
        with log.open("ab", buffering=0) as writer:
            result = self.shell("maintain_runtime_logs")
            self.assertEqual(result.returncode, 0, result.stderr)
            writer.write(b"new log line\n")
        self.assertEqual(log.read_bytes(), b"new log line\n")
        self.assertEqual(log.with_suffix(".log.previous").stat().st_size, 65536)
        self.assertEqual(marker.read_text(), "keep")
        self.assertFalse(list(directory.glob(".log-tail.*")))
        before = log.stat().st_mtime_ns
        self.shell("maintain_runtime_logs")
        self.assertEqual(log.stat().st_mtime_ns, before)

    def test_log_symlink_is_not_followed(self):
        directory = self.base / "diagnostics"
        directory.mkdir()
        target = self.root / "untouched"
        target.write_bytes(b"x" * 1100000)
        (directory / "esphome.log").symlink_to(target)
        self.shell("maintain_runtime_logs")
        self.assertEqual(target.stat().st_size, 1100000)


class HealthParserTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_real_health_driver_with_fake_linux_calls(self):
        program = r'''
#include "health.h"
#include <cassert>
#include <cstring>
#include <map>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <time.h>
#include <unistd.h>
using namespace esphome::tpp06_health;
std::map<std::string,std::string> files{
 {"/proc/meminfo","MemTotal: 10240 kB\nMemAvailable: 5120 kB\n"},
 {"/proc/net/wireless"," wlan0: 0000 70. -42. 0 0\n"},
 {"/data/tpp06-cutter/active_mode","esphome-healthy\n"},
 {"/data/tpp06-cutter/local_control_confirmed","no\n"},
 {"/sys/class/net/wlan0/operstate","up\n"},
 {"/sys/class/net/wlan0/carrier","1\n"}};
std::string reading, heartbeat;
bool directory_ok=true, read_only=false, small_disk=false;
int writes=0, renames=0;
bool reply_ready=true;
long seconds=1234;
extern "C" {
int __wrap_socket(int family,int type,int protocol) {
 assert(family==AF_UNIX && type==(SOCK_DGRAM|SOCK_NONBLOCK|SOCK_CLOEXEC) && protocol==0);return 52;
}
int __wrap_bind(int fd,const struct sockaddr *addr,socklen_t length) {
 assert(fd==52 && addr->sa_family==AF_UNIX && length==offsetof(sockaddr_un,sun_path));return 0;
}
int __wrap_connect(int fd,const struct sockaddr *addr,socklen_t) {
 assert(fd==52 && std::string(reinterpret_cast<const sockaddr_un*>(addr)->sun_path)=="/var/run/wpa_supplicant/wlan0");return 0;
}
ssize_t __wrap_send(int fd,const void *data,size_t length,int flags) {
 assert(fd==52 && flags==MSG_NOSIGNAL && std::string(static_cast<const char*>(data),length)=="SIGNAL_POLL");return length;
}
ssize_t __wrap_recv(int fd,void *data,size_t length,int flags) {
 assert(fd==52 && length==4096 && flags==(MSG_DONTWAIT|MSG_TRUNC));
 if(!reply_ready){errno=EAGAIN;return -1;}
 const std::string reply="RSSI=-40\nLINKSPEED=150\n";memcpy(data,reply.data(),reply.size());return reply.size();
}
int __wrap_open(const char *path,int,...) {
 assert(files.count(path));reading=files.at(path);return 50;
}
ssize_t __wrap_read(int fd,void *buffer,size_t size) {
 assert(fd==50 && size>reading.size());memcpy(buffer,reading.data(),reading.size());return reading.size();
}
int __wrap_close(int fd) {assert(fd==50 || fd==51 || fd==52);return 0;}
int __wrap_mkdir(const char *path, mode_t mode) {
 assert(std::string(path)=="/tmp/tpp06-health" && mode==0700);return 0;
}
int __wrap_lstat(const char *path,struct stat *s) {
 assert(std::string(path)=="/tmp/tpp06-health");*s={};s->st_uid=0;s->st_mode=S_IFDIR|(directory_ok?0700:0777);return 0;
}
uid_t __wrap_geteuid() {return 0;}
pid_t __wrap_getpid() {return 42;}
int __wrap_clock_gettime(clockid_t clock,struct timespec *time) {
 assert(clock==CLOCK_MONOTONIC);*time={};time->tv_sec=seconds;return 0;
}
int __wrap_mkstemp(char *name) {
 assert(std::string(name)=="/tmp/tpp06-health/heartbeat.XXXXXX");return 51;
}
ssize_t __wrap_write(int fd,const void *buffer,size_t size) {
 assert(fd==51);++writes;heartbeat.assign(static_cast<const char*>(buffer),size);return size;
}
int __wrap_rename(const char *from,const char *to) {
 assert(std::string(from)=="/tmp/tpp06-health/heartbeat.XXXXXX");
 assert(std::string(to)=="/tmp/tpp06-health/heartbeat");++renames;return 0;
}
int __wrap_unlink(const char *path) {assert(std::string(path)=="/tmp/tpp06-health/heartbeat.XXXXXX");return 0;}
int __wrap_stat(const char *path,struct stat *s) {
 assert(std::string(path)=="/proc/self/exe");*s={};s->st_size=10*1024*1024;return 0;
}
int __wrap_statvfs(const char *path,struct statvfs *s) {
 assert(std::string(path)=="/data");*s={};s->f_blocks=39*1024;s->f_bavail=(small_disk?5:12)*1024;
 s->f_frsize=1024;s->f_flag=read_only?ST_RDONLY:0;return 0;
}
}
int main() {
 Health health;esphome::text_sensor::TextSensor memory,wifi,supervisor,ota,link;
 health.set_memory(&memory);health.set_wifi_signal(&wifi);health.set_supervisor(&supervisor);health.set_ota_capacity(&ota);
 health.update();assert(writes==0 && renames==0);
 assert(memory.state=="5.0 / 10.0 Mio" && wifi.state=="-42 dBm");
 assert(ota.state=="Marge estimee suffisante");
 health.set_heartbeat(true);health.update();
 assert(writes==1 && renames==1 && heartbeat=="1 42 1234\n" && !health.warning);
 assert(memory.publications==1); // No duplicate API publications for unchanged counters.
 directory_ok=false;health.update();assert(health.warning && writes==1);
 directory_ok=true;read_only=true;health.update();assert(!health.warning && ota.state=="Stockage en lecture seule");
 read_only=false;small_disk=true;health.update();assert(ota.state=="Espace OTA insuffisant");
 health.set_link(&link);health.set_wifi_signal_via_wpa(true);health.update();
 assert(link.state=="Liaison active / Internet non teste");
 health.loop();assert(wifi.state=="-40 dBm");
 reply_ready=false;health.update();health.loop();assert(wifi.state=="-40 dBm");
 seconds+=2;health.loop();assert(wifi.state=="Indisponible");
 health.set_wifi_signal_via_wpa(false);
 for(auto &file:files)file.second="";
 health.update();assert(memory.state=="Indisponible" && wifi.state=="Indisponible" && supervisor.state=="Indisponible");
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stub_files = {
                "esphome/core/component.h": "#pragma once\nnamespace esphome {class PollingComponent {public: virtual void update(){};virtual void loop(){};bool warning=false;void status_set_warning(const char*){warning=true;}void status_clear_warning(){warning=false;}};}\n",
                "esphome/components/text_sensor/text_sensor.h": "#pragma once\n#include <string>\nnamespace esphome::text_sensor {class TextSensor {public:std::string state;int publications=0;void publish_state(const std::string &v){state=v;++publications;}};}\n",
                "test.cpp": program,
            }
            for name, content in stub_files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            driver = ROOT / "esphome-components/tpp06_health"
            wrappers = ["open", "read", "close", "mkdir", "lstat", "geteuid", "getpid",
                        "clock_gettime", "mkstemp", "write", "rename", "unlink", "stat", "statvfs",
                        "socket", "bind", "connect", "send", "recv"]
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-DUSE_HOST",
                            "-I", str(root), "-I", str(driver), str(root / "test.cpp"), str(driver / "health.cpp"),
                            *["-Wl,--wrap=" + name for name in wrappers], "-o", str(root / "test")], check=True)
            subprocess.run([str(root / "test")], check=True, timeout=5)

    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_native_read_only_parsers(self):
        program = r'''
#include "helpers.h"
#include <cassert>
using namespace esphome::tpp06_health;
int main() {
 assert(memory_summary("MemTotal: 97872 kB\nMemAvailable: 79328 kB\n")=="77.5 / 95.6 Mio");
 assert(memory_summary("MemTotal: 10 kB\n")=="Indisponible");
 assert(memory_summary("MemTotal: -1 kB\nMemAvailable: 0 kB\n")=="Indisponible");
 assert(memory_summary("MemTotal: 10 kB\nMemAvailable: 11 kB\n")=="Indisponible");
 assert(memory_summary("MemTotal: 100000000000000000000000000 kB\nMemAvailable: 1 kB\n")=="Indisponible");
 assert(signal_summary(" wlan0: 0000 70. -42. -256 0 0\n", "wlan0")=="-42 dBm");
 assert(signal_summary(" wlan0: 0000 70. 214. 0 0\n", "wlan0")=="Indisponible");
 assert(signal_summary(" wlan0: 0000 70. -42. 0 0\n", "eth0")=="Indisponible");
 assert(signal_summary(" wlan0: 0000 70. nan 0 0\n", "wlan0")=="Indisponible");
 assert(ota_room(12*1024*1024,10*1024*1024));
 assert(!ota_room(12*1024*1024-1,10*1024*1024));
 assert(!ota_room(1000,0));
 assert(!ota_room(~0ULL,~0ULL));
 assert(supervisor_summary("tuya-fallback\n", "")=="Secours Tuya");
 assert(supervisor_summary("esphome-healthy\n", "no\n")=="ESPHome / hors-ligne non valide");
 assert(supervisor_summary("esphome-healthy\n", "yes\n")=="ESPHome / local confirme");
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.cpp").write_text(program)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "esphome-components/tpp06_health"),
                            str(root / "test.cpp"), "-o", str(root / "test")], check=True)
            subprocess.run([str(root / "test")], check=True, timeout=5)

    def test_no_hardware_or_network_command_in_health_driver(self):
        source = (ROOT / "esphome-components/tpp06_health/health.cpp").read_text()
        for forbidden in ("system(", "popen(", "posix_spawn", "/dev/", "reboot(", "KC_CTL", "wpa_cli"):
            self.assertNotIn(forbidden, source)
        self.assertIn("CLOCK_MONOTONIC", source)
        self.assertIn('"/tmp/tpp06-health"', source)
