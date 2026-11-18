#!/bin/sh
# TPP06_MULTIBOOT_V1
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
NETWORK_DIR=$BASE/network
NETWORK_CONFIG=$NETWORK_DIR/wpa_supplicant.conf
WPA_PID_FILE=$BASE/wpa_supplicant.pid
DHCP_PID_FILE=$BASE/udhcpc.pid
LOG_DIR=$BASE/diagnostics
LOG_FILE=$LOG_DIR/multiboot.log

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
    echo "$2" >"$BASE/$1.tmp" || return 1
    mv "$BASE/$1.tmp" "$BASE/$1" || return 1
    sync
}

start_stock() {
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

start_independent_network() {
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
    cleanup_independent_services
    rm -f "$BASE/boot_pending" "$BASE/engine.pid"
    # A failed custom session is never retried automatically on the following
    # physical boot.  The owner must explicitly select it again.
    write_state mode tuya
    write_state active_mode tuya-fallback
    log "FALLBACK stock reason=$reason"
    start_stock
}

supervise() {
    requested=$(read_value "$BASE/mode" tuya)
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
    # the next cycle. Even a healthy session is never re-armed automatically.
    if ! write_state mode tuya; then
        log "ERROR cannot persist stock boot selection; custom launch refused"
        start_stock
        return 1
    fi
    log "one-shot custom boot consumed; next reboot remains stock"

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
    if [ "$failures" -ge "$FAIL_LIMIT" ]; then
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
    if [ -f "$engine_log" ]; then
        engine_log_size=$(wc -c <"$engine_log" 2>/dev/null || echo 0)
        [ "$engine_log_size" -gt 1048576 ] && \
            mv "$engine_log" "$engine_log.previous"
    fi
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

    rm -f "$BASE/boot_pending"
    write_state failure_count 0
    # A listening API does not validate Wi-Fi without Tuya, display, touch,
    # Home Assistant authentication, or stability across a cold boot.
    # Leave both the next boot selection and network policy unchanged.
    write_state active_mode "$requested-healthy"
    log "custom engine healthy engine=$requested pid=$engine_pid"

    if [ "$SESSION_SECONDS" -gt 0 ]; then
        while kill -0 "$engine_pid" 2>/dev/null && \
              [ "$elapsed" -lt "$SESSION_SECONDS" ]; do
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
    supervisor_pid=$(read_value "$BASE/supervisor.pid" '')
    engine_pid=$(read_value "$BASE/engine.pid" '')
    [ -n "$engine_pid" ] && kill "$engine_pid" 2>/dev/null
    [ -n "$supervisor_pid" ] && [ "$supervisor_pid" != "$$" ] && \
        kill "$supervisor_pid" 2>/dev/null
    cleanup_independent_services
    rm -f "$BASE/supervisor.pid" "$BASE/engine.pid" "$BASE/boot_pending"
    write_state active_mode stopped
}

case "$1" in
    start)
        old_pid=$(read_value "$BASE/supervisor.pid" '')
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            log "supervisor already running pid=$old_pid"
            exit 0
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
        echo "requested=$(read_value "$BASE/mode" tuya)"
        echo "active=$(read_value "$BASE/active_mode" unknown)"
        echo "failures=$(read_count "$BASE/failure_count")"
        echo "network=$(read_value "$BASE/network_mode" unavailable)"
        [ -f "$BASE/boot_pending" ] && echo "pending=yes" || echo "pending=no"
        ;;
    *) echo "Usage: $0 {start|stop|restart|status|supervise}"; exit 1 ;;
esac
