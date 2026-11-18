#pragma once
#ifdef USE_HOST
#include <cstdint>
#include <string>
#include "esphome/core/component.h"
#include "esphome/components/switch/switch.h"

namespace esphome::tpp06_local_relays {
class LocalRelays;

class RelaySwitch : public switch_::Switch {
 public:
  void set_parent(LocalRelays *parent, uint8_t channel) { parent_ = parent; channel_ = channel; }
 protected:
  void write_state(bool state) override;
  LocalRelays *parent_{nullptr};
  uint8_t channel_{0};
};

// Fixed TPP06 hardware profile. No network, HA services, preference restore,
// shell commands, GPIO export, direction changes or buzzer writes.
class LocalRelays : public Component {
 public:
  void setup() override;
  void loop() override;
  void on_shutdown() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }
  void set_control_enabled(bool enabled) { enabled_ = enabled; }
  void set_input_device(const std::string &path) { input_device_ = path; }
  void set_indicators_follow_relay(bool follow) { indicators_follow_ = follow; }
  void set_key_channel(uint8_t key, uint8_t channel) { if (key < 3 && channel < 3) key_channel_[key] = channel; }
  void set_pulse_duration(uint8_t channel, uint32_t ms) { if (channel < 3) pulse_ms_[channel] = ms; }
  void set_relay(uint8_t channel, RelaySwitch *relay) {
    if (channel < 3) { relays_[channel] = relay; relay->set_parent(this, channel); }
  }
  bool command(uint8_t channel, bool value);

 protected:
  bool profile_valid_();
  bool stock_present_();
  bool read_channel_(uint8_t channel, bool &value);
  bool resync_keys_();
  void setup_indicators_();
  void update_indicator_(uint8_t channel, bool relay_state);
  void fault_(const char *message);
  void event_(uint16_t type, uint16_t code, int32_t value);
  void close_();
  static std::string gpio_path_(uint8_t channel, const char *attribute);
  RelaySwitch *relays_[3]{};
  uint8_t key_channel_[3]{0, 1, 2};
  bool down_[3]{}, seen_press_[3]{};
  uint32_t last_press_[3]{};
  uint32_t pulse_ms_[3]{}, pulse_started_[3]{};
  bool pulse_active_[3]{};
  bool indicators_follow_{true}, indicator_available_[3]{}, indicator_written_[3]{}, indicator_state_[3]{};
  int indicator_max_[3]{};
  bool enabled_{false}, ready_{false}, faulted_{false}, dropped_{false};
  uint32_t last_check_{0};
  int input_fd_{-1}, lock_fd_{-1};
  std::string input_device_{"/dev/input/event0"};
};
}  // namespace esphome::tpp06_local_relays
#endif
