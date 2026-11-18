"""Portable UI helpers: no networking, commands or hardware writes."""
import esphome.codegen as cg
import esphome.config_validation as cv

DEPENDENCIES = ["host", "lvgl"]
CODEOWNERS = ["@Philiphall6"]
CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    cg.add_global(cg.RawStatement('#include "esphome/components/tpp06_ui/weather.h"'))
