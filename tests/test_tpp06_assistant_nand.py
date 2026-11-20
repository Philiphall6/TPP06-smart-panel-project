"""Synthetic NAND only: no network, no hardware device, no flash commands."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tpp06_assistant_nand as n
import tpp06_assistant_jobs as j
from tpp06_tuya_cutter import PanelSession

MTD = 'dev:    size   erasesize  name\nmtd0: 00020000 00020000 "boot"\n'
STATE = {"MAC": "02:00:00:00:00:01", "BOOT": "11111111-1111-1111-1111-111111111111"}


class MemoryPanel:
    def __init__(self):
        self.scripts = []
        self.files = {}
        self.pass_count = 0
        self.changed = False
        self.truncated = False
        self.fail_download = False
        self.reads = {"/proc/mtd": MTD, "/proc/cmdline": "synthetic-test",
                      "/proc/mounts": "tmpfs /tmp tmpfs rw 0 0\n/dev/mtdblock0 /data jffs2 rw 0 0\n",
                      "/proc/meminfo": "MemFree: 32768 kB\n"}
        for key, value in {"type": "nand", "size": 131072, "erasesize": 131072, "writesize": 2048,
                           "oobsize": 64, "bad_blocks": 0, "ecc_failures": 0}.items():
            self.reads["/sys/class/mtd/mtd0/" + key] = str(value)

    def run_root(self, command, **kwargs):
        self.scripts.append(command)
        if "nanddump -o" in command:
            self.pass_count += 1
            target = re.search(r"-f (\S+) /dev/mtd[0-9]+ro", command)[1]
            length = int(re.search(r"-l ([0-9]+)", command)[1])
            byte = b"X" if self.changed and self.pass_count == 2 else b"A"
            data = (byte * 2048 + b"B" * 64) * (length // 2048)
            self.files[target] = data[:-1] if self.truncated else data
        return SimpleNamespace(stdout="", returncode=0)

    def upload(self, source, target):
        self.files[target] = Path(source).read_bytes()

    def download(self, source, target):
        if self.fail_download:
            raise RuntimeError("synthetic failure")
        Path(target).write_bytes(self.files[source])

    def remote_checksum(self, path):
        return ("sha256", hashlib.sha256(self.files[path]).hexdigest())

    _matches_local_checksum = staticmethod(PanelSession._matches_local_checksum)


class NandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.tool = self.parent / "fixture-tool"
        self.tool.write_bytes(b"not executable")
        self.panel = MemoryPanel()
        for mock in (patch.object(n, "read_file", side_effect=lambda s, p: s.reads[p]),
                     patch.object(n, "identity", return_value=STATE),
                     patch.object(n, "pinned_artifact", return_value=self.tool)):
            mock.start()
            self.addCleanup(mock.stop)

    def capture(self):
        return n.capture_reference(self.panel, self.parent, self.parent)

    def manifest(self):
        return next(self.parent.glob("tpp06-operation-*/nand-manifest.json"))

    def test_capture_two_passes_data_and_oob_not_certified_snapshot(self):
        result = self.capture()
        record = json.loads(self.manifest().read_text())
        self.assertEqual(self.panel.pass_count, 2)
        self.assertEqual(record["phase"], "captured-two-matching-passes")
        self.assertEqual(record["baseline"], "post-adb-current-state")
        self.assertEqual(record["acquisition"], "live")
        self.assertFalse(record["consistency_validated"])
        self.assertFalse(record["restore_validated"])
        self.assertEqual((self.manifest().parent / "mtd0.data.bin").read_bytes(), b"A" * 131072)
        self.assertEqual((self.manifest().parent / "mtd0.data-oob.bin").stat().st_size, 135168)
        self.assertTrue(result["nettoyage_temporaire"])
        commands = "\n".join(self.panel.scripts)
        for forbidden in ("nandwrite", "flash_erase", "reboot", "mount -o", "kill ", " -b ", "> /dev/"):
            self.assertNotIn(forbidden, commands)
        self.assertIn("/dev/mtd0ro", commands)

    def test_changed_second_pass_retains_first_copy_without_success(self):
        self.panel.changed = True
        with self.assertRaises(j.AssistantError):
            self.capture()
        self.assertEqual(json.loads(self.manifest().read_text())["phase"], "incomplete-not-a-reference")
        self.assertTrue((self.manifest().parent / "mtd0.data.bin").exists())
        self.assertIn("rmdir /tmp/tpp06-nand.lock", self.panel.scripts)

    def test_multiple_partitions_and_bounded_chunks(self):
        self.panel.reads["/proc/mtd"] = MTD.replace("00020000 00020000", "00200000 00020000") + 'mtd1: 00020000 00020000 "data"\n'
        self.panel.reads["/sys/class/mtd/mtd0/size"] = "2097152"
        for key in ("type", *n.FIELDS):
            self.panel.reads["/sys/class/mtd/mtd1/" + key] = self.panel.reads["/sys/class/mtd/mtd0/" + key]
        self.panel.reads["/sys/class/mtd/mtd1/size"] = "131072"
        self.capture()
        self.assertEqual(self.panel.pass_count, 6)
        record = json.loads(self.manifest().read_text())
        self.assertEqual(len(record["files"]), 4)
        self.assertEqual(len(record["chunks"]), 3)
        self.assertEqual(record["chunks"][1]["offset"], 1048576)
        self.assertEqual(n.inspect_reference(self.manifest())["partitions"], 2)

    def test_ecc_error_appearing_during_copy_refused(self):
        original = n.inventory
        count = 0

        def changing(session):
            nonlocal count
            count += 1
            if count > 1:
                self.panel.reads["/sys/class/mtd/mtd0/ecc_failures"] = "1"
            return original(session)

        with patch.object(n, "inventory", side_effect=changing):
            with self.assertRaises(j.AssistantError):
                self.capture()
        self.assertEqual(json.loads(self.manifest().read_text())["phase"], "incomplete-not-a-reference")

    def test_symbolic_link_image_refused(self):
        self.capture()
        image = self.manifest().parent / "mtd0.data.bin"
        original = self.parent / "moved-image.bin"
        image.rename(original)
        image.symlink_to(original)
        with self.assertRaises(j.AssistantError):
            n.inspect_reference(self.manifest())

    def test_framing_ignores_echoed_command(self):
        # Exercise the real reader rather than this class's usual file fake.
        import importlib.util
        spec = importlib.util.spec_from_file_location("nand_reader_fixture", n.__file__)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        class EchoConsole:
            def run_root(self, command):
                tag = re.search(r"NAND_[0-9a-f]+", command)[0]
                return SimpleNamespace(stdout=command + f"\r\n{tag}_BEGIN\r\nfixture\r\n\r\n{tag}_END\r\n# ")
        self.assertEqual(module.read_file(EchoConsole(), "/proc/mtd"), "fixture\n")

    def test_short_read_rejected(self):
        self.panel.truncated = True
        with self.assertRaises(j.AssistantError):
            self.capture()

    def test_transport_failure_never_marks_completed(self):
        self.panel.fail_download = True
        with self.assertRaises(RuntimeError):
            self.capture()
        with self.assertRaises(j.AssistantError):
            n.inspect_reference(self.manifest())

    def test_tampering_rejected(self):
        self.capture()
        (self.manifest().parent / "mtd0.data.bin").write_bytes(b"Z" * 131072)
        with self.assertRaises(j.AssistantError):
            n.inspect_reference(self.manifest())

    def test_missing_partition_rejected(self):
        self.capture()
        record = json.loads(self.manifest().read_text())
        record["files"].pop()
        self.manifest().write_text(json.dumps(record))
        with self.assertRaises(j.AssistantError):
            n.inspect_reference(self.manifest())

    def test_path_traversal_rejected(self):
        self.capture()
        record = json.loads(self.manifest().read_text())
        record["files"][0]["name"] = "../outside.bin"
        self.manifest().write_text(json.dumps(record))
        with self.assertRaises(j.AssistantError):
            n.inspect_reference(self.manifest())

    def test_bad_blocks_and_ecc_refused_before_any_upload(self):
        for field in ("bad_blocks", "ecc_failures"):
            with self.subTest(field=field):
                self.panel.reads["/sys/class/mtd/mtd0/" + field] = "1"
                with self.assertRaises(j.AssistantError):
                    self.capture()
                self.panel.reads["/sys/class/mtd/mtd0/" + field] = "0"
                self.assertFalse(self.panel.files)

    def test_tmp_on_nand_refused(self):
        self.panel.reads["/proc/mounts"] = "/dev/mtdblock0 /tmp jffs2 rw 0 0\n"
        with self.assertRaises(j.AssistantError):
            self.capture()
        self.assertFalse(self.panel.files)

    def test_unknown_geometry_refused(self):
        self.panel.reads["/sys/class/mtd/mtd0/writesize"] = "4096"
        with self.assertRaises(j.AssistantError):
            self.capture()

    def test_no_space_refused(self):
        with patch.object(n.shutil, "disk_usage", return_value=SimpleNamespace(free=1)):
            with self.assertRaises(j.AssistantError):
                self.capture()
        self.assertFalse(self.panel.files)

    def test_boot_changed_refused(self):
        with patch.object(n, "identity", side_effect=[STATE, dict(STATE, BOOT="different")]):
            with self.assertRaises(j.AssistantError):
                self.capture()

    def test_readonly_mounts_not_claimed_as_restore_test(self):
        self.panel.reads["/proc/mounts"] = "tmpfs /tmp tmpfs rw 0 0\n/dev/mtdblock0 /data jffs2 ro 0 0\n"
        self.capture()
        record = json.loads(self.manifest().read_text())
        self.assertEqual(record["acquisition"], "no-writable-persistent-mount-observed")
        self.assertFalse(record["restore_validated"])

    def test_duplicate_mtd_and_bad_geometry_refused(self):
        for text in (MTD + MTD.splitlines()[1] + "\n", MTD.replace("00020000 00020000", "00000001 00020000")):
            with self.assertRaises(j.AssistantError):
                n.parse_mtd(text)


class AdbPolicyTests(unittest.TestCase):
    def test_no_original_dump_requires_explicit_acceptance(self):
        with patch.object(j, "pinned_artifact", return_value=Path("unused")):
            with self.assertRaises(j.AssistantError):
                j.activate_adb("192.0.2.1", "unused", "unused")

    def test_post_adb_reference_policy_and_single_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            artifact = parent / "synthetic"
            artifact.write_bytes(b"synthetic archive, never uploaded")
            with patch.object(j, "pinned_artifact", return_value=artifact), \
                 patch("tpp06_authkey_reader.read_configuration", return_value={"authkey": "SYNTHETIC-SECRET"}), \
                 patch("tpp06_ota_uploader.upload") as upload:
                report = j.activate_adb("192.0.2.1", parent, parent, accept_post_adb_reference=True)
                upload.assert_called_once()
            folder = Path(report["dossier_prive"])
            text = (folder / "adb-operation.json").read_text()
            record = json.loads(text)
            self.assertEqual(record["reference_policy"], "post-adb-reference-required")
            self.assertIsNone(record["original_sha256"])
            self.assertFalse(record["backup_complete"])
            self.assertNotIn("SYNTHETIC-SECRET", text)
            self.assertFalse((folder / "original-nand.bin").exists())

    def test_lost_adb_upload_reply_preserves_intent_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            artifact = parent / "fixture"
            artifact.write_bytes(b"not a real archive")
            with patch.object(j, "pinned_artifact", return_value=artifact), \
                 patch("tpp06_authkey_reader.read_configuration", return_value={"authkey": "fixture"}), \
                 patch("tpp06_ota_uploader.upload", side_effect=TimeoutError) as upload:
                with self.assertRaises(TimeoutError):
                    j.activate_adb("192.0.2.1", parent, parent, accept_post_adb_reference=True)
                upload.assert_called_once()
            journal = next(parent.glob("tpp06-operation-*/adb-operation.json"))
            self.assertEqual(json.loads(journal.read_text())["phase"], "upload-intent")
            self.assertFalse((journal.parent / "upload-accepted.txt").exists())


if __name__ == "__main__":
    unittest.main()
