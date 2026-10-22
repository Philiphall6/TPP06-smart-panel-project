# Phase 0 — Passwords to try before reading the NAND

## Purpose

First try a small list of passwords shared by the community through authorised local or UART access, before desoldering the NAND or using the XGecu.

## Source of the list

These candidates are **not derived from the serial number** and have no known relationship to it. They are simply several values shared by the community. A given value may work on multiple panels, but this is not guaranteed.

On the panel documented in this repository, the recovered password matched one of the forum candidates. The list therefore remains the simplest path to try first.

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

## Source

[Integration in HA of new mini 3.5 smart control panel TPP06](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516/120?page=6), Home Assistant Community.
