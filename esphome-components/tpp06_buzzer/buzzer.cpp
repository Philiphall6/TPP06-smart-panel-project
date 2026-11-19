#include "buzzer.h"
#ifdef USE_HOST
#include "pulse.h"
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <climits>
#include <dirent.h>
#include <fcntl.h>
#include <string>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome::tpp06_buzzer {
static const char *const TAG = "tpp06_buzzer";
static const std::string CHIP = "/sys/devices/platform/pwm1/pwm/pwmchip1";

static bool text_is(const std::string &path, const std::string &expected) {
  char buf[80]{};
  int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) return false;
  ssize_t n = read(fd, buf, sizeof(buf) - 1);
  close(fd);
  if (n <= 0) return false;
  while (n > 0 && (buf[n-1] == '\n' || buf[n-1] == '\r' || buf[n-1] == '\0')) --n;
  return std::string(buf, n) == expected;
}

static bool stock_absent() {
  DIR *dir = opendir("/proc");
  if (!dir) return false;
  bool ok = true;
  while (auto *entry = readdir(dir)) {
    if (entry->d_name[0] < '0' || entry->d_name[0] > '9') continue;
    char buf[512]{};
    std::string path = std::string("/proc/") + entry->d_name + "/cmdline";
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
      if (errno != ENOENT && errno != ESRCH) { ok = false; break; }
      continue;
    }
    ssize_t n = read(fd, buf, sizeof(buf) - 1); close(fd);
    if (n < 0) { ok = false; break; }
    for (ssize_t i = 0; i < n; ++i) if (!buf[i]) buf[i] = ' ';
    if (std::strstr(buf, "voice_control_ak3760e") || std::strstr(buf, "tuya_monitor.sh")) {
      ok = false; break;
    }
  }
  closedir(dir);
  return ok;
}

static std::string gate_path(unsigned channel) {
  return "/sys/class/gpio/BUZ_EN" + std::to_string(channel);
}

static bool profile_valid() {
  utsname name{};
  if (uname(&name) || std::strcmp(name.release, "4.4.192V2.4") ||
      std::strcmp(name.machine, "armv5tejl")) return false;
  char resolved[256]{};
  ssize_t count = readlink("/sys/devices/platform/pwm1/of_node", resolved, sizeof(resolved)-1);
  const std::string node(resolved);
  if (count <= 0 || node.size() < 5 || node.substr(node.size()-5) != "/pwm1" ||
      !text_is(CHIP + "/npwm", "1")) return false;
  struct stat st{};
  // Do not take over an already exported channel (even if it looks disabled).
  if (lstat((CHIP + "/pwm0").c_str(), &st) == 0 || errno != ENOENT) return false;
  for (unsigned i = 1; i <= 2; ++i) {
    std::string base = "/proc/device-tree/gpio_export/buz_en" + std::to_string(i);
    unsigned char cells[13]{};
    int fd = open((base + "/gpios").c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    ssize_t n = read(fd, cells, sizeof(cells)); close(fd);
    if (n != 12 || cells[4] || cells[5] || cells[6] || cells[7] != (i == 1 ? 8 : 18) ||
        cells[8] || cells[9] || cells[10] || cells[11] ||
        !text_is(base + "/gpio-export,name", "BUZ_EN" + std::to_string(i)) ||
        !text_is(gate_path(i) + "/direction", "out") ||
        !text_is(gate_path(i) + "/active_low", "0") ||
        !text_is(gate_path(i) + "/value", "0")) return false;
  }
  return stock_absent();
}

class LinuxPulse final : public PulseIO {
 public:
  std::string failure_stage;
  int failure_errno{0};
  bool claim() override {
    lock_ = open("/var/run/tpp06-buzzer.lock", O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (lock_ < 0) return fail("open lock", errno);
    if (flock(lock_, LOCK_EX | LOCK_NB)) { fail("claim lock", errno); release(); return false; }
    if (!profile_valid()) { fail("hardware/ownership profile", 0); release(); return false; }
    return true;
  }
  bool export_channel() override { return put(CHIP + "/export", 0, false); }
  bool read_pwm(const char *attribute, int &value) override {
    return read_value(CHIP + "/pwm0/" + attribute, value);
  }
  bool pwm(const char *attribute, int value) override {
    return put(CHIP + "/pwm0/" + attribute, value);
  }
  bool gate(unsigned channel, int value) override { return put(gate_path(channel) + "/value", value); }
  bool pause_500us() override {
    timespec wait{0, 500000};
    // An interrupted sleep proceeds to cleanup rather than extending a tone.
    if (nanosleep(&wait, nullptr)) return fail("nanosleep", errno);
    return true;
  }
  bool unexport_channel() override { return put(CHIP + "/unexport", 0, false); }
  void release() override { if (lock_ >= 0) { close(lock_); lock_ = -1; } }
 private:
  bool fail(const std::string &stage, int code) {
    // Preserve the first error even if cleanup encounters another failure.
    if (failure_stage.empty()) { failure_stage = stage; failure_errno = code; }
    return false;
  }
  bool read_value(const std::string &path, int &value) {
    char buf[80]{};
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return fail("open-read " + path, errno);
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    int saved = errno;
    int rc = close(fd);
    if (n < 0) return fail("read " + path, saved);
    if (rc) return fail("close-read " + path, errno);
    if (n == 0 || n == sizeof(buf) - 1) return fail("invalid-read " + path, EINVAL);
    char *end = nullptr;
    errno = 0;
    long parsed = std::strtol(buf, &end, 10);
    if (errno || end == buf || parsed < 0 || parsed > INT_MAX)
      return fail("invalid-value " + path, EINVAL);
    while (*end == '\n' || *end == '\r') ++end;
    if (*end) return fail("invalid-value " + path, EINVAL);
    value = static_cast<int>(parsed);
    return true;
  }
  bool put(const std::string &path, int value, bool verify = true) {
    const std::string bytes = std::to_string(value) + "\n";
    int fd = open(path.c_str(), O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return fail("open-write " + path, errno);
    ssize_t n = write(fd, bytes.data(), bytes.size());
    int saved = errno;
    int rc = close(fd);
    if (n != static_cast<ssize_t>(bytes.size()))
      return fail("write " + path + "=" + std::to_string(value), n < 0 ? saved : EIO);
    if (rc) return fail("close-write " + path, errno);
    int actual = -1;
    if (verify && !read_value(path, actual)) return false;
    if (verify && actual != value) return fail("readback " + path, EIO);
    return true;
  }
  int lock_{-1};
};

Buzzer::~Buzzer() { on_shutdown(); }
void Buzzer::setup() {
  ready_ = profile_valid();  // No export, GPIO write or tone during boot.
  if (!ready_) status_set_warning("Buzzer hardware or ownership unavailable");
}
void Buzzer::dump_config() {
  ESP_LOGCONFIG(TAG, "Experimental touch beep: available=%s enabled=%s", YESNO(available()), YESNO(enabled()));
}
void *Buzzer::worker_(void *arg) {
  auto *self = static_cast<Buzzer *>(arg);
  LinuxPulse io;
  if (!play_click(io, self->enabled_)) {
    self->failure_stage_ = io.failure_stage.empty() ? "invalid PWM state" : io.failure_stage;
    self->failure_errno_ = io.failure_errno;
    self->fault_.store(true);
    self->enabled_.store(false);
  }
  self->finished_.store(true);
  return nullptr;
}
void Buzzer::loop() {
  if (joinable_ && finished_.load()) { pthread_join(worker_id_, nullptr); joinable_ = false; }
  if (fault_.load() && !warned_) {
    warned_ = true;
    status_set_warning("Buzzer transaction failed; disabled until restart");
    ESP_LOGE(TAG, "Sound disabled: %s (errno=%d). Cleanup attempted; verify PWM is off",
             failure_stage_.c_str(), failure_errno_);
  }
}
void Buzzer::click() {
  const uint32_t now = millis();
  if (!enabled() || joinable_ || (seen_click_ && uint32_t(now - last_click_) < 200)) return;
  seen_click_ = true; last_click_ = now;
  finished_.store(false);
  int rc = pthread_create(&worker_id_, nullptr, worker_, this);
  if (rc != 0) {
    failure_stage_ = "pthread_create"; failure_errno_ = rc;
    fault_.store(true); enabled_.store(false); return;
  }
  joinable_ = true;  // No queued tones and no sleep on the LVGL thread.
}
void Buzzer::on_shutdown() {
  enabled_.store(false);
  if (joinable_) { pthread_join(worker_id_, nullptr); joinable_ = false; }
  ready_ = false;
}
}  // namespace esphome::tpp06_buzzer
#endif
