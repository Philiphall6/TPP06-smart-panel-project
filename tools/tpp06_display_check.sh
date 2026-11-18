#!/bin/sh
# Read-only snapshot. Run on the panel; never open framebuffer/input devices.
# Alternate proc/sys roots are for offline tests only.
proc_root=${TPP06_CHECK_PROC_ROOT:-/proc}
sys_root=${TPP06_CHECK_SYS_ROOT:-/sys}
stock_fb=0
esp_fb=0
stock_input=0
esp_input=0
stock_found=0
esp_found=0
gui_watchdog=0
complete=yes

[ -r "$proc_root/self/stat" ] || complete=no
for process in "$proc_root"/[0-9]*; do
    [ -d "$process" ] || continue
    if [ ! -r "$process/comm" ]; then
        complete=no
        continue
    fi
    IFS= read -r name < "$process/comm"
    case "$name" in
        voice_control_a|voice_control_ak3760e) role=stock; stock_found=1 ;;
        esphome) role=esp; esp_found=1 ;;
        *) continue ;;
    esac
    [ -r "$process/fd" ] && [ -x "$process/fd" ] || complete=no
    for fd in "$process"/fd/*; do
        [ -L "$fd" ] || continue
        target=$(readlink "$fd" 2>/dev/null) || { complete=no; continue; }
        case "$role:$target" in
            stock:/dev/fb0) stock_fb=1 ;;
            esp:/dev/fb0) esp_fb=1 ;;
            stock:/dev/input/event1) stock_input=1 ;;
            esp:/dev/input/event1) esp_input=1 ;;
        esac
    done
    if [ "$role" = stock ]; then
        for task in "$process"/task/*/comm; do
            [ -r "$task" ] || continue
            IFS= read -r task_name < "$task"
            [ "$task_name" != gui_watchdog ] || gui_watchdog=1
        done
    fi
done
shared=not_observed
if [ "$stock_fb" = 1 ] && [ "$esp_fb" = 1 ]; then
    shared=yes
elif [ "$complete" != yes ]; then
    shared=unknown
fi
printf 'CHECK_STOCK_RUNNING=%s\nCHECK_ESPHOME_RUNNING=%s\n' "$stock_found" "$esp_found"
printf 'CHECK_STOCK_FB0_OPEN=%s\nCHECK_ESPHOME_FB0_OPEN=%s\n' "$stock_fb" "$esp_fb"
printf 'CHECK_STOCK_EVENT1_OPEN=%s\nCHECK_ESPHOME_EVENT1_OPEN=%s\n' "$stock_input" "$esp_input"
printf 'CHECK_GUI_WATCHDOG_OBSERVED=%s\nCHECK_SHARED_FB0=%s\n' "$gui_watchdog" "$shared"
printf 'CHECK_SCAN_COMPLETE=%s\nCHECK_DISPLAY_VERIFIED=no\n' "$complete"
for attribute in virtual_size bits_per_pixel stride pan; do
    file="$sys_root/class/graphics/fb0/$attribute"
    value=unknown
    if [ -r "$file" ]; then
        IFS= read -r candidate < "$file"
        case "$candidate" in
            ''|*[!0-9,]*) : ;;
            *) value=$candidate ;;
        esac
    fi
    printf 'CHECK_FB0_%s=%s\n' "$attribute" "$value"
done
# An open fd is not proof of active drawing, exclusive ownership, or stability.
# Missing processes/maps and races can hide a renderer. Never infer readiness.
