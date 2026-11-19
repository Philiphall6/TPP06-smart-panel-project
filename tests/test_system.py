"""System entities: simulated storage/restart only, never reboot the host/panel."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "esphome-components/tpp06_system"
COMPONENT = r'''
#pragma once
#include <functional>
#include <cstdint>
namespace esphome {
class Component {
 public:
  virtual void update() {}
  virtual void loop() {}
  void status_set_warning(const char *) { warning=true; }
  void status_clear_warning() { warning=false; }
  void set_timeout(const char *, uint32_t, std::function<void()> fn) { callback=fn; ++schedules; }
  void run_pending() { auto fn=callback; callback=nullptr; if(fn) fn(); }
  bool warning=false; int schedules=0; std::function<void()> callback;
};
class PollingComponent : public Component {};
}
'''
PROGRAM = r'''
#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/utsname.h>
#include <spawn.h>
#include <unistd.h>
#include "helpers.h"
#include "system.h"
#include "esphome/core/application.h"
using namespace esphome::tpp06_system;
esphome::Application esphome::App;
bool storage_error=false, healthy=true, mode=true, ota=false, same_inode=true;
bool runnable=true, argv_valid=true;
bool persistent=true, wifi=true, stock=true, boot_pending=false, root_user=true, platform=true;
bool command_path=true, init_path=true;
int spawned=0, spawn_error=0, reaped=0;
uint64_t blocks=39424, available=16384;
std::string fd_text, armed;
namespace esphome::host {
std::string path="/data/tpp06-cutter/esphome/esphome";
char *args[]={nullptr};
char **get_argv() {return argv_valid?args:nullptr;}
const std::string &get_exe_path() {return path;}
const char *get_reexec_path() {return armed.empty()?nullptr:armed.c_str();}
void arm_reexec(const std::string &p) {armed=p;}
}
extern "C" {
int __wrap_statvfs(const char *path, struct statvfs *s) {
 assert(std::string(path)=="/data");
 if(storage_error) {errno=EIO; return -1;}
 *s={};s->f_blocks=blocks;s->f_bavail=available;s->f_frsize=1024;
 s->f_bfree=available+100;return 0;
}
int __wrap_stat(const char *path, struct stat *s) {
 *s={};s->st_dev=1;s->st_ino=(std::string(path)=="/proc/self/exe"||same_inode)?1:2;
 s->st_mode=S_IFREG|0755;return 0;
}
int __wrap_lstat(const char *path, struct stat *) {
 if(std::string(path)=="/data/tpp06-cutter/boot_pending") {if(boot_pending) return 0;}
 else {assert(std::string(path).find(".ota.new")!=std::string::npos);if(ota) return 0;}
 errno=ENOENT;return -1;
}
int __wrap_access(const char *path, int) {
 if(std::string(path)=="/data/tpp06-cutter/S99tuya-app.stock")return stock?0:-1;
 return runnable?0:-1;
}
int __wrap_open(const char *path, int, ...) {
 std::string p(path);
 if(p=="/data/tpp06-cutter/active_mode") fd_text=healthy?"esphome-healthy\n":"tuya\n";
 else if(p=="/data/tpp06-cutter/mode") fd_text=mode?"esphome\n":"tuya\n";
 else if(p=="/data/tpp06-cutter/boot_policy") fd_text=persistent?"persistent\n":"one-shot\n";
 else if(p=="/data/tpp06-cutter/persistent_confirmed") fd_text=persistent?"yes\n":"no\n";
 else if(p=="/data/tpp06-cutter/network_mode") fd_text="isolated\n";
 else if(p=="/data/etc/init.d/S99tuya-app") fd_text="TPP06_MULTIBOOT_V1";
 else if(p=="/data/tpp06-cutter/network/wpa_supplicant.conf") fd_text=wifi?"network={ssid=example psk=test-only}":"";
 else {assert(false);}
 return 50;
}
ssize_t __wrap_read(int fd, void *dest, size_t n) {
 assert(fd==50 && fd_text.size()<n);std::memcpy(dest,fd_text.data(),fd_text.size());return fd_text.size();
}
int __wrap_close(int fd) {assert(fd==50);return 0;}
uid_t __wrap_geteuid() {return root_user?0:1000;}
int __wrap_uname(struct utsname *s) {
 *s={};std::strcpy(s->release,platform?"4.4.192V2.4":"other");std::strcpy(s->machine,"armv5tejl");return 0;
}
char *__wrap_realpath(const char *path, char *result) {
 bool valid=std::string(path)=="/sbin/reboot"?command_path:init_path;
 std::strcpy(result,valid?"/bin/busybox":"/wrong");return result;
}
int __wrap_posix_spawn(pid_t *pid,const char *path,const posix_spawn_file_actions_t *,
                      const posix_spawnattr_t *,char *const args[],char *const env[]) {
 assert(std::string(path)=="/sbin/reboot" && std::string(args[0])==path && args[1]==nullptr);
 assert(std::string(env[0])=="PATH=/sbin:/bin:/usr/sbin:/usr/bin" && env[1]==nullptr);
 ++spawned;if(spawn_error)return spawn_error;*pid=999;return 0;
}
pid_t __wrap_waitpid(pid_t pid,int *status,int) {assert(pid==999);++reaped;*status=0;return pid;}
}
int main() {
 assert(storage_summary(39424,10356,1024)=="10.1 / 38.5 Mio");
 assert(storage_summary(39424,0,1024)=="0.0 / 38.5 Mio");
 assert(storage_summary(0,0,1024)=="Indisponible");
 assert(storage_summary(10,11,1024)=="Indisponible");
 assert(storage_summary(10,1,0)=="Indisponible");
 assert(storage_summary(std::numeric_limits<uint64_t>::max(),1,2)=="Indisponible");
 Storage storage;storage.update();
 assert(storage.state=="16.0 / 38.5 Mio" && !storage.warning);
 storage_error=true;storage.update();assert(storage.state=="Indisponible" && storage.warning);
 storage_error=false;available=blocks+1;storage.update();assert(storage.warning);
 available=16384;storage.update();assert(!storage.warning);
 Restart button;
 assert(esphome::App.restarts==0 && armed.empty() && !button.callback);
 for(bool *guard:{&healthy,&mode,&same_inode,&runnable,&argv_valid}) {
  *guard=false;button.press();assert(button.warning && !button.callback);*guard=true;
 }
 ota=true;button.press();assert(!button.callback);ota=false;
 armed="OTA";button.press();assert(!button.callback);armed.clear();
 button.press();button.press();assert(button.schedules==1 && esphome::App.restarts==0);
 ota=true;button.run_pending();assert(esphome::App.restarts==0 && armed.empty());ota=false;
 button.press();same_inode=false;button.run_pending();assert(esphome::App.restarts==0);same_inode=true;
 button.press();button.run_pending();
 assert(esphome::App.restarts==1 && armed==esphome::host::path && !button.warning);
 armed.clear();
 Restart device;device.set_device_reboot(true);
 assert(spawned==0);
 for(bool *guard:{&persistent,&wifi,&stock,&root_user,&platform,&command_path,&init_path}) {
  *guard=false;device.press();assert(!device.callback && spawned==0);*guard=true;
 }
 boot_pending=true;device.press();assert(!device.callback);boot_pending=false;
 available=100;device.press();assert(!device.callback);available=16384;
 button.press();device.press();assert(button.callback && !device.callback);
 ota=true;button.run_pending();ota=false; // Shared lock released on cancellation.
 device.press();button.press();assert(device.callback && !button.callback);
 ota=true;device.run_pending();assert(spawned==0);ota=false;
 spawn_error=EACCES;device.press();device.run_pending();assert(spawned==1 && device.warning);
 spawn_error=0;device.press();device.run_pending();assert(spawned==2 && armed.empty());
 device.loop();assert(reaped==1);
 device.press();button.press();assert(!device.callback && !button.callback && spawned==2);
 assert(esphome::App.restarts==1); // Linux path never re-execs or exits ESPHome itself.
}
'''

class SystemTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_storage_and_guarded_restart_with_fake_syscalls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "esphome/core/component.h": COMPONENT,
                "esphome/core/log.h": '#pragma once\n#define ESP_LOGW(...) ((void)0)\n#define ESP_LOGI(...) ((void)0)\n',
                "esphome/core/application.h": '#pragma once\nnamespace esphome { struct Application {int restarts=0;void safe_reboot(){++restarts;}};extern Application App;}\n',
                "esphome/components/button/button.h": '#pragma once\nnamespace esphome::button {class Button {public:void press(){press_action();} protected:virtual void press_action()=0;};}\n',
                "esphome/components/text_sensor/text_sensor.h": '#pragma once\n#include <string>\nnamespace esphome::text_sensor {class TextSensor {public:std::string state;void publish_state(const std::string &v){state=v;}};}\n',
                "esphome/components/host/core.h": (ROOT / "esphome-components/host/core.h").read_text(),
                "test.cpp": PROGRAM,
            }
            for name, content in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
            wrappers=["statvfs", "stat", "lstat", "access", "open", "read", "close",
                      "geteuid", "uname", "realpath", "posix_spawn", "waitpid"]
            subprocess.run(["g++", "-std=c++17", "-DUSE_HOST", "-Wall", "-Wextra",
                            "-I", str(root), "-I", str(DRIVER), str(root/"test.cpp"),
                            str(DRIVER/"system.cpp"), *["-Wl,--wrap="+s for s in wrappers],
                            "-o", str(root/"test")],check=True)
            subprocess.run([str(root/"test")],check=True,timeout=5)

    def test_no_forced_reboot_shell_or_gpio_operations(self):
        source=(DRIVER/"system.cpp").read_text()
        for forbidden in ("system(", "popen(", "execl(", "::reboot(", "/dev/mtd", "KC_CTL", "O_WRONLY"):
            self.assertNotIn(forbidden, source)
        self.assertIn('statvfs("/data"', source)
        self.assertIn("fs.f_bavail", source)
        self.assertIn('set_timeout("restart", 500', source)
        self.assertIn("host::arm_reexec(host::get_exe_path())", source)
        self.assertIn("App.safe_reboot()", source)
        self.assertIn('char command[] = "/sbin/reboot"', source)
        self.assertIn("posix_spawn", source)
        self.assertIn("active_request", source)
