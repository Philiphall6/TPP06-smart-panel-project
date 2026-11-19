#pragma once
#ifdef USE_HOST
#include "esphome/core/component.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/components/button/button.h"
#include <sys/types.h>

namespace esphome::tpp06_system {
class Storage : public text_sensor::TextSensor, public PollingComponent {
 public:
  void update() override;
};
class Restart : public button::Button, public Component {
 public:
  void set_device_reboot(bool value) { device_reboot_ = value; }
  void loop() override;
 protected:
  void press_action() override;
  bool can_restart_();
  bool device_ready_();
  void release_request_();
  bool device_reboot_{false};
  bool pending_{false};
  pid_t child_{-1};
};
}  // namespace esphome::tpp06_system
#endif
