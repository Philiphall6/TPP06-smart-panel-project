"""Offline policy tests; no device connection, actual daemon or reboot."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "device/tpp06-multiboot.sh"


class PersistentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.functions = SCRIPT.read_text().rsplit('\ncase "$1" in', 1)[0]
        self.env = {**os.environ, "TPP06_BASE": str(self.base),
                    "TPP06_PERSISTENT_CHECK_SECONDS": "0"}
        (self.base / "mode").write_text("tuya\n")

    def run_monitor(self, confirmed="yes", unhealthy="false", write_fails=False):
        (self.base / "persistent_confirmed").write_text(confirmed + "\n")
        # Mock only the process/network boundary. Keep state, counter and
        # fallback functions real so ordering is observable on temporary files.
        harness = '''
cycles=0
engine_pid=424242
engine_alive=yes
kill() { [ "$engine_alive" = yes ]; }
sleep() { cycles=$((cycles + 1)); [ "$cycles" -lt 5 ] || engine_alive=no; }
wait() { return 7; }
sync() { :; }
write_state() {
    echo "$1=$2" >> "$BASE/events"
    FAIL_WRITE
    printf '%s\n' "$2" > "$BASE/$1"
}
persistent_health_ready() { ! { UNHEALTHY; }; }
stop_owned_engine() { echo stopped >> "$BASE/events"; engine_alive=no; }
cleanup_independent_services() { echo cleaned >> "$BASE/events"; }
start_stock() { echo stock >> "$BASE/events"; }
monitor_persistent
'''.replace("UNHEALTHY", unhealthy).replace(
            "FAIL_WRITE", '[ "$1:$2" != mode:esphome ] || return 1' if write_fails else ":")
        result = subprocess.run(["sh"], input=self.functions + harness, env=self.env,
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.base / "events").read_text().splitlines()

    def test_confirmed_healthy_rearms_then_exit_selects_stock(self):
        events = self.run_monitor()
        self.assertIn("mode=esphome", events)
        self.assertLess(events.index("mode=esphome"), events.index("mode=tuya"))
        self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
        self.assertEqual(events[-1], "stock")

    def test_unconfirmed_and_invalid_confirmation_never_rearm(self):
        for value in ("no", "", "true", "YES"):
            with self.subTest(value=value):
                (self.base / "events").unlink(missing_ok=True)
                self.assertNotIn("mode=esphome", self.run_monitor(confirmed=value))

    def test_three_health_failures_disarm_before_stopping_services(self):
        events = self.run_monitor(unhealthy='[ "$cycles" -ge 1 ]')
        self.assertIn("mode=esphome", events)
        self.assertLess(events.index("mode=tuya"), events.index("stopped"))
        self.assertLess(events.index("mode=tuya"), events.index("cleaned"))
        self.assertEqual((self.base / "failure_count").read_text().strip(), "1")
        self.assertIn("persistent-health-failed", (self.base / "diagnostics/multiboot.log").read_text())

    def test_transient_health_failure_does_not_stop_engine(self):
        events = self.run_monitor(unhealthy='[ "$cycles" -eq 1 ] || [ "$cycles" -eq 2 ]')
        self.assertNotIn("stopped", events)

    def test_rearm_write_failure_stops_and_falls_back(self):
        events = self.run_monitor(write_fails=True)
        self.assertIn("stopped", events)
        self.assertEqual((self.base / "mode").read_text().strip(), "tuya")
        self.assertIn("persistent-selection-write-failed", (self.base / "diagnostics/multiboot.log").read_text())

    def test_health_requires_process_wifi_address_rescue_and_api(self):
        for failed in ("none", "process", "wifi", "address", "rescue", "api"):
            with self.subTest(failed=failed):
                harness = '''
engine_pid=424242
kill() { [ "$FAIL" != process ]; }
wifi_associated() { [ "$FAIL" != wifi ]; }
wlan_has_address() { [ "$FAIL" != address ]; }
rescue_ports_listening() { [ "$FAIL" != rescue ]; }
netstat() { [ "$FAIL" != api ] && echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
persistent_health_ready
'''
                result = subprocess.run(["sh"], input=self.functions + harness,
                    env={**self.env, "FAIL": failed}, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode == 0, failed == "none")

    def test_pid_reuse_requires_same_boot_and_same_supervisor_command(self):
        proc = self.base / "proc"
        (proc / "sys/kernel/random").mkdir(parents=True)
        (proc / "sys/kernel/random/boot_id").write_text("current-boot\n")
        (proc / "42").mkdir()
        (self.base / "supervisor.pid").write_text("42\n")
        for saved_boot, command, running, expected in (
                ("previous-boot", b"sh\0policy-test\0supervise\0", True, False),
                ("current-boot", b"sh\0other-task\0supervise\0", True, False),
                ("current-boot", b"sh\0policy-test\0status\0", True, False),
                ("current-boot", b"sh\0policy-test\0supervise\0", False, False),
                ("current-boot", b"sh\0policy-test\0supervise\0", True, True)):
            with self.subTest(saved_boot=saved_boot, command=command, running=running):
                (self.base / "supervisor.boot_id").write_text(saved_boot + "\n")
                (proc / "42/cmdline").write_bytes(command)
                harness = "\nkill() { " + ("true" if running else "false") + "; }\nsupervisor_is_running\n"
                result = subprocess.run(["sh", "-c", self.functions + harness, "policy-test"],
                    env={**self.env, "TPP06_PROC_ROOT": str(proc)},
                    text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode == 0, expected)

    def test_confirmed_local_policy_tolerates_wifi_and_dhcp_loss_only(self):
        flags = {"local_control_confirmed": "yes", "persistent_confirmed": "yes",
                 "boot_policy": "persistent", "network_mode": "isolated"}
        for name, value in flags.items():
            (self.base/name).write_text(value + "\n")
        harness = '''
engine_pid=424242
kill() { [ "$FAIL" != process ]; }
wifi_associated() { return 1; }
wlan_has_address() { return 1; }
rescue_ports_listening() { [ "$FAIL" != rescue ]; }
netstat() { [ "$FAIL" != api ] && echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
persistent_health_ready
'''
        for failed in ("none", "process", "rescue", "api"):
            result = subprocess.run(["sh"], input=self.functions+harness,
                env={**self.env, "FAIL": failed}, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode == 0, failed == "none")
        # Removing ANY confirmation restores the original strict network guard.
        for name, value in flags.items():
            (self.base/name).write_text("no\n")
            result = subprocess.run(["sh"], input=self.functions+harness,
                env={**self.env, "FAIL": "none"}, text=True, capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0, name)
            (self.base/name).write_text(value + "\n")
        result = subprocess.run(["sh"], input=self.functions+harness,
            env={**self.env, "FAIL": "none", "TPP06_SESSION_SECONDS": "60"},
            text=True, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)  # Never relax bounded trials.

    def test_local_network_loss_does_not_stop_or_disarm_running_engine(self):
        for name, value in {"local_control_confirmed": "yes", "persistent_confirmed": "yes",
                            "boot_policy": "persistent", "network_mode": "isolated"}.items():
            (self.base/name).write_text(value+"\n")
        harness = '''
engine_pid=424242
cycles=0
kill() { [ "$cycles" -lt 6 ]; }
sleep() { cycles=$((cycles+1)); }
wait() { return 9; }
sync() { :; }
wifi_associated() { return 1; }
wlan_has_address() { return 1; }
rescue_ports_listening() { return 0; }
netstat() { echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
write_state() { echo "$1=$2@$cycles" >> "$BASE/events"; echo "$2" > "$BASE/$1"; }
stop_owned_engine() { echo unexpected-stop >> "$BASE/events"; }
cleanup_independent_services() { :; }
start_stock() { echo "fallback@$cycles" >> "$BASE/events"; }
monitor_persistent
'''
        result = subprocess.run(["sh"], input=self.functions+harness, env=self.env,
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = (self.base/"events").read_text()
        self.assertIn("mode=esphome@0", events)
        self.assertNotIn("unexpected-stop", events)
        self.assertIn("fallback@6", events)  # Genuine process death retains rescue.

    def test_invalid_persistent_combination_refused_before_engine_lookup(self):
        for mode, network, seconds, port in (
                ("openhasp", "isolated", "0", "6053"),
                ("esphome", "learning", "0", "6053"),
                ("esphome", "isolated", "300", "6053"),
                ("esphome", "isolated", "0", "0")):
            with self.subTest(mode=mode, network=network, seconds=seconds, port=port):
                (self.base / "mode").write_text(mode + "\n")
                (self.base / "network_mode").write_text(network + "\n")
                (self.base / "boot_policy").write_text("persistent\n")
                harness = '''
sync() { :; }
cleanup_independent_services() { :; }
start_stock() { :; }
engine_command() { echo forbidden > "$BASE/engine-lookup"; return 1; }
supervise
'''
                subprocess.run(["sh"], input=self.functions + harness, env={**self.env,
                    "TPP06_SESSION_SECONDS": seconds, "TPP06_ESPHOME_HEALTH_PORT": port},
                    text=True, check=True, timeout=5)
                self.assertFalse((self.base / "engine-lookup").exists())
                self.assertEqual((self.base / "mode").read_text().strip(), "tuya")


if __name__ == "__main__":
    unittest.main()
