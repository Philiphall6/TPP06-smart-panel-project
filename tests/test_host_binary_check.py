"""Pure offline image validation; never execute the synthetic image."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

try:
    from esphome.core import EsphomeError
except ImportError:
    EsphomeError = None


@unittest.skipIf(EsphomeError is None, "ESPHome Python environment required")
class BinaryCheckTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "esphome-components/host/binary_check.py"
        spec = importlib.util.spec_from_file_location("test_binary_check", source)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.binary = Path(self.temporary.name) / "program"

    def fixture(self):
        data = bytearray(256)
        data[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<HHIIIIIHHHHHH", data, 16,
                         2, 40, 1, 0x10080, 52, 0, 0x05000200, 52, 32, 1, 0, 0, 0)
        struct.pack_into("<IIIIIIII", data, 52, 1, 0, 0x10000, 0, 256, 256, 5, 4096)
        return data

    def test_valid_structural_fixture(self):
        self.binary.write_bytes(self.fixture())
        self.assertEqual(self.module.check_panel_binary(self.binary), self.binary)

    def test_rejects_incompatible_and_truncated_images(self):
        for offset, fmt, value in ((4, "B", 2), (5, "B", 2), (16, "H", 3),
                                   (18, "H", 62), (36, "I", 0x05000400),
                                   (36, "I", 0x04000200), (28, "I", 240),
                                   (42, "H", 0), (44, "H", 0),
                                   (52, "I", 2), (52, "I", 3),
                                   (68, "I", 257), (72, "I", 1), (24, "I", 0)):
            with self.subTest(offset=offset, value=value):
                data = self.fixture()
                struct.pack_into("<" + fmt, data, offset, value)
                self.binary.write_bytes(data)
                with self.assertRaises(EsphomeError):
                    self.module.check_panel_binary(self.binary)
        for data in (b"", self.fixture()[:51], self.fixture()[:100]):
            self.binary.write_bytes(data)
            with self.assertRaises(EsphomeError):
                self.module.check_panel_binary(self.binary)

    def test_missing_file_has_actionable_error(self):
        with self.assertRaisesRegex(EsphomeError, "compile it before uploading"):
            self.module.check_panel_binary(self.binary)
