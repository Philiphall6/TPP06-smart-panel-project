#!/bin/sh
# Rendered by the assistant with validated fixed-path/hex substitutions only.
# No reboot. Only /dev/mtd3 is writable; all other partitions are read-only.
set -eu
umask 077
stage='@STAGE@'
original='@ORIGINAL@'
candidate='@CANDIDATE@'
dirty=no
success=no
matches() { test "$(md5sum "$1" | awk '{print $1}')" = "$2"; }
geometry() {
    test "$(cat /sys/class/mtd/mtd3/name)" = logo &&
    test "$(cat /sys/class/mtd/mtd3/type)" = nand &&
    test "$(cat /sys/class/mtd/mtd3/size)" = 524288 &&
    test "$(cat /sys/class/mtd/mtd3/erasesize)" = 131072 &&
    test "$(cat /sys/class/mtd/mtd3/writesize)" = 2048 &&
    test "$(cat /sys/class/mtd/mtd3/bad_blocks)" = 0 &&
    test "$(cat /sys/class/mtd/mtd3/ecc_failures)" = 0
}
read_verify() {
    "$stage/nandtool" nanddump -f "$stage/readback.bin" /dev/mtd3ro &&
    matches "$stage/readback.bin" "$1" && matches /dev/mtd3ro "$1"
}
restore_original() {
    matches "$stage/logo.before" "$original" &&
    /bin/busybox flash_eraseall /dev/mtd3 &&
    "$stage/nandtool" nandwrite /dev/mtd3 "$stage/logo.before" &&
    sync && read_verify "$original"
}
finish() {
    status=$?
    trap - 0 HUP INT TERM
    if [ "$success" != yes ]; then
        if [ "$dirty" = yes ]; then
            if restore_original; then
                echo RESTORED_ORIGINAL > "$stage/logo-result"
            else
                echo RECOVERY_REQUIRED > "$stage/logo-result"
            fi
        else
            echo PREFLIGHT_FAILED > "$stage/logo-result"
        fi
    fi
    exit "$status"
}
mkdir "$stage/logo-once" # Never replay even if the result was lost.
trap finish 0
trap 'exit 130' HUP INT TERM
geometry
test ! -e /data/tpp06-cutter/esphome/esphome.ota.new
matches /bin/busybox fedb2a75c046de80ed5413cfb129387c
matches "$stage/nandtool" a64974c6ab29d50735cf9d027358ae3a
matches "$stage/logo.before" "$original"
matches "$stage/candidate.bin" "$candidate"
read_verify "$original"
md5sum /dev/mtd0ro /dev/mtd1ro /dev/mtd4ro /dev/mtd5ro \
    /etc/init.d/S99tuya-app > "$stage/protected.md5"
if [ -f /data/tpp06-cutter/esphome/esphome ]; then
    md5sum /data/tpp06-cutter/esphome/esphome >> "$stage/protected.md5"
fi
dirty=yes
/bin/busybox flash_eraseall /dev/mtd3
"$stage/nandtool" nandwrite /dev/mtd3 "$stage/candidate.bin"
sync
read_verify "$candidate"
geometry
md5sum -c "$stage/protected.md5"
success=yes
echo VERIFIED_CANDIDATE > "$stage/logo-result"
