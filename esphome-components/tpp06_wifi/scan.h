#pragma once
#include <algorithm>
#include <cstdlib>
#include <string>
#include <vector>

namespace esphome::tpp06_wifi {
struct WifiNetwork {
  std::string ssid;
  int signal;
  bool supported;
};
inline int scan_hex(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}
// SSIDs are untrusted bytes. Decode wpa's printf encoding, then accept only
// printable UTF-8; never turn them into shell commands or LVGL markup.
inline std::string scan_ssid(const std::string &encoded) {
  std::string out;
  for (size_t i = 0; i < encoded.size(); ++i) {
    char c = encoded[i];
    if (c == '\\') {
      if (++i == encoded.size()) return {};
      c = encoded[i];
      if (c == 'x') {
        if (i + 2 >= encoded.size()) return {};
        int a = scan_hex(encoded[i + 1]), b = scan_hex(encoded[i + 2]);
        if (a < 0 || b < 0) return {};
        c = static_cast<char>(a * 16 + b); i += 2;
      } else if (c != '\\' && c != '"') return {};
    }
    out += c;
    if (out.size() > 32) return {};
  }
  for (size_t i = 0; i < out.size();) {
    unsigned char c = out[i++];
    unsigned code = c, minimum = 0;
    int follow = 0;
    if (c >= 0xC2 && c <= 0xDF) { follow = 1; code = c & 31; minimum = 0x80; }
    else if (c >= 0xE0 && c <= 0xEF) { follow = 2; code = c & 15; minimum = 0x800; }
    else if (c >= 0xF0 && c <= 0xF4) { follow = 3; code = c & 7; minimum = 0x10000; }
    else if (c >= 0x80) return {};
    while (follow--) {
      if (i == out.size()) return {};
      unsigned char next = out[i++];
      if ((next & 0xC0) != 0x80) return {};
      code = (code << 6) | (next & 63);
    }
    if (code < minimum || code > 0x10FFFF || (code >= 0xD800 && code <= 0xDFFF) ||
        code < 32 || (code >= 127 && code <= 159) || code == 0x2028 || code == 0x2029 ||
        (code >= 0x202A && code <= 0x202E) || (code >= 0x2066 && code <= 0x2069)) return {};
  }
  return out;
}
inline std::vector<WifiNetwork> parse_scan(const std::string &raw) {
  std::vector<WifiNetwork> networks;
  if (raw.size() > 12000 || raw.compare(0, 5, "bssid") != 0) return networks;
  size_t start = raw.find('\n');
  if (start == std::string::npos) return networks;
  ++start;
  while (start < raw.size()) {
    size_t end = raw.find('\n', start);
    if (end == std::string::npos) break;  // Ignore a truncated last record.
    std::string row = raw.substr(start, end - start); start = end + 1;
    std::string fields[5];
    size_t pos = 0; bool valid = true;
    for (int f = 0; f < 4; ++f) {
      size_t tab = row.find('\t', pos);
      if (tab == std::string::npos) { valid = false; break; }
      fields[f] = row.substr(pos, tab - pos); pos = tab + 1;
    }
    if (!valid || fields[0].size() != 17) continue;
    for (size_t i = 0; i < 17; ++i)
      if (i % 3 == 2 ? fields[0][i] != ':' : scan_hex(fields[0][i]) < 0) valid = false;
    if (!valid || fields[2].empty() || fields[2].size() > 4) continue;
    char *tail = nullptr;
    long signal = std::strtol(fields[2].c_str(), &tail, 10);
    if (*tail || signal < -127 || signal > 255) continue;
    fields[4] = scan_ssid(row.substr(pos));
    if (fields[4].empty()) continue;
    bool supported = fields[3].find("PSK") != std::string::npos &&
                     fields[3].find("[ESS]") != std::string::npos &&
                     fields[3].find("WEP") == std::string::npos;
    // Some old drivers report unsigned levels; don't invent a dBm conversion.
    int dbm = signal < 0 ? static_cast<int>(signal) : -128;
    auto found = std::find_if(networks.begin(), networks.end(), [&](const WifiNetwork &n) {
      return n.ssid == fields[4] && n.supported == supported;
    });
    if (found != networks.end()) found->signal = std::max(found->signal, dbm);
    else networks.push_back({fields[4], dbm, supported});
  }
  std::stable_sort(networks.begin(), networks.end(), [](const WifiNetwork &a, const WifiNetwork &b) {
    return a.signal > b.signal;
  });
  if (networks.size() > 24) networks.resize(24);
  return networks;
}
}  // namespace esphome::tpp06_wifi
