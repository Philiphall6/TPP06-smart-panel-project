"""Self-contained SHA-256 backend for the OpenSSL-free TPP06 toolchain."""

import esphome.codegen as cg
import esphome.config_validation as cv

CODEOWNERS = ["@Philiphall6"]
CONFIG_SCHEMA = cv.Schema({})


async def to_code(config) -> None:
    cg.add_define("USE_SHA256")
