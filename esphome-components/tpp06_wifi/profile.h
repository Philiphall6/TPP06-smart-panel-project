#pragma once
#include <string>

namespace esphome::tpp06_wifi {
inline bool make_request(const std::string &ssid, const std::string &password,
                         const std::string &token, std::string &result) {
  result.clear();
  if (ssid.empty() || ssid.size() > 32 || password.size() < 8 || password.size() > 64 ||
      token.empty() || token.size() > 48 || token.find_first_not_of("0123456789-") != std::string::npos)
    return false;
  const size_t dash = token.find('-');
  if (dash == 0 || dash == std::string::npos || dash == token.size() - 1 || token.find('-', dash + 1) != std::string::npos)
    return false;
  for (unsigned char c : ssid) if (c < 32 || c == 127) return false;
  for (unsigned char c : password) if (c < 32 || c > 126) return false;
  // Embedded quotes interact with the configuration file's # comment parser.
  // Refuse them rather than silently changing the passphrase (raw PSK works).
  if (password.find('"') != std::string::npos) return false;
  const bool raw_key = password.size() == 64;
  if (raw_key && password.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos) return false;
  const char *hex = "0123456789abcdef";
  std::string encoded;
  for (unsigned char c : ssid) { encoded += hex[c >> 4]; encoded += hex[c & 15]; }
  // Backslashes are literal in WPA's quoted passphrase parser. Quotes,
  // newlines and control characters were rejected above.
  result = token + "\nctrl_interface=/var/run/wpa_supplicant\nupdate_config=0\nnetwork={\nssid=" + encoded +
           "\npsk=" + (raw_key ? password : "\"" + password + "\"") +
           "\nkey_mgmt=WPA-PSK\nscan_ssid=1\nid_str=\"tpp06-" + token + "\"\n}\n";
  return result.size() <= 512;
}
}  // namespace esphome::tpp06_wifi
