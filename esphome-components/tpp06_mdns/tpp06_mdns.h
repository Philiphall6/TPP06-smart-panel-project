#pragma once
#include "esphome/core/component.h"
#include "esphome/components/mdns/mdns_component.h"
#include "mdns_vendor.h"
#include <string>
#include <vector>

namespace esphome::tpp06_mdns {

// Bounds-check a complete DNS datagram before passing it to the vendored parser.
bool valid_packet(const void *data, size_t size);

class Publisher : public Component {
 public:
  void set_records(mdns::MDNSComponent *records) { provider_ = records; }
  void set_interface(const std::string &name) { interface_ = name; }
  void setup() override;
  void loop() override;
  void on_shutdown() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_CONNECTION - 1; }

 protected:
  struct Service {
    std::string type;
    std::string instance;
    std::vector<mdns_record_t> records;
  };
  static int callback_(int sock, const sockaddr *from, size_t addrlen, mdns_entry_type_t entry,
                       uint16_t id, uint16_t type, uint16_t rclass, uint32_t ttl,
                       const void *data, size_t size, size_t name_offset, size_t name_length,
                       size_t record_offset, size_t record_length, void *user);
  void refresh_network_();
  void close_();
  void announce_(uint32_t ttl);
  void probe_();
  bool send_(const std::vector<mdns_record_t> &records, uint32_t ttl,
             const sockaddr *to = nullptr, size_t addrlen = 0, uint16_t id = 0,
             const char *question = nullptr, uint16_t question_type = 0);
  mdns_record_t address_record_() const;
  mdns::MDNSComponent *provider_{nullptr};
  std::string interface_;
  std::string hostname_;
  std::vector<Service> services_;
  int socket_{-1};
  in_addr address_{};
  uint32_t next_network_check_{0};
  uint32_t next_probe_{0};
  uint32_t next_announcement_{0};
  uint8_t probes_{0};
  uint8_t announcements_{0};
  bool advertised_{false};
  bool conflict_{false};
  alignas(4) uint8_t receive_buffer_[4096]{};
  alignas(4) uint8_t send_buffer_[4096]{};
};
}  // namespace esphome::tpp06_mdns
