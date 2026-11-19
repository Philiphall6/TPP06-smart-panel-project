#pragma once
namespace esphome::tpp06_buzzer {
// An enabled schedule with invalid time stays quiet. Equal hours: all-day silence.
inline bool quiet_hours(bool enabled, bool valid_time, int minute, int start_hour, int end_hour) {
  if (!enabled) return false;
  if (!valid_time || minute < 0 || minute >= 1440 || start_hour < 0 || start_hour > 23 ||
      end_hour < 0 || end_hour > 23) return true;
  const int start = start_hour * 60, end = end_hour * 60;
  if (start == end) return true;
  return start < end ? minute >= start && minute < end : minute >= start || minute < end;
}
}  // namespace esphome::tpp06_buzzer
