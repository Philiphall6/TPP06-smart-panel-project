#!/bin/sh
# Sourced by the multiboot supervisor, NOT an independently executable installer.
# No credential is evaluated as shell code or printed. Runtime mailbox is root-only.
# Installation/activation of this helper is separate from firmware OTA.
WIFI_EDIT_RUN=${TPP06_WIFI_EDIT_RUN:-/tmp/tpp06-wifi-editor}
WIFI_EDIT_TRIAL=$NETWORK_DIR/wifi-trial

wifi_edit_now() { cut -d. -f1 "$PROC_ROOT/uptime"; }
wifi_edit_status() {
    printf '%s\n%s\n' "$1" "${wifi_edit_token:-none}" > "$WIFI_EDIT_RUN/status.new" &&
        mv "$WIFI_EDIT_RUN/status.new" "$WIFI_EDIT_RUN/status"
}

wifi_scan_status() {
    printf '%s\n%s\n' "$1" "${wifi_scan_token:-none}" > "$WIFI_EDIT_RUN/scan-status.new" &&
        mv "$WIFI_EDIT_RUN/scan-status.new" "$WIFI_EDIT_RUN/scan-status"
}
wifi_scan_stop() {
    [ "${wifi_scan_phase:-idle}" != scanning ] || wifi_scan_status refused
    wifi_scan_phase=idle
    rm -f "$WIFI_EDIT_RUN/scan-request" "$WIFI_EDIT_RUN/scan-results"
}
wifi_scan_tick() {
    # No reconfiguration, DHCP signal or persistent profile write here.
    # The kernel may briefly leave the serving channel during an active scan.
    if [ -e "$BASE/esphome/esphome.ota.new" ] || [ -f "$WIFI_EDIT_TRIAL/pending" ]; then
        wifi_scan_stop; return 0
    fi
    if [ "${wifi_scan_phase:-idle}" = scanning ]; then
        [ "$now" -ge "$wifi_scan_after" ] || return 0
        # SCAN_RESULTS is a cache, not proof of CTRL-EVENT-SCAN-RESULTS. Label
        # it accordingly in the UI; never use discovery to confirm a connection.
        wpa_cli -iwlan0 scan_results 2>/dev/null | head -c 12000 > "$WIFI_EDIT_RUN/scan-raw"
        if head -n 1 "$WIFI_EDIT_RUN/scan-raw" | grep -q '^bssid / frequency / signal level / flags / ssid'; then
            { printf '%s\n' "$wifi_scan_token"; cat "$WIFI_EDIT_RUN/scan-raw"; } > "$WIFI_EDIT_RUN/scan-results.new" &&
              mv "$WIFI_EDIT_RUN/scan-results.new" "$WIFI_EDIT_RUN/scan-results" && wifi_scan_status available
        else
            wifi_scan_status failed
        fi
        rm -f "$WIFI_EDIT_RUN/scan-raw"
        wifi_scan_phase=idle
    fi
    [ -f "$WIFI_EDIT_RUN/scan-request" ] || return 0
    # Ignore repeated or malformed requests, never interpolate the token into
    # a shell command. Cooldown is enforced here as well as in the screen.
    if [ -L "$WIFI_EDIT_RUN/scan-request" ] ||
       [ "$(wc -c < "$WIFI_EDIT_RUN/scan-request")" -gt 49 ] ||
       ! LC_ALL=C awk 'NR==1 && /^[0-9]+-[0-9]+$/ {ok=1; next} {ok=0; exit} END {exit !(ok && NR==1)}' "$WIFI_EDIT_RUN/scan-request"; then
        rm -f "$WIFI_EDIT_RUN/scan-request"; return 0
    fi
    wifi_scan_token=$(cat "$WIFI_EDIT_RUN/scan-request")
    rm -f "$WIFI_EDIT_RUN/scan-request" "$WIFI_EDIT_RUN/scan-results"
    if [ "$now" -lt "${wifi_scan_next:-0}" ]; then wifi_scan_status refused; return 0; fi
    wifi_scan_next=$((now + 30))
    if [ "$(wpa_cli -iwlan0 scan 2>/dev/null)" != OK ]; then wifi_scan_status failed; return 0; fi
    wifi_scan_after=$((now + 10)); wifi_scan_phase=scanning
    wifi_scan_status scanning
}

wifi_edit_owned_daemons() {
    for spec in "$WPA_PID_FILE:wpa_supplicant" "$DHCP_PID_FILE:udhcpc"; do
        file=${spec%:*}; name=${spec##*:}
        pid=$(read_value "$file" '')
        case "$pid" in ''|*[!0-9]*) return 1 ;; esac
        [ "$(cat "$PROC_ROOT/$pid/comm" 2>/dev/null)" = "$name" ] || return 1
        kill -0 "$pid" 2>/dev/null || return 1
    done
    # Require exactly the supervisor's profile on wlan0, never a stock daemon.
    tr '\000' '\n' < "$PROC_ROOT/$(cat "$WPA_PID_FILE")/cmdline" |
        grep -Fxq -- "-c$NETWORK_CONFIG" || return 1
    tr '\000' '\n' < "$PROC_ROOT/$(cat "$WPA_PID_FILE")/cmdline" |
        grep -Fxq -- '-iwlan0'
}

wifi_edit_reconfigure() {
    # wpa_cli's exit code alone does not indicate command acceptance.
    [ "$(wpa_cli -iwlan0 reconfigure 2>/dev/null)" = OK ]
}

wifi_edit_dhcp() {
    wifi_edit_owned_daemons || return 1
    kill "-$1" "$(cat "$DHCP_PID_FILE")" 2>/dev/null
}

wifi_edit_restore_file() {
    [ -s "$WIFI_EDIT_TRIAL/previous.conf" ] || return 1
    cp "$WIFI_EDIT_TRIAL/previous.conf" "$NETWORK_CONFIG.restore" &&
        chmod 600 "$NETWORK_CONFIG.restore" &&
        mv "$NETWORK_CONFIG.restore" "$NETWORK_CONFIG" && sync
}

wifi_edit_recover() {
    # Called BEFORE networking on boot and BEFORE the stock fallback.
    # A pending transaction never becomes the next boot's default by accident.
    [ -f "$WIFI_EDIT_TRIAL/pending" ] || return 0
    wifi_edit_restore_file || return 1
    rm -f "$WIFI_EDIT_TRIAL/pending"
    sync
}

wifi_edit_init() {
    umask 077
    [ ! -L "$WIFI_EDIT_RUN" ] && [ ! -L "$WIFI_EDIT_TRIAL" ] || return 1
    mkdir -p "$WIFI_EDIT_RUN" "$WIFI_EDIT_TRIAL" || return 1
    chmod 700 "$WIFI_EDIT_RUN" "$WIFI_EDIT_TRIAL" || return 1
    rm -f "$WIFI_EDIT_RUN/ready" "$WIFI_EDIT_RUN/request" "$WIFI_EDIT_RUN/decision" \
        "$WIFI_EDIT_RUN/request.screen-new" "$WIFI_EDIT_RUN/decision.screen-new" \
        "$WIFI_EDIT_RUN/scan-request" "$WIFI_EDIT_RUN/scan-request.screen-new" \
        "$WIFI_EDIT_RUN/scan-results" "$WIFI_EDIT_RUN/scan-status" "$WIFI_EDIT_RUN/scan-raw"
    wifi_edit_phase=idle
    wifi_edit_token=none
    wifi_scan_phase=idle
    wifi_scan_next=0
    wifi_scan_token=none
    wifi_edit_recover || { wifi_edit_status recovery_failed; return 1; }
    wifi_edit_status idle
}

wifi_edit_request_valid() {
    # Canonical file from the local screen; no shell parsing or arbitrary WPA
    # options. Embedded quotes are refused to avoid WPA's # comment parser.
    [ ! -L "$WIFI_EDIT_RUN/request" ] || return 1
    [ "$(wc -c < "$WIFI_EDIT_RUN/request")" -le 512 ] || return 1
    LC_ALL=C awk '
      NR==1 {if ($0 !~ /^[0-9]+-[0-9]+$/ || length($0)>48) exit 1; token=$0; next}
      NR==2 {if ($0!="ctrl_interface=/var/run/wpa_supplicant") exit 1; next}
      NR==3 {if ($0!="update_config=0") exit 1; next}
      NR==4 {if ($0!="network={") exit 1; next}
      NR==5 {v=substr($0,6); if (substr($0,1,5)!="ssid=" || v!~/^[0-9a-f]+$/ || length(v)<2 || length(v)>64 || length(v)%2) exit 1; next}
      NR==6 {v=substr($0,5); if (substr($0,1,4)!="psk=") exit 1;
        if (v~/^[0-9a-fA-F]+$/ && length(v)==64) next;
        if (substr(v,1,1)!="\"" || substr(v,length(v),1)!="\"") exit 1;
        v=substr(v,2,length(v)-2); if(length(v)<8 || length(v)>63 || v~/[^ -~]/ || index(v,"\"")) exit 1; next}
      NR==7 {if ($0!="key_mgmt=WPA-PSK") exit 1; next}
      NR==8 {if ($0!="scan_ssid=1") exit 1; next}
      NR==9 {if ($0!="id_str=\"tpp06-" token "\"") exit 1; next}
      NR==10 {if ($0!="}") exit 1; valid=1; next}
      {exit 1}
      END {if(NR!=10 || !valid) exit 1}
    ' "$WIFI_EDIT_RUN/request"
}

wifi_edit_rollback() {
    rm -f "$WIFI_EDIT_RUN/ready" "$WIFI_EDIT_RUN/decision"
    if ! wifi_edit_restore_file || ! wifi_edit_reconfigure || ! wifi_edit_dhcp USR2; then
        wifi_edit_phase=failed
        wifi_edit_status recovery_failed
        return 1  # Keep pending for a boot/fallback recovery attempt.
    fi
    wifi_edit_phase=rollback_release
    wifi_edit_until=$(( $(wifi_edit_now) + 45 ))
    wifi_edit_status restoring
}

wifi_edit_in_progress() {
    case "${wifi_edit_phase:-idle}" in release|connecting|confirm|rollback_release|rollback_connect) return 0 ;; esac
    return 1
}

wifi_edit_tick() {
    [ -d "$WIFI_EDIT_RUN" ] || return 0
    now=$(wifi_edit_now)
    case "$now" in ''|*[!0-9]*) rm -f "$WIFI_EDIT_RUN/ready"; return 1 ;; esac
    if wifi_edit_in_progress; then
        wifi_scan_stop
        rm -f "$WIFI_EDIT_RUN/ready"
        # Rollback cannot be disabled by an OTA, API disconnect, or page change.
        case "$wifi_edit_phase" in
          rollback_*)
            if [ "$now" -ge "$wifi_edit_until" ]; then
                # For an explicitly validated offline-local installation the
                # old AP may be gone. Keep the screen/relays usable so the owner
                # can correct credentials; the old file and DHCP were restored.
                if [ "$wifi_edit_phase" = rollback_connect ] && local_offline_policy; then
                    rm -f "$WIFI_EDIT_TRIAL/pending"; sync
                    wifi_edit_phase=idle; wifi_edit_status restored_offline; return 0
                fi
                wifi_edit_phase=failed; wifi_edit_status recovery_failed; return 1
            fi
            if [ "$wifi_edit_phase" = rollback_release ] && ! wlan_has_address; then
                wifi_edit_dhcp USR1 || return 1
                wifi_edit_phase=rollback_connect
            elif [ "$wifi_edit_phase" = rollback_connect ] && wifi_associated && wlan_has_address; then
                rm -f "$WIFI_EDIT_TRIAL/pending"; sync
                wifi_edit_phase=idle; wifi_edit_status restored
            fi
            return 0 ;;
        esac
        decision=$(read_value "$WIFI_EDIT_RUN/decision" '')
        if [ "$now" -ge "$wifi_edit_until" ] || [ "$decision" = "cancel:$wifi_edit_token" ]; then
            wifi_edit_rollback; return
        fi
        if [ "$wifi_edit_phase" = release ] && ! wlan_has_address; then
            wifi_edit_dhcp USR1 || { wifi_edit_rollback; return; }
            wifi_edit_phase=connecting
        fi
        # Observed deconfiguration followed by a fresh lease, not a stale IP.
        if [ "$wifi_edit_phase" = connecting ] || [ "$wifi_edit_phase" = confirm ]; then
            status=$(wpa_cli -iwlan0 status 2>/dev/null)
            if printf '%s\n' "$status" | grep -Fxq "id_str=tpp06-$wifi_edit_token" &&
               printf '%s\n' "$status" | grep -Fxq 'wpa_state=COMPLETED' && wlan_has_address; then
                if [ "$wifi_edit_phase" = connecting ]; then
                    wifi_edit_stable_since=$now; wifi_edit_phase=confirm
                fi
                if [ "$((now - wifi_edit_stable_since))" -ge 20 ]; then
                    wifi_edit_status confirm
                    if [ "$decision" = "confirm:$wifi_edit_token" ]; then
                        # Both old profile and candidate remain private. The old
                        # profile is retained for manual recovery after commit.
                        cp "$WIFI_EDIT_TRIAL/previous.conf" "$NETWORK_DIR/wifi-last-good.conf.new" &&
                          chmod 600 "$NETWORK_DIR/wifi-last-good.conf.new" &&
                          mv "$NETWORK_DIR/wifi-last-good.conf.new" "$NETWORK_DIR/wifi-last-good.conf" || return 1
                        sync
                        rm -f "$WIFI_EDIT_TRIAL/pending"; sync
                        wifi_edit_phase=idle; wifi_edit_status saved
                    fi
                fi
            else
                wifi_edit_phase=connecting; wifi_edit_status connecting
                rm -f "$WIFI_EDIT_RUN/decision"  # A stale confirmation is never reused.
            fi
        fi
        return 0
    fi
    # Explicit on-site commissioning is required; an OTA does not enable this.
    if [ "${wifi_edit_phase:-idle}" != idle ] ||
       [ "$(read_value "$BASE/wifi_editor_enabled" no)" != yes ] ||
       [ "$(read_value "$BASE/persistent_confirmed" no)" != yes ] ||
       [ "$(read_value "$BASE/boot_policy" one-shot)" != persistent ] ||
       [ "$(read_value "$BASE/network_mode" learning)" != isolated ] ||
       [ "$SESSION_SECONDS" != 0 ] || ! wifi_edit_owned_daemons; then
        rm -f "$WIFI_EDIT_RUN/ready" "$WIFI_EDIT_RUN/request"
        wifi_scan_stop
        return 0
    fi
    printf '%s\n' "$now" > "$WIFI_EDIT_RUN/ready.new" &&
        mv "$WIFI_EDIT_RUN/ready.new" "$WIFI_EDIT_RUN/ready"
    if [ ! -f "$WIFI_EDIT_RUN/request" ]; then wifi_scan_tick; return 0; fi
    wifi_scan_stop
    rm -f "$WIFI_EDIT_RUN/ready" "$WIFI_EDIT_RUN/decision"
    if ! wifi_edit_request_valid || [ -f "$WIFI_EDIT_TRIAL/pending" ] ||
       [ -e "$BASE/esphome/esphome.ota.new" ] || ! network_profile_valid ||
       { ! local_offline_policy && { ! wifi_associated || ! wlan_has_address; }; }; then
        rm -f "$WIFI_EDIT_RUN/request"; wifi_edit_status refused; return 1
    fi
    wifi_edit_token=$(sed -n '1p' "$WIFI_EDIT_RUN/request")
    # Back up and sync BEFORE the pending journal, then replace the config.
    if ! cp "$NETWORK_CONFIG" "$WIFI_EDIT_TRIAL/previous.conf.new" ||
       ! chmod 600 "$WIFI_EDIT_TRIAL/previous.conf.new" ||
       ! mv "$WIFI_EDIT_TRIAL/previous.conf.new" "$WIFI_EDIT_TRIAL/previous.conf"; then
        rm -f "$WIFI_EDIT_RUN/request"; wifi_edit_status refused; return 1
    fi
    sync
    printf '%s\n' "$wifi_edit_token" > "$WIFI_EDIT_TRIAL/pending.new" &&
        mv "$WIFI_EDIT_TRIAL/pending.new" "$WIFI_EDIT_TRIAL/pending" || return 1
    sync
    tail -n +2 "$WIFI_EDIT_RUN/request" > "$NETWORK_CONFIG.new" &&
        chmod 600 "$NETWORK_CONFIG.new" && mv "$NETWORK_CONFIG.new" "$NETWORK_CONFIG" || {
            wifi_edit_phase=failed; wifi_edit_status recovery_failed; return 1;
        }
    rm -f "$WIFI_EDIT_RUN/request"
    sync
    wifi_edit_until=$((now + 120))
    wifi_edit_phase=release
    wifi_edit_status connecting
    if ! wifi_edit_reconfigure || ! wifi_edit_dhcp USR2; then wifi_edit_rollback; fi
}
