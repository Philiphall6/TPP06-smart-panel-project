# TPP06 — Local project without Tuya

[Version française](README.fr.md)

## Goal

Convert the TPP06 panel into a local device with no Tuya app or cloud dependency, while preserving a recovery path throughout the work.

## Phase 0 — Passwords to try

First test a small community password list before reading the NAND. It is not related to the serial number; a value may work across several panels. If none works, proceed with local NAND recovery.

- [Phase 0 guide](docs/en/00-passwords-to-try.md)

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

## References

- [Hardware to identify — French](docs/materiel.md)
- [NAND and backup — French](docs/nand.md)
- [Board and reassembly — French](docs/remontage.md)

## Community source

Some of the hardware pointers, password list, and NAND-reading approach came from reports in the Home Assistant discussion: [Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6). The repository procedures are adapted and verified on our own panel; no device-specific dump, hash, key, or credential is published.
