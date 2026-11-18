from contextlib import redirect_stdout
from io import StringIO
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "device/tpp06-network-profile.sh"
sys.path.insert(0, str(ROOT / "tools"))
from tpp06_tuya_cutter import CutterError, TuyaCutter, build_parser


class ActiveProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / "proc/42"
        self.proc.mkdir(parents=True)
        (self.proc / "comm").write_text("wpa_supplicant\n")
        self.profile = self.root / "live.conf"
        self.profile.write_text('network={\nssid="private-test"\npsk="private-test"\n}\n')
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.pidof("42")
        self.args("-i", "wlan0", "-c", str(self.profile))

    def pidof(self, result):
        executable = self.bin / "pidof"
        executable.write_text(f"#!/bin/sh\nprintf '%s\\n' '{result}'\n")
        executable.chmod(0o700)

    def args(self, *arguments):
        (self.proc / "cmdline").write_bytes(
            b"wpa_supplicant\0" + b"\0".join(a.encode() for a in arguments) + b"\0")

    def run_selector(self):
        return subprocess.run(["sh", "-c", '. "$1"; tpp06_active_wifi_profile',
                               "profile-check", str(HELPER)],
                              env={**os.environ, "PATH": str(self.bin) + ":" + os.environ["PATH"],
                                   "TPP06_WIFI_PROC_ROOT": str(self.root / "proc")},
                              text=True, capture_output=True, timeout=3)

    def test_uses_actual_config_not_etc_template(self):
        before = self.profile.read_bytes()
        result = self.run_selector()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.profile))
        self.assertNotIn("private", result.stdout)
        self.assertEqual(self.profile.read_bytes(), before)

    def test_compact_flags(self):
        self.args("-iwlan0", "-c" + str(self.profile))
        self.assertEqual(self.run_selector().returncode, 0)

    def test_ambiguous_or_missing_process_rejected(self):
        for pids in ("", "42 43", "invalid"):
            with self.subTest(pids=pids):
                self.pidof(pids)
                result = self.run_selector()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_wrong_interface_or_multiple_configs_rejected(self):
        for args in (("-iwlan1", "-c" + str(self.profile)),
                     ("-iwlan0", "-c" + str(self.profile), "-c/etc/other.conf"),
                     ("-iwlan0", "-crelative.conf")):
            with self.subTest(args=args):
                self.args(*args)
                self.assertNotEqual(self.run_selector().returncode, 0)

    def test_multiple_networks_or_missing_key_rejected(self):
        for content in ('network={\nssid="private"\n}\n',
                        self.profile.read_text() * 2):
            self.profile.write_text(content)
            result = self.run_selector()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("private", result.stdout + result.stderr)

    def test_open_network_supported_without_fake_psk(self):
        self.profile.write_text('network={\nssid="private"\nkey_mgmt=NONE\n}\n')
        self.assertEqual(self.run_selector().returncode, 0)

    def test_missing_file_and_wrong_process_identity_rejected(self):
        original = self.profile.read_bytes()
        self.profile.unlink()
        self.assertNotEqual(self.run_selector().returncode, 0)
        self.profile.write_bytes(original)
        (self.proc / "comm").write_text("other\n")
        self.assertNotEqual(self.run_selector().returncode, 0)

    def compare(self, second, path=None):
        return subprocess.run(["sh", "-c", '. "$1"; tpp06_profiles_equal "$2" "$3"',
                               "profile-check", str(HELPER), str(self.profile), str(second)],
                              executable=shutil.which("sh"),
                              env={**os.environ, "PATH": path if path is not None else os.environ["PATH"]},
                              text=True, capture_output=True, timeout=3)

    def test_private_comparison_equal_different_missing(self):
        second = self.root / "other.conf"
        self.assertEqual(self.compare(second).returncode, 1)
        second.write_bytes(self.profile.read_bytes())
        result = self.compare(second)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        second.write_text("different")
        self.assertEqual(self.compare(second).returncode, 1)

    def test_comparison_without_cmp_uses_md5_and_fails_closed_without_hash(self):
        second = self.root / "other.conf"
        second.write_bytes(self.profile.read_bytes())
        minimal = self.root / "minimal"
        minimal.mkdir()
        self.assertEqual(self.compare(second, str(minimal)).returncode, 2)
        (minimal / "md5sum").symlink_to(shutil.which("md5sum"))
        result = self.compare(second, str(minimal))
        self.assertEqual(result.returncode, 0, result.stderr)
        broken = minimal / "sha256sum"
        broken.write_text("#!/bin/sh\necho invalid\n")
        broken.chmod(0o700)
        self.assertEqual(self.compare(second, str(minimal)).returncode, 2)


class NetworkCheckTests(unittest.TestCase):
    def test_cli_is_read_only_and_output_is_whitelisted(self):
        self.assertEqual(build_parser().parse_args(["192.0.2.1", "network-check"]).command,
                         "network-check")
        cutter = TuyaCutter("192.0.2.1", Path("unused"))
        session = Mock()
        session.run_root.return_value.stdout = (
            "private shell echo\nCHECK_ACTIVE_PROFILE=recognized\n"
            "CHECK_SAVED_PROFILE=different_or_missing\n"
            "CHECK_AUTONOMOUS_WIFI=not_verified\nCHECK_SECRET=private\n")
        cutter.connected_session = Mock(return_value=session)
        output = StringIO()
        with redirect_stdout(output):
            cutter.network_check()
        self.assertNotIn("private", output.getvalue())
        self.assertIn("AUTONOMOUS_WIFI=not_verified", output.getvalue())
        command = session.run_root.call_args.args[0]
        for forbidden in ("kill ", "reboot", "cp ", "mv ", "rm ", " > "):
            self.assertNotIn(forbidden, command)
        self.assertLess(max(map(len, command.splitlines())), 512)
        subprocess.run(["sh", "-n"], input=command, text=True, check=True)
        session.upload.assert_not_called()

    def test_incomplete_diagnostic_fails_closed(self):
        cutter = TuyaCutter("192.0.2.1", Path("unused"))
        session = Mock()
        session.run_root.return_value.stdout = "CHECK_ACTIVE_PROFILE=recognized\n"
        cutter.connected_session = Mock(return_value=session)
        with self.assertRaises(CutterError):
            cutter.network_check()
