#!/bin/sh
# TPP06_MULTIBOOT_V1
# TPP06_RUNTIME_HEALTH_V1 -- optional, observe unless separately commissioned.
# BusyBox/ash supervisor.  The stock SquashFS application is never modified.

BASE=${TPP06_BASE:-/data/tpp06-cutter}
STOCK=${TPP06_STOCK_LAUNCHER:-$BASE/S99tuya-app.stock}
GRACE_SECONDS=${TPP06_GRACE_SECONDS:-60}
SESSION_SECONDS=${TPP06_SESSION_SECONDS:-0}
FAIL_LIMIT=${TPP06_FAIL_LIMIT:-2}
STOCK_READY_FILE=${TPP06_STOCK_READY_FILE:-}
ESPHOME_HEALTH_PORT=${TPP06_ESPHOME_HEALTH_PORT:-6053}
RESCUE_BINARY=${TPP06_RESCUE_BINARY:-/tuya/app/bin/tuya_factory}
DHCP_SCRIPT=${TPP06_DHCP_SCRIPT:-/usr/share/udhcpc/default.script}
SYS_ROOT=${TPP06_SYS_ROOT:-/sys}
PROC_ROOT=${TPP06_PROC_ROOT:-/proc}
FRAMEBUFFER_DEVICE=${TPP06_FRAMEBUFFER_DEVICE:-/dev/fb0}
TOUCH_DEVICE=${TPP06_TOUCH_DEVICE:-/dev/input/event1}
WATCHDOG_DEVICE=${TPP06_WATCHDOG_DEVICE:-/dev/watchdog}
PERSISTENT_CHECK_SECONDS=${TPP06_PERSISTENT_CHECK_SECONDS:-10}
NETWORK_DIR=$BASE/network
NETWORK_CONFIG=$NETWORK_DIR/wpa_supplicant.conf
WPA_PID_FILE=$BASE/wpa_supplicant.pid
DHCP_PID_FILE=$BASE/udhcpc.pid
LOG_DIR=$BASE/diagnostics
LOG_FILE=$LOG_DIR/multiboot.log
HEARTBEAT_FILE=${TPP06_HEARTBEAT_FILE:-/tmp/tpp06-health/heartbeat}

# Optional Wi-Fi editor: firmware OTA alone cannot change the boot/network policy.
wifi_edit_in_progress() { return 1; }
wifi_edit_recover() { return 0; }
wifi_edit_tick() { return 0; }

mkdir -p "$BASE" "$LOG_DIR"

log() {
    if [ -f "$LOG_FILE" ]; then
        log_size=$(wc -c <"$LOG_FILE" 2>/dev/null || echo 0)
        [ "$log_size" -gt 262144 ] && mv "$LOG_FILE" "$LOG_FILE.previous"
    fi
    echo "$(date '+%Y-%m-%dT%H:%M:%S' 2>/dev/null) $*" >>"$LOG_FILE"
}

read_value() {
    if [ -f "$1" ]; then
        sed -n '1p' "$1"
    else
        echo "$2"
    fi
}

read_count() {
    value=$(read_value "$1" 0)
    case "$value" in
        ''|*[!0-9]*) echo 0 ;;
        *) echo "$value" ;;
    esac
}

write_state() {
    # Explicit owner opt-in: no failure or stop may select Tuya on next boot.
    if [ "$1" = mode ] && [ "$2" = tuya ] && stock_fallback_disabled; then
        set -- mode esphome
    fi
    echo "$2" >"$BASE/$1.tmp" || return 1
    mv "$BASE/$1.tmp" "$BASE/$1" || return 1
    sync
}

trim_runtime_log() {
    trim_path=$1
    trim_limit=$2
    [ -f "$trim_path" ] && [ ! -L "$trim_path" ] || return 0
    # Every producer opens with >> / O_APPEND. Copy/truncate keeps its live
    # descriptor attached; rename alone would leave it growing the old inode.
    # Diagnostic lines written during the snapshot may be lost deliberately.
    trim_size=$(wc -c < "$trim_path") || return 1
    case "$trim_size" in ''|*[!0-9]*) return 1 ;; esac
    [ "$trim_size" -gt "$trim_limit" ] || return 0
    [ ! -L "$trim_path.previous" ] || return 1
    if [ -e "$trim_path.previous" ] && [ ! -f "$trim_path.previous" ]; then return 1; fi
    trim_tmp=$(mktemp "$LOG_DIR/.log-tail.XXXXXX") || return 1
    if tail -c 65536 "$trim_path" > "$trim_tmp" &&
       mv "$trim_tmp" "$trim_path.previous"; then
        : > "$trim_path"
        trim_result=$?
        chmod 600 "$trim_path" "$trim_path.previous"
        return "$trim_result"
    fi
    rm -f "$trim_tmp"
    return 1
}

maintain_runtime_logs() {
    # Retention limits checked each supervisor tick, not a hard byte quota.
    # No configuration, executable, firmware dump or unknown log is deleted.
    trim_runtime_log "$LOG_DIR/esphome.log" 1048576
    trim_runtime_log "$LOG_DIR/openhasp.log" 1048576
    trim_runtime_log "$LOG_DIR/wifi.log" 262144
    trim_runtime_log "$LOG_DIR/tuya-factory.log" 262144
}

stock_fallback_disabled() {
    # Marker presence is intentional; an empty/malformed marker must not
    # silently re-enable cloud software. Removal is a manual policy change.
    [ -e "$BASE/no_stock_fallback" ] || [ -L "$BASE/no_stock_fallback" ]
}

start_management_ssh() {
    management_ssh=${TPP06_SSH_SERVICE:-/data/tpp06-ssh/service.sh}
    if [ -x "$management_ssh" ]; then
        "$management_ssh" start >>"$LOG_DIR/ssh-start.log" 2>&1 ||
            log "ERROR SSH service start failed; check local administration"
    else
        log "WARNING SSH service not installed"
    fi
}

start_stock() {
    if stock_fallback_disabled; then
        start_management_ssh
        log "Tuya launch blocked by owner ESPHome-only policy"
        write_state active_mode esphome-maintenance
        return 1
    fi
    if [ ! -x "$STOCK" ]; then
        log "ERROR stock launcher missing: $STOCK"
        write_state active_mode stock-missing
        return 1
    fi
    if pidof voice_control_ak3760e >/dev/null 2>&1 || \
       ps | grep '[t]uya_monitor.sh' >/dev/null 2>&1; then
        log "stock already running"
        return 0
    fi
    log "starting stock Tuya monitor (Wi-Fi and 8090 rescue retained)"
    "$STOCK" start
}

stock_runtime_present() {
    pidof voice_control_ak3760e >/dev/null 2>&1 ||
        ps | grep '[t]uya_monitor.sh' >/dev/null 2>&1
}

wait_stock_ready() {
    elapsed=0
    while [ "$elapsed" -lt 45 ]; do
        if pidof voice_control_ak3760e >/dev/null 2>&1 || \
           { [ -n "$STOCK_READY_FILE" ] && [ -f "$STOCK_READY_FILE" ]; }; then
            log "stock process ready after ${elapsed}s"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    log "ERROR stock process did not become ready"
    return 1
}

network_profile_valid() {
    [ -s "$NETWORK_CONFIG" ] && \
        grep -q '^[[:space:]]*network[[:space:]]*=[[:space:]]*{' "$NETWORK_CONFIG" && \
        grep -q 'ssid[[:space:]]*=' "$NETWORK_CONFIG" && \
        { grep -q 'psk[[:space:]]*=' "$NETWORK_CONFIG" || \
          grep -q 'key_mgmt[[:space:]]*=[[:space:]]*NONE' "$NETWORK_CONFIG"; }
}

isolated_boot_prerequisites() {
    # rc.local must have initialized hardware before calling S99tuya-app.
    # Do not reload drivers, toggle GPIOs, or open/feed the watchdog here.
    if [ ! -d "$SYS_ROOT/class/net/wlan0" ] || \
       [ ! -c "$FRAMEBUFFER_DEVICE" ] || [ ! -c "$TOUCH_DEVICE" ] || \
       [ ! -c "$WATCHDOG_DEVICE" ]; then
        log "ERROR isolated boot hardware devices are not ready"
        return 1
    fi
    if [ ! -x "$DHCP_SCRIPT" ]; then
        log "ERROR DHCP event script is unavailable"
        return 1
    fi
    for program in ifconfig wpa_supplicant wpa_cli udhcpc netstat; do
        if ! command -v "$program" >/dev/null 2>&1; then
            log "ERROR isolated boot requires $program"
            return 1
        fi
    done
    watchdog_owner=no
    for watchdog_pid in $(pidof ak_watchdog 2>/dev/null); do
        case "$watchdog_pid" in ''|*[!0-9]*) continue ;; esac
        for descriptor in "$PROC_ROOT/$watchdog_pid"/fd/*; do
            if [ "$(readlink "$descriptor" 2>/dev/null)" = "$WATCHDOG_DEVICE" ]; then
                watchdog_owner=yes
            fi
        done
    done
    if [ "$watchdog_owner" != yes ]; then
        log "ERROR stock hardware watchdog owner not observed"
        return 1
    fi
    return 0
}

rescue_ports_listening() {
    # Local listeners are necessary, not proof of remote authenticated access.
    for rescue_port in 5555 8090; do
        if ! netstat -lnt 2>/dev/null | grep -q ":$rescue_port "; then
            log "ERROR local rescue listener missing port=$rescue_port"
            return 1
        fi
    done
}

start_rescue_service() {
    if pidof tuya_factory >/dev/null 2>&1; then
        return 0
    fi
    if [ ! -x "$RESCUE_BINARY" ]; then
        log "ERROR local 8090 rescue binary missing"
        return 1
    fi
    "$RESCUE_BINARY" -p 20480 >>"$LOG_DIR/tuya-factory.log" 2>&1 &
    echo $! >"$BASE/rescue.pid"
    sleep 1
    kill -0 "$(cat "$BASE/rescue.pid")" 2>/dev/null
}

stop_recorded_process() {
    pid_file=$1
    expected=$2
    pid=$(read_value "$pid_file" '')
    if [ -n "$pid" ] && [ -r "/proc/$pid/cmdline" ] && \
       tr '\000' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q "$expected"; then
        kill "$pid" 2>/dev/null
    fi
    rm -f "$pid_file"
}

cleanup_independent_services() {
    # Keep the existing management connection when ESPHome stops or fails.
    stock_fallback_disabled && return 0
    # Only stop daemons whose PID files were created by this supervisor.  A
    # stock-owned Wi-Fi process is therefore never touched accidentally.
    stop_recorded_process "$DHCP_PID_FILE" udhcpc
    stop_recorded_process "$WPA_PID_FILE" wpa_supplicant
    stop_recorded_process "$BASE/rescue.pid" tuya_factory
}

wlan_has_address() {
    # DHCP deconfig sets 0.0.0.0; do not mistake that for a usable lease.
    ifconfig wlan0 2>/dev/null | awk '
        { for (i=1; i<NF; i++) if ($i == "inet") {
            address=$(i+1); sub(/^addr:/, "", address)
            count=split(address, octets, "."); valid=(count == 4)
            for (j=1; j<=count; j++)
                if (octets[j] !~ /^[0-9]+$/ || octets[j] > 255) valid=0
            if (valid && octets[1] > 0 && octets[1] < 224 && octets[1] != 127 &&
                !(octets[1] == 169 && octets[2] == 254)) ready=1
        } }
        END { exit !ready }'
}

wifi_associated() {
    wpa_cli -iwlan0 status 2>/dev/null | grep -q '^wpa_state=COMPLETED$'
}

local_offline_policy() {
    # Opt-in only after on-site local-controls validation. Never relax the
    # networking gates of a first trial or an unconfirmed commissioning run.
    [ "$(read_value "$BASE/local_control_confirmed" no)" = yes ] &&
        [ "$(read_value "$BASE/persistent_confirmed" no)" = yes ] &&
        [ "$(read_value "$BASE/boot_policy" one-shot)" = persistent ] &&
        [ "$(read_value "$BASE/network_mode" learning)" = isolated ] &&
        [ "$SESSION_SECONDS" = 0 ]
}

start_independent_network() {
    # A soft restart in ESPHome-only mode retains our network daemons.
    # Never adopt an unverified process just because a PID file exists.
    if stock_fallback_disabled; then
        owned_network=yes
        for pair in "$WPA_PID_FILE:wpa_supplicant" "$DHCP_PID_FILE:udhcpc"; do
            saved_pid=$(read_value "${pair%:*}" '')
            case "$saved_pid" in ''|*[!0-9]*|0) owned_network=no; continue ;; esac
            if ! kill -0 "$saved_pid" 2>/dev/null ||
               ! tr '\000' '\n' < "$PROC_ROOT/$saved_pid/cmdline" 2>/dev/null |
                   grep -Eq "(^|/)${pair##*:}$"; then
                owned_network=no
            fi
        done
        [ "$owned_network" = yes ] && return 0
    fi
    if ! network_profile_valid; then
        log "ERROR independent Wi-Fi profile is unavailable or incomplete"
        return 1
    fi
    # A surviving stock address/daemon is not evidence of independent Wi-Fi.
    # Never take ownership of it or terminate it to make this check pass.
    if wlan_has_address || pidof wpa_supplicant >/dev/null 2>&1 || \
       pidof udhcpc >/dev/null 2>&1; then
        log "ERROR existing network state is not owned by this isolated session"
        return 1
    fi
    if ! command -v wpa_supplicant >/dev/null 2>&1 || \
       ! command -v udhcpc >/dev/null 2>&1 || \
       ! command -v wpa_cli >/dev/null 2>&1 || [ ! -x "$DHCP_SCRIPT" ]; then
        log "ERROR Wi-Fi tools or DHCP event script missing"
        return 1
    fi

    log "starting independent Wi-Fi (credentials remain masked)"
    if ! ifconfig wlan0 up; then
        log "ERROR cannot bring up wlan0"
        return 1
    fi
    if ! pidof wpa_supplicant >/dev/null 2>&1; then
        if ! wpa_supplicant -B -P"$WPA_PID_FILE" -Dnl80211 -iwlan0 \
            -c"$NETWORK_CONFIG" >>"$LOG_DIR/wifi.log" 2>&1; then
            cleanup_independent_services
            return 1
        fi
    fi
    if ! pidof udhcpc >/dev/null 2>&1; then
        if ! udhcpc -b -t 8 -p "$DHCP_PID_FILE" -i wlan0 -s "$DHCP_SCRIPT" \
            >>"$LOG_DIR/wifi.log" 2>&1; then
            cleanup_independent_services
            return 1
        fi
    fi

    if local_offline_policy; then
        # Both daemons have started. WPA reconnects and DHCP retries in the
        # background; an absent AP/lease must not delay local light switches.
        log "local-control policy: Wi-Fi/DHCP recovery continues in background"
        return 0
    fi

    elapsed=0
    while [ "$elapsed" -lt 45 ]; do
        if wifi_associated && wlan_has_address; then
            log "independent Wi-Fi associated with IPv4 after ${elapsed}s"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    log "ERROR independent Wi-Fi association or IPv4 did not become ready"
    cleanup_independent_services
    return 1
}

engine_command() {
    engine=$1
    case "$engine" in
        openhasp)
            ENGINE_BIN=$BASE/openhasp/openhasp
            ENGINE_ARGS="-c $BASE/openhasp"
            ;;
        esphome)
            ENGINE_BIN=$BASE/esphome/esphome
            ENGINE_ARGS=
            ;;
        *) return 1 ;;
    esac
    [ -x "$ENGINE_BIN" ]
}

increment_failure() {
    failures=$(read_count "$BASE/failure_count")
    failures=$((failures + 1))
    write_state failure_count "$failures"
    echo "$failures"
}

fallback_stock() {
    reason=$1
    if stock_fallback_disabled; then
        write_state mode esphome || log "ERROR could not retain ESPHome selection"
        start_management_ssh
        wifi_edit_recover || log "ERROR Wi-Fi recovery incomplete; keeping journal"
        # If boot failed before networking (e.g. missing engine), try once to
        # provide local administration. No retry/reboot loop, no stock launch.
        if ! stock_runtime_present; then
            start_rescue_service || log "ERROR local 8090 service unavailable"
            start_independent_network || log "ERROR network recovery needs attention"
        fi
        rm -f "$BASE/boot_pending" "$BASE/engine.pid"
        write_state active_mode esphome-maintenance
        log "ESPHOME-ONLY maintenance reason=$reason; Tuya remains disabled"
        return 0
    fi
    # Disarm persistence before stopping any service: a reset during cleanup
    # must not retry the engine that just failed.
    if ! write_state mode tuya; then
        log "ERROR cannot persist stock fallback selection"
    fi
    wifi_edit_recover || log "ERROR Wi-Fi trial recovery failed; retaining journal"
    cleanup_independent_services
    rm -f "$BASE/boot_pending" "$BASE/engine.pid"
    # A failed custom session is never retried automatically on the following
    # physical boot.  The owner must explicitly select it again.
    write_state active_mode tuya-fallback
    log "FALLBACK stock reason=$reason"
    start_stock
}

heartbeat_ready() {
    # Backward-compatible observation by default. Requiring a heartbeat is a
    # separate commissioning step after firmware AND helper validation.
    case "$(read_value "$BASE/heartbeat_policy" observe)" in
        observe) return 0 ;;
        required-v1) ;;
        *) return 1 ;;
    esac
    [ -f "$HEARTBEAT_FILE" ] && [ ! -L "$HEARTBEAT_FILE" ] || return 1
    [ "$(wc -c < "$HEARTBEAT_FILE")" -le 96 ] || return 1
    IFS=' ' read -r hb_version hb_pid hb_time hb_extra < "$HEARTBEAT_FILE" || return 1
    [ "$hb_version" = 1 ] && [ "$hb_pid" = "$engine_pid" ] && [ -z "$hb_extra" ] || return 1
    case "$hb_time" in ''|*[!0-9]*|0[0-9]*) return 1 ;; esac
    [ "${#hb_time}" -le 9 ] || return 1
    hb_now=$(cut -d. -f1 < "$PROC_ROOT/uptime") || return 1
    case "$hb_now" in ''|*[!0-9]*) return 1 ;; esac
    [ "${#hb_now}" -le 9 ] || return 1
    # Monotonic boot time: changing the wall clock via HA cannot trigger this.
    [ "$hb_time" -le "$hb_now" ] && [ "$((hb_now - hb_time))" -le 25 ]
}

persistent_health_ready() {
    kill -0 "$engine_pid" 2>/dev/null || return 1
    heartbeat_ready || return 1
    if ! local_offline_policy && ! wifi_edit_in_progress; then
        wifi_associated && wlan_has_address || return 1
    fi
    # Still check local processes/listeners; no ping, Internet or HA login.
    rescue_ports_listening &&
        netstat -lnt 2>/dev/null | grep -q ":$ESPHOME_HEALTH_PORT "
}

stop_owned_engine() {
    # Only the child this supervisor launched, never an arbitrary saved PID.
    kill "$engine_pid" 2>/dev/null
    sleep 2
    kill -KILL "$engine_pid" 2>/dev/null
    wait "$engine_pid" 2>/dev/null
}

monitor_persistent() {
    # An explicit local confirmation is required in addition to boot_policy.
    # First deployment can run unarmed until an authenticated remote check.
    unhealthy=0
    armed=no
    while kill -0 "$engine_pid" 2>/dev/null; do
        maintain_runtime_logs
        if ! wifi_edit_tick && [ -f "$NETWORK_DIR/wifi-trial/pending" ]; then
            stop_owned_engine
            fallback_stock wifi-editor-failed
            return
        fi
        if persistent_health_ready; then
            unhealthy=0
            if [ "$armed" = no ] &&
               [ "$(read_value "$BASE/persistent_confirmed" no)" = yes ]; then
                if ! write_state mode esphome; then
                    stop_owned_engine
                    fallback_stock persistent-selection-write-failed
                    return
                fi
                armed=yes
                log "persistent ESPHome rearmed after grace and local health checks"
            fi
        else
            unhealthy=$((unhealthy + 1))
            if [ "$unhealthy" -ge 3 ]; then
                write_state mode tuya
                stop_owned_engine
                increment_failure >/dev/null
                fallback_stock persistent-health-failed
                return
            fi
        fi
        sleep "$PERSISTENT_CHECK_SECONDS"
    done
    write_state mode tuya
    wait "$engine_pid"
    result=$?
    increment_failure >/dev/null
    fallback_stock "persistent-engine-exit-$result"
}

supervise() {
    stock_fallback_disabled && start_management_ssh
    if [ -f "$BASE/tpp06-wifi-edit.sh" ]; then
        . "$BASE/tpp06-wifi-edit.sh"
        if ! wifi_edit_init; then
            fallback_stock wifi-editor-recovery-failed
            return
        fi
    fi
    requested=$(read_value "$BASE/mode" tuya)
    if stock_fallback_disabled; then
        requested=esphome
        if [ "$(read_value "$BASE/boot_policy" one-shot)" != persistent ] ||
           [ "$(read_value "$BASE/network_mode" learning)" != isolated ] ||
           [ "$SESSION_SECONDS" != 0 ]; then
            fallback_stock incompatible-esphome-only-policy
            return 1
        fi
    fi
    write_state requested_mode "$requested"

    case "$requested" in
        tuya)
            rm -f "$BASE/boot_pending"
            write_state active_mode tuya
            log "requested stock mode"
            start_stock
            return
            ;;
        openhasp|esphome) ;;
        *)
            fallback_stock invalid-mode
            return
            ;;
    esac

    # Consume the custom selection before doing anything risky.  A power cut,
    # kernel watchdog or forced reset anywhere below therefore boots stock on
    # the next cycle. Default one-shot sessions never rearm. Explicit persistent
    # policy can rearm only after grace, local health checks and confirmation.
    if ! write_state mode tuya; then
        log "ERROR cannot persist stock boot selection; custom launch refused"
        start_stock
        return 1
    fi
    if stock_fallback_disabled; then
        log "ESPHome-only policy: next reboot remains ESPHome"
    else
        log "one-shot custom boot consumed; next reboot remains stock"
    fi

    boot_policy=$(read_value "$BASE/boot_policy" one-shot)
    case "$boot_policy" in
        one-shot) ;;
        persistent)
            # Permanent operation is only supported with independent Wi-Fi.
            # A bounded experiment must never rearm the next boot.
            if [ "$requested" != esphome ] ||
               [ "$(read_value "$BASE/network_mode" learning)" != isolated ] ||
               [ "$SESSION_SECONDS" != 0 ] || [ "$ESPHOME_HEALTH_PORT" -le 0 ]; then
                fallback_stock invalid-persistent-policy
                return
            fi
            ;;
        *) fallback_stock invalid-boot-policy; return ;;
    esac

    # A pending marker means that the preceding boot did not survive the
    # grace period.  Two consecutive early failures lock the next boot to the
    # original UI until the owner explicitly selects a custom mode again.
    if [ -f "$BASE/boot_pending" ]; then
        failures=$(increment_failure)
        log "unclean custom boot detected failures=$failures"
        rm -f "$BASE/boot_pending"
    else
        failures=$(read_count "$BASE/failure_count")
    fi
    if [ "$failures" -ge "$FAIL_LIMIT" ] && ! stock_fallback_disabled; then
        fallback_stock failure-limit
        return
    fi

    if ! engine_command "$requested"; then
        increment_failure >/dev/null
        fallback_stock engine-missing
        return
    fi

    network_mode=$(read_value "$BASE/network_mode" learning)
    if [ "$requested" = esphome ] && [ "$network_mode" = isolated ]; then
        # Isolated mode is a cold-start policy, not a live GUI handover. Keeping
        # Tuya/its monitor running would retain framebuffer and touch ownership.
        if stock_runtime_present; then
            log "ERROR isolated mode refused while stock UI or monitor is active"
            increment_failure >/dev/null
            fallback_stock isolated-stock-active
            return
        fi
        if ! isolated_boot_prerequisites; then
            increment_failure >/dev/null
            fallback_stock isolated-prerequisites-failed
            return
        fi
        log "using independent Wi-Fi profile"
        if ! start_rescue_service || ! start_independent_network || ! rescue_ports_listening; then
            increment_failure >/dev/null
            fallback_stock independent-network-failed
            return
        fi
    else
        # Learning/safety boot: stock owns Wi-Fi until the custom engine and
        # its API have survived the complete grace period.
        if ! start_stock; then
            increment_failure >/dev/null
            fallback_stock stock-start-failed
            return
        fi
        if ! wait_stock_ready; then
            increment_failure >/dev/null
            fallback_stock stock-ready-timeout
            return
        fi
    fi

    write_state boot_pending "$(date +%s 2>/dev/null || echo pending):$requested"
    write_state active_mode "$requested-starting"
    engine_log=$LOG_DIR/$requested.log
    maintain_runtime_logs
    log "starting custom engine=$requested grace=${GRACE_SECONDS}s"

    if [ "$requested" = esphome ]; then
        mkdir -p "$BASE/esphome/prefs"
        ESPHOME_PREFDIR="$BASE/esphome/prefs" \
            "$ENGINE_BIN" >>"$engine_log" 2>&1 &
    else
        "$ENGINE_BIN" $ENGINE_ARGS >>"$engine_log" 2>&1 &
    fi
    engine_pid=$!
    write_state engine.pid "$engine_pid"

    elapsed=0
    while [ "$elapsed" -lt "$GRACE_SECONDS" ]; do
        maintain_runtime_logs
        if ! kill -0 "$engine_pid" 2>/dev/null; then
            increment_failure >/dev/null
            fallback_stock early-exit
            return
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    if [ "$requested" = esphome ] && [ "$ESPHOME_HEALTH_PORT" -gt 0 ] && \
       command -v netstat >/dev/null 2>&1 && \
       ! netstat -lnt 2>/dev/null | grep -q ":$ESPHOME_HEALTH_PORT "; then
        kill "$engine_pid" 2>/dev/null
        increment_failure >/dev/null
        fallback_stock api-not-listening
        return
    fi

    if [ "$requested" = esphome ] && ! heartbeat_ready; then
        stop_owned_engine
        increment_failure >/dev/null
        fallback_stock heartbeat-not-ready
        return
    fi

    rm -f "$BASE/boot_pending"
    write_state failure_count 0
    # A listening API does not validate Wi-Fi without Tuya, display, touch,
    # Home Assistant authentication, or stability across a cold boot.
    # Leave both the next boot selection and network policy unchanged.
    write_state active_mode "$requested-healthy"
    log "custom engine healthy engine=$requested pid=$engine_pid"

    if [ "$boot_policy" = persistent ]; then
        monitor_persistent
        return
    fi

    if [ "$SESSION_SECONDS" -gt 0 ]; then
        while kill -0 "$engine_pid" 2>/dev/null && \
              [ "$elapsed" -lt "$SESSION_SECONDS" ]; do
            maintain_runtime_logs
            sleep 2
            elapsed=$((elapsed + 2))
        done
        if kill -0 "$engine_pid" 2>/dev/null; then
            log "bounded session expired after ${elapsed}s"
            kill "$engine_pid" 2>/dev/null
            sleep 2
            kill -KILL "$engine_pid" 2>/dev/null
            wait "$engine_pid" 2>/dev/null
            fallback_stock session-complete
            return
        fi
    fi

    wait "$engine_pid"
    result=$?
    increment_failure >/dev/null
    fallback_stock "engine-exit-$result"
}

stop_supervisor() {
    # Explicit stop leaves stock selected, including after a persistent boot.
    write_state mode tuya
    supervisor_pid=$(read_value "$BASE/supervisor.pid" '')
    engine_pid=$(read_value "$BASE/engine.pid" '')
    [ -n "$engine_pid" ] && kill "$engine_pid" 2>/dev/null
    [ -n "$supervisor_pid" ] && [ "$supervisor_pid" != "$$" ] && \
        kill "$supervisor_pid" 2>/dev/null
    cleanup_independent_services
    rm -f "$BASE/supervisor.pid" "$BASE/engine.pid" "$BASE/boot_pending"
    write_state active_mode stopped
}

supervisor_is_running() {
    # PIDs are reused across boots and after process exit. A saved number alone
    # must never suppress boot of the only display/network supervisor.
    current_boot=$(cat "$PROC_ROOT/sys/kernel/random/boot_id" 2>/dev/null)
    [ -n "$current_boot" ] || return 1
    [ "$(read_value "$BASE/supervisor.boot_id" '')" = "$current_boot" ] || return 1
    old_pid=$(read_value "$BASE/supervisor.pid" '')
    case "$old_pid" in ''|*[!0-9]*|0) return 1;; esac
    [ -r "$PROC_ROOT/$old_pid/cmdline" ] || return 1
    tr '\000' '\n' < "$PROC_ROOT/$old_pid/cmdline" | grep -Fxq "$0" || return 1
    tr '\000' '\n' < "$PROC_ROOT/$old_pid/cmdline" | grep -Fxq supervise || return 1
    kill -0 "$old_pid" 2>/dev/null
}

case "$1" in
    start)
        stock_fallback_disabled && start_management_ssh
        if supervisor_is_running; then
            log "supervisor already running pid=$old_pid"
            exit 0
        fi
        current_boot=$(cat "$PROC_ROOT/sys/kernel/random/boot_id" 2>/dev/null)
        if [ -z "$current_boot" ] || ! write_state supervisor.boot_id "$current_boot"; then
            log "ERROR cannot record supervisor boot identity"
            write_state mode tuya
            start_stock
            exit 1
        fi
        "$0" supervise >/dev/null 2>&1 &
        echo $! >"$BASE/supervisor.pid"
        ;;
    supervise) supervise ;;
    stop) stop_supervisor ;;
    restart)
        stop_supervisor
        "$0" start
        ;;
    status)
        stock_fallback_disabled && echo "fallback=local-maintenance" || echo "fallback=tuya"
        echo "requested=$(read_value "$BASE/mode" tuya)"
        echo "active=$(read_value "$BASE/active_mode" unknown)"
        echo "failures=$(read_count "$BASE/failure_count")"
        echo "network=$(read_value "$BASE/network_mode" unavailable)"
        echo "boot_policy=$(read_value "$BASE/boot_policy" one-shot)"
        echo "persistent_confirmed=$(read_value "$BASE/persistent_confirmed" no)"
        [ -f "$BASE/boot_pending" ] && echo "pending=yes" || echo "pending=no"
        ;;
    *) echo "Usage: $0 {start|stop|restart|status|supervise}"; exit 1 ;;
esac
