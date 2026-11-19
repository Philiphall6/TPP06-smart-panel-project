import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import button
from esphome.const import CONF_ID, DEVICE_CLASS_RESTART, PLATFORM_HOST
from . import system_ns

Restart = system_ns.class_("Restart", button.Button, cg.Component)
CONFIG_SCHEMA = cv.All(
    button.button_schema(Restart, icon="mdi:restart", device_class=DEVICE_CLASS_RESTART)
    .extend({cv.Optional("mode", default="application"): cv.one_of("application", "device")})
    .extend(cv.COMPONENT_SCHEMA), cv.only_on(PLATFORM_HOST)
)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await button.register_button(var, config)
    cg.add(var.set_device_reboot(config["mode"] == "device"))
