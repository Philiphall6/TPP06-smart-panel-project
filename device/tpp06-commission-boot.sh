#!/bin/sh
# TPP06_COMMISSION_V1: one trial; stock next boot until explicitly committed.
# @JOB_ROOT@ is rendered by the commissioning tool, never taken from the LAN.
ROOT='@JOB_ROOT@'
BASE=/data/tpp06-cutter

stock() {
    printf 'tuya\n' > "$BASE/mode.next" && mv "$BASE/mode.next" "$BASE/mode"
    printf 'no\n' > "$BASE/persistent_confirmed"
    sync
    exec "$BASE/S99tuya-app.stock" "$@"
}

# Shutdown/status must not erase a successful commissioning decision.
# A restart is deliberately rejected: it would bypass the one-trial gate.
case "$1" in
    start) ;;
    stop|status) exec "$ROOT/supervisor.sh" "$@" ;;
    *) echo 'Usage: S99tuya-app {start|stop|status}'; exit 1 ;;
esac
if [ -s "$ROOT/committed" ] &&
   [ "$(cat "$ROOT/committed")" = "$(cat "$ROOT/trial-boot")" ] &&
   [ "$(cat "$BASE/persistent_confirmed")" = yes ]; then
    exec "$ROOT/supervisor.sh" start
fi

# Persist the one-use claim before starting a custom process. A reset from
# this point returns to stock, even if the trial never establishes networking.
mkdir "$ROOT/attempted" 2>/dev/null || stock start
sync
cat /proc/sys/kernel/random/boot_id > "$ROOT/trial-boot" || stock start
cut -d. -f1 /proc/uptime > "$ROOT/trial-start" || stock start
printf 'no\n' > "$BASE/persistent_confirmed" || stock start
printf 'persistent\n' > "$BASE/boot_policy" || stock start
printf 'isolated\n' > "$BASE/network_mode" || stock start
printf '0\n' > "$BASE/failure_count" || stock start
printf 'esphome\n' > "$BASE/mode.next" || stock start
mv "$BASE/mode.next" "$BASE/mode" || stock start
sync
nohup sh "$ROOT/guard.sh" > "$ROOT/guard.log" 2>&1 </dev/null &
guard_pid=$!
sleep 1
kill -0 "$guard_pid" 2>/dev/null || stock start
exec "$ROOT/supervisor.sh" start
