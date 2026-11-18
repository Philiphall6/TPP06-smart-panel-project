#pragma once

#ifdef USE_HOST

#include <cstddef>
#include <cstdint>
#include <string>
#include <linux/fb.h>

#include "esphome/components/display/display.h"
#include "esphome/core/component.h"

namespace esphome::fbdev {

enum class PixelFormat { AUTO, RGB565, BGR565 };

class FbdevDisplay final : public display::Display {
 public:
  void setup() override;
  void update() override;
  void loop() override;
  void dump_config() override;
  void on_shutdown() override;

  display::DisplayType get_display_type() override { return display::DISPLAY_TYPE_COLOR; }
  void draw_pixel_at(int x, int y, Color color) override;
  int get_width() override;
  int get_height() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }

  void set_device(const std::string &device) { this->device_ = device; }
  void set_pixel_format(PixelFormat format) { this->pixel_format_ = format; }
  void set_dimensions(uint16_t width, uint16_t height) {
    this->width_ = width;
    this->height_ = height;
  }

 protected:
  void draw_pixels_at(int x_start, int y_start, int w, int h, const uint8_t *ptr,
                      display::ColorOrder order, display::ColorBitness bitness, bool big_endian,
                      int x_offset, int y_offset, int x_pad) override;
  int get_width_internal() override { return this->width_; }
  int get_height_internal() override { return this->height_; }

  static uint16_t rgb565_to_bgr565_(uint16_t pixel);
  void close_();
  bool present_();

  std::string device_{"/dev/fb0"};
  int fd_{-1};
  uint8_t *memory_{nullptr};
  size_t memory_size_{0};
  uint32_t stride_{0};
  uint16_t width_{320};
  uint16_t height_{480};
  bool swap_red_blue_{false};
  PixelFormat pixel_format_{PixelFormat::AUTO};
  // Anyka keeps the bootloader scanout until fb_pan_display programs the
  // kernel framebuffer address. mmap writes alone do not perform that handoff.
  fb_var_screeninfo present_info_{};
  bool needs_pan_{false};
  bool dirty_{false};
  bool present_failed_{false};
  uint32_t last_present_attempt_{0};
};

}  // namespace esphome::fbdev

#endif
