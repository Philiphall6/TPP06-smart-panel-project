#!/usr/bin/env python3
"""Read-only, redacted Linux capability inventory; no hardware activation."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PRESENCE = {
    "FRAMEBUFFER", "TOUCH", "KEYS", "BACKLIGHT", "RELAY_1", "RELAY_2", "RELAY_3",
    "LED_1", "LED_2", "LED_3", "MUTE_DESCRIPTION", "PWM", "RTC_NODE", "RTC_MODULE",
    "IR_NODE", "IR_TX_DRIVER", "BLUETOOTH", "AUDIO_NODE", "AUDIO_MODULE", "CONSOLE_UART",
    "BLUETOOTH_UART", "WATCHDOG_NODE", "WIFI_HELPER", "STOCK_LAUNCHER", "IIO_DEVICE", "THERMAL_ZONE",
}
POLICIES = {"PERSISTENT", "OFFLINE", "WIFI_EDITOR", "HEARTBEAT_REQUIRED"}


def parse_inventory(output):
    if len(output) > 131072:
        raise ValueError("Inventory output too large")
    records = {}
    for key, value in re.findall(r"^CAP_([A-Z_0-9]+)=([^\r\n]*)\r?$", output, re.M):
        allowed = {"present", "absent"} if key in PRESENCE else (
            {"confirmed", "not_confirmed"} if key in POLICIES else {"1"} if key == "FORMAT" else set())
        if key in records or value not in allowed:
            raise ValueError("Unknown, duplicate or invalid inventory field")
        records[key] = value
    if set(records) != PRESENCE | POLICIES | {"FORMAT"}:
        raise ValueError("Incomplete inventory")
    return {
        "format": 1,
        "scope": "metadata_only",
        "hardware_validation": "not_performed",
        "inventory": {key.lower(): records[key] for key in sorted(PRESENCE | POLICIES)},
        "limitations": [
            "Presence does not establish hardware function, ownership or board compatibility.",
            "Policy flags do not prove offline cold boot, relay continuity or Wi-Fi rollback.",
            "No audio/IR/Bluetooth/proximity function was activated or tested.",
        ],
    }


def inspect(session):
    script = (ROOT / "device/tpp06-capabilities.sh").read_text()
    result = session.run_root("sh <<'TPP06_CAPABILITIES'\n" + script +
                              "\nTPP06_CAPABILITIES", timeout=30)
    return parse_inventory(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--host", help="Panel address; authenticated maintenance transport required")
    group.add_argument("--from-file", type=Path, help="Parse saved inventory without connecting")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--backup-dir", type=Path, default=Path.cwd() / "tpp06-private-backups")
    args = parser.parse_args()
    try:
        if args.from_file:
            with args.from_file.open() as stream:
                report = parse_inventory(stream.read(131073))
        else:
            from tpp06_tuya_cutter import TuyaCutter
            with redirect_stdout(io.StringIO()):
                session = TuyaCutter(args.host, args.backup_dir, adb=args.adb).connected_session()
            report = inspect(session)
    except Exception as error:
        # Never print transport exception text: it can contain installation details.
        print(json.dumps({"error": type(error).__name__, "inventory": "unavailable"}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
