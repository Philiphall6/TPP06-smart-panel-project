#pragma once
// Linux-local read-only request. No process, network scan, profile write or IP traffic.
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

namespace esphome::tpp06_health {
inline std::string wpa_signal_summary(const std::string &reply) {
  if (reply.empty() || reply.size() >= 4096 || reply.find('\0') != std::string::npos)
    return "Indisponible";
  bool found = false;
  unsigned magnitude = 0;
  size_t start = 0;
  while (start < reply.size()) {
    const size_t end = reply.find('\n', start);
    if (end == std::string::npos) return "Indisponible";  // Refuse partial responses.
    const std::string line = reply.substr(start, end - start);
    if (line.compare(0, 5, "RSSI=") == 0) {
      if (found || line.size() < 7 || line.size() > 9 || line[5] != '-') return "Indisponible";
      found = true;
      for (size_t i = 6; i < line.size(); ++i) {
        if (line[i] < '0' || line[i] > '9') return "Indisponible";
        magnitude = magnitude * 10 + (line[i] - '0');
      }
      if (magnitude == 0 || magnitude > 127) return "Indisponible";
    }
    start = end + 1;
  }
  return found ? "-" + std::to_string(magnitude) + " dBm" : "Indisponible";
}

class WpaSignalPoll {
 public:
  WpaSignalPoll() = default;
  ~WpaSignalPoll() { cancel(); }
  WpaSignalPoll(const WpaSignalPoll &) = delete;
  WpaSignalPoll &operator=(const WpaSignalPoll &) = delete;
  void cancel() { if (fd_ >= 0) ::close(fd_); fd_ = -1; }
  bool begin(const std::string &path, uint32_t now) {
    cancel();
    struct sockaddr_un remote{};
    if (path.empty() || path[0] != '/' || path.size() >= sizeof(remote.sun_path) ||
        path.find('\0') != std::string::npos) return false;
    fd_ = ::socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (fd_ < 0) return false;
    struct sockaddr_un local{};
    local.sun_family = remote.sun_family = AF_UNIX;
    // Linux autobind creates an abstract address, removed automatically on close.
    // No socket files, mkdir, unlink or credentials are needed in /data or /tmp.
    std::memcpy(remote.sun_path, path.c_str(), path.size() + 1);
    constexpr char REQUEST[] = "SIGNAL_POLL";
    if (::bind(fd_, reinterpret_cast<struct sockaddr *>(&local), offsetof(sockaddr_un, sun_path)) != 0 ||
        ::connect(fd_, reinterpret_cast<struct sockaddr *>(&remote),
                  offsetof(sockaddr_un, sun_path) + path.size() + 1) != 0 ||
        ::send(fd_, REQUEST, sizeof(REQUEST) - 1, MSG_NOSIGNAL) != sizeof(REQUEST) - 1) {
      cancel();
      return false;
    }
    started_ = now;
    return true;
  }
  // Called from loop(): never waits. A slow/unavailable service expires after 1 s.
  bool finish(uint32_t now, std::string &result) {
    if (fd_ < 0) return false;
    if (uint32_t(now - started_) >= 1000) {
      cancel(); result = "Indisponible"; return true;
    }
    char buffer[4096];
    const ssize_t size = ::recv(fd_, buffer, sizeof(buffer), MSG_DONTWAIT | MSG_TRUNC);
    if (size < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) return false;
    result = size > 0 && size < static_cast<ssize_t>(sizeof(buffer))
                 ? wpa_signal_summary(std::string(buffer, size)) : "Indisponible";
    cancel();
    return true;
  }
 protected:
  int fd_{-1};
  uint32_t started_{0};
};
}  // namespace esphome::tpp06_health
