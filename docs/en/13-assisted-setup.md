# Assisted first commissioning — experimental

[Français](../fr/13-installation-assistee.md) · [Beginner guide](START-HERE.md)

**Status: code and offline simulations only. This complete new procedure has
not been run on hardware yet.** It is not recommended for an unassisted beginner.
The working reference panel was not changed for these tests.

[`tpp06_commission.py`](../../tools/tpp06_commission.py) automates private
configuration, checks, a Cutter backup, staging, one boot trial and conditional
primary-boot confirmation. **Compilation stays in Home Assistant.** It does
not install the ADB overlay, flash NAND or replace the logo. An existing working
ESPHome panel must use OTA instead; this tool refuses to stage on such a panel.

## Requirements

- Owner-confirmed compatible TPP06/AK3761E variant and firmware. Kernel and CPU
  checks alone do not establish hardware compatibility.
- Working network ADB, associated Wi-Fi and only the stock Tuya UI running.
- Linux computer, Python **3.11+**, `adb`, `readelf` (binutils). No particular
  Mint machine is required and this computer does not compile firmware.
- Stable power and an operator on site able to recover through UART.
- Existing private backup. A Cutter backup is not a full NAND image and may
  contain Wi-Fi credentials.
- Target: V5/project `0.1.5`, ESPHome `2026.10.2`.

From the repository root:

```bash
python3 -m venv .venv-commission
.venv-commission/bin/pip install 'aioesphomeapi==46.12.0'
```

Replace example IP `192.0.2.1` with the **panel's** IP, `/private/path/panel`
with a new private directory outside Git whose parent exists, and `entrance-panel`
with a unique device name. Match the timezone to HA.

## 1. Generate private configuration, compile in HA

```bash
.venv-commission/bin/python tools/tpp06_commission.py configure --directory /private/path/panel --name entrance-panel --address 192.0.2.1 --timezone Europe/Paris
```

This creates the full YAML, `secrets.yaml`, `api-key.txt` and `connection.json`
with private permissions, without overwriting an existing directory. Copy the
YAML to HA's `/config/esphome`. **Merge the secret entry into the existing
`secrets.yaml`; do not replace that file.** For multiple panels, rename the
secret entry and its YAML reference to avoid replacing another device's key.
Keep the value identical to `api-key.txt`. Never publish these files or binaries.

Customize labels and UI, keeping the expected technical name, version, model
API/OTA settings and `api.reboot_timeout: 0s`. Leave fictional entities and HA
actions disabled for the trial. Validate and compile/manual-download in Builder,
without installing. Save the Linux `program` executable in the private directory;
not an ESP32 firmware. Do not replace it midway through commissioning.

## 2. Check, then stage without rebooting

```bash
.venv-commission/bin/python tools/tpp06_commission.py check --directory /private/path/panel --binary /private/path/panel/program
```

This does not modify panel files. It checks the binary architecture, network
identity, active Wi-Fi profile, recovery listeners, watchdog and free space.
It does not delete files to make room or establish that the next boot will work.

After reviewing the results, **only during an assisted trial with local recovery**:

```bash
.venv-commission/bin/python tools/tpp06_commission.py prepare --directory /private/path/panel --binary /private/path/panel/program --experimental --compatible-panel-confirmed --physical-recovery-ready
```

This **writes to the panel**: initial backup, binary and supervisor installation,
Wi-Fi profile copy and transfer verification. It leaves Tuya selected and does
not request a reboot. Keep an external private copy of the directory, especially
`backups/` and `commission.json`. The three flags are operator declarations,
not automatic proof of compatibility or physical recovery readiness.

## 3. One trial and conditional confirmation

```bash
.venv-commission/bin/python tools/tpp06_commission.py trial --directory /private/path/panel --binary /private/path/panel/program --experimental --compatible-panel-confirmed --physical-recovery-ready
```

The tool requests **one reboot**, then observes automatically. It requires at
least **120 uninterrupted seconds** with the same ESPHome PID and boot identity,
no stock UI, connected Wi-Fi, ADB, recovery port and an authenticated encrypted
API. It compares MAC, name and project version and rechecks the backups. It
does not operate lights or covers. Only then does it confirm primary boot and
verify supervisor rearming and guard disarming. It requests no second test reboot.

An independent on-panel guard is designed to select Tuya and reboot after
**10 minutes without confirmation**, even if the computer disconnects. Client
confirmation closes at 8 minutes. A reset before confirmation should return to
stock through the consumed trial marker. **These protections have only been
simulation-tested with this new tool**, not hardware-validated. They cannot
recover every kernel, NAND or power failure.

## Error or connection loss

Do not rerun `trial`, delete journals/locks or reinstall blindly. If a reboot
request may have been sent, resume checks without resending it using:

```bash
.venv-commission/bin/python tools/tpp06_commission.py verify --directory /private/path/panel --binary /private/path/panel/program
```

A failed trial is not automatically rearmed. Let the guard act, then inspect
state and private logs with assistance. Ambiguous phases deliberately remain
blocked. Do not run an OTA concurrently.

After successful confirmation, add the panel to HA's ESPHome integration using
its private key. Physically verify display and touch. Verify mDNS separately
before changing the initial IP to `.local`. Subsequent updates use Builder OTA,
not first commissioning. Power-loss recovery, endurance, sleep/wake, beep and HA
actions remain separate checks. Fallback is **stock Tuya**, not previous ESPHome.
