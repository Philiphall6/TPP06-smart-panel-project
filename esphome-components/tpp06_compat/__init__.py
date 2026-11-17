import esphome.codegen as cg
import esphome.config_validation as cv

CODEOWNERS = ["@Philiphall6"]
DEPENDENCIES = ["host"]
DOMAIN = "tpp06_compat"

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    del config
    cg.add_build_flag("-Wl,--wrap=clock_gettime")
    cg.add_build_flag("-Wl,--wrap=nanosleep")
    cg.add_build_flag("-Wl,--wrap=select")
    cg.add_build_flag("-Wl,--wrap=time")
