"""Native driver unit tests with fake framebuffer syscalls; no panel/firmware build."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

COMPONENT = r'''
#pragma once
namespace esphome {
namespace setup_priority { constexpr float HARDWARE = 800; }
class Component {
 public:
  virtual ~Component() = default;
  virtual void setup() {}
  virtual void loop() {}
  virtual void update() {}
  virtual void dump_config() {}
  virtual void on_shutdown() {}
  virtual float get_setup_priority() const { return 0; }
  void mark_failed() { failed = true; }
  void status_set_warning(const char *) { warning = true; }
  void status_clear_warning() { warning = false; }
  bool warning = false, failed = false;
};
}
'''
DISPLAY = r'''
#pragma once
#include <cstdint>
#include "esphome/core/component.h"
namespace esphome {
struct Color { uint8_t r, g, b; };
namespace display {
enum DisplayType { DISPLAY_TYPE_COLOR };
enum ColorOrder { COLOR_ORDER_RGB };
enum ColorBitness { COLOR_BITNESS_565, COLOR_BITNESS_888 };
enum DisplayRotation { DISPLAY_ROTATION_0_DEGREES, DISPLAY_ROTATION_90_DEGREES,
  DISPLAY_ROTATION_180_DEGREES, DISPLAY_ROTATION_270_DEGREES };
class Display : public Component {
 public:
  virtual DisplayType get_display_type() = 0;
  virtual int get_width() = 0;
  virtual int get_height() = 0;
  virtual void draw_pixel_at(int, int, Color) = 0;
  void flush(int x, int y, int w, int h, const uint8_t *data) {
    draw_pixels_at(x, y, w, h, data, COLOR_ORDER_RGB, COLOR_BITNESS_565, false, 0, 0, 0);
  }
 protected:
  virtual void draw_pixels_at(int,int,int,int,const uint8_t*,ColorOrder,ColorBitness,bool,int,int,int) {}
  virtual int get_width_internal() = 0;
  virtual int get_height_internal() = 0;
  bool is_point_clipped(int x, int y) { return x < 0 || y < 0 || x >= get_width() || y >= get_height(); }
  void do_update_() {}
  DisplayRotation rotation_ = DISPLAY_ROTATION_0_DEGREES;
};
struct ColorUtil {
  static uint16_t color_to_565(Color c) { return ((c.r >> 3) << 11) | ((c.g >> 2) << 5) | (c.b >> 3); }
};
}}
'''
PROGRAM = r'''
#include <array>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstring>
#include <fcntl.h>
#include <linux/fb.h>
#include <sys/mman.h>
#include "fbdev_display.h"

static std::array<unsigned char, 320*480*2> pixels{};
static fb_var_screeninfo variable{};
static fb_fix_screeninfo fixed{};
static uint32_t clock_ms = 0;
static int pans = 0, closes = 0;
static bool reject_pan = false;
namespace esphome { uint32_t millis() { return clock_ms; } }
extern "C" int __wrap_open(const char *path, int, ...) {
  assert(std::strcmp(path, "/dev/fb0") == 0);
  return 42;
}
extern "C" int __wrap_close(int fd) { assert(fd == 42); ++closes; return 0; }
extern "C" void *__wrap_mmap(void*, size_t size, int, int, int fd, off_t) {
  assert(fd == 42 && size == pixels.size());
  return pixels.data();
}
extern "C" int __wrap_munmap(void *p, size_t) { assert(p == pixels.data()); return 0; }
extern "C" int __wrap_ioctl(int fd, unsigned long request, ...) {
  assert(fd == 42);
  va_list ap; va_start(ap, request); void *arg = va_arg(ap, void*); va_end(ap);
  if (request == FBIOGET_FSCREENINFO) { std::memcpy(arg, &fixed, sizeof(fixed)); return 0; }
  if (request == FBIOGET_VSCREENINFO) { std::memcpy(arg, &variable, sizeof(variable)); return 0; }
  assert(request == FBIOPAN_DISPLAY);  // No blank, mode change or private ioctl.
  assert(std::memcmp(arg, &variable, sizeof(variable)) == 0); // Preserve every field.
  ++pans;
  if (reject_pan) { errno = EIO; return -1; }
  return 0;
}

static void reset(const char *name = "ak-lcd") {
  fixed = {}; variable = {}; pans = 0; closes = 0; clock_ms = 0; reject_pan = false;
  std::strncpy(fixed.id, name, sizeof(fixed.id));
  fixed.line_length = 640; fixed.smem_len = pixels.size();
  variable.xres = variable.xres_virtual = 320;
  variable.yres = variable.yres_virtual = 480;
  variable.bits_per_pixel = 16;
  variable.red.offset = 0; variable.red.length = 5;
  variable.green.offset = 5; variable.green.length = 6;
  variable.blue.offset = 11; variable.blue.length = 5;
}

int main() {
  using esphome::fbdev::FbdevDisplay;
  reset();
  FbdevDisplay d;
  d.setup(); assert(!d.failed);
  d.loop(); assert(pans == 0); // Never present unpainted memory during setup.
  d.draw_pixel_at(0, 0, {255, 0, 0});
  d.draw_pixel_at(1, 0, {0, 255, 0});
  assert(pans == 0); // Batch writes.
  d.loop(); assert(pans == 1);
  for (int i=0; i<100; ++i) d.loop();
  assert(pans == 1); // No repaint, no extra ioctl.
  assert(pixels[0] == 31 && pixels[1] == 0); // BGR565 remains unchanged.
  reject_pan = true;
  d.draw_pixel_at(0, 0, {0, 0, 255});
  d.loop(); assert(pans == 2 && d.warning);
  clock_ms = 999; d.loop(); assert(pans == 2);
  reject_pan = false;
  clock_ms = 1000; d.loop(); assert(pans == 3 && !d.warning);
  d.on_shutdown();
  d.loop(); assert(pans == 3 && closes == 1);

  reset("other-display");
  FbdevDisplay other; other.setup();
  other.draw_pixel_at(0, 0, {255, 0, 0}); other.loop();
  assert(pans == 0); other.on_shutdown();

  reset(); variable.yoffset = 1;
  FbdevDisplay offset; offset.setup();
  assert(offset.failed && pans == 0 && closes == 1);
  offset.loop(); assert(pans == 0);

  reset();
  FbdevDisplay wrap; wrap.setup();
  reject_pan = true; clock_ms = 0xfffffff0;
  wrap.draw_pixel_at(0, 0, {0, 0, 0}); wrap.loop(); assert(pans == 1);
  clock_ms = 500; wrap.loop(); assert(pans == 1);
  reject_pan = false; clock_ms = 1000; wrap.loop(); assert(pans == 2);
  wrap.on_shutdown();

  reset();
  FbdevDisplay tiles; tiles.setup();
  const uint16_t tile[] = {0xf800, 0x07e0, 0x001f, 0xffff};
  tiles.flush(0, 0, 2, 2, reinterpret_cast<const uint8_t *>(tile));
  tiles.flush(2, 0, 2, 2, reinterpret_cast<const uint8_t *>(tile));
  assert(pans == 0);
  tiles.loop(); assert(pans == 1);
  assert(pixels[0] == 31 && pixels[1] == 0);
  assert(pixels[640] == 0 && pixels[641] == 248);
  tiles.loop(); assert(pans == 1);
  tiles.on_shutdown();

  // Explicit TPP06 RGB565 overrides misleading BGR kernel metadata for both
  // individual pixels and the LVGL bulk path, without changing video mode.
  reset();
  FbdevDisplay rgb; rgb.set_pixel_format(esphome::fbdev::PixelFormat::RGB565);
  rgb.setup(); assert(!rgb.failed);
  rgb.draw_pixel_at(0, 0, {255, 0, 0});
  assert(pixels[0] == 0 && pixels[1] == 248);
  rgb.draw_pixel_at(1, 0, {0, 255, 0});
  assert(pixels[2] == 224 && pixels[3] == 7);
  rgb.draw_pixel_at(2, 0, {0, 0, 255});
  assert(pixels[4] == 31 && pixels[5] == 0);
  rgb.draw_pixel_at(3, 0, {10, 132, 255}); // UI accent #0A84FF, not #FF840A.
  assert(pixels[6] == 63 && pixels[7] == 12);
  const uint16_t rgb_tile[] = {0xf800, 0x07e0, 0x001f, 0x0c3f};
  rgb.flush(0, 1, 4, 1, reinterpret_cast<const uint8_t *>(rgb_tile));
  assert(std::memcmp(pixels.data()+640, rgb_tile, sizeof(rgb_tile)) == 0);
  rgb.loop(); assert(pans == 1); rgb.on_shutdown();

  reset("other-display");
  variable.red.offset = 11; variable.blue.offset = 0;
  FbdevDisplay automatic_rgb; automatic_rgb.setup();
  automatic_rgb.flush(0, 0, 4, 1, reinterpret_cast<const uint8_t *>(rgb_tile));
  assert(std::memcmp(pixels.data(), rgb_tile, sizeof(rgb_tile)) == 0);
  automatic_rgb.on_shutdown();
  FbdevDisplay forced_bgr;
  forced_bgr.set_pixel_format(esphome::fbdev::PixelFormat::BGR565);
  forced_bgr.setup();
  forced_bgr.draw_pixel_at(0, 0, {255, 0, 0});
  assert(pixels[0] == 31 && pixels[1] == 0);
  forced_bgr.flush(0, 0, 4, 1, reinterpret_cast<const uint8_t *>(rgb_tile));
  assert(pixels[0] == 31 && pixels[1] == 0);
  assert(pixels[4] == 0 && pixels[5] == 248);
  forced_bgr.loop(); assert(pans == 0); forced_bgr.on_shutdown();
}
'''


class FramebufferPresentationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native g++ required for mocked driver test")
    def test_real_driver_with_fake_kernel(self):
        with tempfile.TemporaryDirectory(prefix="tpp06-fbdev-test-") as folder:
            base = Path(folder)
            files = {
                "esphome/core/component.h": COMPONENT,
                "esphome/components/display/display.h": DISPLAY,
                "esphome/components/display/display_color_utils.h": '#include "display.h"\n',
                "esphome/core/hal.h": '#include <cstdint>\nnamespace esphome { uint32_t millis(); }\n',
                "esphome/core/log.h": '\n'.join('#define ' + macro + '(...) ((void)0)' for macro in (
                    "ESP_LOGE", "ESP_LOGW", "ESP_LOGI", "ESP_LOGCONFIG", "LOG_DISPLAY")) + '\n',
                "test.cpp": PROGRAM,
            }
            for name, content in files.items():
                file = base / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content)
            driver = ROOT / "esphome-components/fbdev"
            binary = base / "test"
            command = ["g++", "-std=c++17", "-DUSE_HOST", "-I" + str(base), "-I" + str(driver),
                       str(base / "test.cpp"), str(driver / "fbdev_display.cpp"), "-o", str(binary)]
            command += ["-Wl,--wrap=" + name for name in ("ioctl", "open", "close", "mmap", "munmap")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
