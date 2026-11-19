#pragma once
#ifdef USE_HOST
#include "esphome/core/component.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include <string>
#include "wpa_signal.h"

namespace esphome::tpp06_health {
class Health : public PollingComponent {
 public:
  void update() override;
  void loop() override;
  void set_heartbeat(bool enabled) { heartbeat_ = enabled; }
  void set_interface(const std::string &value) { interface_ = value; }
  void set_memory(text_sensor::TextSensor *sensor) { memory_ = sensor; }
  void set_wifi_signal(text_sensor::TextSensor *sensor) { wifi_signal_ = sensor; }
  void set_wifi_signal_via_wpa(bool enabled) { wifi_signal_via_wpa_ = enabled; }
  void set_link(text_sensor::TextSensor *sensor) { link_ = sensor; }
  void set_supervisor(text_sensor::TextSensor *sensor) { supervisor_ = sensor; }
  void set_ota_capacity(text_sensor::TextSensor *sensor) { ota_capacity_ = sensor; }
 protected:
  bool heartbeat_{false};
  std::string interface_{"wlan0"};
  text_sensor::TextSensor *memory_{nullptr};
  text_sensor::TextSensor *wifi_signal_{nullptr};
  bool wifi_signal_via_wpa_{false};
  WpaSignalPoll signal_query_;
  text_sensor::TextSensor *link_{nullptr};
  text_sensor::TextSensor *supervisor_{nullptr};
  text_sensor::TextSensor *ota_capacity_{nullptr};
};
}  // namespace esphome::tpp06_health
#endif
