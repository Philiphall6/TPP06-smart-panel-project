"""PC-only assets and download tests; synthetic network responses, no panel."""
import ast
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tpp06_assistant_core as core
import tpp06_assistant_resources as resources
from tpp06_assistant_i18n import Language
from tpp06_logo import decode
from package_assistant import FILES


class Response(io.BytesIO):
    def geturl(self):
        return "https://example.invalid/tool"


class ResourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tools"

    def test_defaults_do_not_create_folders(self):
        with patch.object(Path, "home", return_value=Path(self.tmp.name)):
            self.assertFalse(resources.default_backups().exists())
            self.assertFalse(resources.default_tools().exists())
        self.assertEqual(resources.tool_status(self.path, "nand"), {"nandtool": "missing"})
        self.assertFalse(self.path.exists())

    def test_verified_download_only_and_existing_file_not_downloaded_again(self):
        data = b"synthetic-tool-not-executable"
        opener = Mock(side_effect=lambda *args, **kwargs: Response(data))
        with patch.dict(resources.PINS, nandtool=hashlib.sha256(data).hexdigest()):
            resources.prepare_tools(self.path, "nand", opener)
            self.assertEqual(resources.tool_status(self.path, "nand"), {"nandtool": "ready"})
            resources.prepare_tools(self.path, "nand", opener)
        opener.assert_called_once()
        self.assertEqual((self.path / "nandtool").read_bytes(), data)
        self.assertEqual(list(self.path.iterdir()), [self.path / "nandtool"])

    def test_bad_hash_removed_and_not_installed(self):
        with self.assertRaises(core.AssistantError):
            resources.prepare_tools(self.path, "nand", lambda *a, **k: Response(b"wrong"))
        self.assertEqual(list(self.path.iterdir()), [])

    def test_existing_wrong_file_preserved(self):
        self.path.mkdir()
        target = self.path / "nandtool"
        target.write_bytes(b"user-owned")
        opener = Mock()
        with self.assertRaises(core.AssistantError):
            resources.prepare_tools(self.path, "nand", opener)
        opener.assert_not_called()
        self.assertEqual(target.read_bytes(), b"user-owned")

    def test_symlink_refused(self):
        self.path.mkdir()
        (self.path / "nandtool").symlink_to(self.path / "missing")
        opener = Mock()
        with self.assertRaises(core.AssistantError):
            resources.prepare_tools(self.path, "nand", opener)
        opener.assert_not_called()
        self.assertTrue((self.path / "nandtool").is_symlink())

    def test_non_https_and_oversized_downloads_refused(self):
        response = Response(b"invalid")
        response.geturl = lambda: "http://example.invalid/tool"
        with self.assertRaises(core.AssistantError):
            resources.prepare_tools(self.path, "nand", lambda *a, **k: response)
        class Oversized(Response):
            def read(self, size):
                return b"x" * 65536
        with self.assertRaises(core.AssistantError):
            resources.prepare_tools(self.path, "nand", lambda *a, **k: Oversized())
        self.assertEqual(list(self.path.iterdir()), [])

    def test_dropbear_no_arbitrary_download(self):
        opener = Mock()
        with self.assertRaisesRegex(core.AssistantError, "Dropbear"):
            resources.prepare_tools(self.path, "ssh", opener)
        opener.assert_not_called()

    def test_bundled_public_logo_hash_geometry_blue_and_package(self):
        path = Path(resources.bundled_logo())
        self.assertEqual(path.stat().st_size, 524288)
        rgb = decode(path.read_bytes(), "RGB565")
        blue = tuple(rgb[(280 * 320 + 90) * 3: (280 * 320 + 90) * 3 + 3])
        self.assertLess(blue[0], 40)
        self.assertGreater(blue[1], 170)
        self.assertGreater(blue[2], 230)
        png = path.with_name("home-assistant-320x480.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (320, 480))
        for line in path.with_name("SHA256SUMS.txt").read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(hashlib.sha256(path.with_name(name).read_bytes()).hexdigest(), digest)
            self.assertIn("assets/boot-logo/" + name, FILES)
        for name in ("tools/tpp06_assistant_i18n.py", "tools/tpp06_assistant_resources.py", "assets/boot-logo/README.md", "docs/images/tpp06-home-assistant-boot.svg", "docs/en/21-assistant-ordinateur.md"):
            self.assertIn(name, FILES)

    def test_all_action_titles_details_and_warnings_translated(self):
        lang = Language()
        lang.code = "en"
        for action in core.ACTIONS:
            self.assertNotEqual(lang.text(action.title), action.title)
            self.assertNotEqual(lang.text(action.detail), action.detail)
        tree = ast.parse((core.PROJECT_ROOT / "tools/tpp06_assistant.py").read_text())
        forms = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "forms" for target in node.targets))
        for form in forms.values:
            for index in (0, 2):
                source = ast.literal_eval(form.elts[index])
                self.assertNotEqual(lang.text(source), source, source)


if __name__ == "__main__":
    unittest.main()
