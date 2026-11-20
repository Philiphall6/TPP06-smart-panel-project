#ifndef ESPHOME_TPP06_PROCESS_IDENTITY_H
#define ESPHOME_TPP06_PROCESS_IDENTITY_H
// Shared guard is intentional: ESPHome's umbrella header includes both
// standalone copies in the same translation unit.
#include <cstddef>
#include <string_view>

// Shared implementation kept identical in both standalone drivers; no extra
// ESPHome component or linker flags are needed to use this pure parser.
namespace esphome::tpp06_process_identity {
inline std::string_view basename(std::string_view token) {
  const auto slash = token.find_last_of('/');
  return slash == token.npos ? token : token.substr(slash + 1);
}
inline bool controller_name(std::string_view token) {
  token = basename(token);
  return token == "voice_control_ak3760e" || token == "tuya_monitor.sh";
}
inline bool shell_name(std::string_view token) {
  token = basename(token);
  return token == "sh" || token == "ash" || token == "bash" || token == "dash";
}
inline bool stock_cmdline(const char *data, size_t length) {
  size_t offset = 0;
  auto next = [&]() -> std::string_view {
    const size_t start = offset;
    while (offset < length && data[offset] != '\0') ++offset;
    const auto token = std::string_view(data + start, offset - start);
    if (offset < length) ++offset;
    return token;
  };
  if (length == 0) return false;  // Kernel thread or exited process.
  auto executable = next();
  if (controller_name(executable)) return true;
  if (basename(executable) == "busybox") executable = next();
  if (!shell_name(executable)) return false;
  while (offset < length) {
    auto argument = next();
    if (argument == "--") return controller_name(next());
    if (argument == "-o" || argument == "+o") { next(); continue; }
    if (!argument.empty() && (argument.front() == '-' || argument.front() == '+')) {
      // A shell command string is data, not the executable/script identity.
      // This excludes SSH diagnostics such as sh -c 'pidof ...'.
      if (argument.front() == '-' && argument.find('c') != argument.npos) return false;
      continue;
    }
    return controller_name(argument);
  }
  return false;
}
}  // namespace esphome::tpp06_process_identity
#endif  // ESPHOME_TPP06_PROCESS_IDENTITY_H
