# TPP06 — Local project without Tuya

[Version française](README.fr.md)

> [!CAUTION]
> **ESPHome multiboot is still experimental.** Supervisor V1 retains Tuya,
> Wi-Fi, and port 8090 during learning-mode trials. Every custom selection is
> one-shot: the next boot remains stock even after validation. This software
> fallback is not a recovery guarantee. Offline tests pass, but power-cycle validation is
> still required. Installation needs `--experimental-multiboot` and UART
> recovery must remain available.

Independent Wi-Fi (`wpa_supplicant`/DHCP) remains experimental and requires
explicit selection. A successful trial never enables it automatically.

**Current validation:** touchscreen confirmed, 15-minute supervised trial
passed, encrypted OTA passed on an isolated RAM copy without a Linux reboot.
The real MAC, mDNS records received from the HA host and encrypted API passed
a 150-second on-panel RAM trial. HA integration pairing with the new identity,
Builder's Install-button workflow and permanent boot are not yet validated.
The new build's OTA trial must be repeated with per-upload tracing: two
transfers were observed, and an API check timed out during the second one.

The YAML remains editable and portable: GitHub-sourced components, builds in
Home Assistant, configurable names/entities and a per-installation key in local
`secrets.yaml`, never in GitHub. No computer is required. Example address
`192.0.2.1` is fictional and must be replaced.

## Goal

Convert the TPP06 panel into a local device with no Tuya app or cloud dependency, while preserving a recovery path throughout the work.

## Phase 0 — Network access without disassembly

Query the panel's local product-test service in read-only mode to recover its `AUTHKEY` and derive its `root`/ADB password. This route requires neither UART nor NAND desoldering.

- [Network access and AUTHKEY tool](docs/en/00-network-authkey-access.md)
- [Python tool](tools/tpp06_authkey_reader.py)

**Status:** verified on a TPP06; its device-specific password was recovered over Wi-Fi.

## Phase 0b — Community passwords to try

Prepare a small community password list, then try it after connecting UART and before reading the NAND. It is not related to the serial number; a value may work across several panels. If none works, proceed with local NAND recovery.

- [Community password list](docs/en/00-passwords-to-try.md)

**Status:** list documented; one candidate matched the password recovered from this panel.

## Phase 1 — Hardware and NAND

Identify the board and its NAND, then create a verified backup only if Phase 0 does not provide access or hardware analysis is required.

- [Phase 1 guide](docs/en/01-hardware-nand-password.md)
- [NAND-reading log — French](docs/lecture-nand.md)
- [Field report — English](docs/field-report-password-search.md)

**Status:** NAND backup verified and the panel booted successfully after reassembly.

## Phase 2 — UART and system access

Open a serial console, record the boot process, then access the system with the recovered and authorised credentials.

- [Phase 2 guide](docs/en/02-uart-system-access.md)
- [Detailed UART pinout — French](docs/uart.md)

**Status:** pinout identified; terminal connection remains to be made.

## Phase 3 — Remove Tuya and provide ESPHome access

Keep the Anyka processor and modify its software to remove Tuya, replace its cloud dependencies with a local service, and make the panel accessible through ESPHome.

- [Phase 3 guide: remove Tuya and ESPHome](docs/en/03-remove-tuya-esphome.md)

**Status:** to be completed after UART access and an inventory of the existing software.

## Phase 4 — ADB over Wi-Fi without UART

Install a persistent overlay through the local TCP `8090` production service,
then connect to ADB on port `5555` with the Phase 0 root credentials.

- [Installation, security, and rollback guide](docs/en/04-adb-over-wifi-without-uart.md)
- [Payload uploader](tools/tpp06_ota_uploader.py)

**Status:** validated on one TPP06/AK3761E running kernel `4.4.192V2.4` and
released as experimental. The payload replaces `/data/app` and
`/data/customize`; do not use it on an unknown revision.

## Phase 5 — Local openHASP interface

Build and run openHASP directly on the panel's Anyka Linux system, providing a
local 320×480 interface that can later exchange controls and state with Home
Assistant over MQTT.

- [Phase 5 guide: local openHASP port](docs/en/05-openhasp-local.md)
- [Patch for the upstream openHASP repository](openhasp/openhasp-tpp06.patch)

**Status:** the ARMv5/uClibc binary starts on the real panel; framebuffer,
BGR565 conversion, portrait orientation and Goodix detection are validated.
Boot-time installation and complete physical touch testing remain pending.

## Phase 6 — Native ESPHome + LVGL

Build ESPHome's `host` platform directly for the ARMv5 Anyka and use LVGL with
native Linux components for `/dev/fb0` and `/dev/input/event1`.

- [Phase 6 guide: native ESPHome + LVGL](docs/en/06-native-esphome-lvgl.md)
- [Portable Device Builder YAML](esphome/tpp06-device-builder.yaml)
- [Patch for the upstream ESPHome repository](esphome-lvgl/esphome-tpp06-lvgl.patch)

**Status:** compilation and temporary framebuffer/touch operation are
validated. Multiboot supervisor V1 passes offline automatic-fallback tests;
permanent installation remains behind an explicit experimental option until
hardware power-cycle validation is complete.

## Phase 7 — Reversible Tuya Cutter installer

Automate device-owned credential recovery, ADB access, verified backups, and
temporary or permanent openHASP/ESPHome-LVGL selection.

- [Phase 7 guide: TPP06 Tuya Cutter](docs/en/07-tuya-cutter.md)
- [Python installer](tools/tpp06_tuya_cutter.py)

**Status:** CLI and restore protections tested offline; complete ADB validation
is scheduled after the panel's next reboot.

## References

- [Hardware to identify — French](docs/materiel.md)
- [NAND and backup — French](docs/nand.md)
- [Board and reassembly — French](docs/remontage.md)

## Community source

Some of the hardware pointers, password list, and NAND-reading approach came from reports in the Home Assistant discussion: [Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6). Network `AUTHKEY` extraction and password derivation were discovered by [t0m1o1](https://github.com/t0m1o1), author of TPPwned. The repository procedures are adapted and verified on our own panel; no device-specific dump, hash, key, or credential is published.
