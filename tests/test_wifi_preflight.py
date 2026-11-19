"""The preparation check must not activate or reconfigure a panel."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "device/tpp06-wifi-preflight.sh"


class WifiPreflightTests(unittest.TestCase):
    def test_profile_metadata_without_stat_and_without_reading_secret(self):
        functions = CHECK.read_text().split('\nif [ "$#" != 2 ]; then', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "network").mkdir()
            profile = base / "network/wpa_supplicant.conf"
            profile.write_text("never-print-fixture-secret")
            for mode, uid, expected in [("-rw-------", "0", 0),
                                         ("-rw-r--r--", "0", 1),
                                         ("-rw-------", "1000", 1)]:
                result = subprocess.run(["sh"],
                    input=functions + f'\nls() {{ echo "{mode} 1 {uid} 0 99 date path"; }}\nprivate_profile\n',
                    env={**os.environ, "TPP06_BASE": str(base)},
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, expected)
                self.assertNotIn("never-print", result.stdout + result.stderr)

    def test_syntax_and_usage(self):
        subprocess.run(["sh", "-n", str(CHECK)], check=True)
        result = subprocess.run(["sh", str(CHECK)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_missing_panel_is_blocked_and_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "panel"
            result = subprocess.run(
                ["sh", str(CHECK), str(ROOT / "device/tpp06-multiboot.sh"),
                 str(ROOT / "device/tpp06-wifi-edit.sh")],
                env={**os.environ, "TPP06_BASE": str(base),
                     "TPP06_PROC_ROOT": str(Path(directory) / "proc")},
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn("RESULT blocked-no-changes-made", result.stdout)
            self.assertFalse(base.exists())

    def test_success_is_read_only_and_does_not_claim_network_validation(self):
        # Replace check dependencies, not the check's state/reporting logic.
        functions = CHECK.read_text().split('\nif [ "$#" != 2 ]; then', 1)[0]
        checks = CHECK.read_text().split('\ncheck root ', 1)[1]
        checks = '\ncheck root ' + checks
        mocks = '''
value_is() { [ "$1" != local_control_confirmed ]; }
private_profile() { return 0; }
owned_daemon() { return 0; }
wpa_ready() { return 0; }
associated() { return 0; }
no_trial() { return 0; }
no_ota() { return 0; }
id() { echo 0; }
test() { case "$*" in '-x '*) return 0 ;; *) command test "$@" ;; esac; }
'''
        result = subprocess.run(
            ["sh", "-s", "--", str(ROOT / "device/tpp06-multiboot.sh"),
             str(ROOT / "device/tpp06-wifi-edit.sh")],
            input=functions + mocks + checks, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LIMIT offline-box-replacement-not-commissioned", result.stdout)
        self.assertIn("prerequisites-only-no-activation-no-network-change", result.stdout)


if __name__ == "__main__":
    unittest.main()
