"""Compatibility bridge for ESPHome versions without host.use_address.

No installed ESPHome files are modified. Only configurations explicitly using
this host component and its use_address option override the upstream getter.
StorageJSON and the CLI then consume the same address. Remove this bridge
when upstream CORE.address supports host addresses natively.
"""

import sys

from esphome import compiled_config
from esphome.core import CORE, EsphomeCore


def _disable_host_fast_cache() -> None:
    # upload/logs can otherwise skip importing external components entirely,
    # bypassing this bridge. Revalidate these host configs on every invocation;
    # other platforms retain their normal fast cache. The public storage
    # sidecar (address/build metadata consumed by Builder) is never removed.
    original = compiled_config.save_compiled_config
    if getattr(original, "_tpp06_host_address", False) is True:
        return

    def save(config):
        host = config.get("host")
        if isinstance(host, dict) and host.get("use_address"):
            compiled_config.compiled_config_path(CORE.config_filename).unlink(missing_ok=True)
            return
        return original(config)

    save._tpp06_host_address = True
    compiled_config.save_compiled_config = save
    # writer may already have imported the function before schema validation.
    writer = sys.modules.get("esphome.writer")
    if writer is not None and getattr(writer, "save_compiled_config", None) is original:
        writer.save_compiled_config = save


def install_address_bridge() -> None:
    _disable_host_fast_cache()
    original = EsphomeCore.address
    if getattr(original.fget, "_tpp06_host_address", False):
        return

    def address(core):
        if core.config is not None:
            host = core.config.get("host")
            if isinstance(host, dict) and host.get("use_address"):
                return host["use_address"]
        return original.__get__(core, type(core))

    address._tpp06_host_address = True
    EsphomeCore.address = property(address, doc=original.__doc__)
