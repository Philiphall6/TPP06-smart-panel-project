#include "health.h"
#ifdef USE_HOST
#include "helpers.h"
#include <cerrno>
#include <cstdlib>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <time.h>
#include <unistd.h>

namespace esphome::tpp06_health {
static std::string read_small(const char *path) {
  int fd = ::open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
  if (fd < 0) return {};
  char buffer[8192];
  const ssize_t size = ::read(fd, buffer, sizeof(buffer));
  ::close(fd);
  return size > 0 && size < static_cast<ssize_t>(sizeof(buffer)) ? std::string(buffer, size) : std::string();
}
static bool write_heartbeat() {
  constexpr const char *DIR = "/tmp/tpp06-health";
  if (::mkdir(DIR, 0700) != 0 && errno != EEXIST) return false;
  struct stat st{};
  if (::lstat(DIR, &st) != 0 || !S_ISDIR(st.st_mode) || st.st_uid != ::geteuid() ||
      (st.st_mode & 0777) != 0700) return false;
  struct timespec now{};
  if (::clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec < 0) return false;
  char body[96];
  const int count = std::snprintf(body, sizeof(body), "1 %ld %lld\n", static_cast<long>(::getpid()),
                                  static_cast<long long>(now.tv_sec));
  std::string temp = std::string(DIR) + "/heartbeat.XXXXXX";
  int fd = ::mkstemp(&temp[0]);
  if (fd < 0) return false;
  bool ok = ::write(fd, body, count) == count;
  if (::close(fd) != 0) ok = false;
  // Volatile liveness only: no NAND fsync, no alteration of the watchdog.
  if (ok && ::rename(temp.c_str(), "/tmp/tpp06-health/heartbeat") != 0) ok = false;
  ::unlink(temp.c_str());
  return ok;
}
static void publish(text_sensor::TextSensor *sensor, const std::string &state) {
  if (sensor != nullptr && sensor->state != state) sensor->publish_state(state);
}
static bool monotonic_millis(uint32_t &value) {
  struct timespec now{};
  if (::clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec < 0) return false;
  value = uint32_t(uint64_t(now.tv_sec) * 1000 + now.tv_nsec / 1000000);
  return true;
}
void Health::loop() {
  if (!wifi_signal_ || !wifi_signal_via_wpa_) return;
  uint32_t now;
  if (!monotonic_millis(now)) { signal_query_.cancel(); publish(wifi_signal_, "Indisponible"); return; }
  std::string value;
  if (signal_query_.finish(now, value)) publish(wifi_signal_, value);
}
void Health::update() {
  if (heartbeat_ && !write_heartbeat()) this->status_set_warning("Heartbeat unavailable");
  else this->status_clear_warning();
  if (memory_) publish(memory_, memory_summary(read_small("/proc/meminfo")));
  if (wifi_signal_) {
    if (wifi_signal_via_wpa_) {
      uint32_t now;
      if (!monotonic_millis(now) || !signal_query_.begin("/var/run/wpa_supplicant/" + interface_, now))
        publish(wifi_signal_, "Indisponible");
    } else publish(wifi_signal_, signal_summary(read_small("/proc/net/wireless"), interface_));
  }
  if (link_) {
    const std::string base = "/sys/class/net/" + interface_;
    publish(link_, link_summary(read_small((base + "/operstate").c_str()), read_small((base + "/carrier").c_str())));
  }
  if (supervisor_) publish(supervisor_, supervisor_summary(read_small("/data/tpp06-cutter/active_mode"),
                                                         read_small("/data/tpp06-cutter/local_control_confirmed")));
  if (ota_capacity_) {
    struct stat exe{};
    struct statvfs fs{};
    std::string state = "Indisponible";
    if (::stat("/proc/self/exe", &exe) == 0 && exe.st_size > 0 && ::statvfs("/data", &fs) == 0 &&
        fs.f_frsize > 0 && fs.f_bavail <= fs.f_blocks &&
        fs.f_bavail <= std::numeric_limits<unsigned long long>::max() / fs.f_frsize) {
      const auto available = static_cast<unsigned long long>(fs.f_bavail) * fs.f_frsize;
      state = ota_room(available, exe.st_size) ? "Marge estimee suffisante" : "Espace OTA insuffisant";
      if (fs.f_flag & ST_RDONLY) state = "Stockage en lecture seule";
    }
    // Estimate uses running executable size, NOT a guarantee for a larger update.
    publish(ota_capacity_, state);
  }
}
}  // namespace esphome::tpp06_health
#endif
