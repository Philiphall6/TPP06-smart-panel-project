from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from tpp06_tuya_cutter import (  # noqa: E402
    CutterError,
    PanelSession,
    TuyaCutter,
    build_parser,
    derive_root_password,
    validate_backup_archive,
)


class PasswordTests(unittest.TestCase):
    def test_derives_last_eight_md5_characters(self) -> None:
        authkey = "example-device-authkey"
        expected = hashlib.md5(authkey.encode()).hexdigest()[-8:]
        self.assertEqual(derive_root_password({"authkey": authkey}), expected)

    def test_accepts_auzkey_field(self) -> None:
        self.assertEqual(
            derive_root_password({"auzkey": "abc"}),
            hashlib.md5(b"abc").hexdigest()[-8:],
        )

    def test_missing_key_is_rejected(self) -> None:
        with self.assertRaises(CutterError):
            derive_root_password({})


class ArchiveTests(unittest.TestCase):
    def _archive(self, member: tarfile.TarInfo, content: bytes = b"x") -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "backup.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            if member.isfile():
                member.size = len(content)
                archive.addfile(member, BytesIO(content))
            else:
                archive.addfile(member)
        return path

    def test_valid_data_overlay_is_accepted(self) -> None:
        validate_backup_archive(self._archive(tarfile.TarInfo("data/etc/init.d/S99tuya-app")))

    def test_path_traversal_is_rejected(self) -> None:
        with self.assertRaises(CutterError):
            validate_backup_archive(self._archive(tarfile.TarInfo("data/app/../../etc/shadow")))

    def test_unrelated_path_is_rejected(self) -> None:
        with self.assertRaises(CutterError):
            validate_backup_archive(self._archive(tarfile.TarInfo("etc/passwd")))

    def test_symbolic_link_is_rejected(self) -> None:
        member = tarfile.TarInfo("data/app/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc/shadow"
        with self.assertRaises(CutterError):
            validate_backup_archive(self._archive(member))


class LauncherTests(unittest.TestCase):
    def test_launcher_keeps_stock_tuya_fallback(self) -> None:
        launcher = TuyaCutter._launcher_script().decode()
        self.assertIn("S99tuya-app.stock", launcher)
        self.assertIn("openhasp", launcher)
        self.assertIn("esphome", launcher)
        self.assertIn("ESPHOME_PREFDIR", launcher)
        self.assertNotIn("rm -rf /tuya", launcher)
        self.assertGreaterEqual(launcher.count('"$BASE/S99tuya-app.stock" start'), 3)

    def test_cli_parses_native_esphome_test(self) -> None:
        args = build_parser().parse_args(
            ["192.0.2.1", "test", "esphome", "--binary", "program"]
        )
        self.assertEqual(args.command, "test")
        self.assertEqual(args.engine, "esphome")

    def test_permanent_esphome_install_is_blocked(self) -> None:
        cutter = TuyaCutter("192.0.2.1", Path("backups"))
        with self.assertRaisesRegex(CutterError, "Installation permanente ESPHome"):
            cutter.install("esphome", Path("program"), None, None, True)

    def test_permanent_esphome_switch_is_blocked(self) -> None:
        cutter = TuyaCutter("192.0.2.1", Path("backups"))
        with self.assertRaisesRegex(CutterError, "Mode de démarrage ESPHome"):
            cutter.switch_mode("esphome", True)


class AdbShellTests(unittest.TestCase):
    def test_connect_and_root_marker_protocol(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        fake_adb = Path(directory.name) / "adb"
        fake_adb.write_text(
            """#!/usr/bin/env python3
import re
import sys

if sys.argv[1:2] == ["connect"]:
    print("connected")
elif sys.argv[1:] == ["devices", "-l"]:
    print("List of devices attached")
    print("192.0.2.10:5555      device product:test")
elif sys.argv[-1:] == ["shell"]:
    print("Tuya login: ", end="", flush=True)
    assert sys.stdin.readline().strip() == "root"
    print("Password: ", end="", flush=True)
    assert sys.stdin.readline().strip() == "masked"
    print("[root@Tuya ~]$ ", end="", flush=True)
    data = ""
    while "tpp06_rc=$?" not in data or "exit" not in data:
        data += sys.stdin.readline()
    marker = re.search(r"echo (__TPP06_CUTTER_[0-9a-f]+__)\\$tpp06_rc", data)
    print("command output")
    print(marker.group(1) + "0", flush=True)
else:
    raise SystemExit(1)
""",
            encoding="utf-8",
        )
        fake_adb.chmod(0o755)
        session = PanelSession("192.0.2.10", "masked", adb=str(fake_adb))
        session.connect()
        result = session.run_root("echo test")
        self.assertEqual(result.returncode, 0)
        self.assertIn("command output", result.stdout)

    def test_md5_fallback_checksum(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        payload = Path(directory.name) / "payload"
        payload.write_bytes(b"TPP06")
        remote = ("md5", hashlib.md5(b"TPP06").hexdigest())
        self.assertTrue(PanelSession._matches_local_checksum(payload, remote))


if __name__ == "__main__":
    unittest.main()
