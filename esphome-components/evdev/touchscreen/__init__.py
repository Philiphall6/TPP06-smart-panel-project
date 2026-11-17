import esphome.codegen as cg
from esphome.components import touchscreen
import esphome.config_validation as cv
from esphome.const import CONF_ID, PLATFORM_HOST
from esphome.types import ConfigType

CODEOWNERS = ["@Philiphall6"]
DEPENDENCIES = ["host"]
DOMAIN = "evdev"

CONF_DEVICE = "device"

evdev_ns = cg.esphome_ns.namespace("evdev")
EvdevTouchscreen = evdev_ns.class_("EvdevTouchscreen", touchscreen.Touchscreen)

CONFIG_SCHEMA = cv.All(
    touchscreen.touchscreen_schema(
        "40ms",
        defaults={"x_min": 0, "x_max": 320, "y_min": 0, "y_max": 480},
    ).extend(
        {
            cv.GenerateID(): cv.declare_id(EvdevTouchscreen),
            cv.Optional(CONF_DEVICE, default="/dev/input/event1"): cv.string_strict,
        }
    ),
    cv.only_on(PLATFORM_HOST),
)


async def to_code(config: ConfigType) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    cg.add(var.set_device(config[CONF_DEVICE]))
    await touchscreen.register_touchscreen(var, config)
