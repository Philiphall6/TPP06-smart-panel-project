#!/usr/bin/env python3
"""Upload a tested TPP06 overlay through the local product-test service.

This tool intentionally does not reboot the panel. Power-cycle it only after
the upload has completed successfully.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys


MAGIC = b"\x55\xaa"
DEFAULT_PORT = 8090
CHUNK_SIZE = 4096


def build_frame(command: int, payload: bytes = b"") -> bytes:
    if not 0 <= command <= 0xFF:
        raise ValueError("command must fit in one byte")
    if len(payload) > 0xFFFF:
        raise ValueError("payload is too large for one frame")
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


def exchange(
    connection: socket.socket, command: int, payload: bytes = b""
) -> bytes:
    connection.sendall(build_frame(command, payload))
    response_command, response_payload = receive_frame(connection)
    if response_command != command:
        raise ValueError(
            f"unexpected response: command 0x{response_command:02x}, "
            f"expected 0x{command:02x}"
        )
    return response_payload


def response_is_success(payload: bytes) -> bool:
    if not payload:
        return True
    try:
        response = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(response, dict) and response.get("ret") is True


def upload(host: str, port: int, timeout: float, archive: Path) -> None:
    content = archive.read_bytes()
    digest = hashlib.md5(content).hexdigest()  # Protocol field, not a security check.
    metadata = json.dumps(
        {"fileType": "bootpicture", "size": len(content), "md5": digest},
        separators=(",", ":"),
    ).encode("utf-8")

    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.settimeout(timeout)

        response = exchange(connection, 0x00, b'{"action":"enter"}')
        if not response_is_success(response):
            raise RuntimeError(f"product-test entry failed: {response!r}")

        response = exchange(connection, 0x40, metadata)
        if not response_is_success(response):
            raise RuntimeError(f"upload initialization failed: {response!r}")

        sent = 0
        for offset in range(0, len(content), CHUNK_SIZE):
            chunk = content[offset : offset + CHUNK_SIZE]
            response = exchange(connection, 0x41, chunk)
            if not response_is_success(response):
                raise RuntimeError(
                    f"panel rejected data at offset {offset}: {response!r}"
                )
            sent += len(chunk)
            print(f"\rUpload: {sent}/{len(content)} bytes", end="", flush=True)
        print()

        response = exchange(connection, 0x42)
        if not response_is_success(response):
            raise RuntimeError(f"upload finalization failed: {response!r}")

    print(f"Upload accepted by {host}:{port} (MD5 protocol: {digest}).")
    print("Now power-cycle the panel. Do not interrupt power before this message.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload an experimental TPP06 overlay through TCP port 8090."
    )
    parser.add_argument("host", help="panel IPv4 address or hostname")
    parser.add_argument("archive", type=Path, help="release .tar.gz payload")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--i-understand-this-overwrites-customization",
        action="store_true",
        help="required acknowledgement for the persistent write",
    )
    args = parser.parse_args()

    if not args.i_understand_this_overwrites_customization:
        parser.error(
            "the upload replaces /data/app and /data/customize; read the guide, "
            "then add --i-understand-this-overwrites-customization"
        )
    if not args.archive.is_file():
        parser.error(f"archive not found: {args.archive}")
    if not args.archive.name.endswith(".tar.gz"):
        parser.error("the payload must be the unmodified release .tar.gz archive")

    print("WARNING: experimental persistent modification for a verified TPP06 firmware only.")
    print("The panel must remain powered and connected until the upload completes.")
    try:
        upload(args.host, args.port, args.timeout, args.archive)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
