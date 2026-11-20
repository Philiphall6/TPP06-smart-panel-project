# Desktop assistant — 0.1.0-rc3

Experimental setup and maintenance for the known TPP06 / AK3761E variant,
Linux `4.4.192V2.4`. Simulated tests and Mint GUI checks are not validation of
the complete workflow on a new panel or real Windows hardware.

## Start on your computer

1. Extract the **whole** assistant ZIP. Do not run it as administrator/root.
2. Install [Python 3.11+ with Tcl/Tk](https://www.python.org/downloads/),
   not the Windows embeddable package.
3. Download [Android Platform Tools / ADB](https://developer.android.com/tools/releases/platform-tools)
   for your OS and extract the entire ZIP. Android Studio is not required.
4. Run `Installer-dependances.cmd` on Windows, or `sh Installer-dependances.sh`
   on Linux. It installs pinned Python dependencies on the PC only. The missing
   `elftools` module is provided by `pyelftools`; do not install it on the panel.
5. Run `Assistant-TPP06.cmd` or `sh Assistant-TPP06.sh`, then click **English**.
   If needed, choose `platform-tools/adb.exe` (Windows) or `adb` (Linux).
   On Mint, Tkinter may require the PC's `python3-tk` package.

Nothing connects, downloads or writes at startup. Language switching preserves
fields and password masking without reconnecting. Labels and confirmations are
translated; some technical reports retain their original language.
Use the panel's IP, not Home Assistant's IP. Never expose 22, 5555 or 8090 to the Internet.

## The two folders

Both are **on this PC**, not in Home Assistant or the panel:

- **Backups on this computer** defaults to `TPP06-Backups` in your user folder.
  Each operation creates a private subfolder for copies and its recovery record.
  Keep it outside Git, shared folders and cloud sync. Backups contain secrets;
  retain them and never upload them to GitHub.
- **TPP06 tools on this computer** defaults to `TPP06-Tools`. In the operation
  form, click **Prepare tools**, confirm the PC-only download, then **Check tools**.
  NAND and ADB artifacts are fetched from fixed HTTPS sources and checked against
  pinned SHA-256 hashes. Unknown existing files are refused, not overwritten.
  Dropbear still requires manual compatible preparation using the linked SSH guide
  (French). Arbitrary ARM binaries are not accepted.

No folder is created at startup or by cancelling a form. Confirmed downloads
create the tool folder; confirming an operation creates the backup parent if needed.
Paths stay in memory; passwords are not prefilled or saved in operation records.

## Backup is not a validated full restore

The workflow is ADB unlock → access check → private backup → review → installation.
You may explicitly accept the state **after ADB**, not factory state, as your
reference. The ADB overlay replaces `/data/app` and `/data/customize`; a later
backup cannot recover those earlier files. The rollback package is not a NAND backup.

NAND acquisition copies **all exposed MTD partitions**, data and OOB, in two
matching passes, with sizes and SHA-256 in `nand-manifest.json`. It uses temporary
RAM files, does not stop services, write NAND or reboot. Unsupported bad blocks,
uncorrectable ECC, changing or truncated reads are refused. A matching live copy
does **not** certify filesystem consistency, hidden physical areas, or restoration.
The manifest keeps `consistency_validated: false` and `restore_validated: false`.
Whole-NAND restore is not automated or validated. Keep older backups.

The separate Cutter archive is partial. Restore actions use complete, matching
operation records, not arbitrary NAND images. Never delete locks or repeat an
ambiguous write after losing a connection: inspect its record and use resume/check.

## Boot logo and installation

The [public Home Assistant logo](../../assets/boot-logo/README.md) is included:
PNG preview and 320 × 480 RGB565 image padded to 512 KiB. The Logo form selects
it by default. **It is not ESPHome OTA firmware.** This separate NAND operation
requires a recognized partition geometry, local UART recovery, stable power,
two original copies and read-back verification. Power loss remains dangerous.
No reboot is automatically sent by the Logo action. License and attribution are included.

SSH uses the recognized Dropbear binary, a device-specific host key and access
checks before configuring startup. It does not replace an existing SSH installation.
The known firmware's DES password format only uses eight characters: choose
exactly eight random printable ASCII characters. A rescue console is held during
password changes and the new login is tested; total network/power loss can still
require local recovery.

First ESPHome installation requires your own static ARMv5 program compiled in
Home Assistant, not ESP32 firmware. The assistant does not build firmware on Mint
or ask for your HA YAML. It preserves the active Wi-Fi profile and original launcher,
then prepares ESPHome-only startup without reboot. There is no automatic Tuya fallback.
For an already-working ESPHome panel, use OTA instead of repeating first installation.

Startup and verification are separate actions. A recorded intent prevents sending
the first reboot twice. Verification requires the program's own encrypted API key,
matching identity and 120 continuous seconds of API/process stability within five
minutes. This does not validate touch, relays, sound, offline use or a power cycle.
Each device-changing action requires its own explicit confirmation; do not run OTA
or other maintenance concurrently. No destructive Tuya cleanup is performed.

See the [detailed French guide](../fr/21-assistant-ordinateur.md) for pinned tool
hashes, acquisition limitations and operation-specific recovery details.
