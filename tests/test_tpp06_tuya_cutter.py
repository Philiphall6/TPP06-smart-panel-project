from __future__ import annotations

import hashlib
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import Mock


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from tpp06_tuya_cutter import (  # noqa: E402
    CutterError,
    PanelSession,
    TuyaCutter,
    build_parser,
    derive_root_password,
    persistent_install_fits,
    ota_install_fits,
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


class StorageTests(unittest.TestCase):
    def test_ota_never_counts_the_running_binary_as_free_space(self) -> None:
        mib = 1024 * 1024
        self.assertFalse(ota_install_fits(8 * mib, 20 * mib))
        self.assertFalse(ota_install_fits(8 * mib, 7 * mib))
        self.assertTrue(ota_install_fits(9 * mib, 7 * mib))
        self.assertFalse(ota_install_fits(9 * mib, 0))
        self.assertFalse(ota_install_fits(-1, 1))
        self.assertFalse(ota_install_fits(9 * mib, 1, -1))

    def _ota_check(self, available_kib=10240, running="stopped", target=None, data_root="/data"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        binary = Path(temporary.name) / "program"
        binary.write_bytes(b"example program")
        cutter = TuyaCutter("192.0.2.1", Path(temporary.name))
        session = Mock()
        target = target or "/data/tpp06-cutter/esphome/esphome"
        session.run_root.return_value.stdout = (
            f"CHECK_DATA={data_root}\nCHECK_TARGET={target}\n"
            f"CHECK_FREE_KIB={available_kib}\nCHECK_RUNNING={running}\n"
        )
        cutter.connected_session = Mock(return_value=session)
        return cutter, session, binary

    def test_ota_space_check_is_read_only_and_handles_stopped_engine(self) -> None:
        cutter, session, binary = self._ota_check()
        cutter.ota_space_check(binary)
        session.upload.assert_not_called()
        command = session.run_root.call_args.args[0]
        for forbidden in ("rm ", "mv ", "kill ", "reboot", " > "):
            self.assertNotIn(forbidden, command)
        subprocess.run(["sh", "-n"], input=command, text=True, check=True)

    def test_ota_check_rejects_insufficient_or_unknown_space(self) -> None:
        for available in (1, "", "unknown"):
            with self.subTest(available=available):
                cutter, _, binary = self._ota_check(available_kib=available)
                with self.assertRaises(CutterError):
                    cutter.ota_space_check(binary)

    def test_ota_check_rejects_non_flash_deleted_or_multiple_engines(self) -> None:
        for running in ("/tmp/trial/esphome", "/data/tpp06-cutter/esphome/esphome (deleted)",
                        "stopped\nCHECK_RUNNING=/tmp/other", ""):
            with self.subTest(running=running):
                cutter, _, binary = self._ota_check(running=running)
                with self.assertRaises(CutterError):
                    cutter.ota_space_check(binary)

    def test_ota_check_rejects_redirected_flash_target(self) -> None:
        cutter, _, binary = self._ota_check(target="/tmp/elsewhere")
        with self.assertRaises(CutterError):
            cutter.ota_space_check(binary)

    def test_ota_check_accepts_stock_data_mount_alias(self) -> None:
        target = "/tuya/data/tpp06-cutter/esphome/esphome"
        cutter, _, binary = self._ota_check(
            target=target, data_root="/tuya/data", running=target
        )
        cutter.ota_space_check(binary)

    def test_ota_cli_requires_a_binary(self) -> None:
        args = build_parser().parse_args(
            ["192.0.2.1", "ota-space-check", "--binary", "program"]
        )
        self.assertEqual(args.command, "ota-space-check")
        self.assertEqual(args.binary, Path("program"))

    def test_trial_reuses_identical_flash_binary_without_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "program"
            binary.write_bytes(b"test program")
            cutter = TuyaCutter("192.0.2.1", Path(directory))
            session = Mock()
            session._matches_local_checksum.return_value = True
            cutter.connected_session = Mock(return_value=session)
            root = cutter._stage_engine("esphome", binary, False, None, None)
            self.assertEqual(root, "/tmp/tpp06-cutter/esphome")
            session.upload.assert_not_called()
            self.assertIn("ln -sf /data/tpp06-cutter/esphome/esphome", session.run_root.call_args.args[0])

    def test_replaced_engine_space_is_reclaimable(self) -> None:
        mib = 1024 * 1024
        self.assertTrue(persistent_install_fits(8 * mib, 20 * mib, 20 * mib))

    def test_safety_reserve_blocks_tight_install(self) -> None:
        mib = 1024 * 1024
        self.assertFalse(persistent_install_fits(1 * mib, 7 * mib, 7 * mib))


class LauncherTests(unittest.TestCase):
    def test_trial_auto_stop_is_in_complete_shell_script(self) -> None:
        cutter = TuyaCutter("192.0.2.1", Path("backups"))
        cutter.stop_test = Mock()
        cutter._stage_engine = Mock(return_value="/tmp/tpp06-cutter/esphome")
        session = Mock()
        cutter.connected_session = Mock(return_value=session)
        cutter.start_test("esphome", Path("program"), None, None)
        command = session.run_root.call_args.args[0]
        self.assertLess(max(map(len, command.splitlines())), 512)
        self.assertIn("sleep 60", command)
        self.assertIn("AUTO_STOP after 60s", command)
        subprocess.run(["sh", "-n"], input=command, text=True, check=True)

    def test_keep_stock_install_commits_stock_mode_with_short_lines(self) -> None:
        cutter = TuyaCutter("192.0.2.1", Path("backups"))
        cutter.backup = Mock(return_value=Path("verified-backup.tar.gz"))
        cutter._stage_engine = Mock(return_value="/data/tpp06-cutter/esphome")
        session = Mock()
        cutter.connected_session = Mock(return_value=session)
        cutter.install("esphome", Path("program"), None, None, True,
                       experimental_multiboot=True, keep_stock=True)
        command = session.run_root.call_args.args[0]
        self.assertIn("echo tuya > /data/tpp06-cutter/mode.tmp", command)
        self.assertNotIn("echo esphome >", command)
        self.assertLess(max(map(len, command.splitlines())), 512)
        self.assertIn("sh -n /tmp/S99tuya-app.tpp06-cutter", command)
        self.assertLess(command.index("sh -n"), command.index("mv /data/etc/init.d/.S99"))
        subprocess.run(["sh", "-n"], input=command, text=True, check=True)

    def test_launcher_keeps_stock_tuya_fallback(self) -> None:
        launcher = TuyaCutter._launcher_script().decode()
        self.assertIn("TPP06_MULTIBOOT_V1", launcher)
        self.assertIn("S99tuya-app.stock", launcher)
        self.assertIn("openhasp", launcher)
        self.assertIn("esphome", launcher)
        self.assertIn("ESPHOME_PREFDIR", launcher)
        self.assertNotIn("rm -rf /tuya", launcher)
        self.assertIn("failure_count", launcher)
        self.assertIn("boot_pending", launcher)
        self.assertIn("fallback_stock", launcher)
        self.assertIn("wpa_supplicant", launcher)
        self.assertIn("udhcpc", launcher)
        self.assertIn("network_profile_valid", launcher)
        self.assertIn("tuya_factory", launcher)

    def test_cli_parses_native_esphome_test(self) -> None:
        args = build_parser().parse_args(
            ["192.0.2.1", "test", "esphome", "--binary", "program"]
        )
        self.assertEqual(args.command, "test")
        self.assertEqual(args.engine, "esphome")

    def test_cli_has_read_only_reboot_gate(self) -> None:
        args = build_parser().parse_args(["192.0.2.1", "reboot-check"])
        self.assertEqual(args.command, "reboot-check")
        source = Path(TOOLS / "tpp06_tuya_cutter.py").read_text(encoding="utf-8")
        method = source.split("def reboot_check", 1)[1].split("def enable_adb", 1)[0]
        self.assertNotIn('run_root("reboot', method)

    def test_permanent_esphome_install_is_blocked(self) -> None:
        cutter = TuyaCutter("192.0.2.1", Path("backups"))
        with self.assertRaisesRegex(CutterError, "expérimentale"):
            cutter.install("esphome", Path("program"), None, None, True)

    def test_cli_accepts_explicit_multiboot_guard(self) -> None:
        args = build_parser().parse_args(
            [
                "192.0.2.1",
                "install",
                "esphome",
                "--binary",
                "program",
                "--experimental-multiboot",
            ]
        )
        self.assertTrue(args.experimental_multiboot)

    def test_esphome_temporary_test_keeps_tuya_and_has_watchdog(self) -> None:
        source = Path(TOOLS / "tpp06_tuya_cutter.py").read_text(encoding="utf-8")
        self.assertIn("Keep the stock Tuya process alive", source)
        self.assertIn("ESPHOME_TEST_SECONDS = 60", source)
        self.assertIn("esphome-test.log", source)
        self.assertIn("watchdog.pid", source)


class MultibootScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name) / "state"
        self.base.mkdir()
        self.stock_marker = Path(self.directory.name) / "stock-started"
        self.stock = Path(self.directory.name) / "stock.sh"
        self.stock.write_text(
            f"#!/bin/sh\necho stock >> {self.stock_marker}\n", encoding="utf-8"
        )
        self.stock.chmod(0o755)
        self.script = Path(__file__).resolve().parents[1] / "device" / "tpp06-multiboot.sh"
        self.environment = {
            **os.environ,
            "TPP06_BASE": str(self.base),
            "TPP06_STOCK_LAUNCHER": str(self.stock),
            "TPP06_GRACE_SECONDS": "2",
            "TPP06_FAIL_LIMIT": "2",
            "TPP06_STOCK_READY_FILE": str(self.stock_marker),
            "TPP06_ESPHOME_HEALTH_PORT": "0",
        }

    def _engine(self, body: str) -> None:
        directory = self.base / "esphome"
        directory.mkdir(exist_ok=True)
        binary = directory / "esphome"
        binary.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        binary.chmod(0o755)
        (self.base / "mode").write_text("esphome\n", encoding="utf-8")

    def _network_profile(self, mode: str) -> None:
        network = self.base / "network"
        network.mkdir(exist_ok=True)
        (network / "wpa_supplicant.conf").write_text(
            'ctrl_interface=/var/run/wpa_supplicant\nnetwork={\n'
            '  ssid="masked-test"\n  psk="masked-test"\n}\n',
            encoding="utf-8",
        )
        (self.base / "network_mode").write_text(mode + "\n", encoding="utf-8")

    def test_early_exit_falls_back_without_reboot(self) -> None:
        self._engine("exit 7")
        subprocess.run(
            ["sh", str(self.script), "supervise"],
            env=self.environment,
            check=True,
            timeout=10,
        )
        self.assertEqual((self.base / "active_mode").read_text().strip(), "tuya-fallback")
        self.assertEqual((self.base / "failure_count").read_text().strip(), "1")
        self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
        self.assertTrue(self.stock_marker.exists())

    def test_two_unclean_boots_lock_to_stock(self) -> None:
        self._engine("sleep 30")
        (self.base / "failure_count").write_text("1\n", encoding="utf-8")
        (self.base / "boot_pending").write_text("previous\n", encoding="utf-8")
        subprocess.run(
            ["sh", str(self.script), "supervise"],
            env=self.environment,
            check=True,
            timeout=10,
        )
        self.assertEqual((self.base / "failure_count").read_text().strip(), "2")
        self.assertEqual((self.base / "active_mode").read_text().strip(), "tuya-fallback")
        self.assertFalse((self.base / "boot_pending").exists())

    def test_custom_selection_is_consumed_before_grace_period(self) -> None:
        self._engine("sleep 30")
        process = subprocess.Popen(
            ["sh", str(self.script), "supervise"], env=self.environment
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                active = self.base / "active_mode"
                if (active.exists() and active.read_text().strip() == "esphome-starting"
                        and (self.base / "engine.pid").exists()):
                    break
                time.sleep(0.05)
            else:
                self.fail("custom boot never entered its guarded grace period")
            self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
            self.assertTrue((self.base / "boot_pending").exists())
        finally:
            if (self.base / "engine.pid").exists():
                os.kill(int((self.base / "engine.pid").read_text()), 15)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2)

    def test_failed_mode_write_never_launches_custom_engine(self) -> None:
        marker = self.base / "unexpected-engine"
        self._engine(f"touch {marker}")
        # A directory at the temporary state path makes the write fail even
        # when the test suite is run with root permissions.
        (self.base / "mode.tmp").mkdir()
        result = subprocess.run(["sh", str(self.script), "supervise"],
                                env=self.environment, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertTrue(self.stock_marker.exists())

    def test_surviving_grace_period_is_marked_healthy(self) -> None:
        self._engine("sleep 30")
        self._network_profile("learning")
        process = subprocess.Popen(
            ["sh", str(self.script), "supervise"], env=self.environment
        )
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                active = self.base / "active_mode"
                if active.exists() and active.read_text().strip() == "esphome-healthy":
                    break
                time.sleep(0.1)
            else:
                self.fail("custom engine was not marked healthy")
            self.assertEqual((self.base / "failure_count").read_text().strip(), "0")
            self.assertFalse((self.base / "boot_pending").exists())
            self.assertEqual((self.base / "network_mode").read_text().strip(), "learning")
            self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
        finally:
            if (self.base / "engine.pid").exists():
                os.kill(int((self.base / "engine.pid").read_text()), 15)
            process.wait(timeout=5)

    def test_explicit_isolated_mode_uses_independent_wifi_without_stock(self) -> None:
        self._engine("sleep 30")
        self._network_profile("isolated")
        fake_bin = Path(self.directory.name) / "bin"
        fake_bin.mkdir()
        wifi_ready = Path(self.directory.name) / "wifi-ready"
        rescue_marker = Path(self.directory.name) / "rescue-started"

        (fake_bin / "ifconfig").write_text(
            "#!/bin/sh\n"
            f"[ -f {wifi_ready} ] && echo 'inet addr:192.0.2.2'\n",
            encoding="utf-8",
        )
        (fake_bin / "wpa_supplicant").write_text(
            f"#!/bin/sh\ntouch {wifi_ready}\n", encoding="utf-8"
        )
        (fake_bin / "udhcpc").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        rescue = Path(self.directory.name) / "tuya_factory"
        rescue.write_text(
            f"#!/bin/sh\necho rescue > {rescue_marker}\nsleep 30\n", encoding="utf-8"
        )
        for executable in (*fake_bin.iterdir(), rescue):
            executable.chmod(0o755)

        environment = {
            **self.environment,
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "TPP06_RESCUE_BINARY": str(rescue),
        }
        process = subprocess.Popen(["sh", str(self.script), "supervise"], env=environment)
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                active = self.base / "active_mode"
                if active.exists() and active.read_text().strip() == "esphome-healthy":
                    break
                time.sleep(0.1)
            else:
                self.fail("isolated ESPHome boot was not marked healthy")
            self.assertTrue(wifi_ready.exists())
            self.assertTrue(rescue_marker.exists())
            self.assertFalse(self.stock_marker.exists())
        finally:
            for pid_file in (self.base / "engine.pid", self.base / "rescue.pid"):
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), 15)
                    except ProcessLookupError:
                        pass
            process.wait(timeout=5)

    def test_bounded_session_returns_to_stock_without_failure(self) -> None:
        self._engine("exec sleep 30")
        self._network_profile("learning")
        result = subprocess.run(
            ["sh", str(self.script), "supervise"],
            env={**self.environment, "TPP06_SESSION_SECONDS": "4"},
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
        self.assertEqual((self.base / "network_mode").read_text().strip(), "learning")
        self.assertEqual((self.base / "active_mode").read_text().strip(), "tuya-fallback")
        self.assertEqual((self.base / "failure_count").read_text().strip(), "0")
        self.assertFalse((self.base / "engine.pid").exists())
        self.assertIn("session-complete", (self.base / "diagnostics/multiboot.log").read_text())

    def test_failure_after_health_check_keeps_stock_selected(self) -> None:
        self._engine("sleep 4; exit 9")
        self._network_profile("learning")
        subprocess.run(
            ["sh", str(self.script), "supervise"],
            env=self.environment, check=True, timeout=12,
        )
        log = (self.base / "diagnostics/multiboot.log").read_text()
        self.assertIn("custom engine healthy", log)
        self.assertIn("engine-exit-9", log)
        self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
        self.assertEqual((self.base / "network_mode").read_text().strip(), "learning")
        self.assertEqual((self.base / "failure_count").read_text().strip(), "1")


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
    assert data.index("unalias mv cp rm") < data.index("echo test")
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

    def test_root_shell_is_allowed_to_exit_cleanly(self) -> None:
        source = Path(TOOLS / "tpp06_tuya_cutter.py").read_text(encoding="utf-8")
        self.assertIn("process.wait(timeout=2)", source)
        self.assertIn("process.stdin.close()", source)

    def test_md5_fallback_checksum(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        payload = Path(directory.name) / "payload"
        payload.write_bytes(b"TPP06")
        remote = ("md5", hashlib.md5(b"TPP06").hexdigest())
        self.assertTrue(PanelSession._matches_local_checksum(payload, remote))


if __name__ == "__main__":
    unittest.main()
