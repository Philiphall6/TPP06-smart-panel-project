"""Local screen mailbox for the optional supervised Linux Wi-Fi editor."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID, PLATFORM_HOST

DEPENDENCIES = ["host"]
CODEOWNERS = ["@Philiphall6"]
ns = cg.esphome_ns.namespace("tpp06_wifi")
WifiEditor = ns.class_("WifiEditor", cg.Component)
CONFIG_SCHEMA = cv.All(cv.Schema({
    cv.GenerateID(): cv.declare_id(WifiEditor),
}).extend(cv.COMPONENT_SCHEMA), cv.only_on(PLATFORM_HOST))


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
