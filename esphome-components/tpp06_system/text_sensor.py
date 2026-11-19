import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import PLATFORM_HOST
from . import system_ns

Storage = system_ns.class_("Storage", text_sensor.TextSensor, cg.PollingComponent)
CONFIG_SCHEMA = cv.All(
    text_sensor.text_sensor_schema(Storage, icon="mdi:harddisk")
    .extend(cv.polling_component_schema("60s")), cv.only_on(PLATFORM_HOST)
)

async def to_code(config):
    var = await text_sensor.new_text_sensor(config)
    await cg.register_component(var, config)
