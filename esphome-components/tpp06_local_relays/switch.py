import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome.components import switch
from esphome.const import CONF_ID, CONF_RESTORE_MODE
from . import LocalRelays, ns

DEPENDENCIES = ["tpp06_local_relays"]
RelaySwitch = ns.class_("RelaySwitch", switch.Switch)


def pulse_duration(value):
    value = cv.positive_time_period_milliseconds(value)
    if value.total_milliseconds != 0 and not 100 <= value.total_milliseconds <= 60000:
        raise cv.Invalid("Use 0s for a latching switch, or 100ms..60s for a pulse")
    return value

CONFIG_SCHEMA = switch.switch_schema(
    RelaySwitch, block_inverted=True, default_restore_mode="DISABLED"
).extend({
    cv.GenerateID("relays_id"): cv.use_id(LocalRelays),
    cv.Required("channel"): cv.int_range(min=1, max=3),
    cv.Optional("pulse_duration", default="0s"): pulse_duration,
    cv.Optional(CONF_RESTORE_MODE, default="DISABLED"): cv.enum(
        {"DISABLED": switch.SwitchRestoreMode.SWITCH_RESTORE_DISABLED}, upper=True),
})


def validate_channels(config):
    peers = [item for item in fv.full_config.get().get("switch", [])
             if item.get("platform") == "tpp06_local_relays"
             and str(item["relays_id"]) == str(config["relays_id"])]
    channels = [item["channel"] for item in peers]
    if sorted(channels) != [1, 2, 3]:
        raise cv.Invalid("Declare exactly one switch for each local channel: 1, 2, 3")


FINAL_VALIDATE_SCHEMA = validate_channels


async def to_code(config):
    var = await switch.new_switch(config)
    parent = await cg.get_variable(config["relays_id"])
    cg.add(parent.set_relay(config["channel"] - 1, var))
    cg.add(parent.set_pulse_duration(config["channel"] - 1, config["pulse_duration"].total_milliseconds))
