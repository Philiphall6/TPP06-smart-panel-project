#pragma once
#include <cstdint>
#include <cstdio>
#include <limits>
#include <string>

namespace esphome::tpp06_system {
// Available blocks (f_bavail), not all free blocks (f_bfree). /data only,
// not RAM, the read-only firmware partitions, or a guessed NAND capacity.
inline std::string storage_summary(uint64_t blocks, uint64_t available, uint64_t unit) {
  if (!blocks || !unit || available > blocks || blocks > std::numeric_limits<uint64_t>::max() / unit)
    return "Indisponible";
  constexpr double MIB = 1048576.0;
  char text[96];
  std::snprintf(text, sizeof(text), "%.1f / %.1f Mio", available * unit / MIB, blocks * unit / MIB);
  return text;
}

struct RestartState {
  bool healthy, correct_mode, argv_valid, same_executable, executable, ota_absent, reexec_unarmed;
};
inline bool restart_allowed(const RestartState &s) {
  return s.healthy && s.correct_mode && s.argv_valid && s.same_executable &&
         s.executable && s.ota_absent && s.reexec_unarmed;
}
}  // namespace esphome::tpp06_system
