#include "fbdev_display.h"

#ifdef USE_HOST

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/fb.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "esphome/components/display/display_color_utils.h"
#include "esphome/core/log.h"

namespace esphome::fbdev {

static const char *const TAG = "fbdev";

uint16_t FbdevDisplay::rgb565_to_bgr565_(uint16_t pixel) {
  return static_cast<uint16_t>(((pixel & 0x001FU) << 11) | (pixel & 0x07E0U) | ((pixel & 0xF800U) >> 11));
}

void FbdevDisplay::setup() {
  this->fd_ = open(this->device_.c_str(), O_RDWR | O_CLOEXEC);
  if (this->fd_ < 0) {
    ESP_LOGE(TAG, "Cannot open %s: %s", this->device_.c_str(), std::strerror(errno));
    this->mark_failed();
    return;
  }

  fb_fix_screeninfo fixed{};
  fb_var_screeninfo variable{};
  if (ioctl(this->fd_, FBIOGET_FSCREENINFO, &fixed) < 0 || ioctl(this->fd_, FBIOGET_VSCREENINFO, &variable) < 0) {
    ESP_LOGE(TAG, "Cannot query %s: %s", this->device_.c_str(), std::strerror(errno));
    this->close_();
    this->mark_failed();
    return;
  }
  if (variable.bits_per_pixel != 16 || variable.xres < this->width_ || variable.yres < this->height_) {
    ESP_LOGE(TAG, "Unsupported framebuffer: %ux%u, %u bpp", variable.xres, variable.yres,
             variable.bits_per_pixel);
    this->close_();
    this->mark_failed();
    return;
  }

  this->stride_ = fixed.line_length;
  this->memory_size_ = fixed.smem_len;
  this->swap_red_blue_ = variable.red.offset == 0 && variable.blue.offset == 11;
  void *mapped = mmap(nullptr, this->memory_size_, PROT_READ | PROT_WRITE, MAP_SHARED, this->fd_, 0);
  if (mapped == MAP_FAILED) {
    this->memory_ = nullptr;
    ESP_LOGE(TAG, "Cannot map %s: %s", this->device_.c_str(), std::strerror(errno));
    this->close_();
    this->mark_failed();
    return;
  }
  this->memory_ = static_cast<uint8_t *>(mapped);
  ESP_LOGI(TAG, "Framebuffer %s: %ux%u, stride=%u, %s565", this->device_.c_str(), this->width_, this->height_,
           this->stride_, this->swap_red_blue_ ? "BGR" : "RGB");
}

void FbdevDisplay::close_() {
  if (this->memory_ != nullptr) {
    munmap(this->memory_, this->memory_size_);
    this->memory_ = nullptr;
  }
  if (this->fd_ >= 0) {
    close(this->fd_);
    this->fd_ = -1;
  }
}

void FbdevDisplay::on_shutdown() { this->close_(); }

void FbdevDisplay::dump_config() {
  LOG_DISPLAY("", "Linux framebuffer", this);
  ESP_LOGCONFIG(TAG, "  Device: %s", this->device_.c_str());
  ESP_LOGCONFIG(TAG, "  Pixel format: %s565", this->swap_red_blue_ ? "BGR" : "RGB");
}

int FbdevDisplay::get_width() {
  return this->rotation_ == display::DISPLAY_ROTATION_90_DEGREES ||
                 this->rotation_ == display::DISPLAY_ROTATION_270_DEGREES
             ? this->height_
             : this->width_;
}

int FbdevDisplay::get_height() {
  return this->rotation_ == display::DISPLAY_ROTATION_90_DEGREES ||
                 this->rotation_ == display::DISPLAY_ROTATION_270_DEGREES
             ? this->width_
             : this->height_;
}

void FbdevDisplay::update() { this->do_update_(); }

void FbdevDisplay::draw_pixel_at(int x, int y, Color color) {
  if (this->memory_ == nullptr || this->is_point_clipped(x, y))
    return;

  if (this->rotation_ == display::DISPLAY_ROTATION_180_DEGREES) {
    x = this->width_ - x - 1;
    y = this->height_ - y - 1;
  } else if (this->rotation_ == display::DISPLAY_ROTATION_90_DEGREES) {
    int tmp = x;
    x = this->width_ - y - 1;
    y = tmp;
  } else if (this->rotation_ == display::DISPLAY_ROTATION_270_DEGREES) {
    int tmp = y;
    y = this->height_ - x - 1;
    x = tmp;
  }

  uint16_t pixel = display::ColorUtil::color_to_565(color);
  if (this->swap_red_blue_)
    pixel = rgb565_to_bgr565_(pixel);
  auto *row = reinterpret_cast<uint16_t *>(this->memory_ + static_cast<size_t>(y) * this->stride_);
  row[x] = pixel;
}

void FbdevDisplay::draw_pixels_at(int x_start, int y_start, int w, int h, const uint8_t *ptr,
                                  display::ColorOrder order, display::ColorBitness bitness, bool big_endian,
                                  int x_offset, int y_offset, int x_pad) {
  if (this->memory_ == nullptr)
    return;
  if (this->rotation_ != display::DISPLAY_ROTATION_0_DEGREES || bitness != display::COLOR_BITNESS_565 || big_endian) {
    Display::draw_pixels_at(x_start, y_start, w, h, ptr, order, bitness, big_endian, x_offset, y_offset, x_pad);
    return;
  }

  const int source_stride = x_offset + w + x_pad;
  const auto *source = reinterpret_cast<const uint16_t *>(ptr) + y_offset * source_stride + x_offset;
  for (int y = 0; y < h; y++) {
    auto *destination = reinterpret_cast<uint16_t *>(
        this->memory_ + static_cast<size_t>(y_start + y) * this->stride_ + static_cast<size_t>(x_start) * 2U);
    if (!this->swap_red_blue_) {
      std::memcpy(destination, source, static_cast<size_t>(w) * 2U);
    } else {
      for (int x = 0; x < w; x++)
        destination[x] = rgb565_to_bgr565_(source[x]);
    }
    source += source_stride;
  }
}

}  // namespace esphome::fbdev

#endif
