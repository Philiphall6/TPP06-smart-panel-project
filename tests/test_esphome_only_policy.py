"""Offline opt-in no-Tuya policy tests; no real devices/processes/network."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

DEFAULT = Path(__file__).resolve().parents[1] / 'device/tpp06-multiboot.sh'
SCRIPT = Path(os.environ.get('TPP06_POLICY_TEST_SCRIPT', str(DEFAULT)))


class ESPHomeOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.proc = self.base / 'proc'
        self.proc.mkdir()
        self.functions = SCRIPT.read_text().rsplit('\ncase "$1" in', 1)[0]
        self.env = {**os.environ, 'TPP06_BASE': str(self.base),
                    'TPP06_PROC_ROOT': str(self.proc), 'TPP06_GRACE_SECONDS': '0'}
        for name, value in {'no_stock_fallback': 'owner-confirmed',
                            'boot_policy': 'persistent', 'network_mode': 'isolated',
                            'mode': 'esphome'}.items():
            (self.base / name).write_text(value + '\n')

    def shell(self, code):
        boundary = '''
sync() { :; }
sleep() { :; }
kill() { echo kill >> "$BASE/events"; return 0; }
start_rescue_service() { echo rescue >> "$BASE/events"; }
start_independent_network() { echo network >> "$BASE/events"; }
stock_runtime_present() { return 1; }
stop_recorded_process() { echo stopped-network >> "$BASE/events"; }
'''
        return subprocess.run(['sh'], input=self.functions + boundary + code,
                              env=self.env, text=True, capture_output=True, timeout=5)

    def test_all_failure_reasons_keep_esphome_selection_and_management(self):
        for reason in ('early-exit', 'engine-missing', 'persistent-health-failed',
                       'wifi-editor-failed', 'failure-limit', 'invalid-mode'):
            with self.subTest(reason=reason):
                result = self.shell('fallback_stock ' + reason)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.base/'mode').read_text().strip(), 'esphome')
                self.assertEqual((self.base/'active_mode').read_text().strip(),
                                 'esphome-maintenance')
                self.assertNotIn('stopped-network', (self.base/'events').read_text())

    def test_direct_stock_launch_is_refused_even_with_missing_launcher(self):
        result = self.shell('start_stock')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('blocked by owner', (self.base/'diagnostics/multiboot.log').read_text())

    def test_ssh_is_started_even_if_engine_is_missing(self):
        service = self.base/'ssh-service'
        service.write_text('#!/bin/sh\necho "$1" >> "$TPP06_BASE/ssh-calls"\n')
        service.chmod(0o700)
        self.env['TPP06_SSH_SERVICE'] = str(service)
        result = self.shell('engine_command() { return 1; }; supervise')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base/'ssh-calls').read_text().splitlines(), ['start', 'start'])

    def test_empty_and_invalid_marker_do_not_reenable_tuya(self):
        for value in ('', 'no', 'corrupted'):
            (self.base/'no_stock_fallback').write_text(value)
            self.assertNotEqual(self.shell('start_stock').returncode, 0)
            self.assertEqual(self.shell('write_state mode tuya').returncode, 0)
            self.assertEqual((self.base/'mode').read_text().strip(), 'esphome')

    def test_missing_marker_preserves_legacy_policy(self):
        (self.base/'no_stock_fallback').unlink()
        self.assertEqual(self.shell('write_state mode tuya').returncode, 0)
        self.assertEqual((self.base/'mode').read_text().strip(), 'tuya')

    def test_network_cleanup_is_suppressed(self):
        self.assertEqual(self.shell('cleanup_independent_services').returncode, 0)
        self.assertFalse((self.base/'events').exists())

    def test_stop_keeps_network_and_esphome_next_boot(self):
        (self.base/'engine.pid').write_text('123')
        (self.base/'supervisor.pid').write_text('456')
        self.assertEqual(self.shell('stop_supervisor').returncode, 0)
        self.assertEqual((self.base/'mode').read_text().strip(), 'esphome')
        self.assertNotIn('stopped-network', (self.base/'events').read_text())

    def test_failed_management_recovery_never_starts_stock(self):
        result = self.shell('''
start_rescue_service() { return 1; }
start_independent_network() { return 1; }
wifi_edit_recover() { return 1; }
fallback_stock failed
''')
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.base/'active_mode').read_text().strip(), 'esphome-maintenance')

    def test_old_failure_counter_does_not_lock_next_manual_boot_into_tuya(self):
        (self.base/'failure_count').write_text('99')
        (self.base/'mode').write_text('tuya')
        result = self.shell('engine_command() { return 1; }; supervise')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base/'requested_mode').read_text().strip(), 'esphome')
        self.assertIn('reason=engine-missing', (self.base/'diagnostics/multiboot.log').read_text())

    def test_learning_or_trial_policy_cannot_launch_tuya(self):
        for name, value in (('network_mode', 'learning'), ('boot_policy', 'one-shot')):
            original = (self.base/name).read_text()
            (self.base/name).write_text(value)
            self.assertNotEqual(self.shell('supervise').returncode, 0)
            self.assertEqual((self.base/'active_mode').read_text().strip(), 'esphome-maintenance')
            (self.base/name).write_text(original)

    def test_healthy_boot_runs_esphome_without_stock(self):
        result = self.shell('''
engine_command() { ENGINE_BIN=/bin/true; return 0; }
isolated_boot_prerequisites() { return 0; }
rescue_ports_listening() { return 0; }
netstat() { echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
monitor_persistent() { echo monitored >> "$BASE/events"; }
supervise
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base/'mode').read_text().strip(), 'esphome')
        self.assertEqual((self.base/'active_mode').read_text().strip(), 'esphome-healthy')
        self.assertIn('monitored', (self.base/'events').read_text())

    def test_soft_restart_reuses_only_verified_network_daemons(self):
        for pid, name, file in (('41', 'wpa_supplicant', 'wpa_supplicant.pid'),
                                ('42', 'udhcpc', 'udhcpc.pid')):
            (self.proc/pid).mkdir()
            (self.proc/pid/'cmdline').write_bytes(('/sbin/'+name+'\0-B\0').encode())
            (self.base/file).write_text(pid)
        # Use the real network function, mock only process liveness.
        code = '\nkill() { return 0; }; start_independent_network\n'
        result = subprocess.run(['sh'], input=self.functions+code, env=self.env,
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.proc/'42'/'cmdline').write_bytes(b'/sbin/unrelated\0')
        result = subprocess.run(['sh'], input=self.functions+code, env=self.env,
                                text=True, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)

    def test_offline_opt_in_is_read_live_without_restarting_supervisor(self):
        result = self.shell('''
engine_pid=424242
wifi_associated() { return 1; }
wlan_has_address() { return 1; }
rescue_ports_listening() { return 0; }
netstat() { echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
echo yes > "$BASE/persistent_confirmed"
persistent_health_ready && exit 10
echo yes > "$BASE/local_control_confirmed"
persistent_health_ready || exit 11
# Local failures still count, even with no AP or DHCP lease.
rescue_ports_listening() { return 1; }
persistent_health_ready && exit 12
rescue_ports_listening() { return 0; }
netstat() { return 0; }
persistent_health_ready && exit 13
netstat() { echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
kill() { return 1; }
persistent_health_ready && exit 14
exit 0
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_offline_outage_and_reconnection_do_not_stop_or_disarm_engine(self):
        result = self.shell('''
echo yes > "$BASE/local_control_confirmed"
echo yes > "$BASE/persistent_confirmed"
engine_pid=424242
cycles=0
kill() { [ "$cycles" -lt 10 ]; }
sleep() { cycles=$((cycles+1)); }
wait() { return 9; }
# A loss longer than the three-failure threshold, then recovery.
wifi_associated() { [ "$cycles" -eq 0 ] || [ "$cycles" -ge 8 ]; }
wlan_has_address() { wifi_associated; }
rescue_ports_listening() { return 0; }
netstat() { echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
stop_owned_engine() { echo unexpected-stop >> "$BASE/events"; }
fallback_stock() { echo "fallback@$cycles:$1" >> "$BASE/events"; }
monitor_persistent
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        events = (self.base/'events').read_text()
        self.assertNotIn('unexpected-stop', events)
        self.assertEqual(events.strip(), 'fallback@10:persistent-engine-exit-9')
        self.assertEqual((self.base/'mode').read_text().strip(), 'esphome')
