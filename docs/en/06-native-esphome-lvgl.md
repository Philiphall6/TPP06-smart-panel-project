# Phase 6 — Native ESPHome + LVGL on the TPP06

This route runs **ESPHome itself** on the TPP06 Anyka Linux system. ESPHome's
LVGL engine writes directly to the framebuffer and reads the Goodix touchscreen
through Linux `evdev`; no ESP32 replacement is involved.

> **Hardware-tested on 17 November 2026.** The static ARMv5 program starts on
> the TPP06, detects its 320×480 BGR565 framebuffer and Goodix touchscreen, and
> completes ESPHome setup. The LVGL button responds to touch and displays
> `TACTILE OK`. Startup installation remains experimental; first run several
> successful temporary tests from `/tmp`.

The [reproducible patch](../../esphome-lvgl/esphome-tpp06-lvgl.patch) adds:

- a `/dev/fb0` 320×480 16-bit `fbdev` display component;
- automatic RGB565/BGR565 detection;
- an `/dev/input/event1` Goodix `evdev` touchscreen component;
- the 16-byte 32-bit input-event layout required by the panel's Linux 4.4
  kernel;
- legacy ARM32 Linux 4.4 time and select syscalls for a modern time64 toolchain;
- explicit static `pthread` linkage and a writable `ESPHOME_PREFDIR`;
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
9d2d42251db95ff8564c90cb2d978cf398a214fecc04ed302f6717d78e726802
```

## Portable Device Builder configuration

The compatibility layer is provided as ESPHome `external_components`; patching
ESPHome itself is no longer required. Import only
[`esphome/tpp06-device-builder.yaml`](../../esphome/tpp06-device-builder.yaml)
into the official Device Builder. Installation-specific values are collected
in the top-level `substitutions`: device name, virtual MAC address, and the
three Home Assistant entity IDs. The Linux drivers and LVGL interface are
fetched from this repository.

Two modes are available. `tpp06-device-builder.yaml` stays linked to the GitHub
template and is convenient when only substitutions change. For unrestricted
interface editing, import `tpp06-lvgl.yaml`. The advertised **Take control**
flow uses `import_full_config: true`, so Device Builder copies the complete
configuration locally. Pages, widgets, styles, positions, and actions can then
be edited freely; only the hardware `external_components` remain sourced from
GitHub.

An ARMv5 cross compiler is still required, but no external build server is
needed. On the first build, the external `host` component downloads the
Bootlin toolchain into Device Builder's own cache and verifies its SHA-256.
Every subsequent build reuses that cache and runs locally inside Home
Assistant. The initial download is approximately 82 MB.

If the build log contains a `.remote_builds/...` path, compilation is still
being offloaded. Open **Settings → Send builds**, remove or disable the paired
build server, then clean this device's build files. A normal local path starts
with `/config/.esphome/build/...`.

Before compiling, replace `CHANGE_ME_BEFORE_INSTALL` in the `ota_password`
substitution with an installation-specific password. Never commit that value.

## Initial deployment and later OTA updates

Device Builder cannot use **Install** to place the very first executable into
an untouched Tuya system. The build itself succeeded when the log says
`Successfully compiled program`; download that executable and deploy it
reversibly with Tuya Cutter as described below.

From project version `0.1.3`, the running executable provides ESPHome OTA on
port `8082`. Later builds can therefore be installed directly to the panel's
IP from Device Builder using `ota_password`. Portable MD5 and SHA-256 backends
in this repository avoid the OpenSSL dependency missing from Tuya Linux.

The recommended first test uses Tuya Cutter, which pauses Tuya, selects a
writable temporary preferences directory, and retains a safe rollback path:

```bash
python3 tools/tpp06_tuya_cutter.py --yes PANEL_IP test esphome \
  --binary tpp06/.esphome/build/tpp06-lvgl/.pioenvs/tpp06-lvgl/program
python3 tools/tpp06_tuya_cutter.py PANEL_IP stop-test
```

For an equivalent manual hardware test, reconnect ADB as described in
[Phase 4](04-adb-over-wifi-without-uart.md), copy the binary only to `/tmp`,
pause `voice_control_ak3760e`, and run it in the foreground. Validate the red,
green, and blue bars and the touch button. Stop it with `Ctrl+C`, immediately
resume the Tuya process with `kill -CONT`, and remove the temporary binary.

If this old ADB build cannot use `adb push`, transfer the file with a temporary
`nc -l -p 9001 > /tmp/esphome-tpp06-lvgl` listener on the panel and
`nc PANEL_IP 9001 < program` on the PC. Do not create a startup service until
display, touch, shutdown, and recovery have all passed repeatedly.
