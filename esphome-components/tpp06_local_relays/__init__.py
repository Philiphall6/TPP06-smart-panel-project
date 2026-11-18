"""Experimental local relay control. Disabled until explicitly validated on site."""
import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome.const import CONF_ID, PLATFORM_HOST

DEPENDENCIES = ["host"]
AUTO_LOAD = ["switch"]
CODEOWNERS = ["@Philiphall6"]
ns = cg.esphome_ns.namespace("tpp06_local_relays")
LocalRelays = ns.class_("LocalRelays", cg.Component)


def key_map(value):
    value = cv.ensure_list(cv.int_range(min=1, max=3))(value)
    if sorted(value) != [1, 2, 3]:
        raise cv.Invalid("key_map must contain channels 1, 2, 3 exactly once (F1, F2, F3 order)")
    return value


CONFIG_SCHEMA = cv.All(cv.Schema({
    cv.GenerateID(): cv.declare_id(LocalRelays),
    cv.Optional("control_enabled", default=False): cv.boolean,
    cv.Optional("input_device", default="/dev/input/event0"): cv.string_strict,
    cv.Optional("key_map", default=[1, 2, 3]): key_map,
    cv.Optional("indicator_mode", default="follow_relay"): cv.one_of("follow_relay", "off", lower=True),
}).extend(cv.COMPONENT_SCHEMA), cv.only_on(PLATFORM_HOST))


def validate_no_network_reboot(config):
    for component in ("api", "mqtt"):
        settings = fv.full_config.get().get(component)
        if settings is not None and settings["reboot_timeout"].total_milliseconds != 0:
            raise cv.Invalid(f"Local relay operation requires {component}.reboot_timeout: 0s")


FINAL_VALIDATE_SCHEMA = validate_no_network_reboot


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_control_enabled(config["control_enabled"]))
    cg.add(var.set_input_device(config["input_device"]))
    cg.add(var.set_indicators_follow_relay(config["indicator_mode"] == "follow_relay"))
    for index, channel in enumerate(config["key_map"]):
        cg.add(var.set_key_channel(index, channel - 1))
