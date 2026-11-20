"""Synthetic ELF metadata, not executable firmware and never run on hardware."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tpp06_assistant_elf import inspect
from tpp06_assistant_core import AssistantError


def synthetic(arch=4, extra=b"", flags=0x05000200, segment_type=1, machine=40):
    attributes = bytes((6, arch)) + extra
    group = b"\1" + struct.pack("<I", 5 + len(attributes)) + attributes
    subsection = b"aeabi\0" + group
    arm = b"A" + struct.pack("<I", 4 + len(subsection)) + subsection
    names = b"\0.shstrtab\0.ARM.attributes\0"
    names_offset = 84
    arm_offset = names_offset + len(names)
    sections_offset = (arm_offset + len(arm) + 3) & ~3
    output = bytearray(sections_offset + 3 * 40)
    output[:16] = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<HHIIIIIHHHHHH", output, 16, 2, machine, 1, 0x10034, 52, sections_offset,
                     flags, 52, 32, 1, 40, 3, 1)
    struct.pack_into("<IIIIIIII", output, 52, segment_type, 0, 0x10000, 0x10000, 84, 84, 5, 0x1000)
    output[names_offset:names_offset + len(names)] = names
    output[arm_offset:arm_offset + len(arm)] = arm
    struct.pack_into("<IIIIIIIIII", output, sections_offset + 40, 1, 3, 0, 0, names_offset, len(names), 0, 0, 1, 0)
    struct.pack_into("<IIIIIIIIII", output, sections_offset + 80, 11, 0x70000003, 0, 0, arm_offset, len(arm), 0, 0, 1, 0)
    return output


@unittest.skipUnless(importlib.util.find_spec("elftools"), "pyelftools dependency not installed")
class ElfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic"

    def test_portable_armv5te_and_armv5tej_checks(self):
        for arch in (4, 5):
            self.path.write_bytes(synthetic(arch=arch))
            result = inspect(self.path)
            self.assertEqual(result["bytes"], self.path.stat().st_size)
            self.assertEqual(len(result["sha256"]), 64)

    def test_rejects_other_cpu_float_and_dynamic_abi(self):
        for args in ({"arch": 10}, {"extra": b"\x0a\x01"}, {"extra": b"\x1c\x01"},
                     {"flags": 0x05000400}, {"flags": 0x04000200}, {"segment_type": 3}, {"machine": 3}):
            with self.subTest(args=args):
                self.path.write_bytes(synthetic(**args))
                with self.assertRaises(AssistantError):
                    inspect(self.path)

    def test_missing_executable_entry_is_rejected(self):
        data = synthetic()
        struct.pack_into("<I", data, 24, 0x80000000)
        self.path.write_bytes(data)
        with self.assertRaises(AssistantError):
            inspect(self.path)


if __name__ == "__main__":
    unittest.main()
