"""Optional observation of the Linux mute input, never a power action."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import ENTITY_CATEGORY_DIAGNOSTIC
from . import LocalRelays

DEPENDENCIES = ["tpp06_local_relays"]
CONFIG_SCHEMA = text_sensor.text_sensor_schema(
    icon="mdi:toggle-switch-outline", entity_category=ENTITY_CATEGORY_DIAGNOSTIC
).extend({cv.GenerateID("relays_id"): cv.use_id(LocalRelays)})


async def to_code(config):
    sensor = await text_sensor.new_text_sensor(config)
    parent = await cg.get_variable(config["relays_id"])
    cg.add(parent.set_mute_sensor(sensor))
    cg.add_define("USE_TPP06_MUTE_INPUT")
