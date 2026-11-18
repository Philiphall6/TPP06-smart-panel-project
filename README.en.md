# TPP06 — local ESPHome + LVGL

**[Beginner guide: start here, without dismantling](docs/en/START-HERE.md)**

[Project home](README.md) · [Français](README.fr.md)

## The TPP06 enclosure

<p align="center">
  <img src="media/visuels-produit/01-panneau-blanc.png" alt="TPP06 with white controls" width="300">
  &nbsp;&nbsp;
  <img src="media/visuels-produit/02-panneau-noir.png" alt="TPP06 with black controls" width="300">
</p>

*Reference images of both enclosure variants. Appearance alone does not establish firmware compatibility.*

## Current status — 18 November 2026

**V5 / project `0.1.5` is installed on the reference panel.** Its owner
reported successful wireless installation; direct checks confirm the expected
binary, encrypted API, connected Wi-Fi, healthy supervisor and retained
persistent boot policy. A live framebuffer capture confirms the home page,
icons, date and time. The illustration below contains fictional data.

![Illustrative V5 preview, not a private device screenshot](docs/images/tpp06-mobile-preview.svg)

This is native ESPHome running on the original **Anyka ARMv5 Linux**, not an
ESP32. Build in Home Assistant’s ESPHome Device Builder; no Mint computer or
external compilation server is required. Edit the full YAML to change pages,
labels, colours and Home Assistant entities. Drivers come from GitHub; secrets
stay in each owner’s installation.

> [!WARNING]
> Experimental and hardware-specific, not a universal one-click installer.
> Initial network preparation writes an overlay and can break incompatible
> variants. Keep verified backups and physical recovery available. Software
> restarts were tested; power loss and long-term endurance were not.
> Never open an energised mains panel or expose its ports to the Internet.

## Choose your path

1. **Already running ESPHome:** [update wirelessly](docs/en/START-HERE.md#5-update-a-panel-already-running-esphome).
   Do not reinstall the overlay or boot supervisor for a UI update.
2. **Stock panel:** follow [compatibility, network access, backup and preparation](docs/en/START-HERE.md).
   First permanent standalone activation is still an advanced intervention.
3. **No boot or network:** see [hardware recovery archives](docs/archive/README.md).

The normal path is **network → ADB → backup → HA build → guarded trial → OTA**.
Dismantling, UART and NAND desoldering are no longer normal tutorial steps.
The standard Cutter installation uses one-shot selection and does not
automatically confirm persistent mode. Its fallback is **stock Tuya**, not
automatic rollback to the previous ESPHome binary.

## Documentation

- [V5 features and outstanding validation](docs/en/11-interface-v5.md)
- [Complete editable V5 YAML](esphome/tpp06-lvgl-mobile.yaml)
- [Network AUTHKEY access](docs/en/00-network-authkey-access.md)
- [ADB over Wi-Fi — advanced first preparation](docs/en/04-adb-over-wifi-without-uart.md)
- [Tuya Cutter: backups, checks and recovery](docs/en/07-tuya-cutter.md)
- [Native ESPHome port and historical trials](docs/en/06-native-esphome-lvgl.md)
- [openHASP — a separate experimental path](docs/en/05-openhasp-local.md)
- [Boot logo — optional advanced NAND operation, not ESPHome OTA](docs/en/12-boot-logo.md)

Sleep defaults to **Never**. Physical wake, fallback while asleep, beep and
long-term endurance remain unverified. Beep is explicitly unavailable.

Old ADB releases are **not** V5 firmware. Build your own application: compiled
programs include private keys and entity bindings. Never publish personal
YAML, `secrets.yaml`, firmware, backups, dumps or private screenshots.

## Hardware archives and credit

Historical dismantling, NAND, UART and password-search documents are preserved
in the [archive](docs/archive/README.md), with redirects at their old URLs.

Thanks to [t0m1o1](https://github.com/t0m1o1), author of **TPPwned**, for the
network AUTHKEY extraction and password derivation discovery, and to the
[Home Assistant community](https://community.home-assistant.io/t/integration-in-ha-of-new-mini-3-5-smart-control-panel-tpp06/762516).
Independent community project; not affiliated with MOES, Tuya, Home Assistant,
ESPHome or LVGL.
