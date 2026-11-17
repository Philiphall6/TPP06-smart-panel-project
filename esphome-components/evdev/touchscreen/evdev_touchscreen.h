#pragma once

#ifdef USE_HOST

#include <cstdint>
#include <string>

#include "esphome/components/touchscreen/touchscreen.h"

namespace esphome::evdev {

class EvdevTouchscreen final : public touchscreen::Touchscreen {
 public:
  void setup() override;
  void dump_config() override;
  void on_shutdown() override;
  void set_device(const std::string &device) { this->device_ = device; }

 protected:
  void update_touches() override;

  std::string device_{"/dev/input/event1"};
  int fd_{-1};
  int32_t x_{0};
  int32_t y_{0};
  int32_t slot_{0};
  bool pressed_{false};
};

}  // namespace esphome::evdev

#endif
