#include "tpp06_mdns.h"
#include "esphome/core/application.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include <net/if.h>
#include <sys/ioctl.h>

namespace esphome::tpp06_mdns {
static const char *const TAG = "tpp06.mdns";
static mdns_string_t view(const std::string &s) { return {s.c_str(), s.size()}; }
static bool equal(const mdns_string_t &name, const std::string &s) {
  return name.length == s.size() && strncasecmp(name.str, s.data(), s.size()) == 0;
}
static bool due(uint32_t now, uint32_t deadline) { return int32_t(now - deadline) >= 0; }

bool valid_packet(const void *data, size_t size) {
  if (size < 12 || size > 4096) return false;
  auto *bytes = static_cast<const uint8_t *>(data);
  auto read16 = [bytes](size_t at) { return uint16_t((bytes[at] << 8) | bytes[at + 1]); };
  uint16_t questions = read16(4);
  unsigned records = unsigned(read16(6)) + read16(8) + read16(10);
  if (questions > 64 || records > 128) return false;
  size_t offset = 12;
  for (unsigned i = 0; i < unsigned(questions) + records; i++) {
    if (!mdns_string_skip(data, size, &offset)) return false;
    size_t fixed = i < questions ? 4 : 10;
    if (offset > size || size - offset < fixed) return false;
    size_t length = i < questions ? 0 : read16(offset + 8);
    offset += fixed;
    if (length > size - offset) return false;
    offset += length;
  }
  return offset == size;
}

void Publisher::setup() {
  hostname_ = App.get_name().str() + ".local.";
  const auto &native = provider_->get_services();
  services_.resize(native.size());
  size_t index = 0;
  for (const auto &source : native) {
    auto &service = services_[index++];
    service.type = std::string(reinterpret_cast<const char *>(source.service_type)) + "." +
                   reinterpret_cast<const char *>(source.proto) + ".local.";
    service.instance = App.get_name().str() + "." + service.type;
    mdns_record_t ptr{};
    ptr.name = view(service.type);
    ptr.type = MDNS_RECORDTYPE_PTR;
    ptr.data.ptr.name = view(service.instance);
    service.records.push_back(ptr);
    mdns_record_t srv{};
    srv.name = view(service.instance);
    srv.type = MDNS_RECORDTYPE_SRV;
    srv.data.srv.name = view(hostname_);
    srv.data.srv.port = source.port.value();
    service.records.push_back(srv);
    for (const auto &txt : source.txt_records) {
      const auto *key = reinterpret_cast<const char *>(txt.key);
      const auto *value = reinterpret_cast<const char *>(txt.value);
      if (strlen(key) + strlen(value) + 1 > 255) {
        ESP_LOGE(TAG, "TXT record exceeds DNS-SD limit");
        mark_failed();
        return;
      }
      mdns_record_t record{};
      record.name = view(service.instance);
      record.type = MDNS_RECORDTYPE_TXT;
      record.data.txt.key = {key, strlen(key)};
      record.data.txt.value = {value, strlen(value)};
      service.records.push_back(record);
    }
  }
  refresh_network_();
}

mdns_record_t Publisher::address_record_() const {
  mdns_record_t record{};
  record.name = view(hostname_);
  record.type = MDNS_RECORDTYPE_A;
  record.data.a.addr.sin_family = AF_INET;
  record.data.a.addr.sin_addr = address_;
  return record;
}

void Publisher::refresh_network_() {
  next_network_check_ = millis() + 5000;
  int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
  ifreq request{};
  strncpy(request.ifr_name, interface_.c_str(), IFNAMSIZ - 1);
  bool ok = fd >= 0 && ioctl(fd, SIOCGIFADDR, &request) == 0;
  in_addr ip{};
  if (ok) ip = reinterpret_cast<sockaddr_in *>(&request.ifr_addr)->sin_addr;
  if (fd >= 0) ::close(fd);
  if (socket_ >= 0 && ok && ip.s_addr == address_.s_addr) return;
  close_();
  if (!ok || ip.s_addr == 0 || conflict_) return;
  sockaddr_in bind_address{};
  bind_address.sin_family = AF_INET;
  bind_address.sin_port = htons(MDNS_PORT);
  bind_address.sin_addr = ip;
  socket_ = mdns_socket_open_ipv4(&bind_address);
  if (socket_ < 0) {
    status_set_warning("mDNS socket unavailable; retrying");
    return;
  }
  fcntl(socket_, F_SETFD, FD_CLOEXEC);
  unsigned char ttl = 255;  // RFC 6762, unlike the library's generic default.
  setsockopt(socket_, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, sizeof(ttl));
  address_ = ip;
  probes_ = 0;
  announcements_ = 0;
  next_probe_ = millis() + random_uint32() % 251;
  status_clear_warning();
}

bool Publisher::send_(const std::vector<mdns_record_t> &records, uint32_t ttl,
                      const sockaddr *to, size_t addrlen, uint16_t id,
                      const char *question, uint16_t question_type) {
  if (socket_ < 0 || records.empty()) return false;
  bool legacy = to != nullptr && reinterpret_cast<const sockaddr_in *>(to)->sin_port != htons(MDNS_PORT);
  uint16_t rclass = MDNS_CLASS_IN | (legacy ? 0 : MDNS_CACHE_FLUSH);
  if (legacy && ttl > 10) ttl = 10;
  memset(send_buffer_, 0, 12);
  auto *header = reinterpret_cast<mdns_header_t *>(send_buffer_);
  header->query_id = htons(legacy ? id : 0);
  header->flags = htons(0x8400);
  header->answer_rrs = htons(mdns_answer_get_record_count(records.data(), records.size()));
  mdns_string_table_t table{};
  void *cursor = send_buffer_ + 12;
  if (legacy && question) {
    header->questions = htons(1);
    cursor = mdns_answer_add_question_unicast(send_buffer_, sizeof(send_buffer_), cursor,
        static_cast<mdns_record_type_t>(question_type), question, strlen(question), &table);
  }
  for (auto record : records) {
    record.ttl = ttl;
    record.rclass = record.type == MDNS_RECORDTYPE_PTR ? MDNS_CLASS_IN : rclass;
    cursor = mdns_answer_add_record(send_buffer_, sizeof(send_buffer_), cursor, record, &table);
  }
  cursor = mdns_answer_add_txt_record(send_buffer_, sizeof(send_buffer_), cursor,
      records.data(), records.size(), rclass, ttl, &table);
  if (!cursor) return false;
  size_t length = static_cast<uint8_t *>(cursor) - send_buffer_;
  return (to ? mdns_unicast_send(socket_, to, addrlen, send_buffer_, length)
             : mdns_multicast_send(socket_, send_buffer_, length)) == 0;
}

void Publisher::announce_(uint32_t ttl) {
  for (const auto &service : services_) {
    auto records = service.records;
    records.push_back(address_record_());
    if (!send_(records, ttl)) status_set_warning("mDNS announcement failed");
  }
}

void Publisher::probe_() {
  // Probe the hostname and every service instance before publishing any record.
  // On conflict we stop announcing rather than silently rename away from YAML.
  memset(send_buffer_, 0, 12);
  auto *header = reinterpret_cast<mdns_header_t *>(send_buffer_);
  header->questions = htons(1 + services_.size());
  header->authority_rrs = htons(1 + services_.size());
  mdns_string_table_t table{};
  void *cursor = send_buffer_ + 12;
  auto question = [&](const std::string &name) {
    if (!cursor) return;
    cursor = mdns_string_make(send_buffer_, sizeof(send_buffer_), cursor, name.data(), name.size(), &table);
    if (!cursor || static_cast<uint8_t *>(cursor) > send_buffer_ + sizeof(send_buffer_) - 4) {
      cursor = nullptr; return;
    }
    cursor = mdns_htons(cursor, MDNS_RECORDTYPE_ANY);
    cursor = mdns_htons(cursor, MDNS_CLASS_IN);
  };
  question(hostname_);
  for (const auto &service : services_) question(service.instance);
  auto add = [&](mdns_record_t record) {
    record.rclass = MDNS_CLASS_IN;
    record.ttl = 120;
    cursor = mdns_answer_add_record(send_buffer_, sizeof(send_buffer_), cursor, record, &table);
  };
  add(address_record_());
  for (const auto &service : services_) add(service.records[1]);
  if (cursor) mdns_multicast_send(socket_, send_buffer_, static_cast<uint8_t *>(cursor) - send_buffer_);
}

int Publisher::callback_(int, const sockaddr *from, size_t addrlen, mdns_entry_type_t entry,
    uint16_t id, uint16_t type, uint16_t rclass, uint32_t ttl, const void *data, size_t size,
    size_t name_offset, size_t, size_t record_offset, size_t record_length, void *user) {
  auto *self = static_cast<Publisher *>(user);
  char name_buffer[256]{};
  auto name = mdns_string_extract(data, size, &name_offset, name_buffer, sizeof(name_buffer)-1);
  if (name.length >= sizeof(name_buffer)-1) return 0;
  name_buffer[name.length] = 0;
  if (entry != MDNS_ENTRYTYPE_QUESTION) {
    // A query's known-answer cache may contain our old address after DHCP.
    // Only an actual response or a competing probe establishes a conflict.
    if (!(static_cast<const uint8_t *>(data)[2] & 0x80) && entry != MDNS_ENTRYTYPE_AUTHORITY) return 0;
    if (ttl == 0) return 0;
    bool conflict = false;
    if (type == MDNS_RECORDTYPE_A && record_length == 4 && equal(name, self->hostname_)) {
      in_addr ip{};
      memcpy(&ip.s_addr, static_cast<const uint8_t *>(data) + record_offset, 4);
      conflict = ip.s_addr != self->address_.s_addr;
    }
    if (type == MDNS_RECORDTYPE_SRV && record_length >= 7) {
      for (const auto &service : self->services_) {
        if (!equal(name, service.instance)) continue;
        char target[256]{};
        auto srv = mdns_record_parse_srv(data, size, record_offset, record_length, target, sizeof(target));
        conflict |= !equal(srv.name, self->hostname_) || srv.port != service.records[1].data.srv.port;
      }
    }
    if (conflict) {
      self->conflict_ = true;
      self->status_set_error(LOG_STR("mDNS name conflict; choose a unique device_name"));
      ESP_LOGE(TAG, "Name conflict: announcements stopped; IP access remains available");
      return 1;
    }
    return 0;
  }
  if (!self->advertised_ || self->conflict_) return 0;
  bool unicast = (rclass & MDNS_UNICAST_RESPONSE) ||
      reinterpret_cast<const sockaddr_in *>(from)->sin_port != htons(MDNS_PORT);
  auto answer = [&](const std::vector<mdns_record_t> &records) {
    self->send_(records, 120, unicast ? from : nullptr, addrlen, id, name_buffer, type);
  };
  if (equal(name, self->hostname_) && (type == MDNS_RECORDTYPE_A || type == MDNS_RECORDTYPE_ANY)) {
    answer({self->address_record_()});
  }
  for (const auto &service : self->services_) {
    if (equal(name, "_services._dns-sd._udp.local.") && (type == MDNS_RECORDTYPE_PTR || type == MDNS_RECORDTYPE_ANY)) {
      mdns_record_t record{};
      record.name = {"_services._dns-sd._udp.local.", strlen("_services._dns-sd._udp.local.")};
      record.type = MDNS_RECORDTYPE_PTR;
      record.data.ptr.name = view(service.type);
      answer({record});
    } else if ((equal(name, service.type) && (type == MDNS_RECORDTYPE_PTR || type == MDNS_RECORDTYPE_ANY)) ||
               (equal(name, service.instance) && (type == MDNS_RECORDTYPE_SRV || type == MDNS_RECORDTYPE_TXT || type == MDNS_RECORDTYPE_ANY))) {
      auto records = service.records;
      records.push_back(self->address_record_());
      answer(records);
    }
  }
  return 0;
}

void Publisher::loop() {
  uint32_t now = millis();
  if (conflict_) { close_(); return; }
  if (due(now, next_network_check_)) refresh_network_();
  if (socket_ < 0) return;
  // Bounded work per loop: a multicast flood must not stall LVGL or the API.
  for (unsigned i = 0; i < 4; i++) {
    ssize_t size = recv(socket_, receive_buffer_, sizeof(receive_buffer_), MSG_PEEK | MSG_TRUNC);
    if (size < 0) break;
    if (!valid_packet(receive_buffer_, size)) {
      recv(socket_, receive_buffer_, sizeof(receive_buffer_), 0);
      continue;
    }
    mdns_socket_listen(socket_, receive_buffer_, sizeof(receive_buffer_), callback_, this);
    if (conflict_) { close_(); return; }
  }
  if (!advertised_ && due(now, next_probe_)) {
    if (probes_ < 3) {
      probe_();
      probes_++;
      next_probe_ = now + 250;
    } else {
      advertised_ = true;
      next_announcement_ = now;
      ESP_LOGI(TAG, "IPv4 DNS-SD publishing started");
    }
  }
  if (advertised_ && due(now, next_announcement_)) {
    announce_(120);
    next_announcement_ = now + (announcements_++ == 0 ? 1000 : 60000);
    if (announcements_ > 2) announcements_ = 2;
  }
}

void Publisher::close_() {
  if (socket_ < 0) return;
  if (advertised_ && !conflict_) announce_(0);
  mdns_socket_close(socket_);
  socket_ = -1;
  advertised_ = false;
}
void Publisher::on_shutdown() { close_(); }
void Publisher::dump_config() {
  ESP_LOGCONFIG(TAG, "Linux IPv4 mDNS, interface: %s", interface_.c_str());
}
}  // namespace esphome::tpp06_mdns
