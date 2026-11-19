"""Local storage reporting and guarded ESPHome application restart on TPP06."""
import esphome.codegen as cg

DEPENDENCIES = ["host"]
AUTO_LOAD = ["button", "text_sensor"]
CODEOWNERS = ["@Philiphall6"]
system_ns = cg.esphome_ns.namespace("tpp06_system")
