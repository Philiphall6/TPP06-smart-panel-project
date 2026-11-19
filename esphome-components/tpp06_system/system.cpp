#include "system.h"
#ifdef USE_HOST
#include "helpers.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"
#include "esphome/components/host/core.h"
#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <spawn.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>

namespace esphome::tpp06_system {
static const char *const TAG = "tpp06_system";
// Serialize both buttons: no second request while either action is pending.
static Restart *active_request = nullptr;
void Storage::update() {
  struct statvfs fs{};
  if (statvfs("/data", &fs) != 0) {
    ESP_LOGW(TAG, "Cannot read /data storage (errno=%d)", errno);
    this->status_set_warning("Storage unavailable");
    this->publish_state("Indisponible");
    return;
  }
  const auto summary = storage_summary(fs.f_blocks, fs.f_bavail, fs.f_frsize);
  if (summary == "Indisponible") this->status_set_warning("Invalid storage counters");
  else this->status_clear_warning();
  this->publish_state(summary);
}

static bool state_is(const char *path, const char *expected) {
  char buffer[64]{};
  int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) return false;
  ssize_t n = read(fd, buffer, sizeof(buffer) - 1);
  close(fd);
  if (n <= 0 || n == static_cast<ssize_t>(sizeof(buffer) - 1)) return false;
  while (n && (buffer[n - 1] == '\n' || buffer[n - 1] == '\r')) --n;
  return std::string(buffer, n) == expected;
}
bool Restart::can_restart_() {
  const auto &path = host::get_exe_path();
  struct stat running{}, disk{}, staged{};
  const bool same = !path.empty() && stat("/proc/self/exe", &running) == 0 &&
                    stat(path.c_str(), &disk) == 0 && S_ISREG(disk.st_mode) &&
                    running.st_dev == disk.st_dev && running.st_ino == disk.st_ino;
  const bool no_ota = lstat((path + ".ota.new").c_str(), &staged) < 0 && errno == ENOENT;
  const bool application_ready = restart_allowed({
      state_is("/data/tpp06-cutter/active_mode", "esphome-healthy"),
      state_is("/data/tpp06-cutter/mode", "esphome"), host::get_argv() != nullptr,
      same, !path.empty() && access(path.c_str(), X_OK) == 0, no_ota,
      host::get_reexec_path() == nullptr});
  return application_ready && (!device_reboot_ || device_ready_());
}

static bool contains(const char *path, const char *token) {
  char buffer[4097]{};
  int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) return false;
  ssize_t n = read(fd, buffer, sizeof(buffer) - 1);
  close(fd);
  return n > 0 && std::strstr(buffer, token) != nullptr;
}
bool Restart::device_ready_() {
  struct utsname name{};
  char command[PATH_MAX]{}, init[PATH_MAX]{};
  struct stat st{};
  struct statvfs fs{};
  if (geteuid() != 0 || uname(&name) != 0 || std::strcmp(name.release, "4.4.192V2.4") ||
      std::strcmp(name.machine, "armv5tejl") ||
      realpath("/sbin/reboot", command) == nullptr || std::strcmp(command, "/bin/busybox") ||
      realpath("/proc/1/exe", init) == nullptr || std::strcmp(init, "/bin/busybox") ||
      access("/sbin/reboot", X_OK) != 0 ||
      access("/data/tpp06-cutter/S99tuya-app.stock", X_OK) != 0 ||
      !contains("/data/etc/init.d/S99tuya-app", "TPP06_MULTIBOOT_V1") ||
      !state_is("/data/tpp06-cutter/boot_policy", "persistent") ||
      !state_is("/data/tpp06-cutter/persistent_confirmed", "yes") ||
      !state_is("/data/tpp06-cutter/network_mode", "isolated")) return false;
  if (lstat("/data/tpp06-cutter/boot_pending", &st) == 0 || errno != ENOENT) return false;
  const char *wifi = "/data/tpp06-cutter/network/wpa_supplicant.conf";
  if (!contains(wifi, "network") || !contains(wifi, "ssid=") ||
      !(contains(wifi, "psk=") || contains(wifi, "NONE"))) return false;
  if (statvfs("/data", &fs) != 0 || (fs.f_flag & ST_RDONLY) ||
      storage_summary(fs.f_blocks, fs.f_bavail, fs.f_frsize) == "Indisponible" ||
      uint64_t(fs.f_bavail) * fs.f_frsize < 2097152) return false;
  return true;
}
void Restart::release_request_() {
  pending_ = false;
  if (active_request == this) active_request = nullptr;
}
void Restart::loop() {
  if (child_ <= 0) return;
  int status = 0;
  const pid_t result = waitpid(child_, &status, WNOHANG);
  if (result == 0 || (result < 0 && errno == EINTR)) return;
  child_ = -1;
  if (result < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
    status_set_warning("Linux reboot command failed or outcome unknown; no retry");
    ESP_LOGW(TAG, "Linux reboot child failed or could not be reaped; no automatic retry");
  }
  // Remain latched until process restart, even on ambiguous command failure.
  // An accepted request must never turn into repeated init signals.
}
void Restart::press_action() {
  if (pending_ || active_request != nullptr) return;
  if (!can_restart_()) {
    this->status_set_warning("Restart refused: check health or OTA in progress");
    ESP_LOGW(TAG, "Application restart refused: health, executable or OTA guard");
    return;
  }
  pending_ = true;
  active_request = this;
  // Return the API acknowledgement first; recheck all guards after the delay.
  this->set_timeout("restart", 500, [this]() {
    if (!this->can_restart_()) {
      this->release_request_();
      this->status_set_warning("Restart cancelled: state changed");
      return;
    }
    this->status_clear_warning();
    if (this->device_reboot_) {
      ESP_LOGI(TAG, "Requesting orderly Linux reboot; network and relay states may change");
      char command[] = "/sbin/reboot";
      char *args[] = {command, nullptr};
      char path_env[] = "PATH=/sbin:/bin:/usr/sbin:/usr/bin";
      char *env[] = {path_env, nullptr};
      // BusyBox reboot without -f delegates shutdown/sync to PID 1. Never use
      // a raw reboot syscall, shell, watchdog reset, or force flag here.
      const int rc = posix_spawn(&this->child_, command, nullptr, nullptr, args, env);
      if (rc != 0) {
        this->child_ = -1;
        this->status_set_warning("Cannot execute Linux reboot command");
        ESP_LOGW(TAG, "Cannot spawn Linux reboot (errno=%d); no fallback", rc);
        this->release_request_();
      }
      return;
    }
    ESP_LOGI(TAG, "Restarting ESPHome application only; Linux stays running");
    // Standard host restart exits instead of relaunching. Arm the same re-exec
    // path used by host OTA, then run safe hooks (preferences, buzzer, relays).
    host::arm_reexec(host::get_exe_path());
    App.safe_reboot();
    this->release_request_();  // Only reached if a test stub returns.
  });
}
}  // namespace esphome::tpp06_system
#endif
