# Phase 6 — Native ESPHome + LVGL on the TPP06

This route runs **ESPHome itself** on the TPP06 Anyka Linux system. ESPHome's
LVGL engine writes directly to the framebuffer and reads the Goodix touchscreen
through Linux `evdev`; no ESP32 replacement is involved.

> **Experimental status.** The ESPHome configuration and static ARMv5 binary
> compile successfully. The final real-panel display test still requires the
> panel's next reboot. Do not install it at boot until repeated temporary tests
> from `/tmp` have succeeded.

The [reproducible patch](../../esphome-lvgl/esphome-tpp06-lvgl.patch) adds:

- a `/dev/fb0` 320×480 16-bit `fbdev` display component;
- automatic RGB565/BGR565 detection;
- an `/dev/input/event1` Goodix `evdev` touchscreen component;
- the 16-byte 32-bit input-event layout required by the panel's Linux 4.4
  kernel;
- an LVGL colour/touch test and an ARMv5 cross-build script.

It targets ESPHome revision `9bf2bbc` (`dev`, `2026.12.0-dev`) and the official
Bootlin ARMv5 EABI/uClibc stable 2026.08-1 toolchain (GCC 15.3):

```bash
git clone https://github.com/esphome/esphome.git
cd esphome
git checkout 9bf2bbc
git am /path/to/esphome-tpp06-lvgl.patch

export TPP06_TOOLCHAIN_PREFIX=/opt/armv5-eabi--uclibc--stable-2026.08-1/bin/arm-linux
export ESPHOME_PYTHON=/path/to/esphome-venv/bin/python
./tpp06/build.sh
```

The result is
`tpp06/.esphome/build/tpp06-lvgl/.pioenvs/tpp06-lvgl/program`. The first build
produced a roughly 2.8 MiB static binary with SHA-256:

```text
cc56aebcd623e13169571e66a1c949ab75a5b7e0112b6901775bbfd5dd94fea9
```

For the first hardware test, reconnect ADB as described in
[Phase 4](04-adb-over-wifi-without-uart.md), copy the binary only to `/tmp`,
pause `voice_control_ak3760e`, and run it in the foreground. Validate the red,
green, and blue bars and the touch button. Stop it with `Ctrl+C`, immediately
resume the Tuya process with `kill -CONT`, and remove the temporary binary.

If this old ADB build cannot use `adb push`, transfer the file with a temporary
`nc -l -p 9001 > /tmp/esphome-tpp06-lvgl` listener on the panel and
`nc PANEL_IP 9001 < program` on the PC. Do not create a startup service until
display, touch, shutdown, and recovery have all passed repeatedly.
