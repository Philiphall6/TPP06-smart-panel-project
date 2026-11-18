"""IPv4 DNS-SD publisher for the TPP06 Linux host, using native ESPHome records."""
import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome.components import mdns
from esphome.components.host import CONF_NETWORK_INTERFACE, validate_network_interface
from esphome.const import CONF_ID, CONF_DISABLED
from esphome.core import CORE

DEPENDENCIES = ["host", "mdns"]
ns = cg.esphome_ns.namespace("tpp06_mdns")
Publisher = ns.class_("Publisher", cg.Component)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(Publisher),
    cv.Optional(CONF_NETWORK_INTERFACE, default="wlan0"): validate_network_interface,
}).extend(cv.COMPONENT_SCHEMA)


def final_validate(config):
    full = fv.full_config.get()
    if full["mdns"][CONF_DISABLED]:
        raise cv.Invalid("tpp06_mdns requires mdns.disabled: false")
    if full["host"].get(CONF_NETWORK_INTERFACE) != config[CONF_NETWORK_INTERFACE]:
        raise cv.Invalid("host and tpp06_mdns must use the same network_interface for the real MAC")


FINAL_VALIDATE_SCHEMA = final_validate


async def to_code(config):
    mdns.enable_mdns_storage()
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    provider = await cg.get_variable(CORE.config["mdns"][CONF_ID])
    cg.add(var.set_records(provider))
    cg.add(var.set_interface(config[CONF_NETWORK_INTERFACE]))
