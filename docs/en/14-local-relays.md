# Local relays, physical buttons and indicators (experimental)

Status on 18 November 2026: mocked tests passed, followed by observation and
local-control installations (`0.1.5-relays.1`). The owner confirmed all three
lighting loads switch from the front buttons. GPIO/indicator readings agreed;
three switches are exposed over the encrypted API. **HA/AP-loss and offline
cold-start acceptance tests remain pending.** This is not mains-wiring approval
or a compatibility guarantee for other variants.

| Channel | Linux output | GPIO | Input | Indicator GPIO |
| --- | --- | --- | --- | --- |
| 1 | `KC_CTL1/value` | 65 | F1 / 59, GPIO 62 | 6 |
| 2 | `KC_CTL2/value` | 66 | F2 / 60, GPIO 63 | 85 |
| 3 | `KC_CTL3/value` | 67 | F3 / 61, GPIO 64 | 79 |

Outputs live under `/sys/class/gpio/`; indicators are
`/sys/class/leds/button{1,2,3}_led/brightness`. Inputs use the `gpiokeys` evdev
device, separate from touch. On the reference panel, observed presses and loads
confirmed **top → F1 → relay 1, middle → F2 → relay 2, bottom → F3 → relay 3**.
Verify your own variant. Extra events occurred during initial mapping and their
cause remains unresolved; repeat press/release tests to check for double toggles.

A fourth device-tree input is named `mic_mute`, GPIO 19 active-low, type `EV_SW`
(5), code `SW_MUTE_DEVICE` (14), not `KEY_POWER`. Whether this is the physical
top button reported by the owner still needs observation. The relay driver
logs this event without acting on it; it does not shut down Linux or switch all relays.

## ESPHome / Home Assistant

The optional [package](../../esphome/packages/local-relays-experimental.yaml)
is merged into the full native TPP06 configuration; add `tpp06_local_relays` to
the existing external-component list. Compile firmware in Home Assistant, not
Mint. This is not a standalone configuration or ESP32 firmware.

- `control_enabled: false`: read-only observation, including LEDs. HA commands
  cannot switch outputs in this mode.
- Three native ESPHome switches named Relais 1–3 report GPIO readback to HA.
  Physical presses call the same local driver without Wi-Fi, Internet or HA.
- `key_map: [1, 2, 3]`: permutation of relay channels for F1/F2/F3.
- `indicator_mode: follow_relay` or `off`: follow actual relay software state
  or keep indicators dark. Indicator failure does not disable relay operation.
- `pulse_duration: 0s` per switch: normal latching ON/OFF, the default.
- An optional duration of 100 ms–60 s enables local inching. Repeated ON does
  not extend an active pulse; OFF cancels it. It remains a switch entity in HA.
- `restore_mode: DISABLED`: inherit current GPIO levels at process startup;
  never restore stale preferences or force outputs during orderly shutdown.

A GPIO readback is **not contact/voltage feedback**. Power loss differs from a
process restart: the stock device tree initializes outputs to zero. Inching is
a software timer, **not safety-rated**: crashes can prevent timed OFF. An ON
state inherited at startup is preserved, with no invented remaining timeout;
only an explicit ON command starts a new pulse.

The driver validates the hardware profile and input capabilities, guards
against held/repeated keys and event overflow, and checks for the stock app.
An advisory lock prevents two instances of this driver, not the uncooperative
stock application. Tuya and its monitor must remain stopped. An I/O/ownership
fault locks new relay commands until process restart, without toggling loads.
LVGL can use `switch.toggle` on the same IDs; current V5/V6 pages have not yet
been remapped to these local outputs.

### First observation finding

`0.1.5-observation.1` exposes the three switches over the encrypted API, but
the driver cannot become ready: it puts its lock file under `/run`, which is on
the panel's read-only squashfs root. Its original generic warning did not prove
that another controller was running. The correction uses `/var/run` on the
writable `/var` tmpfs and distinguishes open failures from lock failures,
including errno. Mocked tests now cover a read-only lock directory.
**Correction built in HA and installed as `0.1.5-observation.2`: lock and inputs
ready, encrypted API available during a 90-second check.** `0.1.5-relays.1`
subsequently enabled the confirmed physical tests described above.
Rebooting the first build does not repair this path.

## Offline supervisor policy

API (and MQTT if present) must use `reboot_timeout: 0s`. The component rejects
network-client reboot timeouts.

The historical supervisor also required Wi-Fi association and DHCP. A new
opt-in policy allows a missing AP/lease only when all of these markers match:
`local_control_confirmed=yes`, `persistent_confirmed=yes`,
`boot_policy=persistent`, `network_mode=isolated`, and no bounded trial.
Wi-Fi/DHCP keep running in the background; local process and API/rescue listener
checks remain. Internet/HA reachability is not a health criterion. First trials
and unconfirmed commissioning retain the strict network guard. **No marker was
enabled on a live panel by this work.** Application OTA does not update this
Linux supervisor script.

Remaining hardware acceptance includes repeated key/indicator tests, HA
commands/state/reconnection, loss of HA/AP, and a cold start
without an AP with recovery available. Only confirm autonomous operation after
supervised testing. Never open or handle mains conductors while energized.

## First observation build

1. Keep private backups of the working configuration and program. Preserve the
   existing API/OTA credentials and network settings; never publish them.
2. Compile in HA with `control_enabled: false`. Check the static ARMv5TE
   soft-float binary and room for OTA staging alongside the running program,
   with a further 2 MiB reserve, before any transfer.
3. After an explicitly chosen installation, verify encrypted API, display and
   recovery access. Do not enable the offline supervisor policy yet.
4. Watch ESPHome logs and observe one short front-key press at a time. Record
   its physical position and `F… press -> channel … (observation only)` line.
   This driver does not write relays or LEDs in this mode; the three HA switches
   cannot yet be used to control loads.
5. Leave the unidentified top button without a Power action. A logged
   `SW_MUTE_DEVICE=…` event needs correlation with an observed manipulation;
   the event name alone does not establish its physical function.

Compilation and observation do not validate electrical output order, LEDs or
network-independent operation. Enabling commands and supervised load tests are
a separate stage.

After identifying keys and loads, with on-site supervision, explicitly set
`control_enabled: true`, compile in HA and install by OTA. Test one relay at
a time and check its indicator and HA state. The public package remains `false`
to avoid blindly enabling another panel's outputs. Inching has only been
mock-tested, not tested with the reference panel's loads.
