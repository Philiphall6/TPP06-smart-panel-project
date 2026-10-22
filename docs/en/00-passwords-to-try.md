# Phase 0 — Passwords to try before reading the NAND

## Purpose

Prepare a small list of passwords shared by the community. They will be tried once the UART console is connected, before desoldering the NAND or using the XGecu.

## Prerequisite: UART console

The list alone does not provide a login: the serial console must be wired and opened first. Follow [Phase 2 — UART and system access](02-uart-system-access.md), then try each candidate in the terminal through authorised access.

## Source of the list

These candidates are **not derived from the serial number** and have no known relationship to it. They are simply several values shared by the community. A given value may work on multiple panels, but this is not guaranteed.

On the panel documented in this repository, the recovered password matched one of the forum candidates. The list therefore remains the simplest path to try once UART is working.

## Candidate list

```text
6b7835db
80a69d0f
de8ba884
33a644d0
314b6d93
5bfd1d91
```

Try this list only on a panel that you are authorised to access, without repeated attempts.

## If no candidate works

Proceed to [Phase 1 — hardware and NAND read](01-hardware-nand-password.md): create a verified backup with the XGecu, then search for panel-specific login information in the local dump. Do not publish a NAND dump, hash, or device-specific credential.

## Practical order

1. Prepare the list from this phase.
2. Connect the UART and open the terminal (Phase 2).
3. Try the candidates.
4. If none provides access, back up and analyse the NAND (Phase 1).

## Source

[Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6), Home Assistant Community.
