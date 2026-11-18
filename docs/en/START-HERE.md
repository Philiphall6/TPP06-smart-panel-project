# Start here — TPP06 and Home Assistant, without dismantling

[Français](../fr/DEMARRER-ICI.md) · [Project home](../../README.en.md)

This guide separates **first preparation** from **updates**. A compatible
panel can use the network path without opening its enclosure. This remains
experimental: remote recovery cannot be guaranteed if Linux stops booting.

## 1. What runs where?

- The panel keeps its Anyka Linux and runs the ESPHome/LVGL touch interface.
- Home Assistant (HA) supplies time and the states of your household devices.
- ESPHome Device Builder in HA edits the YAML configuration, builds the
  application and sends updates. No Mint computer or remote build server is required.

Adding the ESPHome integration in HA does not automatically create a Builder
configuration. “Online” is not proof of a working API: check the logs for
successful connection and authentication.

**OTA** means a network update. **ADB** is Linux maintenance access for initial
preparation and backups. **UART** is a wired recovery console for advanced use.
Already running ESPHome? **Go to step 5**. Do not reinstall ADB, boot scripts
or the boot logo for a UI update.

## 2. Prepare without writing to the panel

You need your own working Wi-Fi-connected TPP06, HA, a computer on a trusted
LAN, stable power and on-site recovery capability. Install ESPHome Device
Builder in HA; the tested ESPHome version is **2026.10.2**. Install Python 3,
Git and Android Platform Tools (`adb`) on the computer for maintenance, not
firmware compilation.

The tested network preparation targets **TPP06/AK3761E**, identified as
`ak3761e_tpp06z`, kernel `4.4.192V2.4`. Similar appearance does not establish
compatibility. If existing device information cannot confirm the variant,
**stop before sending an overlay and ask for help**. Do not dismantle it just
to follow this guide.

In a computer terminal:

```bash
git clone https://github.com/Philiphall6/TPP06-smart-panel-project.git
cd TPP06-smart-panel-project
python3 --version
adb version
```

On Windows, use `py -3` instead of `python3` if needed; the advanced guide’s
`sha256sum` commands require a compatible environment. All `192.0.2.1`
addresses below are **fictional examples**. Replace them with the panel IP
from your router’s connected-device list, not the HA address.

```bash
python3 tools/tpp06_authkey_reader.py 192.0.2.1
```

Expected: a response, masked AUTHKEY and locally derived root password. No
persistent write or reboot is requested. Keep the output private. If it fails,
check the address, Wi-Fi and network filtering; do not blindly proceed.
[Network access details](00-network-authkey-access.md).

## 3. First ADB preparation and backup — a safety gate

If ADB already works, do not reinstall its package. Otherwise read the entire
[ADB-over-Wi-Fi guide](04-adb-over-wifi-without-uart.md) and verify the listed
release checksums before writing anything.

> [!WARNING]
> The ADB overlay replaces `/data/app` and `/data/customize`. A Cutter backup
> taken afterwards cannot recover customisations overwritten beforehand.
> If those matter and no backup access is available, stop and seek assistance.
> An ADB rollback archive is not a complete backup of your device.

Once ADB access is verified, from the repository directory:

```bash
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 status
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 backup
python3 tools/tpp06_tuya_cutter.py 192.0.2.1 network-check
```

The Cutter derives credentials in memory without displaying them. Wait for
backup verification and keep a copy on separate private storage. This covers
the Cutter’s defined scope, **not the whole NAND**; it can include Wi-Fi
credentials. An identical saved Wi-Fi profile does not establish standalone
network recovery. Stop on missing, ambiguous or unknown state; do not invent
ESP32 Wi-Fi configuration for this Linux panel.

## 4. Prepare V5 in Device Builder

An [experimental assisted procedure](13-assisted-setup.md) generates private
configuration and coordinates the transition after compilation. It has only
been tested offline and still requires an assisted hardware trial. Do not run
first commissioning on a panel already using ESPHome.

1. Back up existing HA/Builder configurations.
2. Copy the complete
   [`esphome/tpp06-lvgl-mobile.yaml`](../../esphome/tpp06-lvgl-mobile.yaml)
   into `/config/esphome`, for example `my-panel.yaml`, using HA’s file editor.
   It then appears in Builder. Do not use the wizard to create an ESP32.
3. Click **Edit** and change the substitutions at the top:

   | Variable | Your value |
   | --- | --- |
   | `device_name` | Unique technical name, e.g. `entrance-panel`, without spaces |
   | `friendly_name` | Display name |
   | `device_address` | Current panel IP initially; `.local` name after verifying mDNS |
   | `cover_entity` | Your cover entity, or leave the fictional example for display-only testing |
   | `cave_light_entity`, `bar_light_entity` | Your two light entities; historical variable names, not required room names |
   | Titles and `ui_*` colours | Your labels and palette |

   Find entity IDs in **HA → Developer tools → States**. A visible light name
   is not its `light.…` entity ID. Keep fictional entities for initial tests
   that must not control household equipment.
4. For a **new panel only**, generate a private random key with
   `openssl rand -base64 32` and add this to Builder’s `secrets.yaml`:

   ```yaml
   tpp06_api_encryption_key: "PASTE_YOUR_PRIVATE_KEY_HERE"
   ```

   The placeholder is not a usable key. Use a separate secret entry per panel
   and adjust its `!secret` reference. For an update, **keep the existing key**.
5. Keep `api`, `ota`, `host`, `external_components` and
   `api.reboot_timeout: 0s`. The model uses ESPHome 2026.10.2 OTA encryption;
   do not invent an OTA password or use the root password as an API key.
   Do not add ESP32 `wifi:` configuration: the supervisor preserves Linux Wi-Fi.
6. **Validate**, then request a **compile/manual download** in HA, without
   installation. The result is a Linux executable named `program`, not an
   ESP32 `.bin`. Initial tool downloads may take time; read the final result.

GitHub is specified inside `external_components`, not Builder’s appearance
settings. No developer-workstation or another owner’s private path is required. Later
ESPHome versions are not automatically validated by this guide.

### Stop before first standalone activation

**Successful compilation installs nothing.** A stock panel has no ESPHome OTA
listener. First copying uses the Cutter, not ESP32 USB flashing. Builder’s
generic “first installation via USB” advice does not describe this Linux port.

The advanced path is in [Tuya Cutter](07-tuya-cutter.md). A standard trial
keeps Tuya active and does not establish exclusive screen ownership.
`install --experimental-multiboot --keep-stock` stages without selecting
ESPHome. Standard `install` **never** automatically confirms permanent
standalone boot. Profile, backup, fallback, a bounded trial and authenticated
API checks must precede separate confirmation.

**Beginners should stop here and request assisted commissioning.** There is
not yet a universal one-click transition. Do not manually copy `mode`,
`network_mode` or `persistent_confirmed` values from someone else’s logs.
Success on another panel does not validate yours.

## 5. Update a panel already running ESPHome

1. Privately back up the YAML, `secrets.yaml`, previous working executable and
   Cutter archive. Do not change the device name or key during the UI update.
2. For V4 → V5, compare your YAML with the full mobile V5 model. Keep your
   substitutions, keys and addresses; include new `tpp06_backlight`, scripts,
   globals and automations, not only `lvgl:`. Do not remove older local
   component directories without comparing them with the published drivers.
3. Check project version **`0.1.5`**, then **Validate**. Leave sleep on
   **Never**. Do not create a second device for this update.
4. Build/download the candidate in HA. With the downloaded program, check
   space from the administration computer:

   ```bash
   python3 tools/tpp06_tuya_cutter.py 192.0.2.1 ota-space-check --binary /path/to/program
   ```

   Respect the check result; allow room for the new executable and a reserve
   (at least 2 MiB in the reference trial). Never randomly delete Tuya data,
   network profiles or backups to free space.
5. Click **Install → Wirelessly once** in Builder. Choose the current panel
   address if asked. Do not start another upload or interrupt power.
6. Wait for **Installation successful**, not just “Successfully compiled”.
   Open logs and confirm connection, encrypted authentication and project
   version `0.1.5`. Check home, date and menu without household actions first.
   A brief API interruption does not necessarily mean Linux rebooted.

The full configuration is an editable local copy: GitHub changes do not
automatically overwrite your pages. No update badge is required for this
manual workflow. Record ESPHome version and driver commit for reproducibility;
`ref: main` follows the repository.

## 6. Connect HA and customise

In **Settings → Devices & services → ESPHome**, accept discovery or add the
panel name/IP and **your API key**. The root password is not the API key.
If HA says “different device / MAC mismatch”, do not force pairing or delete
all entities: inspect the old registration and the panel’s real MAC first.

Before enabling HA actions in this integration’s options, verify entity
bindings. Leave permission off for display-only tests. An API connection can
also be a log client, so a connected label alone does not establish HA service
control. Edit pages/widgets in `lvgl:`, then validate, compile and update OTA.

See [V5 features](11-interface-v5.md). Physical wake still needs on-site
testing; **beep is unavailable**. Replacing the [initial MOES logo](12-boot-logo.md)
is separate, optional and risky; normal interface OTA does not change it.

## 7. Troubleshooting

| Symptom | Safe next check |
| --- | --- |
| Build failed | Save logs; find the first error, not just `build stopped`. Do not upload. |
| Build succeeded, installation failed | Check network, address, space and key; do not reflash the overlay. |
| API refused on `6053` | Verify the ESPHome process, not only Wi-Fi; inspect Cutter `status`. |
| Key rejected | Use the key of the installed application, not a newly invented key. |
| `.local` missing | Try the known IP and inspect mDNS/VLAN separately. |
| Screen black after sleep | Avoid repeated reboots; arrange local recovery and investigate. |
| Boot loop / no network | Stop OTA attempts; use [advanced recovery archives](../archive/README.md). |

Multiboot fallback is **stock Tuya**, not automatic V4 rollback. Keep old
executables off-device. Review archive scope before using [Cutter restore](07-tuya-cutter.md).
Never expose maintenance/API/OTA ports to the Internet. The ADB patch accepts
LAN clients’ RSA transport, making trusted-network filtering important.

Official references: [API/encryption](https://esphome.io/components/api/),
[ESPHome OTA](https://esphome.io/components/ota/esphome/),
[YAML secrets](https://esphome.io/guides/configuration-types/#secret).
