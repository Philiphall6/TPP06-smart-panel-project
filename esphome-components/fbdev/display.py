import esphome.codegen as cg
from esphome.components import display
from esphome.components.const import BYTE_ORDER_LITTLE
import esphome.config_validation as cv
from esphome.const import (
    CONF_AUTO_CLEAR_ENABLED,
    CONF_DIMENSIONS,
    CONF_HEIGHT,
    CONF_ID,
    CONF_LAMBDA,
    CONF_PAGES,
    CONF_ROTATION,
    CONF_WIDTH,
    PLATFORM_HOST,
)
from esphome.types import ConfigType

CODEOWNERS = ["@Philiphall6"]
DEPENDENCIES = ["host"]
DOMAIN = "fbdev"

CONF_DEVICE = "device"

fbdev_ns = cg.esphome_ns.namespace("fbdev")
FbdevDisplay = fbdev_ns.class_("FbdevDisplay", display.Display, cg.Component)

def _add_display_metadata(config: ConfigType) -> ConfigType:
    dimensions = config[CONF_DIMENSIONS]
    if isinstance(dimensions, dict):
        width = dimensions[CONF_WIDTH]
        height = dimensions[CONF_HEIGHT]
    else:
        width, height = dimensions
    display.add_metadata(
        config[CONF_ID],
        width,
        height,
        byte_order=BYTE_ORDER_LITTLE,
        has_writer=config.get(CONF_AUTO_CLEAR_ENABLED) is True
        or config.get(CONF_PAGES) is not None
        or config.get(CONF_LAMBDA) is not None
        or config.get(display.CONF_SHOW_TEST_CARD) is True,
        rotation=config.get(CONF_ROTATION, 0),
    )
    return config


CONFIG_SCHEMA = cv.All(
    display.FULL_DISPLAY_SCHEMA.extend(
        {
            cv.GenerateID(): cv.declare_id(FbdevDisplay),
            cv.Optional(CONF_DEVICE, default="/dev/fb0"): cv.string_strict,
            cv.Optional(
                CONF_DIMENSIONS,
                default={CONF_WIDTH: 320, CONF_HEIGHT: 480},
            ): cv.Any(
                cv.dimensions,
                cv.Schema(
                    {
                        cv.Required(CONF_WIDTH): cv.positive_int,
                        cv.Required(CONF_HEIGHT): cv.positive_int,
                    }
                ),
            ),
        }
    ),
    _add_display_metadata,
    cv.only_on(PLATFORM_HOST),
)


async def to_code(config: ConfigType) -> None:
    var = cg.new_Pvariable(config[CONF_ID])
    await display.register_display(var, config)
    cg.add(var.set_device(config[CONF_DEVICE]))
    dimensions = config[CONF_DIMENSIONS]
    if isinstance(dimensions, dict):
        width = dimensions[CONF_WIDTH]
        height = dimensions[CONF_HEIGHT]
    else:
        width, height = dimensions
    cg.add(var.set_dimensions(width, height))
