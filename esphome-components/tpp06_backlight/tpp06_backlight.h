#pragma once

#include <string>
#include "esphome/core/component.h"

namespace esphome::tpp06_backlight {

class Backlight : public Component {
 public:
  void set_device(const std::string &name) { this->base_ = "/sys/class/backlight/" + name; }
  void setup() override;
  void dump_config() override;
  void on_shutdown() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }
  bool available() const { return this->available_; }
  bool sleep();
  bool wake();
  bool set_percent(int percent);

 protected:
  bool read_(const char *attribute, int &value);
  bool write_(int value);
  std::string base_;
  int maximum_{0};
  int original_{0};
  int percent_{100};
  bool available_{false};
  bool sleeping_{false};
};

}  // namespace esphome::tpp06_backlight
