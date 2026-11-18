import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tpp06_api_check import probe


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    def client(self):
        return SimpleNamespace(
            connect=AsyncMock(), disconnect=AsyncMock(),
            device_info=AsyncMock(return_value=SimpleNamespace(
                esphome_version="test", mac_address="private", name="private")),
            list_entities_services=AsyncMock(return_value=([object()], [])),
        )

    async def test_reads_protocol_without_claiming_ha_connection(self):
        client = self.client()
        report = await probe(client)
        self.assertEqual(report["api_protocol"], "ok")
        self.assertEqual(report["entity_count"], 1)
        self.assertEqual(report["home_assistant_link"], "not_verified")
        self.assertNotIn("private", str(report))
        client.connect.assert_awaited_once_with(login=True, log_errors=False)
        client.disconnect.assert_awaited_once()

    async def test_disconnect_on_error(self):
        client = self.client()
        client.device_info.side_effect = ValueError("bad response")
        with self.assertRaises(ValueError):
            await probe(client)
        client.disconnect.assert_awaited_once()

    async def test_timeout_closes_partial_connection(self):
        client = self.client()
        async def stalled(**kwargs):
            await asyncio.sleep(30)
        client.connect.side_effect = stalled
        with self.assertRaises(TimeoutError):
            await probe(client, timeout=0.02)
        client.disconnect.assert_awaited_once()
