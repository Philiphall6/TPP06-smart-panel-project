# Phase 7 — TPP06 Tuya Cutter

`tpp06_tuya_cutter.py` provides a reversible installer around the project's
network access, backup, openHASP, and native ESPHome-LVGL work. Given the panel
IP, it reads the `AUTHKEY` over port `8090`, derives the root password in memory,
connects through ADB, and performs verified transfers.

> **Development version.** Offline logic and archive validation have automated
> tests. End-to-end ADB operations still require validation after the panel's
> next reboot. Do not use permanent mode before successful temporary tests.

Start the interactive assistant with:

```bash
python3 tools/tpp06_tuya_cutter.py 192.168.1.52
```

Main non-interactive commands are:

```bash
# Inspect and back up
python3 tools/tpp06_tuya_cutter.py PANEL_IP status
python3 tools/tpp06_tuya_cutter.py PANEL_IP backup

# Temporary tests
python3 tools/tpp06_tuya_cutter.py PANEL_IP test openhasp \
  --binary openhasp-tpp06 --config config.json --pages pages.jsonl
python3 tools/tpp06_tuya_cutter.py PANEL_IP test esphome --binary program
python3 tools/tpp06_tuya_cutter.py PANEL_IP stop-test

# Reversible boot selection, only after testing
python3 tools/tpp06_tuya_cutter.py PANEL_IP install esphome --binary program
python3 tools/tpp06_tuya_cutter.py PANEL_IP switch tuya

# Recovery
python3 tools/tpp06_tuya_cutter.py PANEL_IP restore BACKUP.tar.gz
python3 tools/tpp06_tuya_cutter.py PANEL_IP uninstall
```

The tool never deletes stock Tuya partitions. A permanent cut-over stores the
new engine under `/data/tpp06-cutter` and overrides only `S99tuya-app` in the
writable overlay. The saved stock launcher remains selectable. Every permanent
install and restore first creates a verified local backup.

Backups are mode `0600`, ignored by Git, and accompanied by SHA-256 metadata.
Restores reject absolute paths, traversal, links, and files outside the allowed
overlay scope. `AUTHKEY`, root password, Wi-Fi credentials, and device keys are
never printed or written by the Cutter.
