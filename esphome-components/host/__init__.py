import fcntl
import hashlib
import logging
import os
from pathlib import Path
import platform
import sys
import tarfile
import urllib.request

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import (
    CONF_MAC_ADDRESS,
    KEY_CORE,
    KEY_FRAMEWORK_VERSION,
    KEY_TARGET_FRAMEWORK,
    KEY_TARGET_PLATFORM,
    PLATFORM_HOST,
    ThreadModel,
    Toolchain,
)
from esphome.core import CORE, EsphomeError
from esphome.storage_json import StorageJSON
from esphome.types import ConfigType

from .const import KEY_HOST

# force import gpio to register pin schema
from .gpio import host_pin_to_code  # noqa: F401

CODEOWNERS = ["@esphome/core", "@clydebarrow"]
AUTO_LOAD = ["network", "preferences"]
DOMAIN = "host"
IS_TARGET_PLATFORM = True

_LOGGER = logging.getLogger(__name__)
CONF_CROSS_COMPILE = "cross_compile"
CONF_URL = "url"
CONF_SHA256 = "sha256"
CONF_DIRECTORY = "directory"
CONF_PREFIX = "prefix"

DEFAULT_TOOLCHAIN_URL = (
    "https://toolchains.bootlin.com/downloads/releases/toolchains/"
    "armv5-eabi/tarballs/armv5-eabi--uclibc--stable-2026.08-1.tar.xz"
)
DEFAULT_TOOLCHAIN_SHA256 = "2e78440c4b37a9c84d6165f12fd2525e72bf88c32445e1c3400d1e01384c92ce"
DEFAULT_TOOLCHAIN_DIRECTORY = "armv5-eabi--uclibc--stable-2026.08-1"
DEFAULT_TOOLCHAIN_PREFIX = "arm-buildroot-linux-uclibcgnueabi"

ZIG_VERSION = "0.17.1"
ZIG_AARCH64_URL = (
    f"https://ziglang.org/download/{ZIG_VERSION}/zig-aarch64-linux-{ZIG_VERSION}.tar.xz"
)
ZIG_AARCH64_SHA256 = "a1546d5646eb184437918d6635ca6b762a0e889eac09cef720ee7a1ed3fe7795"
ZIG_AARCH64_DIRECTORY = f"zig-aarch64-linux-{ZIG_VERSION}"

CROSS_COMPILE_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_URL, default=DEFAULT_TOOLCHAIN_URL): cv.url,
        cv.Optional(CONF_SHA256, default=DEFAULT_TOOLCHAIN_SHA256): cv.All(
            cv.string_strict, cv.Length(min=64, max=64)
        ),
        cv.Optional(CONF_DIRECTORY, default=DEFAULT_TOOLCHAIN_DIRECTORY): cv.string_strict,
        cv.Optional(CONF_PREFIX, default=DEFAULT_TOOLCHAIN_PREFIX): cv.string_strict,
    }
)


def set_core_data(config: ConfigType) -> ConfigType:
    CORE.data[KEY_HOST] = {}
    CORE.data[KEY_CORE][KEY_TARGET_PLATFORM] = PLATFORM_HOST
    CORE.data[KEY_CORE][KEY_TARGET_FRAMEWORK] = "host"
    CORE.data[KEY_CORE][KEY_FRAMEWORK_VERSION] = cv.Version(1, 0, 0)
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Optional(CONF_MAC_ADDRESS, default="98:35:69:ab:f6:79"): cv.mac_address,
            cv.Optional(CONF_CROSS_COMPILE): CROSS_COMPILE_SCHEMA,
        }
    ),
    # The host builds with the machine's own compiler through ninja; there
    # is no PlatformIO backend, so a CLI --toolchain must name this one
    cv.resolve_toolchain("host", (Toolchain.HOST,), Toolchain.HOST),
    set_core_data,
)


async def to_code(config: ConfigType) -> None:
    cg.add_build_flag("-DUSE_HOST")
    cg.add_define("USE_NATIVE_64BIT_TIME")
    # The prefs file finds stored preferences by key, so key migration is possible
    cg.add_define("USE_PREFERENCE_KEY_LOOKUP")
    cg.add_define("USE_ESPHOME_HOST_MAC_ADDRESS", config[CONF_MAC_ADDRESS].parts)
    cg.set_cpp_standard("gnu++20")
    cg.add_define("ESPHOME_BOARD", "host")
    cg.add_define("ESPHOME_VARIANT", "HOST")
    cg.add_define(ThreadModel.MULTI_ATOMICS)


def get_download_types(storage_json: StorageJSON) -> list[dict[str, str]]:
    """Download entries for a built host program; same contract as
    ``esp32.get_download_types`` (title / description / file / download)."""
    if storage_json.firmware_bin_path is None:
        return []
    return [
        {
            "title": "Executable",
            "description": "Native program for the machine this was built on; "
            "copy it to the host and run it.",
            "file": "program",
            "download": storage_json.name,
        }
    ]


# Called by __main__.compile_program; True means this platform built the
# program itself instead of falling through to the PlatformIO toolchain.
def run_compile(args: object, config: ConfigType) -> bool:
    from esphome.host import toolchain

    if sys.platform == "win32":
        # Here, not in validation: `esphome config` must keep working
        raise EsphomeError(
            "The host platform uses POSIX interfaces and does not build on "
            "Windows; use WSL or a Linux or macOS machine"
        )
    if cross_compile := config[DOMAIN].get(CONF_CROSS_COMPILE):
        _configure_cross_compiler(cross_compile)
    if toolchain.run_compile(config, CORE.verbose) != 0:
        raise EsphomeError("Host build failed")
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download_toolchain(url: str, destination: Path, expected_sha256: str) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    _LOGGER.info("Downloading a verified TPP06 compiler archive (first build only)")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = _sha256(partial)
        if actual.lower() != expected_sha256.lower():
            partial.unlink(missing_ok=True)
            raise EsphomeError(
                f"TPP06 toolchain checksum mismatch: expected {expected_sha256}, got {actual}"
            )
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _configure_cross_compiler(config: ConfigType) -> None:
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        _configure_zig_cross_compiler()
        return

    if machine not in ("x86_64", "amd64"):
        raise EsphomeError(
            f"Unsupported Device Builder architecture {machine!r}; "
            "TPP06 compilation supports x86-64 and ARM64 hosts"
        )

    _configure_bootlin_cross_compiler(config)


def _configure_bootlin_cross_compiler(config: ConfigType) -> None:
    cache = CORE.relative_internal_path("tpp06-armv5-toolchain")
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = cache / "toolchain.tar.xz"
    prefix_path = cache / config[CONF_DIRECTORY] / "bin" / config[CONF_PREFIX]
    lock_path = cache / ".install.lock"

    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        compiler = Path(f"{prefix_path}-gcc")
        if not compiler.is_file():
            if not archive_path.is_file() or _sha256(archive_path).lower() != config[CONF_SHA256].lower():
                archive_path.unlink(missing_ok=True)
                _download_toolchain(config[CONF_URL], archive_path, config[CONF_SHA256])
            _LOGGER.info("Extracting the TPP06 ARMv5 toolchain into the ESPHome cache")
            with tarfile.open(archive_path, "r:xz") as archive:
                archive.extractall(cache, filter="data")
        if not compiler.is_file():
            raise EsphomeError(f"TPP06 cross compiler missing after extraction: {compiler}")

    tools = {
        "CC": "gcc",
        "CXX": "g++",
        "AR": "ar",
        "OBJDUMP": "objdump",
        "READELF": "readelf",
    }
    for variable, suffix in tools.items():
        executable = Path(f"{prefix_path}-{suffix}")
        if not executable.is_file():
            raise EsphomeError(f"TPP06 toolchain program is missing: {executable}")
        os.environ[variable] = str(executable)
    architecture_flags = " -march=armv5te -marm -mfloat-abi=soft"
    os.environ["CC"] += architecture_flags
    os.environ["CXX"] += architecture_flags
    os.environ["ESPHOME_PCH_ENABLE"] = "0"


def _configure_zig_cross_compiler() -> None:
    cache = CORE.relative_internal_path("tpp06-armv5-zig")
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = cache / f"zig-{ZIG_VERSION}.tar.xz"
    install_path = cache / ZIG_AARCH64_DIRECTORY
    zig = install_path / "zig"
    lock_path = cache / ".install.lock"

    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not zig.is_file():
            if (
                not archive_path.is_file()
                or _sha256(archive_path).lower() != ZIG_AARCH64_SHA256
            ):
                archive_path.unlink(missing_ok=True)
                _download_toolchain(
                    ZIG_AARCH64_URL, archive_path, ZIG_AARCH64_SHA256
                )
            _LOGGER.info("Extracting the ARM64 Zig compiler into the ESPHome cache")
            with tarfile.open(archive_path, "r:xz") as archive:
                archive.extractall(cache, filter="data")
        if not zig.is_file():
            raise EsphomeError(f"TPP06 Zig compiler missing after extraction: {zig}")

        ar_wrapper = cache / "zig-ar"
        wrapper_contents = f'#!/bin/sh\nexec "{zig}" ar "$@"\n'
        if not ar_wrapper.is_file() or ar_wrapper.read_text() != wrapper_contents:
            ar_wrapper.write_text(wrapper_contents)
            ar_wrapper.chmod(0o755)

    target = "-target arm-linux-musleabi -mcpu=arm926ej_s -DTPP06_ZIG_TOOLCHAIN"
    os.environ["CC"] = f"{zig} cc {target}"
    os.environ["CXX"] = f"{zig} c++ {target}"
    os.environ["AR"] = str(ar_wrapper)
    # Zig has no objdump/readelf subcommands; they are not needed to compile.
    os.environ.pop("OBJDUMP", None)
    os.environ.pop("READELF", None)
    os.environ["ESPHOME_PCH_ENABLE"] = "0"
