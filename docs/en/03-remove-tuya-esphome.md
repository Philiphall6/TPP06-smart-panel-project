# Phase 3 — Remove Tuya and provide local ESPHome access

## Purpose

Keep the TPP06 board and its Anyka processor, while modifying the existing software to remove the Tuya app and cloud dependency. The result must be available locally through ESPHome.

No controller replacement is planned, and ESPHome is not to be flashed directly onto the Anyka processor.

## Prerequisites

- Verified local NAND backup.
- Working UART access.
- Identified authorised account and established system login.
- Boot logs and a service inventory saved without secrets.

## Work plan

1. Identify Tuya services, startup scripts, network interfaces, and the processes that control the display, buttons, and outputs.
2. Map existing local mechanisms: Unix sockets, network ports, commands, configuration files, and hardware buses.
3. Create or adapt a local service that controls the panel without the Tuya cloud.
4. Expose that service to ESPHome through a documented local interface. The protocol will be selected after the inventory: an ESPHome API if feasible on the system, or an ESPHome component/adapter connected to the panel's local interface.
5. Disable Tuya startup and communications only after local control has been completely validated.
6. Verify that buttons, display, and local automations work with no Internet connection.

## Success criteria

- The panel boots and remains functional with no Tuya account or cloud access.
- Local panel controls remain operational.
- ESPHome can read state and control the required functions on the local network.
- The change is reversible through the NAND backup retained outside GitHub.
- Documentation describes modified services, the local interface, and the rollback method without publishing a password or key.

## Phase outcome

Localized TPP06 software with no active Tuya service and a documented ESPHome integration.
