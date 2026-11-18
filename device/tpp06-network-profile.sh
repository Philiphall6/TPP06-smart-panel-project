#!/bin/sh
# Sourced helper: select the configuration actually used by wlan0's supplicant.
# Never emit credentials or modify the network. /etc/wpa_supplicant.conf may
# only be a template; never silently use it when the running process is unknown.
tpp06_profiles_equal() (
    # Some panel BusyBox builds have no cmp. Fail closed if hashing fails;
    # distinguish a mismatch (1) from an unavailable comparison (2).
    [ "$#" = 2 ] || return 2
    [ -f "$1" ] && [ -f "$2" ] || return 1
    [ -r "$1" ] && [ -r "$2" ] || return 2
    if command -v sha256sum >/dev/null 2>&1; then
        tpp06_hash=sha256sum; tpp06_hash_length=64
    elif command -v md5sum >/dev/null 2>&1; then
        tpp06_hash=md5sum; tpp06_hash_length=32
    else
        return 2
    fi
    tpp06_left=$($tpp06_hash < "$1") || return 2
    tpp06_right=$($tpp06_hash < "$2") || return 2
    tpp06_left=${tpp06_left%% *}
    tpp06_right=${tpp06_right%% *}
    case "$tpp06_left:$tpp06_right" in *[!0-9a-f:]*) return 2 ;; esac
    [ "${#tpp06_left}" = "$tpp06_hash_length" ] || return 2
    [ "${#tpp06_right}" = "$tpp06_hash_length" ] || return 2
    [ "$tpp06_left" = "$tpp06_right" ]
)

tpp06_active_wifi_profile() (
    tpp06_proc=${TPP06_WIFI_PROC_ROOT:-/proc}
    tpp06_pid=$(pidof wpa_supplicant 2>/dev/null) || return 1
    case "$tpp06_pid" in ''|*[!0-9]*) return 1 ;; esac
    tpp06_args=$tpp06_proc/$tpp06_pid/cmdline
    [ -r "$tpp06_args" ] || return 1
    [ "$(cat "$tpp06_proc/$tpp06_pid/comm" 2>/dev/null)" = wpa_supplicant ] || return 1
    tpp06_interface=$(tr '\000' '\n' < "$tpp06_args" | awk '
        want { print; want=0; next }
        $0 == "-i" { want=1; next }
        /^-i./ { print substr($0,3) }')
    [ "$tpp06_interface" = wlan0 ] || return 1
    tpp06_config=$(tr '\000' '\n' < "$tpp06_args" | awk '
        want { print; want=0; next }
        $0 == "-c" { want=1; next }
        /^-c./ { print substr($0,3) }')
    # A single absolute path. Reject control characters/multiple results.
    case "$tpp06_config" in /*) ;; *) return 1 ;; esac
    case "$tpp06_config" in *[!a-zA-Z0-9_./-]*) return 1 ;; esac
    [ -s "$tpp06_config" ] && [ -r "$tpp06_config" ] || return 1
    [ "$(grep -c '^[[:space:]]*network[[:space:]]*=[[:space:]]*{' "$tpp06_config")" = 1 ] || return 1
    [ "$(grep -c '^[[:space:]]*ssid[[:space:]]*=' "$tpp06_config")" = 1 ] || return 1
    grep -Eq '^[[:space:]]*(psk[[:space:]]*=|key_mgmt[[:space:]]*=[[:space:]]*NONE)' "$tpp06_config" || return 1
    # Refuse a process change during selection; this is not a connectivity test.
    [ "$(pidof wpa_supplicant 2>/dev/null)" = "$tpp06_pid" ] || return 1
    printf '%s\n' "$tpp06_config"
)
