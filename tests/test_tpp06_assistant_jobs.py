"""Offline state-machine tests. No panel, SSH server or firmware is contacted."""
import asyncio
import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tpp06_assistant_jobs as j
from tpp06_tuya_cutter import PanelSession

MAC = "02:00:00:00:00:01"
BOOT = "11111111-1111-1111-1111-111111111111"
NEXT_BOOT = "22222222-2222-2222-2222-222222222222"


class FakeSession:
    host, password, adb = "192.0.2.1", "old-test", "adb"

    def __init__(self):
        self.files = {j.LAUNCHER: b"#!/bin/sh\n# original\nexit 0\n", "/etc/passwd": b"passwd fixture\n", "/etc/shadow": b"shadow fixture\n",
                      "/etc/init.d/rc.local": b"#!/bin/sh\nifconfig wlan0 up\n/etc/init.d/S99tuya-app start\n"}
        self.scripts = []
        self.uploads = []
        self.lock = False
        self.reboot_count = 0

    def connect(self):
        pass

    def run_root(self, command, **kwargs):
        self.scripts.append(command)
        if "mkdir /data/tpp06-assistant.lock" in command:
            if self.lock:
                raise RuntimeError("lock exists")
            self.lock = True
        if command == "rmdir /data/tpp06-assistant.lock":
            self.lock = False
        if "/sbin/reboot" in command:
            self.reboot_count += 1
        for line in command.splitlines():
            if not line.startswith(("cp ", "mv ")):
                continue
            parts = shlex.split(line, comments=True)
            if len(parts) == 3 and parts[0] in ("cp", "mv"):
                src, target = parts[1:]
                if src == "$profile":
                    self.files[target] = b"network={\nssid=\"synthetic\"\nkey_mgmt=NONE\n}\n"
                elif src in self.files:
                    self.files[target] = self.files[src]
        return SimpleNamespace(stdout="ssh-ed25519 YQ== fixture\n" if command.startswith("/data/tpp06-ssh/dropbearmulti dropbearkey -y") else "", returncode=0)

    def upload(self, local, remote):
        self.files[remote] = Path(local).read_bytes()
        self.uploads.append((str(local), remote))

    def download(self, remote, local):
        Path(local).write_bytes(self.files[remote])
        Path(local).chmod(0o600)

    def remote_checksum(self, remote):
        return ("sha256", hashlib.sha256(self.files[remote]).hexdigest()) if remote in self.files else None

    _matches_local_checksum = staticmethod(PanelSession._matches_local_checksum)

    @contextmanager
    def console(self):
        yield self.rescue


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.session = FakeSession()
        self.state = {"MAC": MAC, "BOOT": BOOT, "stockage_libre_mio": 100,
                      "esphome_actif": False, "application_tuya_active": True}
        self.identity = patch.object(j, "identity", side_effect=lambda session: self.state.copy())
        self.identity.start()
        self.addCleanup(self.identity.stop)
        ssh = patch.object(j, "installed_ssh_key", return_value=None)
        ssh.start()
        self.addCleanup(ssh.stop)

    def test_job_private_journal_does_not_save_credentials(self):
        job = j.Job(self.session, self.parent, "test")
        contents = (job.directory / "operation.json").read_text()
        self.assertNotIn(self.session.password, contents)
        self.assertEqual(job.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((job.directory / "operation.json").stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.session.lock)
        job.finish()
        self.assertFalse(self.session.lock)

    def test_existing_device_lock_not_overridden(self):
        self.session.lock = True
        with self.assertRaises(RuntimeError):
            j.Job(self.session, self.parent, "test")
        self.assertTrue(self.session.lock)

    def test_journal_cannot_target_another_panel(self):
        job = j.Job(self.session, self.parent, "test")
        self.state["MAC"] = "02:00:00:00:00:02"
        with self.assertRaises(j.AssistantError):
            j.Job.resume(self.session, job.directory / "operation.json")

    def test_backup_tampering_refuses_restore_before_lock_or_write(self):
        job = j.Job(self.session, self.parent, "esphome")
        file = job.backup("launcher", j.LAUNCHER)
        job.finish("prepared-no-reboot")
        file.write_text("modified")
        calls = len(self.session.scripts)
        with self.assertRaises(j.AssistantError):
            j.restore_operation(self.session, self.parent, job.directory / "operation.json")
        self.assertEqual(len(self.session.scripts), calls)

    def test_interrupted_job_is_not_restored_blindly(self):
        job = j.Job(self.session, self.parent, "esphome")
        job.phase("launcher-commit-intent")
        with self.assertRaises(j.AssistantError):
            j.restore_operation(self.session, self.parent, job.directory / "operation.json")

    def test_preparation_saves_original_before_atomic_mounted_launcher_write(self):
        binary = self.parent / "firmware"
        binary.write_bytes(b"synthetic ARM fixture")
        with patch.object(j, "inspect_firmware", return_value={"sha256": j.sha256_file(binary)}):
            result = j.prepare_esphome(self.session, self.parent, binary)
        journal = Path(result["journal_prive"])
        record = json.loads(journal.read_text())
        self.assertEqual(record["phase"], "prepared-no-reboot")
        self.assertTrue((journal.parent / "launcher.before").is_file())
        self.assertTrue((journal.parent / "wifi.before").is_file())
        self.assertEqual(self.session.reboot_count, 0)
        scripts = "\n".join(self.session.scripts)
        self.assertIn("/etc/init.d/S99tuya-app.assistant-", scripts)
        self.assertNotIn("/data/etc/init.d", scripts)
        self.assertIn("no_stock_fallback", scripts)
        self.assertNotIn("kill ", scripts)
        self.assertEqual(self.session.files[j.LAUNCHER], (j.PROJECT_ROOT / "device/tpp06-multiboot.sh").read_bytes())
        for script in self.session.scripts:
            subprocess.run(["sh", "-n"], input=script, text=True, check=True)

    def test_preparation_refuses_existing_esphome_before_any_write(self):
        self.state["esphome_actif"] = True
        with patch.object(j, "inspect_firmware", return_value={}):
            with self.assertRaises(j.AssistantError):
                j.prepare_esphome(self.session, self.parent, self.parent / "not-used")
        self.assertFalse(self.session.scripts)

    def prepared(self):
        binary = self.parent / "program"
        binary.write_bytes(b"synthetic")
        with patch.object(j, "inspect_firmware", return_value={"sha256": j.sha256_file(binary)}):
            return Path(j.prepare_esphome(self.session, self.parent, binary)["journal_prive"])

    def test_reboot_intent_persisted_before_send_and_not_replayed(self):
        path = self.prepared()
        original = self.session.run_root
        def inspect(command, **kwargs):
            if "/sbin/reboot" in command:
                self.assertEqual(json.loads(path.read_text())["phase"], "reboot-intent")
                raise RuntimeError("lost reply")
            return original(command, **kwargs)
        self.session.run_root = inspect
        with self.assertRaises(RuntimeError):
            j.reboot_prepared(self.session, path)
        with self.assertRaises(j.AssistantError):
            j.reboot_prepared(self.session, path)

    def test_manual_power_cycle_prevents_second_reboot(self):
        path = self.prepared()
        self.state["BOOT"] = NEXT_BOOT
        with self.assertRaises(j.AssistantError):
            j.reboot_prepared(self.session, path)
        self.assertEqual(self.session.reboot_count, 0)

    def test_mutated_program_refuses_reboot(self):
        path = self.prepared()
        self.session.files[j.BASE + "/esphome/esphome"] = b"other"
        with self.assertRaises(j.AssistantError):
            j.reboot_prepared(self.session, path)

    def test_restore_startup_is_atomic_and_keeps_program(self):
        path = self.prepared()
        result = j.restore_operation(self.session, self.parent, path)
        self.assertEqual(self.session.files[j.LAUNCHER], (path.parent / "launcher.before").read_bytes())
        self.assertIn(j.BASE + "/esphome/esphome", self.session.files)
        self.assertEqual(self.session.reboot_count, 0)
        self.assertEqual(result["etat"], "complete")

    def test_password_invalid_inputs_are_rejected_before_job(self):
        for password in ("root", "ninechars", "1234567\n", "é2345678"):
            with self.assertRaises(j.AssistantError):
                j.change_password(self.session, self.parent, password)
        self.assertFalse(self.session.scripts)

    def test_password_failure_restores_using_held_console(self):
        self.session.rescue = Mock()
        self.session.rescue.passwd.side_effect = RuntimeError("private-password")
        with self.assertRaises(j.AssistantError) as raised:
            j.change_password(self.session, self.parent, "Test-123")
        self.assertNotIn("private-password", str(raised.exception))
        self.session.rescue.send.assert_called_with(b"\x03\n")
        command = self.session.rescue.command.call_args.args[0]
        self.assertIn("passwd.before /etc/passwd", command)
        self.assertIn("shadow.before /etc/shadow", command)
        self.assertFalse(self.session.lock)
        journal = next(self.parent.glob("tpp06-operation-*/operation.json"))
        self.assertNotIn("Test-123", journal.read_text())

    def test_password_success_uses_new_connection(self):
        self.session.rescue = Mock()
        with patch.object(j, "AssistantSession") as fresh:
            result = j.change_password(self.session, self.parent, "Test-123")
            fresh.assert_called_once_with(self.session.host, "Test-123", adb="adb")
            fresh.return_value.connect.assert_called_once()
        self.assertEqual(result["etat"], "complete")
        self.assertEqual(self.session.password, "Test-123")

    def test_pinned_tools_refuse_unknown_bytes(self):
        file = self.parent / "dropbearmulti"
        file.write_bytes(b"unknown or time64 incompatible")
        with self.assertRaises(j.AssistantError):
            j.pinned_artifact(self.parent, "dropbearmulti")

    def test_dependency_checked_before_device_mutation(self):
        with patch.object(j, "pinned_artifact", return_value=self.parent / "test"), patch.object(j, "dependency", side_effect=j.AssistantError("missing")):
            with self.assertRaises(j.AssistantError):
                j.install_ssh(self.session, self.parent, self.parent)
        self.assertFalse(self.session.scripts)

    def test_ssh_setup_verifies_auth_before_startup_hook(self):
        tool = self.parent / "fixture-binary"
        tool.write_bytes(b"mocked compatible auxiliary")
        def verify(session, public, **kwargs):
            self.assertNotIn(b"TPP06_ASSISTANT_SSH", self.session.files["/etc/init.d/rc.local"])
            return "password" not in kwargs
        with patch.object(j, "pinned_artifact", return_value=tool), patch.object(j, "dependency"), patch.object(j, "ssh_probe", side_effect=verify):
            result = j.install_ssh(self.session, self.parent, self.parent)
        self.assertIn(b"TPP06_ASSISTANT_SSH", self.session.files["/etc/init.d/rc.local"])
        self.assertEqual(self.session.reboot_count, 0)
        self.assertTrue((Path(result["journal_prive"]).parent / "rc-local.before").exists())

    def test_password_ssh_failure_rolls_back_even_if_adb_passes(self):
        self.session.rescue = Mock()
        with patch.object(j, "installed_ssh_key", return_value="mock public"), patch.object(j, "AssistantSession"), patch.object(j, "ssh_probe", return_value=False):
            with self.assertRaises(j.AssistantError):
                j.change_password(self.session, self.parent, "Test-123")
        self.assertIn("shadow.before", self.session.rescue.command.call_args.args[0])
        self.assertEqual(self.session.password, "old-test")

    def test_verification_does_not_reboot_and_requires_authenticated_api(self):
        path = self.prepared()
        self.state.update(BOOT=NEXT_BOOT, esphome_actif=True, application_tuya_active=False)
        self.session.run_root = Mock(return_value=SimpleNamespace(stdout="ASSIST_PID=123\nASSIST_ACTIVE=esphome-healthy\n"))
        with patch.object(j, "dependency"), patch.object(j, "probe_api", new_callable=AsyncMock) as api:
            result = j.verify_boot(self.session, path, base64.b64encode(bytes(32)).decode(), stable_seconds=0)
        self.assertEqual(result["stabilite_secondes"], 0)
        api.assert_awaited_once()
        self.assertEqual(self.session.reboot_count, 0)

    def test_logo_reconcile_never_replays_flash(self):
        job = j.Job(self.session, self.parent, "logo")
        image = job.directory / "payload-candidate.bin"
        image.write_bytes(b"candidate fixture")
        self.session.files["/dev/mtd3ro"] = image.read_bytes()
        job.phase("logo-write-intent")
        original = self.session.run_root
        def state(command, **kwargs):
            if "cat " + job.remote + "/logo-result" in command:
                return SimpleNamespace(stdout="VERIFIED_CANDIDATE\n")
            return original(command, **kwargs)
        self.session.run_root = state
        j.reconcile_logo(self.session, job.directory / "operation.json")
        self.assertFalse(self.session.lock)
        self.assertNotIn("flash_eraseall", "\n".join(self.session.scripts))


class LogoTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.device = self.root / "mtd3"
        self.original = b"original simulated pixels"
        self.candidate = b"candidate simulated pixels"
        self.device.write_bytes(self.original)
        (self.stage / "logo.before").write_bytes(self.original)
        (self.stage / "candidate.bin").write_bytes(self.candidate)
        self.busybox = self.root / "busybox"
        self.busybox.write_text('#!/bin/sh\necho erase >> "' + str(self.stage / "events") + '"\n: > "$2"\n')
        self.busybox.chmod(0o700)
        tool = self.stage / "nandtool"
        tool.write_text('''#!/bin/sh
case "$1" in
nanddump) cp "$4" "$3" ;;
nandwrite)
  case "$3" in *candidate.bin) [ ! -f "''' + str(self.stage / "fail-write") + '''" ] || exit 9;; esac
  cp "$3" "$2" ;;
*) exit 2;;
esac
''')
        tool.chmod(0o700)
        sysdir = self.root / "geometry"
        sysdir.mkdir()
        for name, value in {"name": "logo", "type": "nand", "size": "524288", "erasesize": "131072", "writesize": "2048", "bad_blocks": "0", "ecc_failures": "0"}.items():
            (sysdir / name).write_text(value + "\n")
        source = (j.PROJECT_ROOT / "device/tpp06-assistant-logo.sh").read_text()
        source = source.replace("@STAGE@", str(self.stage)).replace("@ORIGINAL@", hashlib.md5(self.original).hexdigest()).replace("@CANDIDATE@", hashlib.md5(self.candidate).hexdigest())
        source = source.replace("/sys/class/mtd/mtd3", str(sysdir)).replace("/bin/busybox", str(self.busybox))
        source = source.replace("fedb2a75c046de80ed5413cfb129387c", hashlib.md5(self.busybox.read_bytes()).hexdigest())
        source = source.replace("a64974c6ab29d50735cf9d027358ae3a", hashlib.md5(tool.read_bytes()).hexdigest())
        source = source.replace("/dev/mtd3ro", str(self.device)).replace("/dev/mtd3", str(self.device))
        for index in (0, 1, 4, 5):
            protected = self.root / f"protected{index}"
            protected.write_bytes(b"protected")
            source = source.replace(f"/dev/mtd{index}ro", str(protected))
        launcher = self.root / "launcher"
        launcher.write_bytes(b"protected launcher")
        source = source.replace("/etc/init.d/S99tuya-app", str(launcher))
        source = source.replace("/data/tpp06-cutter", str(self.root / "unused-data"))
        self.assertNotIn("/dev/mtd", source)  # No real device may reach the test shell.
        self.script = self.root / "test.sh"
        self.script.write_text(source)

    def execute(self):
        return subprocess.run(["sh", str(self.script)], capture_output=True, timeout=10)

    def test_success_verified_then_second_attempt_refused(self):
        self.assertEqual(self.execute().returncode, 0)
        self.assertEqual(self.device.read_bytes(), self.candidate)
        self.assertEqual((self.stage / "logo-result").read_text().strip(), "VERIFIED_CANDIDATE")
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertEqual((self.stage / "events").read_text().splitlines(), ["erase"])

    def test_candidate_failure_restores_original_exactly_once(self):
        (self.stage / "fail-write").touch()
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertEqual(self.device.read_bytes(), self.original)
        self.assertEqual((self.stage / "logo-result").read_text().strip(), "RESTORED_ORIGINAL")
        self.assertEqual((self.stage / "events").read_text().splitlines(), ["erase", "erase"])

    def test_bad_block_or_wrong_candidate_never_erases(self):
        (self.root / "geometry/bad_blocks").write_text("1\n")
        self.assertNotEqual(self.execute().returncode, 0)
        self.assertFalse((self.stage / "events").exists())
        self.assertEqual(self.device.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
