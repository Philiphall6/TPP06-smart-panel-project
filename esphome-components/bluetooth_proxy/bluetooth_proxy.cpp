#include "bluetooth_proxy.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include <cstdio>
#include <cstring>

namespace esphome::bluetooth_proxy {
static const char *const TAG = "linux_ble_proxy";
BluetoothProxy *global_bluetooth_proxy = nullptr;
BluetoothProxy::BluetoothProxy() { global_bluetooth_proxy = this; }

void BluetoothProxy::setup() {
  char path[80];
  snprintf(path, sizeof(path), "/sys/class/bluetooth/hci%u/address", controller_);
  FILE *file = fopen(path, "r");
  unsigned int values[6]{};
  if (file) {
    if (fscanf(file, "%2x:%2x:%2x:%2x:%2x:%2x", &values[0], &values[1], &values[2],
               &values[3], &values[4], &values[5]) == 6) {
      for (unsigned i = 0; i < 6; ++i) mac_[i] = values[i];
    }
    fclose(file);
  }
  scanner_.set_callback(this, [](void *self, const linux_mgmt::Advertisement &adv) {
    static_cast<BluetoothProxy *>(self)->advertisement_(adv);
  });
  if (!scanner_.open(millis())) status_set_warning("Bluetooth MGMT unavailable");
}

void BluetoothProxy::loop() {
  const uint32_t now = millis();
  scanner_.tick(now);
  const auto state = scanner_.state();
  if (state != last_state_) {
    last_state_ = state; report_pending_ = true;
    if (state == linux_mgmt::State::FAILED) {
      status_set_warning("BLE discovery failed");
      ESP_LOGW(TAG, "Discovery failed (code %u); no controller reset", scanner_.error());
    } else status_clear_warning();
  }
  if (uint32_t(now - flushed_at_) < 100) return;
  flushed_at_ = now;
  flush_();
  if (report_pending_ && connection_) {
    api::BluetoothScannerStateResponse response;
    response.state = static_cast<api::enums::BluetoothScannerState>(state);
    response.mode = api::enums::BLUETOOTH_SCANNER_MODE_ACTIVE;
    response.configured_mode = api::enums::BLUETOOTH_SCANNER_MODE_ACTIVE;
    report_pending_ = !connection_->send_message(response);
  }
}

void BluetoothProxy::advertisement_(const linux_mgmt::Advertisement &adv) {
  if (!connection_) return;
  if (response_.advertisements_len == response_.advertisements.size()) flush_();
  auto &out = response_.advertisements[response_.advertisements_len];
  if (adv.size > sizeof(out.data)) { ++dropped_; return; }
  out.address = adv.address; out.address_type = adv.address_type; out.rssi = adv.rssi;
  out.data_len = adv.size;
  std::memcpy(out.data, adv.data, adv.size);
  ++response_.advertisements_len;
}

void BluetoothProxy::flush_() {
  if (!response_.advertisements_len) return;
  if (connection_ && connection_->send_message(response_)) forwarded_ += response_.advertisements_len;
  else dropped_ += response_.advertisements_len;
  response_.advertisements_len = 0; // bounded memory, no backlog across sessions
}

void BluetoothProxy::subscribe_api_connection(api::APIConnection *connection, uint32_t flags) {
  // HA/aioesphomeapi negotiate raw advertisements. Older parsed-only clients
  // cannot receive this backend: do not start a scan for an incompatible client.
  if (!(flags & 1)) { ESP_LOGW(TAG, "Raw advertisement subscription required"); return; }
  connection_ = connection; response_.advertisements_len = 0;
  scanner_.set_subscriber(true); report_pending_ = true;
}
void BluetoothProxy::unsubscribe_api_connection(api::APIConnection *connection) {
  if (connection_ != connection) return;
  connection_ = nullptr; response_.advertisements_len = 0;
  scanner_.set_subscriber(false);
}
void BluetoothProxy::bluetooth_scanner_set_mode(bool active) {
  if (!active) ESP_LOGW(TAG, "Linux MGMT uses active LE discovery; passive mode is not supported");
  report_pending_ = true; // Always report actual mode, never pretend to switch.
}
void BluetoothProxy::get_bluetooth_mac_address_pretty(char *buffer) const {
  snprintf(buffer, 18, "%02X:%02X:%02X:%02X:%02X:%02X", mac_[0], mac_[1], mac_[2], mac_[3], mac_[4], mac_[5]);
}
const char *BluetoothProxy::status() const {
  if (scanner_.state() == linux_mgmt::State::FAILED) return "Pilote indisponible / consulter les logs";
  if (!enabled()) return "Detection desactivee";
  if (!subscribed()) return "En attente de Home Assistant";
  if (running()) return "Detection BLE active";
  return "Initialisation BLE";
}
void BluetoothProxy::dump_config() {
  ESP_LOGCONFIG(TAG, "Linux BLE advertisements: controller %u, no pairing or GATT", controller_);
}
}  // namespace esphome::bluetooth_proxy
