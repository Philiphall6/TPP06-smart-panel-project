# Boot logo — separate from OTA interface updates

The initial MOES logo is stored in the NAND partition named `logo`, not in
the ESPHome application. Normal OTA updates can change LVGL pages, icons,
menus and sleep behavior; they do not replace this early boot logo.

Reference-panel status: Home Assistant logo programmed and fully read back,
followed by one successful software reboot and over two minutes of encrypted
API checks without a process change or another boot. The supervisor confirmed
`esphome-healthy`, with Wi-Fi and recovery access available. Visual appearance,
colour and orientation still need on-site confirmation. The application was
V4 during that logo trial; [V5](11-interface-v5.md) was subsequently installed
and checked separately.

## Artwork and format

The [prepared artwork](../images/tpp06-home-assistant-boot.svg) contains only
the official Home Assistant mark, centered on black, without an ESPHome logo.
Source: [home-assistant/assets](https://github.com/home-assistant/assets/tree/8d4090f492d60841a0db4b3b26585184b29333ba),
`logo/home-assistant-logo.zip`, `home-assistant-logomark-color-on-light.svg`.
Paths are unchanged; uniform scaling and a black background were added.
Open Home Foundation trademark; asset licensed CC BY-NC-SA 4.0. This community
project is not an official or certified Home Assistant product.

On the reference panel only: 320×480 little-endian 16-bit pixels, 307,200
payload bytes, padded with `0xff` to 512 KiB; 128 KiB erase blocks and 2 KiB
pages. The original bytes exactly match the dumped MOES PNG after conversion.
BGR565 was selected from the live LCD device-tree format and video driver;
the monochrome original cannot distinguish RGB from BGR. Do not generalize
this geometry to other hardware.

## Offline preparation

Render the SVG as an opaque 320×480 PNG, then use Python with Pillow:

```sh
python tools/tpp06_logo.py logo-320x480.png logo-candidate.bin --pixel-order BGR565
```

The codec has no device connection, erase, programming or reboot feature.
It rejects output paths under `/dev`, symlinks and existing files. **Do not
upload this partition image as an ESPHome OTA firmware.**

## Programming precautions

The private procedure is device-specific, not a universal installer; this
document deliberately provides no automatic erase script. Resolve MTD by
partition **name**, validate geometry and ECC/bad-block counters, retain two
matching original reads off-device, verify tools and files, and have stable
power and local recovery available. Program only the logo partition using
appropriate NAND/ECC handling, then compare the complete readback before
rebooting.

**Observed failure:** an `armv5l` binary can contain floating-point instructions
unsupported by the SoC. Successful help output, NAND reads and QEMU execution
do not validate the write path. During this test a hard-float tool failed
after erasing; a compatible tool restored the original MOES logo, followed
by a complete byte-for-byte readback without rebooting. Checked application,
launcher and SPL/U-Boot/DTB contents were unchanged. Do not reuse the rejected
tool.

Application multiboot recovery cannot protect against incorrect NAND writes,
power loss during erasure or bootloader damage. Hardware backups and logs
remain private.
