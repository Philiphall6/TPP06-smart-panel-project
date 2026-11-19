# Current interface — ESPHome + LVGL

[Latest release](https://github.com/Philiphall6/TPP06-smart-panel-project/releases/latest) ·
[Beginner guide](START-HERE.md) · [Français](../fr/interface.md)

The current template is [`tpp06-lvgl-modern.yaml`](../../esphome/tpp06-lvgl-modern.yaml).
Release notes identify the published version and its validation evidence.
Older templates remain available for reference; do not mix arbitrary sections.

## Home screen

Dark gradients, rounded cards, time, date, configurable weather and cover/light
shortcuts. The upper-left Home Assistant logo gently pulses blue when a live
API client identifies as Home Assistant, otherwise it stays grey. A log-only
client is insufficient. This is visual status, not extra authentication or
proof that every HA service is available. The small clock sits beside Wi-Fi
at the top right. No duplicate Wi-Fi text below weather and no fictional battery.
The Wi-Fi icon reflects the Linux link, not Internet availability.
Public previews contain fictional values, not private panel captures.

## Settings and entities

- Remembered brightness/sleep preferences; sleep defaults to **Never** until
  physical wake is checked on site.
- [Local touch beep](15-touch-beep.md), enabled by default with remembered off
  preference and explicit unavailable-driver indication.
- Compact version/time/network diagnostics.
- Available/total `/data` storage in MiB on the ESPHome device alongside HA
  relay entities; read failures publish unavailable text.
- Separate **Redemarrer ESPHome** (application) and **Redemarrer le panneau**
  (Linux) buttons with guards that may refuse the request. Full reboot interrupts
  networking and may change relay states. Real button tests remain pending.
- [Wi-Fi settings](17-screen-wifi.md): manual scan, selection, masked password,
  bounded trial and confirmation/cancellation. The optional Linux service must
  be commissioned separately. Idle operation was checked, **not real network
  migration or rollback**.

[Local relays](14-local-relays.md) are separate from pages controlling HA
entities. Physical buttons and indicators were validated on the reference
hardware. Public configuration remains observation-only until the hardware
and loads are identified. Wi-Fi/HA-loss and power-loss behaviour still need testing.

## Customisation and updates

Edit substitutions for names, entities, `weather_entity`, labels and colours.
Keep keys in `secrets.yaml`. Compile in HA and follow the
[OTA guide](START-HERE.md#5-update-a-panel-already-running-esphome).
The published template pins drivers to its release tag. A deliberate update
uses the next release’s template while retaining private settings.

UI OTA does not replace the Linux supervisor, network profile or
[initial NAND logo](12-boot-logo.md). Do not reinstall boot support for a visual
change. No private executable is distributed. See [remaining Tuya gaps](16-tuya-gaps.md).
