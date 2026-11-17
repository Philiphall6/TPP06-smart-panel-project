#include "evdev_touchscreen.h"

#ifdef USE_HOST

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/input.h>
#include <unistd.h>

#include "esphome/core/log.h"

namespace esphome::evdev {

static const char *const TAG = "evdev.touchscreen";

// Kernel 4.4 on the 32-bit TPP06 always sends a 16-byte input_event. Defining
// the wire layout explicitly avoids a time_t-size mismatch with modern uClibc.
struct InputEvent32 {
  int32_t seconds;
  int32_t microseconds;
  uint16_t type;
  uint16_t code;
  int32_t value;
};

void EvdevTouchscreen::setup() {
  this->fd_ = open(this->device_.c_str(), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
  if (this->fd_ < 0) {
    ESP_LOGE(TAG, "Cannot open %s: %s", this->device_.c_str(), std::strerror(errno));
    this->mark_failed();
    return;
  }
  ESP_LOGI(TAG, "Reading Goodix events from %s", this->device_.c_str());
}

void EvdevTouchscreen::dump_config() {
  ESP_LOGCONFIG(TAG, "Linux evdev touchscreen:");
  ESP_LOGCONFIG(TAG, "  Device: %s", this->device_.c_str());
}

void EvdevTouchscreen::on_shutdown() {
  if (this->fd_ >= 0) {
    close(this->fd_);
    this->fd_ = -1;
  }
}

void EvdevTouchscreen::update_touches() {
  if (this->fd_ < 0)
    return;

  InputEvent32 event{};
  while (read(this->fd_, &event, sizeof(event)) == sizeof(event)) {
    if (event.type != EV_ABS)
      continue;
    if (event.code == ABS_MT_SLOT) {
      this->slot_ = event.value;
    } else if (this->slot_ == 0 && event.code == ABS_MT_POSITION_X) {
      this->x_ = event.value;
    } else if (this->slot_ == 0 && event.code == ABS_MT_POSITION_Y) {
      this->y_ = event.value;
    } else if (this->slot_ == 0 && event.code == ABS_MT_TRACKING_ID) {
      this->pressed_ = event.value >= 0;
    }
  }
  if (this->pressed_)
    this->add_raw_touch_position_(0, this->x_, this->y_);
}

}  // namespace esphome::evdev

#endif
