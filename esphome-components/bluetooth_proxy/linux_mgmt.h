#pragma once

// Linux MGMT wire ABI, documented by BlueZ:
// https://github.com/bluez/bluez/wiki/MGMT
// Byte-wise decoding avoids alignment and endian assumptions on ARMv5.
// This backend performs LE discovery only; it never pairs, advertises,
// connects, resets the adapter, powers it off, or accesses Wi-Fi.
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <sys/socket.h>
#include <unistd.h>

namespace esphome::bluetooth_proxy::linux_mgmt {
inline uint16_t u16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline uint32_t u32(const uint8_t *p) { return uint32_t(u16(p)) | (uint32_t(u16(p + 2)) << 16); }
inline void put16(uint8_t *p, uint16_t n) { p[0] = n & 255; p[1] = n >> 8; }

struct Advertisement {
  uint64_t address;
  uint8_t address_type;
  int8_t rssi;
  const uint8_t *data;
  uint16_t size;
};

// Check AD element boundaries; never truncate a manufacturer/service field.
inline bool advertisement(const uint8_t *p, size_t n, Advertisement &out) {
  if (n < 14 || (p[6] != 1 && p[6] != 2)) return false;
  const size_t size = u16(p + 12);
  if (size != n - 14 || size > 62 || static_cast<int8_t>(p[7]) == 127) return false;
  size_t pos = 0;
  while (pos < size) {
    const uint8_t len = p[14 + pos];
    if (len == 0) {
      for (size_t i = pos; i < size; ++i) if (p[14 + i] != 0) return false;
      break;
    }
    if (size_t(len) + 1 > size - pos) return false;
    pos += size_t(len) + 1;
  }
  out.address = 0;
  for (int i = 5; i >= 0; --i) out.address = (out.address << 8) | p[i];
  out.address_type = p[6] - 1;
  out.rssi = static_cast<int8_t>(p[7]);
  out.data = p + 14;
  out.size = size;
  return true;
}

enum class State : uint8_t { IDLE, STARTING, RUNNING, FAILED, STOPPING, STOPPED };

class Scanner {
 public:
  using Callback = void (*)(void *, const Advertisement &);
  void set_callback(void *instance, Callback callback) { instance_ = instance; callback_ = callback; }
  void set_controller(uint16_t controller) { index_ = controller; }
  bool enabled() const { return desired_; }
  bool running() const { return owned_ && state_ == State::RUNNING; }
  bool subscriber_ready() const { return subscriber_; }
  State state() const { return state_; }
  uint8_t error() const { return error_; }
  uint32_t received() const { return received_; }
  uint32_t rejected() const { return rejected_; }
  const uint8_t *address() const { return address_; }
  void set_subscriber(bool value) { subscriber_ = value; }
  void set_enabled(bool value) {
    if (desired_ == value) return;
    desired_ = value;
    if (value && state_ == State::FAILED && pending_ == 0 && !owned_) {
      error_ = 0; state_ = State::IDLE;
    }
  }

  bool open(uint32_t now) {
    if (fd_ >= 0) return true;
    fd_ = ::socket(31, SOCK_RAW | SOCK_NONBLOCK | SOCK_CLOEXEC, 1);
    if (fd_ < 0) { fail_(0xf0); return false; }
    struct Address { sa_family_t family; uint16_t device, channel; } addr{31, 0xffff, 3};
    if (::bind(fd_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0) {
      ::close(fd_); fd_ = -1; fail_(0xf1); return false;
    }
    return command_(4, nullptr, 0, now);  // Read cached controller information.
  }

  void tick(uint32_t now) {
    if (fd_ < 0) return;
    // Bound main-loop work even in a busy radio environment.
    for (unsigned i = 0; i < 8; ++i) {
      uint8_t packet[1024];
      const ssize_t n = ::recv(fd_, packet, sizeof(packet), MSG_DONTWAIT | MSG_TRUNC);
      if (n < 0) {
        if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) fail_(0xf2);
        break;
      }
      if (n == 0) { fail_(0xf2); break; }
      if (size_t(n) > sizeof(packet)) { ++rejected_; continue; }
      consume(packet, static_cast<size_t>(n), now);
    }
    if (pending_ && uint32_t(now - sent_at_) > 10000) {
      // Never retry START blindly: a late completion could already own a scan.
      fail_(0xf3);
      return;
    }
    if (pending_ || state_ == State::FAILED || !info_ready_) return;
    if (!desired_ || !subscriber_) {
      if (owned_) { const uint8_t type = 6; state_ = State::STOPPING; command_(0x24, &type, 1, now); }
      else state_ = State::STOPPED;
      return;
    }
    if (owned_) return;
    state_ = State::STARTING;
    const uint8_t on = 1;
    if (!(settings_ & 0x200)) { command_(0x0d, &on, 1, now); return; }
    if (!(settings_ & 1)) { command_(5, &on, 1, now); return; }
    if (uint32_t(now - ended_at_) < 500) return;
    const uint8_t type = 6;  // LE public and random, NOT Bluetooth Classic.
    command_(0x23, &type, 1, now);
  }

  // Public for offline wire-format/state-machine tests.
  void consume(const uint8_t *p, size_t n, uint32_t now) {
    if (n < 6 || u16(p + 2) != index_ || u16(p + 4) != n - 6) return;
    const uint16_t event = u16(p);
    p += 6; n -= 6;
    if (event == 1 || event == 2) { // Command Complete / Command Status.
      if (n < 3 || u16(p) != pending_ || !pending_) return;
      const uint16_t op = pending_;
      pending_ = 0;
      if (p[2]) { fail_(p[2]); return; }
      if (event == 2) { fail_(0xf4); return; } // These commands require Complete.
      p += 3; n -= 3;
      if (op == 4) {
        if (n < 17 || !(u32(p + 9) & 0x200)) { fail_(0x0c); return; }
        std::memcpy(address_, p, 6);
        settings_ = u32(p + 13); info_ready_ = true;
      } else if (op == 5 || op == 0x0d) {
        if (n != 4) { fail_(0xf4); return; }
        settings_ = u32(p);
        if (!(settings_ & (op == 5 ? 1u : 0x200u))) { fail_(0xf4); return; }
      } else if (op == 0x23) {
        if (n != 1 || p[0] != 6) { fail_(0xf4); return; }
        owned_ = true;
        // If cancellation arrived during START, tick() sends STOP next.
        state_ = desired_ && subscriber_ ? State::RUNNING : State::STOPPING;
      } else if (op == 0x24) {
        owned_ = false; state_ = State::STOPPED; ended_at_ = now;
      }
    } else if (event == 6 && n == 4) { // New settings (external changes).
      settings_ = u32(p);
      if (!(settings_ & 1) && owned_) { owned_ = false; fail_(0x0f); }
    } else if (event == 0x13 && n == 2 && p[0] == 6 && p[1] == 0 && owned_) {
      owned_ = false; ended_at_ = now;
      if (!pending_) state_ = State::IDLE;
    } else if (event == 0x12 && running() && desired_ && subscriber_) {
      Advertisement adv{};
      if (!advertisement(p, n, adv)) { ++rejected_; return; }
      ++received_;
      if (callback_) callback_(instance_, adv);
    }
  }

  void close() {
    // Best effort STOP only for this scanner's acknowledged discovery.
    // No controller power-off/reset: the shared combo chip stays intact.
    if (fd_ >= 0) {
      if (owned_) {
        uint8_t stop[7] = {0x24, 0, 0, 0, 1, 0, 6};
        put16(stop + 2, index_);
        ::send(fd_, stop, sizeof(stop), MSG_DONTWAIT | MSG_NOSIGNAL);
      }
      ::close(fd_); fd_ = -1;
    }
    owned_ = false; pending_ = 0; info_ready_ = false;
  }

 protected:
  bool command_(uint16_t op, const uint8_t *data, size_t size, uint32_t now) {
    uint8_t packet[7] = {};
    if (size > 1 || pending_) return false;
    put16(packet, op); put16(packet + 2, index_); put16(packet + 4, size);
    if (size) packet[6] = data[0];
    if (::send(fd_, packet, 6 + size, MSG_DONTWAIT | MSG_NOSIGNAL) != ssize_t(6 + size)) {
      fail_(0xf5); return false;
    }
    pending_ = op; sent_at_ = now;
    return true;
  }
  void fail_(uint8_t error) { error_ = error; state_ = State::FAILED; }
  int fd_{-1};
  uint16_t index_{0}, pending_{0};
  uint32_t sent_at_{0}, ended_at_{0}, settings_{0}, received_{0}, rejected_{0};
  uint8_t address_[6]{}, error_{0};
  bool desired_{false}, subscriber_{false}, owned_{false}, info_ready_{false};
  State state_{State::IDLE};
  void *instance_{nullptr};
  Callback callback_{nullptr};
};
}  // namespace esphome::bluetooth_proxy::linux_mgmt
