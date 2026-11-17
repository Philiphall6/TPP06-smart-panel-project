# Phase 5 — Local openHASP interface on the TPP06

This phase ports openHASP to the TPP06 embedded Linux system without replacing
Tuya immediately. The first milestone runs entirely from `/tmp` and disappears
after reboot, allowing display, touch and MQTT testing before persistent
changes are made.

## Verified state

The following points were tested on a TPP06/AK3761E:

- ARM926EJ-S, `armv5tejl`, soft-float ABI;
- Linux 4.4 with a Buildroot/uClibc userland;
- `/dev/fb0`, 320×480, 16 bpp, 640-byte stride;
- hardware BGR565 converted from LVGL RGB565;
- Goodix `/dev/input/event1`, multitouch ranges 0–320 and 0–480;
- GPIO keys on `/dev/input/event0`;
- LVGL and openHASP 0.7.2 start without crashing.

Red, green, blue and white were verified from a raw framebuffer capture. Tuya
was resumed after every test.

## Build the port

The patch is based on openHASP commit `c4fb5a7`.

```bash
git clone https://github.com/HASwitchPlate/openHASP.git
cd openHASP
git checkout c4fb5a7
git am /path/TPP06-smart-panel-project/openhasp/openhasp-tpp06.patch
```

Install PlatformIO and a Bootlin ARMv5 EABI/uClibc toolchain, then set their
paths when needed:

```bash
export TPP06_TOOLCHAIN_DIR=/path/armv5-eabi--uclibc--stable-2018.02-2
export PIO=/path/to/pio
./tpp06/build-openhasp.sh
```

The resulting file is `build-tpp06/openhasp-tpp06`, an ARM EABI5 soft-float
static executable. The build applies the Goodix multitouch and BGR565 fixes.

## Reversible first run

Recover authorised access through Phase 0 and enable ADB over Wi-Fi through
Phase 4. Copy the executable, `pages.jsonl`, and a local MQTT `config.json` to
a test directory under `/tmp`.

First create `/tmp/openhasp` from the panel's authorised root shell, then run
the transfers from the host computer:

```bash
adb connect PANEL_IP:5555
adb push build-tpp06/openhasp-tpp06 /tmp/openhasp-tpp06
adb push tpp06/runtime/pages.jsonl /tmp/openhasp/pages.jsonl
adb push tpp06/runtime/config.example.json /tmp/openhasp/config.json
```

Some old Tuya ADB servers terminate `adb push` early. If that happens, use the
panel's BusyBox `nc` or a temporary local HTTP transfer and verify the received
file's SHA-256.

From the panel's authorised root shell:

```sh
chmod +x /tmp/openhasp-tpp06
/tmp/openhasp-tpp06 -c /tmp/openhasp
```

Tuya and openHASP otherwise write to the framebuffer concurrently. For a short
visual test, suspend Tuya only with an independent watchdog that automatically
resumes it. Do not alter boot startup until touch, MQTT, and rollback have all
been validated.

## MQTT and Home Assistant

Copy `tpp06/runtime/config.example.json`, replace the `CHANGE_ME` values only in
the local copy, and never commit the real MQTT password. The sample page has
bathroom shutter, cellar light and brightness controls; connect their openHASP
events to the actual Home Assistant entities through MQTT or automations.

## Remaining work before replacing Tuya

1. Physically verify touch press, release and orientation.
2. Validate MQTT authentication and Home Assistant events.
3. Map backlight, relays, LEDs, buzzer, and infrared hardware.
4. Add a supervisor, watchdog, and automatic Tuya fallback.
5. Install openHASP at boot only after repeated reboot tests.

The patch contains no key, `AUTHKEY`, password, or device-specific data.
