# TPP06 — Local project without Tuya

[Version française](README.fr.md)

## Goal

Convert the TPP06 panel into a local device with no Tuya app or cloud dependency, while preserving a recovery path throughout the work.

## Phase 1 — Hardware, NAND, and password

Identify the board and its NAND, create a verified backup, then recover the authorised credentials needed for local maintenance.

- [Phase 1 guide](docs/en/01-hardware-nand-password.md)
- [NAND-reading log — French](docs/lecture-nand.md)
- [Field report — English](docs/field-report-password-search.md)

**Status:** NAND backup verified and the panel booted successfully after reassembly.

## Phase 2 — UART and system access

Open a serial console, record the boot process, then access the system with the recovered and authorised credentials.

- [Phase 2 guide](docs/en/02-uart-system-access.md)
- [Detailed UART pinout — French](docs/uart.md)

**Status:** pinout identified; terminal connection remains to be made.

## Phase 3 — Remove Tuya and migrate to local control

Remove the Tuya dependency and choose a local-control architecture. ESPHome does not run directly on the identified Anyka processor, so this phase starts with an architecture decision.

- [Phase 3 guide: remove Tuya and ESPHome](docs/en/03-remove-tuya-esphome.md)

**Status:** to be designed after the UART and hardware inventory.

## References

- [Hardware to identify — French](docs/materiel.md)
- [NAND and backup — French](docs/nand.md)
- [Board and reassembly — French](docs/remontage.md)
