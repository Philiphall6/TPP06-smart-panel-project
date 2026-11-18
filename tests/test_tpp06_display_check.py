import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/tpp06_display_check.sh"


class DisplayCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "proc/self").mkdir(parents=True)
        (self.root / "proc/self/stat").touch()

    def process(self, pid, name, devices=(), watchdog=False):
        root = self.root / f"proc/{pid}"
        (root / "fd").mkdir(parents=True)
        (root / "comm").write_text(name + "\n")
        for index, device in enumerate(devices):
            (root / f"fd/{index}").symlink_to(device)
        if watchdog:
            (root / "task/42").mkdir(parents=True)
            (root / "task/42/comm").write_text("gui_watchdog\n")

    def check(self):
        result = subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True,
                                check=True, env={**os.environ,
                                    "TPP06_CHECK_PROC_ROOT": str(self.root / "proc"),
                                    "TPP06_CHECK_SYS_ROOT": str(self.root / "sys")})
        self.assertEqual(result.stderr, "")
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def test_shared_display_and_input(self):
        self.process(10, "voice_control_a", ["/dev/fb0", "/dev/input/event1"], True)
        self.process(20, "esphome", ["/dev/fb0", "/dev/input/event1"])
        report = self.check()
        self.assertEqual(report["CHECK_SHARED_FB0"], "yes")
        self.assertEqual(report["CHECK_GUI_WATCHDOG_OBSERVED"], "1")
        self.assertEqual(report["CHECK_ESPHOME_EVENT1_OPEN"], "1")
        self.assertEqual(report["CHECK_DISPLAY_VERIFIED"], "no")

    def test_stock_only_is_not_display_validation(self):
        self.process(10, "voice_control_ak3760e", ["/dev/fb0"])
        report = self.check()
        self.assertEqual(report["CHECK_SHARED_FB0"], "not_observed")
        self.assertEqual(report["CHECK_ESPHOME_RUNNING"], "0")
        self.assertEqual(report["CHECK_DISPLAY_VERIFIED"], "no")

    def test_incomplete_scan_is_unknown(self):
        (self.root / "proc/30").mkdir()
        self.assertEqual(self.check()["CHECK_SHARED_FB0"], "unknown")

    def test_sysfs_only_emits_numeric_geometry(self):
        fb = self.root / "sys/class/graphics/fb0"
        fb.mkdir(parents=True)
        (fb / "virtual_size").write_text("320,480\n")
        (fb / "stride").write_text("private unexpected content\n")
        report = self.check()
        self.assertEqual(report["CHECK_FB0_virtual_size"], "320,480")
        self.assertEqual(report["CHECK_FB0_stride"], "unknown")
        self.assertNotIn("private", str(report))


if __name__ == "__main__":
    unittest.main()
