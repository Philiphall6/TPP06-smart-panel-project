# Phase 3 — Remove Tuya and migrate to ESPHome

## Purpose

Remove dependence on the Tuya app and cloud to achieve durable local control.

## Hardware constraint

The board uses an Anyka `AK3761EE128` processor. ESPHome lists its supported microcontrollers, but not the Anyka family. ESPHome should therefore not be flashed directly onto the Anyka processor.

Reference: [ESPHome supported microcontrollers](https://esphome.io/components/).

## Two paths to evaluate

### A. Replace the controller with an ESP32 running ESPHome

This is the most direct route to removing Tuya. It requires:

1. Mapping buttons, LEDs, display, power, and board outputs.
2. Defining electrical levels and any required isolation.
3. Testing inputs, display, and LEDs on a bench first.
4. Building a minimal ESPHome configuration, then adding functions one at a time.
5. Validating local Home Assistant control before permanently retiring the Tuya logic.

### B. Keep the Anyka processor with local software

After UART access, assess whether the existing Linux system can run a local service. This may avoid a hardware replacement, but it is not a native ESPHome installation and requires analysis of the system, available memory, and build toolchain.

## Success criteria

- The panel runs without a Tuya account or cloud access.
- Essential controls remain available locally.
- Home Assistant controls the panel over the local network.
- The I/O map, final wiring, and configuration are documented.
- The NAND backup remains outside GitHub.

## Phase outcome

A validated local architecture: either ESPHome on a replacement controller or a local solution adapted to the Anyka system.
