"""Inspect, never execute, a panel image. No version allowlist or network IO.

These checks reject structural/ABI mismatches, not every ARM instruction,
kernel syscall incompatibility or runtime bug. Keep target toolchain settings.
"""
from pathlib import Path
import struct

from esphome.core import EsphomeError


def check_panel_binary(binary):
    def require(ok, reason):
        if not ok:
            raise EsphomeError(f"TPP06: incompatible OTA image: {reason}")

    try:
        with Path(binary).open("rb") as stream:
            size = stream.seek(0, 2)
            require(52 <= size <= 256 * 1024 * 1024, "invalid executable size")
            stream.seek(0)
            header = stream.read(52)
            require(len(header) == 52 and header[:7] == b"\x7fELF\x01\x01\x01",
                    "ELF32 little-endian required")
            (kind, machine, version, entry, phoff, _, flags, ehsize,
             phsize, phnum, _, _, _) = struct.unpack_from("<HHIIIIIHHHHHH", header, 16)
            require(kind == 2 and machine == 40 and version == 1, "ARM executable required")
            require(flags & 0xFF000000 == 0x05000000, "ARM EABI5 required")
            require(flags & 0x200 and not flags & 0x400, "soft-float ABI required")
            require(ehsize == 52 and phsize == 32 and 0 < phnum < 0xFFFF
                    and phoff >= ehsize and phoff + phsize * phnum <= size,
                    "invalid program header table")
            stream.seek(phoff)
            executable_entry = False
            for _ in range(phnum):
                record = stream.read(32)
                require(len(record) == 32, "truncated program header")
                ptype, offset, vaddr, _, filesz, memsz, perms, _ = struct.unpack("<IIIIIIII", record)
                require(ptype not in (2, 3), "dynamic loading is not supported on this target")
                require(offset + filesz <= size, "truncated segment")
                if ptype == 1:
                    require(filesz <= memsz, "invalid load segment")
                    if perms & 1 and vaddr <= entry < vaddr + filesz:
                        executable_entry = True
            require(executable_entry, "entry point outside executable file-backed segments")
    except OSError as error:
        raise EsphomeError("TPP06: cannot read OTA executable; compile it before uploading") from error
    return Path(binary)
