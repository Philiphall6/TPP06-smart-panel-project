"""Portable MD5 backend for cross-compiled ESPHome host targets.

The upstream host implementation links OpenSSL.  The TPP06 uClibc toolchain
does not ship OpenSSL, so this component keeps the same ESPHome API while
using a small self-contained implementation.
"""

import esphome.codegen as cg

CODEOWNERS = ["@Philiphall6"]


async def to_code(config) -> None:
    cg.add_define("USE_MD5")
