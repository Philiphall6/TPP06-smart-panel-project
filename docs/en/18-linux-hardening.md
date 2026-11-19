# Linux hardening candidate

Work dated 19 November 2026, included in the **v0.1.7 source release**.
The application was installed by OTA on the reference panel; the new Linux
supervisor was not deployed and remains experimental. Templates and components
pin the same tag. Historical batch results below retain their original scope;
see also [BLE, screen controls and YAML](20-ble-screen-yaml.md).

The [full 22-area tracking table](../fr/18-consolidation-linux.md) distinguishes
implemented candidate code, software tests, and outstanding hardware validation.

Prepared in this batch:

- Checksummed, atomic preference saves with a previous valid copy and legacy import.
- Runtime log retention preserving append-mode descriptors, rather than only rotating at launch.
- RAM, Linux Wi-Fi signal, supervisor state and estimated OTA headroom diagnostics.
- Optional monotonic main-loop heartbeat written to tmpfs; enforcement remains unarmed.
- Three local relay cards, with unavailable/disabled states and no HA service dependency.
- Configurable quiet hours, independent from the remembered touch-beep preference.
- Observation-only Linux mute input, with resynchronization and no assumed Power action.
- Redacted, read-only hardware capability inventory.

No Linux reboot, output command, Wi-Fi migration, module load, IR transmission or
Bluetooth pairing was performed. The inventory was run on the reference panel;
unit tests use temporary files and mocked hardware calls, not actual power failures.

Candidate validation: **200 software tests passed**, followed by a complete
Home Assistant build and static ARMv5TE, little-endian, soft-float binary checks.
The reference executable is 10,221,608 bytes; its staging headroom was checked
above 2 MiB before transfer. One encrypted application OTA then completed:
version and checksum match, encrypted API and heartbeat remained stable for
180 seconds, all three relay states stayed unchanged, Linux did not reboot,
and recovery paths stayed intact. A framebuffer capture confirms the home page
and Local entry, not all touch interactions. Both new preference copies exist.
The private Builder YAML now matches the installed application; the previous
YAML is backed up and the duplicate compilation YAML is privately archived.
Offline, power-loss and persistence-after-restart tests remain pending.
Other installations must check their own artifact and available space.
No private firmware is published. After installation, the diagnostic correctly
reported insufficient reserve for another same-size OTA. A subsequently requested
cleanup archived and checksum-verified 19 inactive historical Tuya log files on
the computer before deleting only those files from the panel. The two newest
archives, live logs and recovery backups were retained. This reclaimed 3.40 MiB:
15.02 MiB free out of 38.50 MiB, leaving 5.28 MiB after a same-size OTA. Removed
files are recoverable from the private archive. No Linux reboot or relay state
change was observed. Recheck space for every OTA. This one-time cleanup does not
deploy the new supervisor log-retention policy. In that first installed candidate,
Wi-Fi signal remains unavailable rather than reporting invented dBm values.

## Network/driver batch (OTA verified on the reference panel)

Read-only inspection found a positive, non-dBm value in `/proc/net/wireless`,
but a signed RSSI from wpa_supplicant `SIGNAL_POLL`. The optional
`wifi_signal_via_wpa` setting defaults off in the component and on in the candidate
package. It sends only this read-only request to the local Unix control socket,
without scans, subprocesses, profile changes or Internet traffic. Nonblocking
reception expires after one second. Invalid, truncated or absent replies report
unavailable. A Linux abstract client socket leaves no filesystem entry.

Link status reads sysfs `operstate` and `carrier`; an active link does not establish
working DHCP, DNS, Internet or HA connectivity. The additional driver package
exposes reported relay, buzzer, backlight and Wi-Fi editor availability. These are
software-state diagnostics, not physical self-tests; a busy Wi-Fi service need not
be faulty. No output is commanded.

**206 software tests passed**, including Unix socket requests, absent/silent
services, invalid replies, timeout and timer wraparound. The separate HA build
succeeded: 10,237,224 bytes, verified static ARMv5TE little-endian soft-float ABI,
5.26 MiB staging reserve at inspection. Encrypted API and recovery access remained
available; Linux boot, application PID, relay states and supervisor/recovery
checksums stayed unchanged during the build. One encrypted OTA subsequently
installed this batch: version and checksum verified, API and heartbeat stable for
180 seconds, no Linux reboot or change in relay/switch states. Signed RSSI is
received and all four driver/service diagnostics report available. This is not a
physical output test: no load was commanded. A read-only framebuffer capture
confirms the normal home page. The Builder configuration is aligned with the
installed application; its previous YAML is backed up and the candidate archived
privately to avoid a duplicate device. The supervisor remains unchanged.
Prolonged monitoring and offline tests remain outstanding.

References: [wpa_supplicant control interface](https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html),
[Linux Unix sockets](https://man7.org/linux/man-pages/man7/unix.7.html),
[Linux 4.4 wireless unit conversion](https://github.com/torvalds/linux/blob/v4.4/net/wireless/wext-proc.c).

## Compatibility and limits

Preferences migrate from `<name>.prefs` to `<name>.prefs.v2` and a `.bak` copy.
The legacy file is retained unchanged for older firmware. Downgrading therefore
returns to **pre-migration settings**, not the newest settings. Corrupt current
data uses the valid backup; it does not resurrect legacy data. Checksums are not
encryption. These files are not NAND or Wi-Fi backups.

Runtime log checks retain a 64 KiB tail after a threshold of 1 MiB for application
logs or 256 KiB for Wi-Fi/rescue logs. Copy/truncate preserves open append handles
but may lose concurrent diagnostic lines. This is not a hard quota between checks,
and does not eliminate flash writes. Backups and unrelated files are untouched.

The `tpp06_health` component writes `1 PID monotonic_seconds` to a private
`/tmp/tpp06-health/heartbeat`. Default polling is 5 seconds. The supervisor stays
backward-compatible unless separately commissioned with `required-v1`; that mode
checks process identity and a 25-second maximum age. **Do not enable enforcement
before prolonged runtime, OTA and fault testing.** A main-loop heartbeat does not
prove every device driver is healthy. The hardware watchdog owner is unchanged.

OTA headroom is only an estimate based on the current executable size plus 2 MiB.
Use the existing `ota-space-check` with the actual new file before deployment.
Automatic previous-ESPHome rollback and host OTA durability hardening remain open.

Quiet hours default off. Equal start/end hours mean all-day silence; unknown time
means silence when the schedule is enabled. No relay or backlight is changed.
The experimental relay package keeps control disabled until commissioned.

## Candidate packages and inventory

On a private copy of the modern YAML, use local external components from this
checkout, include `tpp06_health` and `tpp06_local_relays`, and merge:

- `esphome/packages/local-relays-experimental.yaml`
- `esphome/packages/runtime-health.yaml`
- `esphome/packages/mute-input-observation.yaml`
- `esphome/packages/local-controls-ui.yaml`
- `esphome/packages/driver-diagnostics.yaml` (requires the modern UI and local drivers)

Preserve existing private bindings and commissioned relays; do not duplicate them.
Configuration validation and C++ generation are tested. ARMv5TE compilation in HA
and size/ABI checks passed for both private reference candidates. Repeat these
checks for other configurations; the bounded device trial of the network/driver
batch passed on the reference panel and must be repeated elsewhere. Never replace the
application and its Linux supervisor simultaneously without separate validation.

```sh
python3 tools/tpp06_capabilities.py --host 192.0.2.1 --backup-dir /private/backups
```

The address is an example. `--adb` selects the existing maintenance transport.
The filtered report omits installation identifiers and secrets. Presence of a
node/module does not prove a working device. No device nodes are opened by the
inventory script. Keep maintenance ports LAN-only.

RTC, IR, Bluetooth, audio, proximity and ambient sensors require separate hardware
identification and supervised validation. Do not reuse the console/Bluetooth UART,
disable rescue ports or remove stock initialization/watchdog dependencies. Offline
cold boot, Wi-Fi rollback, relay power-loss behavior and sleep/wake require staged
on-site tests before activating new policies. Screensavers, alarms, lock, languages,
on-panel card editing and settings export remain outside this batch.
