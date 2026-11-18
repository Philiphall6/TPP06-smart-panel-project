"""Opt-in Linux backlight control; no GPIO, PWM export or boot changes."""
import re

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["host"]
CODEOWNERS = ["@Philiphall6"]
ns = cg.esphome_ns.namespace("tpp06_backlight")
Backlight = ns.class_("Backlight", cg.Component)


def backlight_name(value):
    value = cv.string_strict(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise cv.Invalid("Use a single /sys/class/backlight device name, not a path")
    return value


CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(Backlight),
    cv.Optional("device", default="backlight"): backlight_name,
}).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_device(config["device"]))
