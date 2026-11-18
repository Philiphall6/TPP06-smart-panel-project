#!/usr/bin/env python3
"""Read-only ESPHome protocol check; never uploads, reboots or calls actions."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any


async def probe(client: Any, timeout: float = 15) -> dict[str, object]:
    try:
        async with asyncio.timeout(timeout):
            await client.connect(login=True, log_errors=False)
            info = await client.device_info()
            entities, services = await client.list_entities_services()
            # Deliberately exclude MAC, network details, entity names and keys.
            return {
                "api_protocol": "ok",
                "esphome_version": info.esphome_version,
                "entity_count": len(entities),
                "service_count": len(services),
                "home_assistant_link": "not_verified",
                "display_and_touch": "not_verified",
            }
    finally:
        # Also close a partially established connection following a timeout.
        try:
            await asyncio.wait_for(client.disconnect(), timeout=5)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=6053)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if args.timeout <= 0 or not 1 <= args.port <= 65535:
        parser.error("timeout must be positive and port must be 1..65535")
    try:
        from aioesphomeapi import APIClient
    except ImportError:
        parser.exit(2, "Install aioesphomeapi in your Python environment first.\n")
    # Secrets are optional environment variables, never CLI arguments/output.
    logging.getLogger("aioesphomeapi").setLevel(logging.CRITICAL)

    async def run() -> dict[str, object]:
        client = APIClient(
            args.host, args.port,
            password=os.environ.get("ESPHOME_API_PASSWORD"),
            noise_psk=os.environ.get("ESPHOME_API_KEY"),
            client_info="TPP06 read-only diagnostic",
        )
        return await probe(client, args.timeout)

    try:
        report = asyncio.run(run())
    except Exception as error:
        # Library messages can contain local details; only expose the class.
        print(json.dumps({"api_protocol": "failed", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
