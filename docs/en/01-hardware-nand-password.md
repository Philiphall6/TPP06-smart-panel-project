# Phase 1 — Hardware, NAND, and authorised password recovery

## Purpose

Establish a reliable hardware baseline before any software change: identify the components, produce a stable NAND backup, and keep sensitive information outside Git.

## Identified hardware

| Item | Identification |
| --- | --- |
| Board | `TPP06-Z-AK V1.0.2` |
| Processor | Anyka `AK3761EE128` |
| NAND | GigaDevice `GD5F1GM7UEYIG` |
| NAND package | WSON-8 / QFN-8, 8 × 6 mm, 3.3 V |
| Programmer | XGecu T48 with a 8 × 6 mm QFN/WSON-8 adapter |

![T48 programmer](../../media/lecture-nand/01-programmateur-t48.jpg)

## NAND read

1. Disconnect the panel and the T48 before each physical change.
2. Read the chip out of circuit using the 8 × 6 mm adapter.
3. Confirm the chip ID before reading.
4. Make several reads and compare them locally.
5. Never use `Erase` or `Program` to create a backup.
6. Re-solder the chip with pin 1 in the correct corner, then validate the boot sequence.

![Verified read in XGPro](../../media/lecture-nand/10-lecture-verifiee.png)

The binary backup remains private and outside GitHub.

## Authorised password search

On the two observed panels, the relevant hash was found by searching the raw NAND dump for `root:` or `root`. The MD5crypt hash beginning with `$1$`, found in SquashFS, was not the relevant lead for that method.

This observation does not guarantee the same outcome on another board. Do not publish the hash, password, dump, keys, or identifiers.

## Phase outcome

- Local NAND backup validated.
- Panel reassembled and booted.
- Secrets stored only in private storage.
