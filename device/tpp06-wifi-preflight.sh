#!/bin/sh
# Read-only commissioning checks. Never source the supervisor/helper here:
# their initialization can recover a pending transaction and write files.
# Success means prerequisites only, NOT a validated network migration.
BASE=${TPP06_BASE:-/data/tpp06-cutter}
PROC_ROOT=${TPP06_PROC_ROOT:-/proc}
failed=0
check() {
    label=$1
    shift
    if "$@"; then printf 'OK %s\n' "$label"
    else printf 'BLOCKED %s\n' "$label"; failed=1; fi
}
value_is() {
    [ ! -L "$BASE/$1" ] && [ -f "$BASE/$1" ] &&
        [ "$(head -n 1 "$BASE/$1")" = "$2" ]
}
private_profile() {
    [ ! -L "$BASE/network/wpa_supplicant.conf" ] &&
        [ -s "$BASE/network/wpa_supplicant.conf" ] &&
        LC_ALL=C ls -ldn "$BASE/network/wpa_supplicant.conf" |
            awk '$1=="-rw-------" && $3=="0" {ok=1} END {exit !ok}'
}
owned_daemon() {
    name=$1
    [ ! -L "$BASE/$name.pid" ] && [ -f "$BASE/$name.pid" ] || return 1
    pid=$(head -n 1 "$BASE/$name.pid")
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    [ "$(cat "$PROC_ROOT/$pid/comm" 2>/dev/null)" = "$name" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    # Reject additional competing daemons; do not terminate them.
    [ "$(pidof "$name")" = "$pid" ] || return 1
    if [ "$name" = wpa_supplicant ]; then
        tr '\000' '\n' < "$PROC_ROOT/$pid/cmdline" |
            grep -Fxq -- "-c$BASE/network/wpa_supplicant.conf" || return 1
        tr '\000' '\n' < "$PROC_ROOT/$pid/cmdline" | grep -Fxq -- '-iwlan0'
    else
        tr '\000' '\n' < "$PROC_ROOT/$pid/cmdline" |
            awk 'last=="-i" && $0=="wlan0" {ok=1} {last=$0} END {exit !ok}'
    fi
}
wpa_ready() { [ "$(wpa_cli -iwlan0 ping 2>/dev/null)" = PONG ]; }
associated() { wpa_cli -iwlan0 status 2>/dev/null | grep -Fxq 'wpa_state=COMPLETED'; }
no_trial() { [ ! -e "$BASE/network/wifi-trial/pending" ]; }
no_ota() { [ ! -e "$BASE/esphome/esphome.ota.new" ]; }

if [ "$#" != 2 ]; then
    echo 'Usage: sh tpp06-wifi-preflight.sh CANDIDATE_SUPERVISOR CANDIDATE_HELPER'
    exit 2
fi
check root test "$(id -u)" = 0
check candidate-supervisor-syntax sh -n "$1"
check candidate-helper-syntax sh -n "$2"
check helper-hook grep -Fq '. "$BASE/tpp06-wifi-edit.sh"' "$1"
check healthy value_is active_mode esphome-healthy
check persistent value_is boot_policy persistent
check confirmed value_is persistent_confirmed yes
check independent-network value_is network_mode isolated
check private-profile private_profile
check stock-launcher test -x "$BASE/S99tuya-app.stock"
check no-pending-trial no_trial
check no-ota no_ota
check owned-wpa owned_daemon wpa_supplicant
check owned-dhcp owned_daemon udhcpc
check wpa-control wpa_ready
check associated associated
if value_is local_control_confirmed yes; then
    echo 'INFO offline-policy-flag-present-not-a-hardware-test'
else
    echo 'LIMIT offline-box-replacement-not-commissioned'
fi
if [ "$failed" != 0 ]; then
    echo 'RESULT blocked-no-changes-made'
    exit 1
fi
echo 'RESULT prerequisites-only-no-activation-no-network-change'
