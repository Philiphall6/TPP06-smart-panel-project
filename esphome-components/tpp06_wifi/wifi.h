#pragma once
#ifdef USE_HOST
#include "esphome/core/component.h"
#include <string>
#include "scan.h"

namespace esphome::tpp06_wifi {
class WifiEditor : public Component {
 public:
  bool available() const;
  bool start(const std::string &ssid, const std::string &password);
  bool confirm();
  bool cancel();
  std::string status_text() const;
  bool request_scan();
  void refresh_scan();
  void next_scan_page();
  std::string scan_status_text() const;
  std::string scan_row_text(size_t row) const;
  std::string scan_row_ssid(size_t row) const;
 protected:
  bool decision_(const char *action);
  std::string token_;
  std::string error_;
  std::string scan_token_, scan_state_, scan_loaded_;
  std::vector<WifiNetwork> networks_;
  size_t scan_page_{0};
  long long scan_started_{0};
  bool scan_fresh_() const;
};
}  // namespace esphome::tpp06_wifi
#endif
