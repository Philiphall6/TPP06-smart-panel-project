# Phase 7 — TPP06 Tuya Cutter

> **Advanced reference and chronological test log.** The
> [beginner guide](START-HERE.md) describes the current workflow.
> [V5](11-interface-v5.md) is installed on the reference panel, with encrypted
> API and healthy state checked and persistent policy retained. Reports below
> preserve the limits at the time of each trial. Standard `install` does not
> automate first persistent standalone activation.

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

The ESPHome temporary test keeps Tuya running and stops automatically; it
does not validate exclusive display ownership. The historical openHASP test
still suspends the entire Tuya process with `SIGSTOP`, not just its GUI. That
path is not safe for a remote trial without physical recovery access and must
not be used as a display workaround.

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

Installation reads the running `wlan0` supplicant's arguments to select its
actual `-c` configuration, then copies it to
`/data/tpp06-cutter/network/wpa_supplicant.conf`. It no longer assumes that
`/etc/wpa_supplicant.conf` is active: the examined panel used a different file
in Tuya's data directory. Selection rejects ambiguous processes, another
interface or multiple network blocks. Failure sets network mode to
`unavailable` instead of copying an arbitrary template. The copy is checksum
verified before replacement and protected with mode `0600`. Comparison uses
SHA-256 or MD5 as a fallback because some panel BusyBox builds lack `cmp`;
this is local file comparison, not signature verification. The Cutter never
prints the SSID, key or profile checksum.

Read-only diagnostic, without restarting or changing the network:

```bash
python3 tools/tpp06_tuya_cutter.py PANEL_IP network-check
```

`SAVED_PROFILE=identical` only confirms that the copy matches the active file.
`AUTONOMOUS_WIFI=not_verified` remains explicit: this tests neither reassociation
nor driver startup without Tuya. The current `COMPLETED` state reported by
[wpa_supplicant STATUS](https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html)
does not validate a future standalone boot.

The two network policies are separate; there is no automatic transition:

1. **learning boot:** stock Tuya retains Wi-Fi while ESPHome must survive the
   60-second grace period and listen on API port `6053`;
2. **isolated boot (experimental, explicit selection only):** the supervisor starts `wpa_supplicant` and `udhcpc`,
   waits for an IPv4 address, keeps only the local `tuya_factory` rescue
   service on port `8090`, and then starts ESPHome.

A successful learning session does not validate independent Wi-Fi. Do not
select isolated mode remotely without an on-site recovery option.

The corrected supervisor refuses isolated mode while the Tuya application or
its monitor is still present. It also refuses to mistake an inherited address
or existing Wi-Fi/DHCP processes for networking it started itself. It never
kills those processes to bypass the refusal. These guards are tested offline;
they do not prove hardware boot readiness.

On 18 November 2026, the recovery profile was prepared from the active profile
on the panel after private backup and verification. Active network settings,
the flash program and installed supervisor stayed unchanged; modes remain
`tuya` and `learning`. The new supervisor was not deployed during preparation.
No reboot or Tuya stop was sent.

#### Standalone boot prerequisites

Scripts retrieved from the current firmware show that `rc.local` loads the
display, touch and Wi-Fi drivers, brings up `wlan0`, starts ADB and launches
`ak_watchdog` before `S99tuya-app`. The selector must preserve that ordering:
it does not reload modules, toggle GPIOs or open `/dev/watchdog` itself.

The prepared supervisor now requires:

- the `wlan0` interface and display, touch and watchdog devices;
- an `ak_watchdog` process holding an open watchdog descriptor;
- network tools and the stock DHCP event script;
- `wpa_state=COMPLETED` association **and** a usable IPv4 address;
- both local listeners, ADB `5555` and recovery `8090`, before ESPHome starts.

The DHCP event script is passed explicitly to `udhcpc`. Failure to bring up
`wlan0` aborts the attempt. An unspecified, loopback or link-local address is
not accepted as a ready lease. These checks are necessary, not sufficient:
a listening port is not proof of remote authenticated access, and an open
watchdog descriptor does not prove long-term keepalive operation.

At that stage, all 69 offline tests passed. Read-only hardware checks also passed on the panel in
its current Tuya state. A separate RAM trial verified only **refusal** of
isolated mode while Tuya is active: no custom engine launched, network
processes unchanged, flash program, Wi-Fi profile and installed supervisor
unchanged. The sentinel program in that trial was not ESPHome. This validates
neither standalone boot nor fallback following an actual network failure.
A hardware handover trial still requires on-site recovery; no reboot was
performed for these checks.

#### Short standalone trial on 18 November 2026

A separate trial then started ESPHome after a software reboot without starting
the stock Tuya GUI. A temporary launcher restored the original launcher
**before** attempting the trial; global selections remained `tuya` and
`learning`. The Home Assistant-built binary was copied into a separate trial
directory without replacing the installed program.

Independent Wi-Fi associated and obtained an IPv4 address. ADB and port `8090`
remained accessible during the session. All 18 encrypted API probes succeeded.
A framebuffer capture shows the LVGL interface rather than the Tuya clock;
ESPHome held the display and touch device open without a competing stock GUI
process. No touches or household actions were sent during this remote check.

The supervisor stopped ESPHome after 120 seconds and triggered stock fallback.
An independent timer then requested a reboot after 210 seconds through the
already-restored original launcher. A client-side ADB connection had become
`offline` after this reboot: disconnecting/reconnecting that specific transport
restored access without an additional panel reboot. A separate final check
confirmed 93 seconds of stock stability, associated Wi-Fi, and original file
checksums restored or unchanged.

This is a **short trial**, not a permanent installation or power-cut validation.
It does not validate recovery from a kernel hang, long-term stability, household
actions, or OTA in standalone mode. Logs, profiles, keys and captures stay
private. The trial timer is not a hardware recovery guarantee.

#### 15-minute standalone trial

The same Home Assistant-built binary was then tested for a 900-second session,
with an independent return-by-reboot timer set to 990 seconds. No OTA transfer
or household action was sent. The original launcher was restored before the
trial supervisor started.

Observations show a single ESPHome process on the same boot, constant resident
memory of **4,792 KiB**, and **51 successful encrypted probes**. Beginning and
end framebuffer captures show the same LVGL interface. This is not a new
physical touchscreen test.

One ADB sample failed during the session; the following sample found the same
process without a reboot. An additional API probe failed during shutdown:
the sampled uptime and supervisor log place it at the scheduled 900-second
expiry. These observation failures are retained in the report rather than
described as an entirely successful set of probes.

Stock fallback and the recovery reboot were observed, followed by 90 seconds
of verified stock stability. Checksums confirmed that the four tracked
original files were restored or unchanged. The standalone system
clock remained in 1970 in that first binary. Subsequent v3/V4 trials added
HA time synchronization; V4 revealed a timezone offset, documented in the
[mobile interface report](06-native-esphome-lvgl.md#ios-inspired-mobile-variant). An additional HA-side
mDNS check was not performed because the SSH tool's Docker access was
protected; that protection was not changed. Long-term endurance, standalone
OTA, household actions and power cuts remain outside this validation.

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

### Persistent boot policy — experimental opt-in

The supervisor defaults to `boot_policy=one-shot`. The standard installer
explicitly resets this policy and its confirmation; installation or a
successful trial never automatically enables persistent boot.

`boot_policy=persistent` is restricted to ESPHome with `network_mode=isolated`,
an unbounded session and a verifiable API port. Each boot initially selects
stock for the next cycle. Only after the grace period, local process/network/
listener checks and explicit `persistent_confirmed=yes` does the supervisor
reselect ESPHome. First-deployment confirmation must follow an authenticated
remote check; listening ports alone do not prove authentication.

Three consecutive local health failures, checked ten seconds apart, stop
ESPHome and select stock **before** network cleanup. Process exit also falls
back. Loss of Home Assistant or Internet alone does not trigger a reboot.
Explicit supervisor stop leaves stock selected.

Startup also checks the Linux boot ID and supervisor command line: a reused
PID from an earlier boot is not mistaken for a running supervisor. The 84
offline tests cover this case, incompatible policy rejection and fallback
after local health failures.

This cannot guarantee recovery from a kernel hang after rearming, storage
failure or hardware damage. Physical recovery access remains required. The
first deployment separately uses a stock-only launcher and a recovery timer,
disarmed only after remote verification. No bootloader or raw NAND modification
is required. Standard `install` does not enable persistence; do not copy state
files without the guarded deployment procedure.
