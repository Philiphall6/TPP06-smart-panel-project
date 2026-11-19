#pragma once
#include "esphome/core/component.h"
#include "esphome/components/api/api_connection.h"
#include "linux_mgmt.h"

namespace esphome::bluetooth_proxy {
class BluetoothProxy : public Component {
 public:
  BluetoothProxy();
  void set_controller(uint16_t value) { controller_ = value; scanner_.set_controller(value); }
  void setup() override;
  void loop() override;
  void on_shutdown() override { scanner_.close(); }
  void dump_config() override;
  void set_enabled(bool enabled) { scanner_.set_enabled(enabled); }
  bool enabled() const { return scanner_.enabled(); }
  bool running() const { return scanner_.running(); }
  bool subscribed() const { return connection_ != nullptr; }
  const char *status() const;
  uint32_t received() const { return scanner_.received(); }
  uint32_t forwarded() const { return forwarded_; }
  uint32_t dropped() const { return dropped_ + scanner_.rejected(); }
  uint32_t get_feature_flags() const { return 1u | 32u | 64u; } // advertisements, raw data, scanner status; no GATT
  void get_bluetooth_mac_address_pretty(char *buffer) const;
  api::APIConnection *get_api_connection() const { return connection_; }
  void subscribe_api_connection(api::APIConnection *connection, uint32_t flags);
  void unsubscribe_api_connection(api::APIConnection *connection);
  void bluetooth_scanner_set_mode(bool active);
 protected:
  void advertisement_(const linux_mgmt::Advertisement &adv);
  void flush_();
  linux_mgmt::Scanner scanner_;
  api::APIConnection *connection_{nullptr};
  api::BluetoothLERawAdvertisementsResponse response_;
  uint32_t flushed_at_{0}, forwarded_{0}, dropped_{0};
  uint16_t controller_{0};
  uint8_t mac_[6]{};
  bool report_pending_{true};
  linux_mgmt::State last_state_{linux_mgmt::State::IDLE};
};
extern BluetoothProxy *global_bluetooth_proxy;
}  // namespace esphome::bluetooth_proxy
