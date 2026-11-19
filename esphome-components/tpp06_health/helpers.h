#pragma once
#include <cmath>
#include <cstdio>
#include <limits>
#include <sstream>
#include <string>

namespace esphome::tpp06_health {
inline std::string link_summary(const std::string &operstate, const std::string &carrier) {
  if (carrier == "0\n" || carrier == "0") return "Liaison inactive";
  if ((carrier == "1\n" || carrier == "1") && (operstate == "up\n" || operstate == "up"))
    return "Liaison active / Internet non teste";
  return "Indisponible";
}
inline std::string memory_summary(const std::string &input) {
  std::istringstream lines(input);
  std::string line;
  unsigned long long total = 0, available = 0;
  bool found_total = false, found_available = false;
  while (std::getline(lines, line)) {
    std::istringstream fields(line);
    std::string key, number, unit, extra;
    if (!(fields >> key >> number >> unit) || (fields >> extra) || unit != "kB" ||
        number.empty() || number.find_first_not_of("0123456789") != std::string::npos)
      continue;
    unsigned long long value = 0;
    bool valid = true;
    for (char digit : number) {
      if (value > (std::numeric_limits<unsigned long long>::max() - (digit - '0')) / 10) {
        valid = false; break;
      }
      value = value * 10 + (digit - '0');
    }
    if (!valid) continue;
    if (key == "MemTotal:") { total = value; found_total = true; }
    if (key == "MemAvailable:") { available = value; found_available = true; }
  }
  if (!found_total || !found_available || total == 0 || available > total)
    return "Indisponible";
  char result[96];
  std::snprintf(result, sizeof(result), "%.1f / %.1f Mio", available / 1024.0, total / 1024.0);
  return result;
}
inline std::string signal_summary(const std::string &input, const std::string &interface) {
  std::istringstream lines(input);
  std::string line;
  while (std::getline(lines, line)) {
    const auto colon = line.find(':');
    if (colon == std::string::npos) continue;
    auto name = line.substr(0, colon);
    const auto start = name.find_first_not_of(" \t");
    if (start == std::string::npos || name.substr(start) != interface) continue;
    std::istringstream fields(line.substr(colon + 1));
    std::string status;
    double quality, level;
    if (!(fields >> status >> quality >> level) || !std::isfinite(level) || level >= 0 || level < -127)
      return "Indisponible";
    // Do not invent dBm when a driver reports an unsigned/proprietary scale.
    char result[32];
    std::snprintf(result, sizeof(result), "%.0f dBm", level);
    return result;
  }
  return "Indisponible";
}
inline std::string supervisor_summary(const std::string &mode, const std::string &offline) {
  if (mode == "esphome-healthy\n" || mode == "esphome-healthy")
    return offline == "yes\n" || offline == "yes" ? "ESPHome / local confirme" : "ESPHome / hors-ligne non valide";
  if (mode == "tuya-fallback\n" || mode == "tuya-fallback") return "Secours Tuya";
  if (mode == "esphome-starting\n" || mode == "esphome-starting") return "ESPHome / demarrage";
  return "Indisponible";
}
inline bool ota_room(unsigned long long available, unsigned long long binary_size) {
  constexpr unsigned long long RESERVE = 2 * 1024 * 1024;
  return binary_size > 0 && binary_size <= std::numeric_limits<unsigned long long>::max() - RESERVE &&
         available >= binary_size + RESERVE;
}
}  // namespace esphome::tpp06_health
