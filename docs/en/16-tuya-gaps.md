# Tuya feature parity: remaining gaps

Update: see the [Linux hardening candidate and 22-area tracking](18-linux-hardening.md).
This page retains the original inventory; prepared code is not a claim of
deployment or hardware validation.

Read-only inventory dated 18 November 2026, comparing the private stock dump,
project code and reference panel. No factory test, IR transmission, Bluetooth
command, sound, relay change or reboot was performed for this audit.

**The stock library serves several panel families. Symbols and translations
alone do not prove that a feature or sensor exists on this model.** This is
not a complete parity certification. See the
[detailed French evidence table](../fr/16-ecarts-tuya.md).

## Already verified on the reference installation

- LVGL display/touch and corrected colours, physically checked.
- Three physical buttons, local relays and indicators, with HA entities.
- Encrypted API, OTA and real network identity.
- ESPHome application startup with Tuya fallback, not protection against NAND
  programming failures.

## Main gaps

| Area | Remaining work |
| --- | --- |
| Offline operation | Local button-to-relay control exists. Separately test HA loss, Wi-Fi loss and cold boot without a network. Prepared offline supervisor policy is not deployed. |
| Relay power-loss behaviour | Define and test an explicit policy; do not assume saved relay state is restored. Stock has `tuya_cc_get_relay_last_status`, which alone does not prove a user setting. |
| Local relay screen | Existing lighting pages are not yet a generic touch page for all three local relays. |
| Inching | Software/simulation coverage exists; physical timing, interruption and recovery remain unverified. Switch mode is the validated mode. |
| Top Power button | Physical mapping remains unconfirmed. A mute-type input is only a candidate; no shutdown action is assigned. |
| Sleep/wake | Settings exist; test actual sleep, wake without an unintended household action, OTA and fallback while asleep. |
| Touch beep | `0.1.6-buzzer.1` installed and audible feedback confirmed by the owner. See [touch beep and limitations](15-touch-beep.md). |
| Weather | V6 installed and display confirmed on the panel. Missing/stale data must stay explicit. |
| Storage | `0.1.6-system.2` adds available/total MiB as a text entity on the same ESPHome device as the relays. Reads `/data` every 60 s; errors publish unavailable text instead of retaining stale values. Post-OTA check pending. |
| ESPHome restart | Application-only restart through host re-exec and safe hooks. OTA, changed executable or unhealthy supervisor blocks it. No Linux reboot. Real button test pending. |
| Full device reboot | A separate button requests `/sbin/reboot` without force through the verified BusyBox init. Additional guards check fallback, confirmed persistent mode, Wi-Fi profile and 2 MiB free. Buttons are mutually exclusive; an accepted Linux request is latched without automatic retry. Network is interrupted and relay states may change on boot. Real button test pending. |
| Wi-Fi settings | Scan/selection/password and bounded trial are implemented; the Linux service was verified at idle only. No real network migration/rollback validation. See [separate commissioning and limits](17-screen-wifi.md). |
| Offline time | HA time sync exists; cold boot without HA and fallback time remain unverified. No RTC appeared in `/sys/class/rtc`. |

## Stock features found, not ported

- Automatic brightness and proximity: `gui_ctrl_*bright_auto`,
  `gui_ctrl_proximity_*`, `tuya_sensor_light_get` and
  `tuya_sensor_distance_get`. Sensors not identified in standard IIO/I²C
  inventory; vendor-specific access is still possible.
- Scheduled Do Not Disturb (`gui_ctrl_dnd_*`), screen-saver choices and local
  passcode functions. No equivalent global policy/editor implemented.
- Alarm-clock translations and card/scene/notification configuration in shared
  resources; availability on this model needs confirmation.
- IR: `/dev/lirc0` exists and the library contains learning/transmission
  functions. No receive, learn or transmit test performed.
- Bluetooth: `hci0` exists. Pairing, audio and HA proxy use are not validated.
- Voice/microphone/audio functions exist in the shared library, not proof of
  hardware or working services on this panel.

Stock library SHA-256:
`f940aeee4a70e6ccb7f12eda075b40c7a3577484f1a460c327d9055d5d8477f7`.
Shared resource family: `pkg_res/dgnzk_3.5/default_language.json`.
Observed inputs: `gpio-keys`, `goodix-ts`; I²C: `ak-i2c`, `gt1x`;
IIO exposed only `iio_sysfs_trigger`, not an `iio:device` sensor.

Priorities: offline/relay recovery, sleep and top-button identification,
supervised beep validation, unavailable/stale weather checks, then optional sensors and
independent IR/Bluetooth investigation. Do not silently restore Tuya Cloud;
the project's goal is local control. Private identifiers, secrets, load names
and firmware dumps are not part of this report or repository.
