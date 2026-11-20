#include "local_relays.h"
#include "process_identity.h"
#ifdef USE_HOST
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <linux/input.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#ifdef USE_TPP06_MUTE_INPUT
#include "esphome/components/text_sensor/text_sensor.h"
#endif

namespace esphome::tpp06_local_relays {
static const char *const TAG = "tpp06_local_relays";
// TPP06's kernel 4.4 uses the 32-bit timeval ABI even with a time64 libc.
struct InputEvent32 { int32_t sec, usec; uint16_t type, code; int32_t value; };
static_assert(sizeof(InputEvent32) == 16);

static bool read_text(const std::string &path, const char *expected) {
  char buffer[64]{};
  int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) return false;
  ssize_t size = read(fd, buffer, sizeof(buffer) - 1);
  close(fd);
  if (size <= 0) return false;
  while (size > 0 && (buffer[size - 1] == '\n' || buffer[size - 1] == '\r')) buffer[--size] = 0;
  return std::strcmp(buffer, expected) == 0;
}

static bool bit_set(const unsigned char *bits, unsigned int bit) {
  return (bits[bit / 8] & (1U << (bit % 8))) != 0;
}

std::string LocalRelays::gpio_path_(uint8_t channel, const char *attribute) {
  return "/sys/class/gpio/KC_CTL" + std::to_string(channel + 1) + "/" + attribute;
}

bool LocalRelays::read_channel_(uint8_t channel, bool &value) {
  if (channel >= 3 || !read_text(gpio_path_(channel, "direction"), "out") ||
      !read_text(gpio_path_(channel, "active_low"), "0")) return false;
  if (read_text(gpio_path_(channel, "value"), "0")) { value = false; return true; }
  if (read_text(gpio_path_(channel, "value"), "1")) { value = true; return true; }
  return false;
}

bool LocalRelays::profile_valid_() {
  struct utsname name{};
  if (uname(&name) != 0 || std::strcmp(name.release, "4.4.192V2.4") != 0 ||
      std::strcmp(name.machine, "armv5tejl") != 0) return false;
  for (uint8_t channel = 0; channel < 3; ++channel) {
    const std::string base = "/proc/device-tree/gpio_export/kc_ctl" + std::to_string(channel + 1);
    unsigned char gpio[13]{};
    int fd = open((base + "/gpios").c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    const ssize_t count = read(fd, gpio, sizeof(gpio)); close(fd);
    // The phandle (first cell) may vary; pin and polarity must match exactly.
    if (count != 12 || gpio[4] || gpio[5] || gpio[6] || gpio[7] != 65 + channel ||
        gpio[8] || gpio[9] || gpio[10] || gpio[11] ||
        !read_text(base + "/gpio-export,name", ("KC_CTL" + std::to_string(channel + 1)).c_str()))
      return false;
    bool state;
    if (!read_channel_(channel, state)) return false;
  }
  return true;
}

bool LocalRelays::stock_present_() {
  DIR *dir = opendir("/proc");
  if (dir == nullptr) return true;  // Unverifiable ownership: refuse writes.
  bool found = false;
  while (auto *entry = readdir(dir)) {
    if (entry->d_name[0] < '0' || entry->d_name[0] > '9') continue;
    char buffer[512]{};
    const std::string path = std::string("/proc/") + entry->d_name + "/cmdline";
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
      if (errno != ENOENT && errno != ESRCH) { found = true; break; }
      continue;
    }
    const ssize_t size = read(fd, buffer, sizeof(buffer) - 1); close(fd);
    if (size < 0) { found = true; break; }
    if (tpp06_process_identity::stock_cmdline(buffer, static_cast<size_t>(size))) {
      found = true; break;
    }
  }
  closedir(dir);
  return found;
}

bool LocalRelays::resync_keys_() {
  unsigned char keys[(KEY_MAX + 8) / 8]{};
  if (ioctl(input_fd_, EVIOCGKEY(sizeof(keys)), keys) < 0) return false;
  for (uint8_t i = 0; i < 3; ++i) down_[i] = bit_set(keys, KEY_F1 + i);
  resync_mute_();
  return true;  // Held keys never generate a synthetic press.
}

void LocalRelays::publish_mute_(const char *state) {
#ifdef USE_TPP06_MUTE_INPUT
  if (mute_sensor_ != nullptr && mute_sensor_->state != state) mute_sensor_->publish_state(state);
#else
  (void) state;
#endif
}

void LocalRelays::resync_mute_() {
#ifdef USE_TPP06_MUTE_INPUT
  if (mute_sensor_ == nullptr) return;
  unsigned char bits[(SW_MAX + 8) / 8]{};
  if (ioctl(input_fd_, EVIOCGBIT(EV_SW, sizeof(bits)), bits) < 0 || !bit_set(bits, SW_MUTE_DEVICE) ||
      ioctl(input_fd_, EVIOCGSW(sizeof(bits)), bits) < 0) {
    publish_mute_("Indisponible");
    return;  // An optional input failure must never disable the three relays.
  }
  publish_mute_(bit_set(bits, SW_MUTE_DEVICE) ? "Actif" : "Inactif");
#endif
}

void LocalRelays::setup_indicators_() {
  // An absent/broken optional indicator must never disable the local relay.
  const uint8_t pins[3] = {6, 85, 79};
  for (uint8_t i = 0; i < 3; ++i) {
    const std::string name = "button" + std::to_string(i + 1) + "_led";
    const std::string path = "/proc/device-tree/leds/" + name + "/gpios";
    unsigned char gpio[13]{};
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) continue;
    const ssize_t size = read(fd, gpio, sizeof(gpio)); close(fd);
    if (size != 12 || gpio[4] || gpio[5] || gpio[6] || gpio[7] != pins[i] ||
        gpio[8] || gpio[9] || gpio[10] || gpio[11]) continue;
    const std::string base = "/sys/class/leds/" + name;
    if (read_text(base + "/max_brightness", "255")) indicator_max_[i] = 255;
    else if (read_text(base + "/max_brightness", "1")) indicator_max_[i] = 1;
    indicator_available_[i] = indicator_max_[i] != 0;
  }
}

void LocalRelays::update_indicator_(uint8_t channel, bool relay_state) {
  if (!enabled_ || !indicator_available_[channel]) return;
  const bool on = indicators_follow_ && relay_state;
  if (indicator_written_[channel] && indicator_state_[channel] == on) return;
  const std::string path = "/sys/class/leds/button" + std::to_string(channel + 1) + "_led/brightness";
  const std::string expected = std::to_string(on ? indicator_max_[channel] : 0);
  const std::string bytes = expected + "\n";
  const int fd = open(path.c_str(), O_WRONLY | O_CLOEXEC);
  bool ok = false;
  if (fd >= 0) {
    const ssize_t written = write(fd, bytes.data(), bytes.size());
    const int closed = close(fd);
    ok = written == static_cast<ssize_t>(bytes.size()) && closed == 0 && read_text(path, expected.c_str());
  }
  if (!ok) {
    indicator_available_[channel] = false;
    ESP_LOGW(TAG, "Indicator %u unavailable; relay control is unchanged", channel + 1);
    return;
  }
  indicator_written_[channel] = true;
  indicator_state_[channel] = on;
}

void LocalRelays::fault_(const char *message) {
  if (!faulted_) ESP_LOGE(TAG, "%s; relay commands locked until restart", message);
  faulted_ = true;
  ready_ = false;
  publish_mute_("Indisponible");
  status_set_warning(message);
  // Never force outputs OFF on a fault: loads must not be switched implicitly.
}

void LocalRelays::setup() {
  for (auto *relay : relays_) if (relay == nullptr) { fault_("Three switches required"); return; }
  if (!profile_valid_() || stock_present_()) { fault_("Hardware or exclusive ownership check failed"); return; }
  // Stock TPP06 leaves /run on read-only squashfs; /var is writable tmpfs.
  lock_fd_ = open("/var/run/tpp06-local-relays.lock", O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (lock_fd_ < 0) {
    ESP_LOGE(TAG, "Cannot open runtime lock (errno=%d)", errno);
    fault_("Runtime lock file unavailable"); close_(); return;
  }
  if (flock(lock_fd_, LOCK_EX | LOCK_NB) != 0) {
    ESP_LOGE(TAG, "Cannot acquire runtime lock (errno=%d)", errno);
    fault_("Exclusive runtime lock unavailable"); close_(); return;
  }
  input_fd_ = open(input_device_.c_str(), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
  char name[64]{};
  unsigned char keys[(KEY_MAX + 8) / 8]{};
  if (input_fd_ < 0 || ioctl(input_fd_, EVIOCGNAME(sizeof(name)), name) < 0 ||
      std::strncmp(name, "gpiokeys", sizeof(name)) != 0 ||
      ioctl(input_fd_, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) < 0 ||
      !bit_set(keys, KEY_F1) || !bit_set(keys, KEY_F2) || !bit_set(keys, KEY_F3) || !resync_keys_()) {
    fault_("Physical key device does not match"); close_(); return;
  }
  // No restored preferences and no write at startup. Read actual GPIO levels.
  // Keep ready_ false during publication to reject startup callback writes.
  for (uint8_t i = 0; i < 3; ++i) {
    bool state;
    if (!read_channel_(i, state)) { fault_("Cannot read initial relay state"); return; }
    relays_[i]->publish_state(state);
  }
  ready_ = true;
  setup_indicators_();
  for (uint8_t i = 0; i < 3; ++i) update_indicator_(i, relays_[i]->state);
  last_check_ = millis();
  if (!enabled_) status_set_warning("Observation only: relay control disabled");
}

bool LocalRelays::command(uint8_t channel, bool value) {
  if (!ready_ || faulted_ || !enabled_ || channel >= 3) return false;
  bool before;
  if (stock_present_() || !read_channel_(channel, before)) {
    fault_("Relay ownership or read check failed"); return false;
  }
  if (before == value) {
    // Explicit ON starts a timer even if boot inherited an ON state. Repeated
    // ON commands do not extend an existing pulse (e.g. HA reconnects).
    if (value && pulse_ms_[channel] && !pulse_active_[channel]) {
      pulse_active_[channel] = true; pulse_started_[channel] = millis();
    }
    if (!value) pulse_active_[channel] = false;
    update_indicator_(channel, before);
    relays_[channel]->publish_state(before); return true;
  }
  int fd = open(gpio_path_(channel, "value").c_str(), O_WRONLY | O_CLOEXEC);
  if (fd < 0) { fault_("Cannot open relay output"); return false; }
  const char bytes[2] = {value ? '1' : '0', '\n'};
  const ssize_t written = write(fd, bytes, sizeof(bytes));
  const int closed = close(fd);
  bool actual;
  const bool readable = read_channel_(channel, actual);
  if (written != sizeof(bytes) || closed != 0 || !readable || actual != value) {
    fault_("Relay write/readback failed");
    if (readable) relays_[channel]->publish_state(actual);
    return false;
  }
  pulse_active_[channel] = value && pulse_ms_[channel] != 0;
  if (pulse_active_[channel]) pulse_started_[channel] = millis();
  update_indicator_(channel, actual);
  relays_[channel]->publish_state(actual);
  return true;
}

void LocalRelays::event_(uint16_t type, uint16_t code, int32_t value) {
  if (type == EV_SYN && code == SYN_DROPPED) {
    dropped_ = true; publish_mute_("Indisponible"); return;
  }
  if (dropped_) {
    if (type == EV_SYN && code == SYN_REPORT) {
      if (!resync_keys_()) fault_("Cannot resynchronize keys");
      dropped_ = false;
    }
    return;
  }
  if (type == EV_SW && code == SW_MUTE_DEVICE && (value == 0 || value == 1)) {
    // Identify the fourth input on site; never interpret it as KEY_POWER or
    // assign a shutdown/general relay action from an unverified label.
    ESP_LOGI(TAG, "SW_MUTE_DEVICE=%d (observation only, no action)", value);
    publish_mute_(value ? "Actif" : "Inactif");
    return;
  }
  if (type != EV_KEY || code < KEY_F1 || code > KEY_F3 || (value != 0 && value != 1)) return;
  const uint8_t key = code - KEY_F1;
  if (value == 0) { down_[key] = false; return; }
  if (down_[key]) return;
  down_[key] = true;
  const uint32_t now = millis();
  if (seen_press_[key] && uint32_t(now - last_press_[key]) < 150) return;
  seen_press_[key] = true; last_press_[key] = now;
  ESP_LOGI(TAG, "F%u press -> channel %u (%s)", key + 1, key_channel_[key] + 1,
           enabled_ ? "local control" : "observation only");
  if (!enabled_) return;
  bool state;
  const uint8_t channel = key_channel_[key];
  if (!read_channel_(channel, state)) { fault_("Cannot read relay before toggle"); return; }
  command(channel, !state);  // Direct local call: no API, Wi-Fi or HA dependency.
}

void LocalRelays::loop() {
  if (!ready_ || faulted_) return;
  const uint32_t now = millis();
  for (uint8_t i = 0; i < 3; ++i) {
    if (pulse_active_[i] && uint32_t(now - pulse_started_[i]) >= pulse_ms_[i]) {
      if (!command(i, false)) return;
    }
  }
  if (uint32_t(now - last_check_) >= 1000) {
    last_check_ = now;
    if (stock_present_()) { fault_("Stock controller detected"); return; }
    for (uint8_t i = 0; i < 3; ++i) {
      bool state;
      if (!read_channel_(i, state)) { fault_("Relay state unavailable"); return; }
      update_indicator_(i, state);
      relays_[i]->publish_state(state);
    }
  }
  // Bound work per loop; a held key or busy event stream cannot starve LVGL.
  for (uint8_t count = 0; count < 32 && ready_; ++count) {
    InputEvent32 event{};
    const ssize_t size = read(input_fd_, &event, sizeof(event));
    if (size == -1 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) break;
    if (size != sizeof(event)) { fault_("Key event read failed"); break; }
    event_(event.type, event.code, event.value);
  }
}

void LocalRelays::close_() {
  ready_ = false;
  if (input_fd_ >= 0) { close(input_fd_); input_fd_ = -1; }
  if (lock_fd_ >= 0) { close(lock_fd_); lock_fd_ = -1; }
}
void LocalRelays::on_shutdown() { close_(); }
void LocalRelays::dump_config() {
  ESP_LOGCONFIG(TAG, "TPP06 local relays: control=%s ready=%s", YESNO(enabled_), YESNO(ready_));
}
void RelaySwitch::write_state(bool state) {
  if (parent_ != nullptr) parent_->command(channel_, state);
}
}  // namespace esphome::tpp06_local_relays
#endif
