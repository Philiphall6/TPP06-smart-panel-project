# BLE discovery, screen controls and YAML sections

Use the [complete template](../../esphome/tpp06-lvgl-complete.yaml) for the
modern UI, local relays, Linux diagnostics, screen controls and BLE advertising
forwarding. Every import is pinned to the same release. The
[detailed UI template](../../esphome/tpp06-lvgl-modern.yaml) remains editable.

Edit `substitutions` for your cover, two HA lights, weather and local relay
labels. The legacy variable names `cave_light_entity` and `bar_light_entity`
are compatibility names, not required rooms. Keep names, keys and entities
private. Never deploy a test key from this repository.

French `[TPP06]` section comments identify imports, drivers, logic and each
screen: home, cover, lights, settings, Wi-Fi, brightness, sound, weather and
diagnostics. Additional views live in `esphome/packages/`. After a private
backup, `python3 tools/tpp06_yaml_sections.py /private/path/panel.yaml` adds
these comments without changing existing configuration lines or running OTA.

## BLE and backlight

**Settings → BLE** and HA's **Detection Bluetooth BLE** share one persisted
switch, off by default in the public template. Scanning starts only when an
API client subscribes to BLE advertisements. Logs alone do not trigger it.
Linux MGMT forwards advertisements through the encrypted ESPHome API, without
a BlueZ daemon or Tuya Cloud. Compatible HA integrations can consume them.
Counters count advertisements, not distinct devices or pairings.

Experimental, active LE discovery only: no GATT, pairing, audio or connections.
Stopping discovery is not a radio-power-off command. Linux must already expose
the controller; no kernel driver is installed by the UI OTA.

HA exposes **Luminosite ecran** (10–100%), **Veille automatique ecran** (never,
30 seconds, 1, 2 or 5 minutes), **Reveiller ecran** and **Ecran en veille**.
These share the existing panel preferences; they do not control room lighting.

## Updating and evidence

Keep the existing private name, keys, entities, button mapping and relay
`control_enabled` setting. The public template intentionally defaults to
relay observation, so do not blindly overwrite a commissioned configuration.
Use matching component/package tags, validate and compile in HA, check staging
space and safety reserve, then send one OTA. No Wi-Fi change, supervisor
replacement or NAND logo write is needed for these application features.

Reference application `0.1.7-dev.3` was built in HA and installed through one
encrypted OTA. A 181-second observation confirmed forwarded advertisements,
eight registered HA entities, HA scan stop/start, unchanged brightness/sleep
settings and actual backlight wake. Linux and relay states were unchanged.
This is not a long-term, power-loss or all-device compatibility guarantee.
Public release numbering does not imply another hardware-tested build.
Optional supervisor changes have software tests only and were not deployed
for this release.

See the [Linux capability and validation tracker](18-linux-hardening.md).
