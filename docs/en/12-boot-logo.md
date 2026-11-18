# Boot logo — separate from OTA interface updates

The initial MOES logo is stored in the NAND partition named `logo`, not in
the ESPHome application. Normal OTA updates can change LVGL pages, icons,
menus and sleep behavior; they do not replace this early boot logo.

Status on 18 November 2026: the first Home Assistant logo booted but appeared
yellow. BGR565 video metadata was misleading: physical colour bars confirmed
RGB565 scanout. The same artwork was re-encoded as RGB565, written only to the
`logo` partition and fully read back with byte-for-byte and checksum verification.
No reboot was performed after this correction: **visual confirmation of the
blue boot logo is still pending**. Checked boot partitions, launcher and ESPHome
program were unchanged; the API and supervisor remained healthy.

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
RGB565 was confirmed by visible red/green/blue test bars despite BGR565 kernel
metadata; the monochrome original cannot distinguish RGB from BGR. Do not
generalize this geometry or pixel order to other hardware without verification.

## Offline preparation

Render the SVG as an opaque 320×480 PNG, then use Python with Pillow:

```sh
python tools/tpp06_logo.py logo-320x480.png logo-candidate.bin --pixel-order RGB565
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
