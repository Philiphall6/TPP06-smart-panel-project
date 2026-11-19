"""Read-only Linux diagnostics and optional main-loop heartbeat in tmpfs."""
import re
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import CONF_ID, ENTITY_CATEGORY_DIAGNOSTIC, PLATFORM_HOST

DEPENDENCIES = ["host"]
AUTO_LOAD = ["text_sensor"]
CODEOWNERS = ["@Philiphall6"]
ns = cg.esphome_ns.namespace("tpp06_health")
Health = ns.class_("Health", cg.PollingComponent)


def interface_name(value):
    value = cv.string_strict(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", value):
        raise cv.Invalid("Expected a Linux interface name, not a path")
    return value


FIELDS = ("memory", "wifi_signal", "link", "supervisor", "ota_capacity")


def heartbeat_interval(config):
    if config["heartbeat"] and not 1000 <= config["update_interval"].total_milliseconds <= 10000:
        raise cv.Invalid("Heartbeat requires update_interval between 1s and 10s (supervisor expiry: 25s)")
    return config


CONFIG_SCHEMA = cv.All(cv.Schema({
    cv.GenerateID(): cv.declare_id(Health),
    cv.Optional("heartbeat", default=False): cv.boolean,
    cv.Optional("wifi_signal_via_wpa", default=False): cv.boolean,
    cv.Optional("network_interface", default="wlan0"): interface_name,
    **{cv.Optional(field): text_sensor.text_sensor_schema(
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC) for field in FIELDS},
}).extend(cv.polling_component_schema("5s")), cv.only_on(PLATFORM_HOST), heartbeat_interval)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_heartbeat(config["heartbeat"]))
    cg.add(var.set_wifi_signal_via_wpa(config["wifi_signal_via_wpa"]))
    cg.add(var.set_interface(config["network_interface"]))
    for field in FIELDS:
        if field in config:
            sensor = await text_sensor.new_text_sensor(config[field])
            cg.add(getattr(var, "set_" + field)(sensor))
