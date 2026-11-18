#!/bin/sh
# Independent deadline if the PC disconnects or API authentication fails.
ROOT='@JOB_ROOT@'
BASE=/data/tpp06-cutter
boot=$(cat /proc/sys/kernel/random/boot_id) || exit 1
start=$(cat "$ROOT/trial-start") || exit 1
case "$start" in ''|*[!0-9]*) exit 1;; esac
elapsed=0
while [ "$elapsed" -lt 600 ]; do
    if [ "$(cat "$ROOT/committed" 2>/dev/null)" = "$boot" ] &&
       [ "$(cat "$ROOT/trial-boot")" = "$boot" ] &&
       [ "$(cat "$BASE/persistent_confirmed")" = yes ] &&
       [ "$(cat "$BASE/mode")" = esphome ]; then
        echo committed-guard-disarmed
        exit 0
    fi
    sleep 5
    now=$(cut -d. -f1 /proc/uptime) || break
    case "$now" in ''|*[!0-9]*) break;; esac
    elapsed=$((now - start))
done
# The client refuses confirmation after 480s, leaving a two-minute margin.
mkdir "$ROOT/expired" 2>/dev/null || exit 1
printf 'tuya\n' > "$BASE/mode.guard" || exit 1
mv "$BASE/mode.guard" "$BASE/mode" || exit 1
printf 'no\n' > "$BASE/persistent_confirmed" || exit 1
sync
echo unconfirmed-trial-returning-to-stock
/sbin/reboot
