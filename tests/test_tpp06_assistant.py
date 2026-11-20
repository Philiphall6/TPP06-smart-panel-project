"""Assistant tests use synthetic archives and mocked devices, never real panels."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tpp06_assistant_core as a
import tpp06_assistant as gui
from tpp06_tuya_cutter import PanelSession


def state():
    return ("ASSIST_ARCH=armv5tejl\nASSIST_KERNEL=4.4.192V2.4\nASSIST_DATA=/tuya/data\n"
            "ASSIST_FREE=24000\nASSIST_TOTAL=39424\nASSIST_ESP=yes\nASSIST_STOCK=no\n")


def make_archive(path, name="data/app/example", kind=tarfile.REGTYPE):
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        member.type = kind
        if member.isfile():
            member.size = 5
            archive.addfile(member, io.BytesIO(b"hello"))
        else:
            archive.addfile(member)


class AccessTests(unittest.TestCase):
    def test_host_must_be_one_ipv4_not_a_command(self):
        self.assertEqual(a.validate_host(" 192.0.2.10 "), "192.0.2.10")
        for value in ("", "localhost", "127.0.0.1", "0.0.0.0", "255.255.255.255", "224.1.1.1", "::1", "-oProxyCommand=x", "192.0.2.1;reboot"):
            with self.subTest(value=value), self.assertRaises(a.AssistantError):
                a.validate_host(value)

    def test_ports_are_passive_connections_to_fixed_ports(self):
        connector = Mock(side_effect=OSError("private server message"))
        with patch.object(a.socket, "create_connection", connector), patch.object(a, "AssistantSession") as session:
            report = a.probe_ports("192.0.2.1")
        self.assertEqual([c.args[0][1] for c in connector.call_args_list], [22, 6053, 8082, 8090])
        self.assertNotIn("private server message", json.dumps(report))
        self.assertNotIn("192.0.2.1", json.dumps(report))

    def test_factory_password_returns_only_password_not_raw_config(self):
        with patch.object(a, "read_configuration", return_value={"authkey": "synthetic", "wifi_password": "private"}):
            result = a.factory_password("192.0.2.1")
        self.assertRegex(result, r"^[0-9a-f]{8}$")
        with patch.object(a, "read_configuration", side_effect=RuntimeError("sensitive response")):
            with self.assertRaises(a.AssistantError) as raised:
                a.factory_password("192.0.2.1")
        self.assertNotIn("sensitive", str(raised.exception))

    def test_raw_transport_error_never_reaches_gui(self):
        self.assertNotIn("secret", a.safe_failure(RuntimeError("secret")))
        self.assertEqual(a.safe_failure(a.AssistantError("Contrôle refusé.")), "Contrôle refusé.")

    def test_windows_uses_portable_transport(self):
        with patch.object(a.sys, "platform", "win32"), patch.object(a, "AssistantSession") as session, patch.object(a.shutil, "which", return_value="adb.exe"):
            a.connect_adb("192.0.2.1", "test")
            session.return_value.connect.assert_called_once()

    def test_password_controls_rejected_before_connecting(self):
        with patch.object(a.sys, "platform", "linux"), patch.object(a, "AssistantSession") as session:
            for password in ("", "test\nroot", "test\x00", "test\x7f"):
                with self.assertRaises(a.AssistantError):
                    a.connect_adb("192.0.2.1", password)
            session.assert_not_called()

    def test_diagnostic_has_no_writes_or_false_stock_detection(self):
        session = Mock()
        session.run_root.return_value.stdout = state() + "unrecognized private shell output\n"
        result = a.device_report(session)
        self.assertTrue(result["plateforme_connue"])
        self.assertTrue(result["esphome_actif"])
        self.assertNotIn("private", json.dumps(result))
        command = session.run_root.call_args.args[0]
        for forbidden in ("voice_control_ak3760e", "tuya_monitor.sh", "reboot", "rm ", "kill ", " > "):
            self.assertNotIn(forbidden, command)
        subprocess.run(["sh", "-n"], input=command, text=True, check=True)

    def test_ambiguous_or_missing_diagnostic_rejected(self):
        for output in ("", state() + "ASSIST_ESP=no\n", state().replace("24000", "unknown")):
            session = Mock()
            session.run_root.return_value.stdout = output
            with self.assertRaises(a.AssistantError):
                a.device_report(session)

    def test_unrecognized_architecture_is_not_compatible(self):
        session = Mock()
        session.run_root.return_value.stdout = state().replace("armv5tejl", "aarch64")
        self.assertFalse(a.device_report(session)["plateforme_connue"])

    def test_installation_catalog_has_explicit_operations(self):
        self.assertEqual(len(a.ACTIONS), 8)
        self.assertTrue(all(action.available for action in a.ACTIONS))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sample.tar.gz"

    def test_archive_without_checksum_is_not_claimed_authenticated(self):
        make_archive(self.path)
        result = a.inspect_backup(self.path)
        self.assertFalse(result["fiche_sha256_identique"])
        self.assertEqual(result["entrees"], 1)
        self.assertFalse((self.path.parent / "data").exists())

    def test_sidecar_is_checked_and_not_just_displayed(self):
        make_archive(self.path)
        result = a.inspect_backup(self.path)
        sidecar = self.path.with_suffix(".gz.json")
        sidecar.write_text(json.dumps({"format": 1, "sha256": result["sha256"]}))
        self.assertTrue(a.inspect_backup(self.path)["fiche_sha256_identique"])
        sidecar.write_text(json.dumps({"format": 1, "sha256": "0" * 64}))
        with self.assertRaises(a.AssistantError):
            a.inspect_backup(self.path)

    def test_path_traversal_and_device_files_refused(self):
        for name, kind in (("/etc/shadow", tarfile.REGTYPE), ("data/app/../../etc/shadow", tarfile.REGTYPE),
                           ("data/app/evil", tarfile.SYMTYPE), ("data/app/evil", tarfile.LNKTYPE),
                           ("data/app/fifo", tarfile.FIFOTYPE), ("data/app/device", tarfile.CHRTYPE),
                           ("data/app/evil\\path", tarfile.REGTYPE)):
            with self.subTest(name=name, kind=kind):
                make_archive(self.path, name, kind)
                with self.assertRaises(a.AssistantError):
                    a.inspect_backup(self.path)

    def test_duplicate_and_empty_archive_refused(self):
        with tarfile.open(self.path, "w:gz"):
            pass
        with self.assertRaises(a.AssistantError):
            a.inspect_backup(self.path)
        with tarfile.open(self.path, "w:gz") as archive:
            for _ in range(2):
                archive.addfile(tarfile.TarInfo("data/app/duplicate"))
        with self.assertRaises(a.AssistantError):
            a.inspect_backup(self.path)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.session = Mock(host="192.0.2.1", adb="adb", serial="192.0.2.1:5555")
        self.session.run_root.side_effect = lambda command, **kwargs: SimpleNamespace(stdout=(
            state() if command == a.DIAGNOSTIC else "ASSIST_SIZE=1000\nASSIST_TMP=100000\n" if command == a.BACKUP_SPACE else ""))
        self.session._matches_local_checksum.side_effect = PanelSession._matches_local_checksum
        self.source = Path(self.tmp.name) / "fixture.tar.gz"
        make_archive(self.source)
        digest = a.inspect_backup(self.source)["sha256"]
        self.session.remote_checksum.return_value = ("sha256", digest)

        def pull(*args, **kwargs):
            Path(args[-1]).write_bytes(self.source.read_bytes())
            return SimpleNamespace(returncode=0)
        self.session._adb.side_effect = pull

    def test_backup_uses_adb_only_private_unique_folder_and_verified_checksum(self):
        with patch.object(a.sys, "platform", "linux"):
            first = a.backup_panel(self.session, self.tmp.name)
            second = a.backup_panel(self.session, self.tmp.name)
        self.assertNotEqual(first["dossier_prive"], second["dossier_prive"])
        folder = Path(first["dossier_prive"])
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        self.assertEqual((folder / "sauvegarde.tar.gz").stat().st_mode & 0o777, 0o600)
        self.assertTrue(first["fiche_sha256_identique"])
        self.assertTrue(first["archive_temporaire_supprimee"])
        for call in self.session.run_root.call_args_list:
            script = call.args[0]
            for forbidden in ("nc ", "rm -rf", "reboot", "kill ", "voice_control_ak3760e"):
                self.assertNotIn(forbidden, script)
            subprocess.run(["sh", "-n"], input=script, text=True, check=True)

    def test_existing_repository_destination_is_refused(self):
        with self.assertRaises(a.AssistantError):
            a.backup_panel(self.session, a.PROJECT_ROOT)
        self.session.run_root.assert_not_called()

    def test_insufficient_space_refuses_before_creating_archive(self):
        self.session.run_root.side_effect = [SimpleNamespace(stdout=state()), SimpleNamespace(stdout="ASSIST_SIZE=100000\nASSIST_TMP=100\n")]
        with self.assertRaises(a.AssistantError):
            a.backup_panel(self.session, self.tmp.name)
        self.session._adb.assert_not_called()
        self.assertEqual(self.session.run_root.call_count, 2)

    def test_adb_failure_does_not_use_netcat_or_delete_partial_evidence(self):
        self.session._adb.return_value = SimpleNamespace(returncode=1)
        self.session._adb.side_effect = None
        with self.assertRaises(a.AssistantError):
            a.backup_panel(self.session, self.tmp.name)
        self.session.download.assert_not_called()
        self.assertIn("rmdir /tmp/tpp06-assistant-", self.session.run_root.call_args.args[0])

    def test_failed_cleanup_is_not_reported_as_successful_cleanup(self):
        original = self.session.run_root.side_effect
        def fail_cleanup(command, **kwargs):
            if command.startswith("rm -f"):
                raise RuntimeError("private output")
            return original(command, **kwargs)
        self.session.run_root.side_effect = fail_cleanup
        result = a.backup_panel(self.session, self.tmp.name)
        self.assertFalse(result["archive_temporaire_supprimee"])
        self.assertIn("attention", result)
        self.assertNotIn("private output", json.dumps(result))


class GuiSourceTests(unittest.TestCase):
    def test_import_never_connects_or_launches_tk(self):
        # GUI can be imported without Tk installed, without a display or network.
        self.assertTrue(callable(gui.main))

    def test_no_legacy_installation_called(self):
        source = Path(gui.__file__).read_text()
        for forbidden in ("Commission(", ".restore(", ".install(", ".enable_adb(", "shell=True"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
