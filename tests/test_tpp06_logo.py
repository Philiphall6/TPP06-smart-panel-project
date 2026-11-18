import tempfile
from pathlib import Path
import unittest

from tools.tpp06_logo import encode, decode, write_new_regular, WIDTH, HEIGHT, PAYLOAD_SIZE, PARTITION_SIZE


class LogoCodecTests(unittest.TestCase):
    def test_known_primary_colours_and_little_endian(self):
        for order, red, blue in (("RGB565", b"\x00\xf8", b"\x1f\x00"),
                                 ("BGR565", b"\x1f\x00", b"\x00\xf8")):
            for colour, expected in (((255, 0, 0), red), ((0, 255, 0), b"\xe0\x07"),
                                     ((0, 0, 255), blue), ((0, 0, 0), b"\x00\x00"),
                                     ((255, 255, 255), b"\xff\xff")):
                rgb = bytes(colour) * WIDTH * HEIGHT
                image = encode(rgb, order)
                self.assertEqual(len(image), PARTITION_SIZE)
                self.assertEqual(image[:PAYLOAD_SIZE], expected * WIDTH * HEIGHT)
                self.assertEqual(image[PAYLOAD_SIZE:], b"\xff" * (PARTITION_SIZE - PAYLOAD_SIZE))
                self.assertEqual(decode(image, order), rgb)

    def test_rejects_unknown_format_size_and_metadata(self):
        with self.assertRaises(ValueError):
            encode(b"", "AUTO")
        with self.assertRaises(ValueError):
            encode(b"", "RGB565")
        with self.assertRaises(ValueError):
            decode(b"", "BGR565")
        with self.assertRaises(ValueError):
            decode(b"\x00" * PARTITION_SIZE, "BGR565")

    def test_output_refuses_devices_existing_files_and_symlinks(self):
        with self.assertRaises(ValueError):
            write_new_regular("/dev/tpp06-never-create", b"test")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "logo.bin"
            write_new_regular(target, b"original")
            with self.assertRaises(FileExistsError):
                write_new_regular(target, b"replacement")
            link = Path(directory) / "link"
            link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                write_new_regular(link, b"replacement")
            self.assertEqual(target.read_bytes(), b"original")
