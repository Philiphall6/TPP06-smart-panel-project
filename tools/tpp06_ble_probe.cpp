// Bounded hardware acceptance test for the same backend used by ESPHome.
// Default: cached information only. Radio activity requires --scan-seconds.
#include "linux_mgmt.h"
#include <cstdio>
#include <cstdlib>
#include <ctime>

static uint32_t now_ms() {
  timespec ts{};
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return uint32_t(uint64_t(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000);
}
int main(int argc, char **argv) {
  unsigned seconds = 0;
  if (argc != 1) {
    if (argc != 3 || std::strcmp(argv[1], "--scan-seconds")) return 2;
    char *end = nullptr;
    unsigned long parsed = std::strtoul(argv[2], &end, 10);
    if (*end || parsed < 1 || parsed > 60) return 2;
    seconds = parsed;
  }
  using namespace esphome::bluetooth_proxy::linux_mgmt;
  Scanner scanner;
  const auto started = now_ms();
  if (!scanner.open(started)) return 1;
  scanner.set_subscriber(true);
  scanner.set_enabled(seconds > 0);
  bool running = false;
  while (uint32_t(now_ms() - started) < (seconds ? seconds * 1000 : 1500)) {
    scanner.tick(now_ms());
    running |= scanner.running();
    if (scanner.state() == State::FAILED) break;
    usleep(10000);
  }
  scanner.set_enabled(false);
  const auto stopping = now_ms();
  while (uint32_t(now_ms() - stopping) < 12000 && scanner.state() != State::FAILED) {
    scanner.tick(now_ms());
    if (scanner.state() == State::STOPPED) break;
    usleep(10000);
  }
  printf("RUNNING_OBSERVED=%u\nADVERTISEMENTS=%u\nREJECTED=%u\nFINAL_STATE=%u\nERROR=%u\n",
         running, scanner.received(), scanner.rejected(), unsigned(scanner.state()), scanner.error());
  const bool ok = scanner.state() == State::STOPPED && (!seconds || running);
  scanner.close();
  return ok ? 0 : 1;
}
