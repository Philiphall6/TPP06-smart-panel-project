# Settings → Wi-Fi — Linux bridge enabled on the reference panel

Development template `0.1.6-wifi.2-dev` adds network discovery, tap-to-select
SSID, a local keyboard, masked password, **Try**, **Confirm** and **Cancel**. The reference
panel's active network has not been changed. Do not install an OTA assuming
this feature is already commissioned.

Open **Settings → Wi-Fi → Rechercher les reseaux** (Search networks), wait
about 20 seconds, then tap your network. Its name is filled in and the keyboard
targets the masked password field. Selecting a result does not connect.
**Saisie manuelle** (Manual entry) remains available for hidden/missing networks.

The proposed Try flow saves the old profile, tests the new network, waits for
association to the requested network, observed old-lease deconfiguration,
a usable IPv4 address and 20 seconds of stability, then allows confirmation
on the screen. Without confirmation within 120 seconds, or on cancellation,
the supervisor restores the old configuration. Checks run on the supervisor's
normally ten-second interval; reconnection takes additional time.

Restoring a profile cannot restore a missing access point. Driver/system
failures may need on-site recovery. Wi-Fi association does not verify Internet
or Home Assistant connectivity, neither of which is required to confirm locally.

## Local discovery

Discovery only runs after tapping Search, never automatically on boot or page
entry. The supervisor requests `SCAN`, then reads `SCAN_RESULTS` on its next
cycle. This may include cached results: the UI says so, without claiming to
have received the completion event of a fresh scan. Retry later or use manual
entry if results are old or empty.

- Four rows per page, **Suite** (Next), up to 24 distinct names/security classes.
  Duplicate name/security classes retain the strongest signal, sorted by
  descending signal where the driver reports negative dBm values.
- Unsupported networks are marked and cannot be selected. Discovery itself
  does not guarantee connectivity.
- Two-minute result expiry and a 30-second scan cooldown; no automatic loop.
- At most 12,000 bytes of private results, never logged. Hidden names, malformed
  UTF-8, control characters and truncated records are ignored. Valid names
  remain data, never shell commands.
- No scans during Wi-Fi trials/rollback, an OTA detected by the supervisor,
  or against network daemons it does not own. Discovery does not change the
  profile or DHCP lease, but active radio scanning may briefly add latency.
  Real driver behavior still needs on-site testing.

## Scope and privacy

- Linux `wlan0`, not ESP32 `wifi:`. WPA/WPA2 Personal only initially: no
  WPA3-only, enterprise/open networks, captive portals or static addressing.
- Manual SSID, including hidden networks; 1–32 UTF-8 bytes. Password: 8–63
  printable ASCII characters excluding double quotes, or a 64-digit hex PSK.
  Embedded quotes are refused because of WPA configuration comment parsing.
- Manual entry remains available; no file import or saved-network library yet.
- No HA entities carrying credentials. The password field is cleared after
  submission and on page exit. The component never logs passwords.
- Mailbox directory `0700`, files `0600`. Persistent profiles are root-readable
  local secrets, **not encrypted files**; never commit them or backups to GitHub.
- No relay commands, reboots or firmware-partition writes. Only Wi-Fi link
  health is temporarily exempted; process/API/rescue-listener checks remain.
- A persistent journal restores the old profile before the next supervised
  network startup or stock fallback if confirmation was interrupted.
- Replacing an already unavailable AP additionally requires the supervisor's
  separately validated offline-local policy (`local_control_confirmed`). The
  editor never enables it. With that policy, restoring an unavailable old
  profile keeps the screen usable to correct credentials; otherwise starting
  a trial from an already lost connection is refused.
- Stock Tuya's network profile is not rewritten: after a confirmed migration,
  stock recovery may still require the old access point.
- IP changes may require HA reconfiguration where mDNS cannot cross networks.
  API encryption keys, device identity and entities are unchanged.

## Read-only preparation

`device/tpp06-wifi-preflight.sh` checks staged candidates without sourcing
them or changing networking. Run on the panel with the two candidate paths:

```sh
sh /private/staging/tpp06-wifi-preflight.sh \
  /private/staging/tpp06-multiboot.sh /private/staging/tpp06-wifi-edit.sh
```

It checks shell syntax, persistent boot policy, private profile permissions,
the stock launcher, absence of pending OTA/Wi-Fi transactions, ownership of
WPA/DHCP processes and the Wi-Fi control response. No SSID or key is printed.
Success means prerequisites only, not activation or a tested network change.
An unconfirmed offline-local policy is reported as a limitation for replacing
an already unavailable access point.

Keep private verified backups of the active supervisor, stock launcher and
network profile. Check their hashes again after staging. Staged files are not
loaded automatically: do not replace the active launcher, create the enable
flag or reboot remotely in place of supervised commissioning.

## Separate commissioning required

`tpp06_wifi` only writes a private mailbox. Actual network operations belong
to `device/tpp06-wifi-edit.sh`, loaded by the updated multiboot supervisor.
A fresh readiness lease from that running supervisor is required. Firmware
OTA alone neither installs this helper nor activates the editor. The
`wifi_editor_enabled` opt-in is never written automatically.

Back up and verify the live supervisor, active Wi-Fi profile and rescue path;
install the scripts together and start the updated supervisor through a
supervised boot. Never overwrite the running shell script in place or delete
`network/wifi-trial/pending` to bypass recovery. This installation/activation
workflow is not yet automated or validated on hardware.

Before release, with on-site power/UART recovery available:

1. Compile in HA; verify ARM ABI, OTA size and free-space reserve.
2. Check list/keyboard layout, selected SSID, password privacy and touch handling;
   test empty lists, duplicates, pagination, accented names and hidden networks.
3. Test wrong credentials, cancellation and timeout without HA.
4. Test a real second access point, DHCP renewal, confirmation and HA/mDNS.
5. Test application interruption and reboot before confirmation.
6. Verify local relays and recovery access across disconnection and rollback.

Offline tests cover the WPA/DHCP state machine, journal recovery, simulated
discovery (sorting, duplicates, security, expiry/cooldown), invalid inputs,
private mailbox permissions, YAML validation and LVGL C++ generation.
They do **not** validate radio behavior or replace the on-site tests.
A `0.1.6-wifi.2-dev` candidate has now been compiled in HA and checked as a
static ARMv5TE soft-float executable. OTA storage headroom was checked on the
reference panel and must be recalculated for each installation. This does not
validate network switching: the Linux helper was still absent/not enabled on
that panel. Installation was subsequently detected and verified by checksum
and encrypted API, without sending a second OTA. A 120-second observation found
a stable process, no Linux reboot, four switch states, two restart buttons and
the storage entity. No relays were commanded. Visual/touch and on-site network
tests remain outstanding. Installing only the interface leaves Wi-Fi management
unavailable.

The Linux bridge was subsequently installed separately on the reference panel
after confirmation of on-site recovery availability. One reboot was requested.
The process remained stable during 120 seconds of post-boot observation;
encrypted API and recovery access responded. Persistent boot was rearmed,
then the Wi-Fi service's fresh readiness lease, idle state and absence of a
pending transaction were verified. Active Wi-Fi profile and stock rescue
launcher checksums were unchanged. **This validates the idle software bridge,
not a network migration.** Touch-driven discovery, access-point switching and
real rollback remain untested. Offline-local policy was not enabled.
Other installations still require their own commissioning checks.

Technical reference: [wpa_supplicant control interface](https://w1.fi/wpa_supplicant/devel/ctrl_iface_page.html).
