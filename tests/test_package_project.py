"""Lean package checks; optional GitHub imports, never device access or builds."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import unquote
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package_project as package


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.archive = package.build(cls.tmp.name, "v0.1.9-rc2")
        with zipfile.ZipFile(cls.archive) as z:
            prefix = "TPP06-HA-Panel-v0.1.9-rc2/"
            cls.files = {name[len(prefix):]: z.read(name) for name in z.namelist()}

    def test_runtime_present_developer_material_absent(self):
        for name in ("Assistant-TPP06.cmd", "tools/tpp06_assistant.py", "tools/tpp06_assistant_resources.py",
                     "device/tpp06-multiboot.sh", "esphome/tpp06-lvgl-complete.yaml",
                     "assets/boot-logo/home-assistant-320x480-rgb565.bin", "assets/boot-logo/README.md"):
            self.assertIn(name, self.files)
        for name in self.files:
            self.assertFalse(name.startswith(("tests/", "media/", "esphome-components/", "esphome/packages/", "docs/archive/", "docs/releases/")), name)
            self.assertNotIn("__pycache__", name)
            self.assertNotIn(Path(name).name, package.OMIT_TOOLS)
        self.assertEqual([name for name in self.files if name.endswith(".yaml")], ["esphome/tpp06-lvgl-complete.yaml"])

    @unittest.skipUnless(os.environ.get("TPP06_TEST_REMOTE_CONFIG") == "1", "Opt-in real GitHub import validation")
    def test_yaml_alone_fetches_remote_packages_and_drivers(self):
        from esphome import yaml_util
        from esphome.config import validate_config
        from esphome.core import CORE
        CORE.reset()
        self.addCleanup(CORE.reset)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            CORE.config_path = root / "panel.yaml"
            CORE.config_path.write_bytes(self.files["esphome/tpp06-lvgl-complete.yaml"])
            # Public deterministic test key, never shipped or installed on a device.
            (root / "secrets.yaml").write_text("tpp06_api_encryption_key: MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=\n")
            result = validate_config(yaml_util.load_yaml(CORE.config_path), {})
            self.assertFalse(result.errors, str(result.errors))
            self.assertEqual(result["esphome"]["project"]["version"], "0.1.9-rc2")
            self.assertFalse(result["tpp06_local_relays"]["control_enabled"])
            self.assertFalse((root / "esphome-components").exists())
            self.assertFalse((root / "packages").exists())
            self.assertEqual(len(result["lvgl"][0]["pages"]), 14)

    def test_local_document_links_exist(self):
        import posixpath
        for name, data in self.files.items():
            if not name.endswith(".md"):
                continue
            for target in re.findall(r'\]\(([^\s)]+)\)', data.decode()):
                if re.match(r'[a-zA-Z][\w+.-]*:', target) or target.startswith('#'):
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(target.split('#')[0])))
                self.assertIn(resolved, self.files, (name, target))

    def test_hashes_and_runtime_unchanged_from_tag(self):
        import subprocess
        manifest = json.loads(self.files["PACKAGE-CONTENTS.json"])
        for name, digest in manifest["sha256"].items():
            self.assertEqual(hashlib.sha256(self.files[name]).hexdigest(), digest)
            if not name.endswith(".md"):
                original = subprocess.check_output(["git", "show", manifest["source_commit"] + ":" + name], cwd=package.ROOT)
                self.assertEqual(self.files[name], original, name)

    def test_existing_output_refused(self):
        with self.assertRaisesRegex(ValueError, "Output exists"):
            package.build(self.tmp.name, "v0.1.9-rc2")

    def test_not_a_tag_and_outside_links_refused(self):
        for tag in ("main", "--all", "../v1", ""):
            with self.assertRaises(ValueError):
                package.build(self.tmp.name, tag)
        with self.assertRaises(ValueError):
            package.rewrite_links("README.md", "[bad](../../private)", set(), "v0.1.9-rc2")


if __name__ == "__main__":
    unittest.main()
