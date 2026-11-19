#pragma once

#ifdef USE_HOST

// 2026.11 split the GPIO definitions and made InternalGPIOPin a platform
// alias. Including hal.h here would re-enter gpio.h before this class exists.
#if __has_include("esphome/core/gpio_pin.h")
#include "esphome/core/gpio_pin.h"
#define TPP06_HOST_GPIO_ALIAS 1
#define TPP06_HOST_INTERNAL_OVERRIDE
#else
#include "esphome/core/hal.h"
#define TPP06_HOST_GPIO_ALIAS 0
#define TPP06_HOST_INTERNAL_OVERRIDE override
#endif

namespace esphome::host {

#if TPP06_HOST_GPIO_ALIAS
class HostGPIOPin final : public GPIOPin {
#else
class HostGPIOPin final : public InternalGPIOPin {
#endif
 public:
  void set_pin(uint8_t pin) { pin_ = pin; }
  void set_inverted(bool inverted) { inverted_ = inverted; }
  void set_flags(gpio::Flags flags) { flags_ = flags; }

  void setup() override { pin_mode(flags_); }
  void pin_mode(gpio::Flags flags) override;
  bool digital_read() override;
  void digital_write(bool value) override;
  size_t dump_summary(char *buffer, size_t len) const override;
  void detach_interrupt() const TPP06_HOST_INTERNAL_OVERRIDE;
  ISRInternalGPIOPin to_isr() const TPP06_HOST_INTERNAL_OVERRIDE;
  uint8_t get_pin() const TPP06_HOST_INTERNAL_OVERRIDE { return pin_; }
  gpio::Flags get_flags() const override { return flags_; }
  bool is_inverted() const TPP06_HOST_INTERNAL_OVERRIDE { return inverted_; }
  bool is_internal() override { return true; }

#if TPP06_HOST_GPIO_ALIAS
  template<typename T> void attach_interrupt(void (*func)(T *), T *arg, gpio::InterruptType type) const {
    this->attach_interrupt_(reinterpret_cast<void (*)(void *)>(func), arg, type);
  }
#else
  using InternalGPIOPin::attach_interrupt;
#endif

 protected:
  void attach_interrupt_(void (*func)(void *), void *arg, gpio::InterruptType type) const;
#if !TPP06_HOST_GPIO_ALIAS
  void attach_interrupt(void (*func)(void *), void *arg, gpio::InterruptType type) const override {
    this->attach_interrupt_(func, arg, type);
  }
#endif

  uint8_t pin_{};
  bool inverted_{};
  gpio::Flags flags_{};
};

}  // namespace esphome::host

#undef TPP06_HOST_INTERNAL_OVERRIDE
#undef TPP06_HOST_GPIO_ALIAS

#endif  // USE_HOST
