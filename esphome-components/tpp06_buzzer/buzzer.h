#pragma once
#ifdef USE_HOST
#include <atomic>
#include <cstdint>
#include <pthread.h>
#include <string>
#include "esphome/core/component.h"

namespace esphome::tpp06_buzzer {
class Buzzer : public Component {
 public:
  ~Buzzer();
  void setup() override;
  void loop() override;
  void on_shutdown() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }
  bool available() const { return ready_ && !fault_.load(); }
  bool enabled() const { return available() && enabled_.load(); }
  // Accept restored preferences before component setup; available() still gates playback.
  void set_enabled(bool enabled) { enabled_.store(enabled); }
  void click();
 protected:
  static void *worker_(void *self);
  bool ready_{false}, joinable_{false}, seen_click_{false}, warned_{false};
  uint32_t last_click_{0};
  pthread_t worker_id_{};
  std::string failure_stage_;
  int failure_errno_{0};
  std::atomic<bool> enabled_{false}, finished_{false}, fault_{false};
};
}  // namespace esphome::tpp06_buzzer
#endif
