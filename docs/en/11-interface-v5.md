# V5 interface — installed on the reference panel

On 18 November 2026 the owner confirmed successful wireless installation of
V5, project version **0.1.5**, built in Home Assistant. Direct post-install
checks confirmed the expected binary, version `0.1.5` over the encrypted API,
associated Wi-Fi, `esphome-healthy`, retained persistent boot policy and no
Tuya graphical process. A live framebuffer capture confirms the home page,
icons, date and time. This is not a complete trace of the OTA transfer or an
endurance test of every page. Physical sleep/wake and beep remain unverified.

The executable is static ARMv5TE / ARM926EJ-S, soft-float ABI.
See the [beginner guide](START-HERE.md) for the normal workflow.

The existing configuration was updated, not duplicated. The V4 YAML was
backed up; identity, addresses, private entity bindings, API/OTA keys and
previously pinned drivers were preserved. The new `tpp06_backlight` component
was staged in a Builder-local relative directory for the first trial. It is
now published under `esphome-components`, referenced from GitHub by the public
model. Compare older local drivers before removing them; no developer-specific
path is required.

For an already prepared panel, verify `0.1.5` in YAML, retain the previous
program and check free space before **Install → Wirelessly**. Leave sleep on
**Never** initially. No boot logo or supervisor rewrite is required for a UI update.

V5 adds built-in LVGL navigation icons, a contrasting clock/date
card, brightness (10–100%) and idle settings (never/30s/1m/2m/5m). Settings are
stored locally. No external font or full-screen bitmap is required.

Sleep is **disabled by default**. After an on-site wake test, it can pause
LVGL and turn off the Linux backlight. Linux, Wi-Fi, ADB, encrypted API, OTA
and the supervisor remain active. The first touch/release wakes the screen
without activating a household control. This behavior still needs hardware
verification with the candidate build.

The `tpp06_backlight` component only accesses
`/sys/class/backlight/<device>/brightness`, after checking the maximum and
permissions. Missing hardware disables sleep; a failed off operation resumes
LVGL. Orderly shutdown restores the original brightness. Abrupt termination
cannot run that cleanup: fallback/OTA from sleep must be tested separately.
The device name is a substitution; there are no GPIO/PWM exports, relay writes,
network stops or reboot actions in the UI.

Touch beep remains explicitly unavailable pending driver verification. Named
`BUZ_EN1`/`BUZ_EN2` outputs and a firmware tone generator were identified
read-only. No sound/GPIO write was made; there is no fake working toggle.

The requested logo change targets the **initial MOES boot logo**, not an
additional ESPHome splash. The reference `logo` partition is 512 KiB with
128 KiB erase blocks. Its private backup was checked against a second read.
The 320×480 16-bit image (307,200 bytes) exactly matches the dumped MOES PNG
after conversion, followed by `0xff`. The monochrome content cannot establish
RGB565 versus BGR565. BGR565 was selected from the live LCD device tree and
video driver.

The Home Assistant-only logo has been programmed on the reference panel;
the complete readback matches the prepared image. Visual confirmation of
colour and orientation remains pending. This is separate from V5 and ESPHome
OTA. See the [procedure and limitations](12-boot-logo.md), including the
incompatible-tool incident and verified original restoration before the final
write. No flash executable or universal erase script is distributed.

Next gates: endurance and subsequent updates with a fresh free-space
check, brightness/sleep/wake test, no household action on wake, uninterrupted API/Wi-Fi, fallback and OTA
from sleep. Validate sound and visually confirm the boot logo independently. Keep all
private YAML, keys, NAND backups and installation identifiers out of GitHub.

Sources: [LVGL](https://github.com/lvgl/lvgl),
[ESPHome LVGL](https://esphome.io/components/lvgl/),
[LVGL symbols](https://github.com/lvgl/lvgl/blob/v9.5.0/src/font/lv_symbol_def.h).
