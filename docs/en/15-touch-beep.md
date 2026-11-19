# Touch beep: correction confirmed on the reference panel

On 19 November 2026 the owner confirmed working touch sound after installing
`0.1.6-buzzer.1`. The installed binary and encrypted API were verified. This
confirms audible feedback on the reference panel, not every hardware variant
or the exact electrical pulse duration.

History: initial V6 weather worked, but the first touch faulted the driver.
Read-only checks after that failure showed both gates at zero and PWM
disabled/unrequested.

Correction `0.1.6-buzzer.1` follows stock ordering: period first when the new
period exceeds the previous duty, duty first otherwise. The previous code
wrote duty zero before initializing the period; Linux 4.4 rejects even duty
zero when the period is zero. A regression test models this constraint and
retained state across exports. This is a confirmed code defect, not proof of
the sole on-device cause. Errors now retain the first failing stage, path and
errno. The owner subsequently confirmed audible feedback with the correction.

Kernel reference: [`duty_cycle_store` passes the current period to
`pwm_config`](https://github.com/torvalds/linux/blob/v4.4/drivers/pwm/sysfs.c),
which [rejects a zero period](https://github.com/torvalds/linux/blob/v4.4/drivers/pwm/core.c).

The V6 settings page and HA expose the same real local driver. As requested by
the owner, `RESTORE_DEFAULT_ON` defaults the preference to ON and retains later
user choices, including OFF. No boot tone is requested. Persistence across a
real power cut remains untested. Startup performs no GPIO/PWM writes.

The driver checks the hardware profile and ownership, refuses an already
exported channel, and uses a local advisory lock. A separate worker runs one
4-ms requested tone with no queue and a 200-ms request interval. OFF cancels
between 0.5-ms waits; every post-export path attempts PWM-off and gate cleanup.
Transaction errors disable playback until process restart. A SIGKILL, kernel
failure or blocked sysfs write can prevent cleanup: this is **not a hardware
timeout guarantee**. A supervised on-target acoustic test remains required
before treating the feature as validated.

Reference library: `libtuya_app.so`, SHA-256
`f940aeee4a70e6ccb7f12eda075b40c7a3577484f1a460c327d9055d5d8477f7`.
The proprietary library is not distributed. Addresses identify this exact
file only; they are not instructions to call into the stock process.

- `tuya_buzzer_init` (`0x2c27ec`) registers callback `0x2c23e8` through
  `lv_event_add_all_clicked_cb`. It checks the click-sound setting and mute.
- `0x2c2280` enforces at least 200 ms between requests and dispatches worker
  `0x2c21ec` through a thread pool.
- The click selects `BUZ_EN1=0`, `BUZ_EN2=1`: GPIOs 8 and 18 respectively.
- Tone generation uses hardware `pwm1/pwmchip1/pwm0`, not relay outputs.
- Requested frequency: 4,750 Hz; period: 210,526 ns; duty: 105,250 ns, close to
  50% with stock integer rounding. Requested duration: 4,000 µs, then PWM off.
  Physical duration has not been measured.
- `0x2c1ef4` orders period/duty writes according to the previous setting,
  enables PWM, waits using `select`, then disables PWM.

The live reference kernel is `4.4.192V2.4`, `armv5tejl`. Both BUZ outputs read
zero, direction `out`, `active_low=0`; device-tree GPIO mappings and initial
zero levels match. PWM chip 1 has one channel, but its `pwm0` sysfs directory
was not exported. This alone does not prove the electrical PWM state. ESPHome
remained healthy during inspection.

Before deployment: verify the hardware/ownership, validate bounded playback
with cleanup and state restoration on the target, test failure
paths without hardware, then perform one brief supervised acoustic test.
Do not block LVGL/local relays, run vendor factory tests, or assume closing a
sysfs file stops hardware PWM. Only then connect LVGL clicks to an editable
local sound setting; turning it off must also stop active sound.

See the [detailed French investigation](../fr/15-bip-tactile.md). Weather support
is independent of this driver and requires no GPIO access.
