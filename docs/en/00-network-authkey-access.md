# Phase 0 — Recover the password over the network

## Goal

Read the device-specific `AUTHKEY` from the panel's local product-test service and derive its `root`/ADB password without opening the enclosure, using UART, or desoldering the NAND.

This method was discovered and published as **TPPwned** by [t0m1o1](https://github.com/t0m1o1). The implementation in this repository was reconstructed and verified on our own TPP06 from the firmware protocol.

Only use this tool on a panel you own or are explicitly authorised to test.

## How it works

The panel exposes its product-test service on TCP port `8090`. Its frames use this layout:

```text
55 AA | version | command | length (2 bytes) | data | checksum
```

The checksum is the sum of all preceding bytes truncated to one byte.

The tool uses two read-only operations:

1. command `0x00` with `{"action":"enter"}` temporarily enables the in-memory test context;
2. command `0x04` reads the configuration containing the `AUTHKEY`.

The temporary state is cleared by a reboot. The script sends no persistent write, reboot, or OTA command.

The password is derived as follows:

```text
root_password = last 8 hexadecimal characters of MD5(AUTHKEY)
```

## Usage

First check the panel address and port:

```bash
ping 192.0.2.1
nc -vz 192.0.2.1 8090
```

Then run the tool from the repository root:

```bash
python3 tools/tpp06_authkey_reader.py 192.0.2.1
```

Example output:

```text
Panel: 192.0.2.1:8090
AUTHKEY: abcd…wxyz
Root/ADB password: 1234abcd
No persistent write or reboot was requested.
```

The `AUTHKEY` is masked by default. For a local intervention only, its full value can be shown with:

```bash
python3 tools/tpp06_authkey_reader.py 192.0.2.1 --show-authkey
```

## Security

The raw response may also contain `uuid`, `pskKey`, `ap_ssid`, and `ap_pwd`. The script never prints them. Never publish a raw response, an `AUTHKEY`, a password, a dump, or Wi-Fi credentials in an issue or commit.

If port `8090` is unavailable, confirm the IP address, ensure the panel is on the same LAN, and check whether its firmware still exposes the product-test service.
