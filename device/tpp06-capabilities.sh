#!/bin/sh
# Read-only inventory. No device-node open, scan, ioctl, insmod, output or reboot.
# Output is deliberately allowlisted: no SSID, MAC, IP, key, hostname or cmdline.
CAP_SYS=${TPP06_CAP_SYS:-/sys}
CAP_PROC=${TPP06_CAP_PROC:-/proc}
CAP_DEV=${TPP06_CAP_DEV:-/dev}
CAP_BASE=${TPP06_CAP_BASE:-/data/tpp06-cutter}
CAP_MODULES=${TPP06_CAP_MODULES:-/usr/modules}
emit() { printf 'CAP_%s=%s\n' "$1" "$2"; }
presence() { if [ -e "$2" ]; then emit "$1" present; else emit "$1" absent; fi; }
confirmed() {
    if [ -f "$2" ] && [ ! -L "$2" ] && grep -qx "$3" "$2"; then
        emit "$1" confirmed
    else
        emit "$1" not_confirmed
    fi
}
emit FORMAT 1
presence FRAMEBUFFER "$CAP_DEV/fb0"
presence TOUCH "$CAP_DEV/input/event1"
presence KEYS "$CAP_DEV/input/event0"
presence BACKLIGHT "$CAP_SYS/class/backlight/backlight"
for i in 1 2 3; do
    presence "RELAY_$i" "$CAP_SYS/class/gpio/KC_CTL$i/value"
    presence "LED_$i" "$CAP_SYS/class/leds/button${i}_led/brightness"
done
presence MUTE_DESCRIPTION "$CAP_PROC/device-tree/gpiokeys/mic_mute"
presence PWM "$CAP_SYS/devices/platform/pwm1/pwm/pwmchip1"
presence RTC_NODE "$CAP_DEV/rtc0"
presence RTC_MODULE "$CAP_MODULES/ak_rtc.ko"
presence IR_NODE "$CAP_DEV/lirc0"
presence IR_TX_DRIVER "$CAP_SYS/bus/platform/drivers/gpio-ir-tx/ir_tx0"
presence BLUETOOTH "$CAP_SYS/class/bluetooth/hci0"
presence AUDIO_NODE "$CAP_DEV/snd"
presence AUDIO_MODULE "$CAP_MODULES/ak_pcm.ko"
presence CONSOLE_UART "$CAP_DEV/ttySAK0"
presence BLUETOOTH_UART "$CAP_DEV/ttySAK1"
presence WATCHDOG_NODE "$CAP_DEV/watchdog"
presence WIFI_HELPER "$CAP_BASE/tpp06-wifi-edit.sh"
presence STOCK_LAUNCHER "$CAP_BASE/S99tuya-app.stock"
confirmed PERSISTENT "$CAP_BASE/persistent_confirmed" yes
confirmed OFFLINE "$CAP_BASE/local_control_confirmed" yes
confirmed WIFI_EDITOR "$CAP_BASE/wifi_editor_enabled" yes
confirmed HEARTBEAT_REQUIRED "$CAP_BASE/heartbeat_policy" required-v1
cap_iio=absent
for cap_path in "$CAP_SYS"/bus/iio/devices/iio:device*; do
    [ ! -d "$cap_path" ] || cap_iio=present
done
emit IIO_DEVICE "$cap_iio"
cap_thermal=absent
for cap_path in "$CAP_SYS"/class/thermal/thermal_zone*; do
    [ ! -d "$cap_path" ] || cap_thermal=present
done
emit THERMAL_ZONE "$cap_thermal"
# Presence is never reported as 'working' or permission to enable a driver.
