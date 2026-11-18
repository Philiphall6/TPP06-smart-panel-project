# Phase 7 — TPP06 Tuya Cutter

> [!CAUTION]
> Multiboot supervisor V1 passes offline tests but has not yet completed a full
> power-cycle validation on the panel. Permanent ESPHome installation requires
> the explicit `--experimental-multiboot` option. Keep UART available for the
> first hardware validation.

`tpp06_tuya_cutter.py` provides a reversible installer around the project's
network access, backup, openHASP, and native ESPHome-LVGL work. Given the panel
IP, it reads the `AUTHKEY` over port `8090`, derives the root password in memory,
connects through ADB, and performs verified transfers.

> **Development version.** Offline logic and archive validation have automated
> tests. End-to-end ADB operations still require validation after the panel's
> next reboot. Do not use permanent mode before successful temporary tests.

Start the interactive assistant with:

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1
```

Main non-interactive commands are:

```bash
# Inspect and back up
python3 tools/tpp06_tuya_cutter.py PANEL_IP status
python3 tools/tpp06_tuya_cutter.py PANEL_IP backup

# Temporary tests
python3 tools/tpp06_tuya_cutter.py PANEL_IP test openhasp \
  --binary openhasp-tpp06 --config config.json --pages pages.jsonl
python3 tools/tpp06_tuya_cutter.py PANEL_IP test esphome --binary program
python3 tools/tpp06_tuya_cutter.py PANEL_IP stop-test

# Reversible boot selection, only after testing
python3 tools/tpp06_tuya_cutter.py PANEL_IP install esphome --binary program \
  --experimental-multiboot
python3 tools/tpp06_tuya_cutter.py PANEL_IP switch tuya

# Recovery
python3 tools/tpp06_tuya_cutter.py PANEL_IP restore BACKUP.tar.gz
python3 tools/tpp06_tuya_cutter.py PANEL_IP uninstall
```

The tool never deletes stock Tuya partitions. A permanent cut-over stores the
new engine under `/data/tpp06-cutter` and overrides only `S99tuya-app` in the
writable overlay. The saved stock launcher remains selectable. Every permanent
install and restore first creates a verified local backup.

## Multiboot V1 automatic recovery

To install files while retaining stock Tuya for the next boot:

```bash
python3 tools/tpp06_tuya_cutter.py PANEL_IP install esphome \
  --binary program --experimental-multiboot --keep-stock
```

The selected mode stays `tuya`. Temporary trials reuse the flash executable
when its checksum matches the local binary, saving RAM. `reboot-check` is a
diagnostic: it cannot block reboots initiated by other tools or prove that
independent Wi-Fi will work after reboot.

Hardware check on 18 November 2026: a 60-second ESPHome trial kept TCP API
6053 reachable at the sampled times, preserved ADB and 8090 and the original
Tuya process, and stopped automatically without a reboot. Available memory
remained around 40 MiB. The supervisor was then installed with `--keep-stock`,
verified by checksum and executed in stock mode. Cold boot, independent Wi-Fi,
screen rendering, touch input and an authenticated Home Assistant session
remain unverified. Device backups and logs are kept outside this repository.

A second hardware trial ran the corrected supervisor in a separate temporary
directory: 60 seconds of health checks, followed by automatic stop at 80
seconds. State progressed from `esphome-starting` to `esphome-healthy`, then
`tuya-fallback`. The stock process stayed unchanged, uptime increased without
a reboot, ADB/8090 remained reachable at the sampled times, and API port 6053
closed after stopping. A test engine exiting with code 7 also triggered the
expected fallback. The corrected supervisor was then installed and checksum
verified after backing up its predecessor, with `MODE=tuya`, `ACTIVE=tuya`,
`NETWORK=learning`. All 29 automated tests pass. This still does not validate
cold boot or Wi-Fi without the stock Tuya application.

Before doing risky work, the persistent supervisor consumes the custom boot
selection, writes stock Tuya as the next mode, and syncs it to storage. It then
starts the original Tuya monitor to preserve Wi-Fi and local port 8090 recovery
before starting the custom engine. A `boot_pending` marker covers a 60-second
grace period. Even a healthy custom session is never re-armed automatically.
An exit, watchdog reset, or power loss, including after validation, therefore
leaves stock Tuya selected for the following physical boot.

A listening API does not validate display, touch, or an authenticated Home
Assistant connection. `TPP06_SESSION_SECONDS` bounds a supervisor trial
(default `0`: unlimited); expiry stops the engine and returns to stock without
counting a failure. These software protections cannot guarantee recovery from
storage corruption or a kernel/hardware failure.

### Learning and independent Wi-Fi

Installation copies the active `/etc/wpa_supplicant.conf` profile to
`/data/tpp06-cutter/network/wpa_supplicant.conf`. It stays on the panel with
mode `0600`; the Cutter never prints the SSID or key.

The two network policies are separate; there is no automatic transition:

1. **learning boot:** stock Tuya retains Wi-Fi while ESPHome must survive the
   60-second grace period and listen on API port `6053`;
2. **isolated boot (experimental, explicit selection only):** the supervisor starts `wpa_supplicant` and `udhcpc`,
   waits for an IPv4 address, keeps only the local `tuya_factory` rescue
   service on port `8090`, and then starts ESPHome.

A successful learning session does not validate independent Wi-Fi. Do not
select isolated mode remotely without an on-site recovery option.

A missing profile, DHCP failure, or absent ESPHome API triggers the stock
fallback. `status` reports `NETWORK=learning`, `isolated`, or `unavailable`.

Before every manual reboot, run the read-only gate:

```bash
python3 tools/tpp06_tuya_cutter.py PANEL_IP reboot-check
```

It fails unless the stock rescue launcher, supervisor, selected engine, Wi-Fi
profile, free space, and `PENDING` state are safe. This command never reboots
the panel.

> [!IMPORTANT]
> Cutter backups now include the Wi-Fi profile. They are created with mode
> `0600`, but remain sensitive and must never be committed or published.

Permanent ESPHome therefore uses the explicit command:

```bash
python3 tools/tpp06_tuya_cutter.py PANEL_IP install esphome \
  --binary program --experimental-multiboot
```

Backups are mode `0600`, ignored by Git, and accompanied by SHA-256 metadata.
Restores reject absolute paths, traversal, links, and files outside the allowed
overlay scope. `AUTHKEY`, root password, Wi-Fi credentials, and device keys are
never printed or written by the Cutter.
