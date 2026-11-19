import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capabilities", ROOT / "tools/tpp06_capabilities.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CapabilityTests(unittest.TestCase):
    def test_fake_tree_inventory_and_strict_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ)
            for kind in ("SYS", "PROC", "DEV", "BASE", "MODULES"):
                path = root / kind
                path.mkdir()
                env["TPP06_CAP_" + kind] = str(path)
            (root / "DEV/rtc0").touch()
            (root / "SYS/class/bluetooth/hci0").mkdir(parents=True)
            (root / "BASE/local_control_confirmed").write_text("yes\n")
            (root / "BASE/wifi_editor_enabled").write_text("no\n")
            secret = root / "BASE/network/wpa_supplicant.conf"
            secret.parent.mkdir()
            secret.write_text("SECRET_MUST_NOT_APPEAR")
            result = subprocess.run(["sh", str(ROOT / "device/tpp06-capabilities.sh")],
                                    env=env, text=True, capture_output=True, check=True, timeout=5)
            report = module.parse_inventory(result.stdout)
            self.assertEqual(report["inventory"]["rtc_node"], "present")
            self.assertEqual(report["inventory"]["bluetooth"], "present")
            self.assertEqual(report["inventory"]["audio_node"], "absent")
            self.assertEqual(report["inventory"]["offline"], "confirmed")
            self.assertNotIn("SECRET", str(report))
            for invalid in (result.stdout + "CAP_FORMAT=1\n",
                            result.stdout.replace("CAP_RTC_NODE=present", "CAP_RTC_NODE=SECRET"),
                            result.stdout.replace("CAP_FORMAT=1\n", ""),
                            result.stdout + "CAP_PRIVATE=SECRET\n", "x" * 131073):
                with self.assertRaises(ValueError):
                    module.parse_inventory(invalid)
            self.assertEqual(secret.read_text(), "SECRET_MUST_NOT_APPEAR")

    def test_no_active_operation_in_inventory(self):
        source = (ROOT / "device/tpp06-capabilities.sh").read_text()
        commands = "\n".join(line for line in source.splitlines() if not line.startswith("#"))
        for forbidden in ("insmod ", "modprobe ", "reboot", "kill ", "wpa_cli", "i2cdetect", "hcitool", "dd ",
                          "wpa_supplicant.conf", "cmdline", "nand", "brightness >"):
            self.assertNotIn(forbidden, commands)
