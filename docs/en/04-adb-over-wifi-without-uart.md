# Phase 4 — Enable ADB over Wi-Fi without UART

This experimental procedure uploads a persistent overlay through the local
TCP `8090` production-test service and starts `adbd` on TCP port `5555`. It was
validated only on an `AK3761E` TPP06 identified as `ak3761e_tpp06z`, running
kernel `4.4.192V2.4` dated 13 December 2024.

> **Warning.** The `bootpicture` update handler deletes and replaces
> `/data/app` and `/data/customize`. A different hardware or firmware revision
> may fail to boot. Never interrupt power during the upload.

## Requirements

- Python 3 and Android Platform Tools (`adb`);
- the panel and computer on the same trusted LAN;
- the panel-specific root password obtained in [Phase 0](00-network-authkey-access.md);
- `tpp06-adb-network-final.tar.gz`, `tpp06-adb-rollback.tar.gz`, and
  `SHA256SUMS` from the release.

Verify the downloads, then upload from the repository root:

```bash
sha256sum -c SHA256SUMS
python3 tools/tpp06_ota_uploader.py \
  PANEL_IP tpp06-adb-network-final.tar.gz \
  --i-understand-this-overwrites-customization
```

Wait for the complete success message before power-cycling the panel. After
about one minute:

```bash
adb kill-server
adb connect PANEL_IP:5555
adb devices -l
adb shell
```

Log in as `root` with the password derived in Phase 0, then verify with `id`
and `uname -a`.

## Security warning

The old Tuya `adbd` RSA verifier crashed while processing the host signature.
The installed copy patches that verifier to return success. Consequently,
**any LAN client can establish the ADB transport**, although the Tuya shell
still asks for the panel-specific root password. Never expose ports `5555` or
`8090` to the Internet; isolate the panel and firewall both ports to the
administration host.

## Rollback

Upload the rollback payload with the same tool, wait for success, and then
power-cycle:

```bash
python3 tools/tpp06_ota_uploader.py \
  PANEL_IP tpp06-adb-rollback.tar.gz \
  --i-understand-this-overwrites-customization
```

The rollback restores the original `S50adbd` startup script and disables
network ADB after reboot. If the panel no longer boots or port `8090` no longer
starts, UART remains the recovery route.
