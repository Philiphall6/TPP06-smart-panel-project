# Phase 2 — UART and system access

## Purpose

Open a UART console to document boot and access the system with the recovered credentials, where authorised.

## Hardware

The T48 is not a serial terminal. Use a USB–UART TTL adapter whose logic level matches the board.

| USB–UART adapter | TPP06 board |
| --- | --- |
| GND | GND |
| RX | TX0 |
| TX | RX0, only after confirming the logic level |
| VCC | Leave disconnected |

First measure TX0 at idle relative to GND: use a 1.8 V interface if the line is near 1.8 V, or a 3.3 V interface if it is near 3.3 V. Never connect 5 V.

![Board rear and UART](../../media/uart/carte-verso-uart.jpg)

## Terminal

Open the terminal before powering the panel:

```text
115200 baud, 8 data bits, no parity, 1 stop bit, no flow control
```

Start with GND and adapter RX/board TX0 to read boot output. Once the logic level is confirmed, connect adapter TX to board RX0 to transmit commands.

## System access

- Use only the account and password recovered for this authorised device.
- Save logs without passwords, keys, tokens, or identifiers.
- Record the system version, startup services, network interfaces, and peripherals attached to the processor.

## Phase outcome

A non-sensitive boot log and an interface map required for the local-control solution.
