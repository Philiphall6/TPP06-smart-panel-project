"""Opt-in Linux advertisement-only proxy; not an ESP32 replacement.

Uses Linux's asynchronous MGMT ABI, available on the panel's kernel 4.4.
No BlueZ daemon, pairing, GATT, audio or Wi-Fi commands are installed.
Explicitly select this external component only in a host configuration.
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["host", "api"]
ns = cg.esphome_ns.namespace("bluetooth_proxy")
BluetoothProxy = ns.class_("BluetoothProxy", cg.Component)
CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(BluetoothProxy),
    cv.Optional("controller", default=0): cv.int_range(min=0, max=15),
}).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_controller(config["controller"]))
    cg.add_define("USE_BLUETOOTH_PROXY")
    cg.add_define("BLUETOOTH_PROXY_MAX_CONNECTIONS", 0)
    cg.add_define("BLUETOOTH_PROXY_ADVERTISEMENT_BATCH_SIZE", 4)
