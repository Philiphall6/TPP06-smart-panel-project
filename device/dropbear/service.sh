#!/bin/sh
# Manual service only: no boot, Wi-Fi, relay, or recovery modifications.
set -eu
BASE=/data/tpp06-ssh
PIDFILE=/var/run/tpp06-dropbear.pid
running() {
    test -s "$PIDFILE" || return 1
    read -r daemon_pid < "$PIDFILE"
    case "$daemon_pid" in ''|*[!0-9]*) return 1;; esac
    test "$(readlink /proc/"$daemon_pid"/exe 2>/dev/null)" = \
        "$(readlink -f "$BASE/dropbearmulti")"
}
case "${1:-status}" in
start)
    running && exit 0
    test -d /sys/class/net/wlan0
    test -s "$BASE/host_ed25519"
    if netstat -lnt | grep -q ':22 '; then
        echo 'Port 22 already occupied; nothing changed.' >&2
        exit 1
    fi
    umask 077
    "$BASE/dropbearmulti" dropbear -E -m -l wlan0 -p 0.0.0.0:22 \
        -r "$BASE/host_ed25519" -P "$PIDFILE" -I 900 -K 60 -T 3 -W 32768 \
        </dev/null >/tmp/tpp06-dropbear.log 2>&1
    ;;
stop)
    if running; then kill "$daemon_pid"; fi
    ;;
status)
    if running; then echo 'SSH running'; else echo 'SSH stopped'; exit 1; fi
    ;;
*) echo 'Usage: service.sh start|stop|status' >&2; exit 2;;
esac
