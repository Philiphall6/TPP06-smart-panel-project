#!/usr/bin/env python3
"""Maintainer-only Linux renderer: public SVG -> PNG + RGB565. No device access.

Requires system librsvg/Cairo and Python Pillow. Not required by the assistant.
Outputs only new files into the explicitly supplied directory.
"""
import argparse
import ctypes as C
import hashlib
from pathlib import Path
import tempfile

from tpp06_logo import encode, decode, write_new_regular

ROOT = Path(__file__).resolve().parents[1]


def render(output):
    from PIL import Image
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stem = "home-assistant-320x480"
    names = (stem + ".png", stem + "-rgb565.bin", "SHA256SUMS.txt")
    if any((output / name).exists() or (output / name).is_symlink() for name in names):
        raise ValueError("Output exists; choose another directory")
    rsvg, cairo, gobject = C.CDLL("librsvg-2.so.2"), C.CDLL("libcairo.so.2"), C.CDLL("libgobject-2.0.so.0")
    rsvg.rsvg_handle_new_from_data.argtypes = [C.c_char_p, C.c_size_t, C.c_void_p]
    rsvg.rsvg_handle_new_from_data.restype = C.c_void_p
    rsvg.rsvg_handle_render_cairo.argtypes = [C.c_void_p, C.c_void_p]
    rsvg.rsvg_handle_render_cairo.restype = C.c_int
    cairo.cairo_image_surface_create.argtypes = [C.c_int, C.c_int, C.c_int]
    cairo.cairo_image_surface_create.restype = C.c_void_p
    cairo.cairo_create.argtypes = [C.c_void_p]
    cairo.cairo_create.restype = C.c_void_p
    cairo.cairo_surface_write_to_png.argtypes = [C.c_void_p, C.c_char_p]
    cairo.cairo_surface_write_to_png.restype = C.c_int
    cairo.cairo_destroy.argtypes = [C.c_void_p]
    cairo.cairo_surface_destroy.argtypes = [C.c_void_p]
    gobject.g_object_unref.argtypes = [C.c_void_p]
    svg = (ROOT / "docs/images/tpp06-home-assistant-boot.svg").read_bytes()
    handle = rsvg.rsvg_handle_new_from_data(svg, len(svg), None)
    if not handle:
        raise ValueError("SVG could not be loaded")
    surface = cairo.cairo_image_surface_create(0, 320, 480)
    context = cairo.cairo_create(surface)
    try:
        with tempfile.TemporaryDirectory(prefix="tpp06-logo-render-") as directory:
            path = Path(directory) / "logo.png"
            if not rsvg.rsvg_handle_render_cairo(handle, context):
                raise ValueError("SVG render failed")
            if cairo.cairo_surface_write_to_png(surface, str(path).encode()):
                raise ValueError("PNG render failed")
            with Image.open(path) as picture:
                if picture.size != (320, 480) or picture.convert("RGBA").getchannel("A").getextrema() != (255, 255):
                    raise ValueError("Expected opaque 320x480 image")
                binary = encode(picture.convert("RGB").tobytes(), "RGB565")
                decode(binary, "RGB565")
            png = path.read_bytes()
    finally:
        cairo.cairo_destroy(context)
        cairo.cairo_surface_destroy(surface)
        gobject.g_object_unref(handle)
    files = {names[0]: png, names[1]: binary}
    for name, data in files.items():
        write_new_regular(output / name, data)
    sums = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in files.items())
    write_new_regular(output / names[2], sums.encode("ascii"))
    print(sums, end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    render(parser.parse_args().output)
