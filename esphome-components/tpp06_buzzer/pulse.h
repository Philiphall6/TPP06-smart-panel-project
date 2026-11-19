#pragma once
#include <atomic>

namespace esphome::tpp06_buzzer {

// Injectable transaction boundary. Never call this on the UI/event-loop thread.
class PulseIO {
 public:
  virtual ~PulseIO() = default;
  virtual bool claim() = 0;  // Read-only profile/ownership checks + advisory lock.
  virtual bool export_channel() = 0;
  virtual bool read_pwm(const char *attribute, int &value) = 0;
  virtual bool pwm(const char *attribute, int value) = 0;
  virtual bool gate(unsigned channel, int value) = 0;
  virtual bool pause_500us() = 0;
  virtual bool unexport_channel() = 0;
  virtual void release() = 0;
};

inline bool play_click(PulseIO &io, const std::atomic<bool> &enabled) {
  if (!enabled.load()) return true;
  if (!io.claim()) return false;
  if (!enabled.load()) { io.release(); return true; }
  if (!io.export_channel()) { io.release(); return false; }

  // Linux 4.4 rejects duty writes while period is zero, even duty=0.
  // Match stock ordering, using the actual retained duty after export.
  int period = 0, duty = 0;
  bool ok = io.pwm("enable", 0) && io.read_pwm("period", period) &&
            io.read_pwm("duty_cycle", duty) && duty <= period;
  if (ok) {
    if (210526 > duty)
      ok = io.pwm("period", 210526) && io.pwm("duty_cycle", 105250);
    else
      ok = io.pwm("duty_cycle", 105250) && io.pwm("period", 210526);
  }
  if (ok && enabled.load()) ok = io.gate(1, 0) && io.gate(2, 1);
  if (ok && enabled.load()) {
    ok = io.pwm("enable", 1);
    // 4 ms requested total, cancellable between short waits. Not hard real-time.
    for (int step = 0; ok && enabled.load() && step < 8; ++step)
      ok = io.pause_500us();
  }

  // Cleanup on EVERY post-export path, including failed writes and cancellation.
  bool stopped = false;
  for (int attempt = 0; attempt < 3 && !stopped; ++attempt)
    stopped = io.pwm("enable", 0);
  bool gate2 = io.gate(2, 0);
  bool gate1 = io.gate(1, 0);
  // Keep sysfs accessible if PWM-off cannot be confirmed; report a hard fault.
  bool removed = stopped && io.unexport_channel();
  io.release();
  return ok && stopped && gate2 && gate1 && removed;
}
}  // namespace esphome::tpp06_buzzer
