#include "tpp06_backlight.h"

#include <cstdio>
#include <unistd.h>
#include "esphome/core/log.h"

namespace esphome::tpp06_backlight {
static const char *const TAG = "tpp06_backlight";

bool Backlight::read_(const char *attribute, int &value) {
  FILE *file = fopen((this->base_ + "/" + attribute).c_str(), "r");
  if (file == nullptr) return false;
  const bool ok = fscanf(file, "%d", &value) == 1;
  fclose(file);
  return ok;
}

void Backlight::setup() {
  // Read-only discovery. Unknown/missing devices never cause screen-off.
  this->available_ = this->read_("max_brightness", this->maximum_) &&
      this->maximum_ > 0 && this->maximum_ <= 65535 &&
      this->read_("brightness", this->original_) &&
      this->original_ >= 0 && this->original_ <= this->maximum_ &&
      access((this->base_ + "/brightness").c_str(), W_OK) == 0;
  if (!this->available_) this->status_set_warning("Backlight unavailable; sleep disabled");
}

bool Backlight::write_(int value) {
  if (!this->available_ || value < 0 || value > this->maximum_) return false;
  FILE *file = fopen((this->base_ + "/brightness").c_str(), "w");
  if (file == nullptr) {
    this->status_set_warning("Backlight write failed");
    return false;
  }
  const bool written = fprintf(file, "%d\n", value) > 0;
  const bool closed = fclose(file) == 0;
  int actual = -1;
  const bool ok = written && closed && this->read_("brightness", actual) && actual == value;
  if (ok) this->status_clear_warning();
  else this->status_set_warning("Backlight readback failed");
  return ok;
}

bool Backlight::set_percent(int percent) {
  // Never let the brightness slider leave the owner with an invisible UI.
  this->percent_ = percent < 10 ? 10 : percent > 100 ? 100 : percent;
  return this->sleeping_ || this->wake();
}

bool Backlight::sleep() {
  if (!this->write_(0)) {
    this->wake();  // Best effort recovery if writing succeeded but readback failed.
    return false;
  }
  this->sleeping_ = true;
  return true;
}

bool Backlight::wake() {
  this->sleeping_ = false;
  const int value = (this->maximum_ * this->percent_ + 99) / 100;
  return this->write_(value);
}

void Backlight::on_shutdown() {
  // Orderly stop/OTA must leave the stock fallback visible, even during sleep.
  if (this->available_) this->write_(this->original_ > 0 ? this->original_ : this->maximum_);
}

void Backlight::dump_config() {
  ESP_LOGCONFIG(TAG, "Linux backlight: %s, available=%s", this->base_.c_str(), YESNO(this->available_));
}
}  // namespace esphome::tpp06_backlight
