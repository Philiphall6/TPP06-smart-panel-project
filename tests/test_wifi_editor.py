"""Offline transactions: fake WPA/DHCP/clock, no real network or process signals."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "device/tpp06-wifi-edit.sh"
SUPERVISOR = ROOT / "device/tpp06-multiboot.sh"


def request(token="1000-42", password='"fixture-password"'):
    return (f'{token}\nctrl_interface=/var/run/wpa_supplicant\nupdate_config=0\nnetwork={{\n'
            f'ssid=66697874757265\npsk={password}\nkey_mgmt=WPA-PSK\nscan_ssid=1\n'
            f'id_str="tpp06-{token}"\n}}\n')


class WifiTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "base"
        self.net = self.base / "network"
        self.net.mkdir(parents=True)
        self.run = self.root / "run"
        self.old = 'ctrl_interface=/var/run/wpa_supplicant\nnetwork={\nssid="original"\npsk="fixture-original"\n}\n'
        (self.net / "wpa_supplicant.conf").write_text(self.old)
        for key, value in {"wifi_editor_enabled": "yes", "persistent_confirmed": "yes",
                           "boot_policy": "persistent", "network_mode": "isolated"}.items():
            (self.base / key).write_text(value + "\n")
        (self.root / "request-fixture").write_text(request())
        self.env = {**os.environ, "TPP06_BASE": str(self.base), "TPP06_WIFI_EDIT_RUN": str(self.run)}
        self.functions = SUPERVISOR.read_text().rsplit('\ncase "$1" in', 1)[0] + "\n" + HELPER.read_text()
        self.mocks = r'''
now=1000
address=yes
associated=yes
owned=yes
reconfigure_ok=yes
scan_ok=yes
sync() { :; }
wifi_edit_now() { echo "$now"; }
wifi_edit_owned_daemons() { [ "$owned" = yes ]; }
wlan_has_address() { [ "$address" = yes ]; }
wifi_associated() { [ "$associated" = yes ]; }
wifi_edit_dhcp() { echo "$1" >> "$BASE/dhcp-events"; }
wpa_cli() {
  case "$2" in
    reconfigure) echo reconfigure >> "$BASE/wpa-events"; [ "$reconfigure_ok" = yes ] && echo OK || echo FAIL ;;
    status) [ "$associated" = yes ] && printf 'wpa_state=COMPLETED\nid_str=tpp06-%s\n' "${status_token:-$wifi_edit_token}" ;;
    scan) echo scan >> "$BASE/wpa-events"; [ "$scan_ok" = yes ] && echo OK || echo FAIL-BUSY ;;
    scan_results) echo scan_results >> "$BASE/wpa-events"; printf 'bssid / frequency / signal level / flags / ssid\n00:11:22:33:44:55\t2412\t-50\t[WPA2-PSK-CCMP][ESS]\tfixture-network\n' ;;
    *) exit 90 ;;
  esac
}
prepare() {
  wifi_edit_init || exit 91
  cp "$TPP06_BASE/../request-fixture" "$WIFI_EDIT_RUN/request"
  wifi_edit_tick
}
connect() {
  address=no; now=1010; wifi_edit_tick
  address=yes; now=1020; wifi_edit_tick
  now=1040; wifi_edit_tick
}
'''

    def run_case(self, script):
        result = subprocess.run(["sh"], input=self.functions + self.mocks + script,
                                env=self.env, text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("fixture-password", result.stdout + result.stderr)
        return result

    def status(self):
        return (self.run / "status").read_text().splitlines()[0]

    def test_no_activation_at_init_and_private_files(self):
        self.run_case("wifi_edit_init; wifi_edit_tick\n")
        self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)
        self.assertFalse((self.base / "wpa-events").exists())
        self.assertEqual(self.run.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.run / "ready").stat().st_mode & 0o777, 0o600)

    def test_scan_only_on_request_with_private_results_and_no_network_change(self):
        self.run_case('''wifi_edit_init; wifi_edit_tick
echo 1000-42 > "$WIFI_EDIT_RUN/scan-request"
wifi_edit_tick
test "$(head -n 1 "$WIFI_EDIT_RUN/scan-status")" = scanning || exit 1
test ! -f "$WIFI_EDIT_RUN/scan-results" || exit 1
now=1009; wifi_edit_tick
test ! -f "$WIFI_EDIT_RUN/scan-results" || exit 1
now=1010; wifi_edit_tick
''')
        self.assertEqual((self.run / "scan-status").read_text(), "available\n1000-42\n")
        self.assertTrue((self.run / "scan-results").read_text().startswith("1000-42\nbssid"))
        self.assertEqual((self.run / "scan-results").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.base / "wpa-events").read_text().splitlines(), ["scan", "scan_results"])
        self.assertFalse((self.base / "dhcp-events").exists())
        self.assertFalse((self.net / "wifi-trial/pending").exists())
        self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)

    def test_scan_fail_busy_and_cooldown(self):
        self.run_case('''wifi_edit_init
scan_ok=no
echo 1000-42 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
test "$(head -n 1 "$WIFI_EDIT_RUN/scan-status")" = failed || exit 1
scan_ok=yes
now=1010; echo 1010-42 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
test "$(head -n 1 "$WIFI_EDIT_RUN/scan-status")" = refused || exit 1
now=1030; echo 1030-42 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
now=1040; wifi_edit_tick
''')
        self.assertEqual((self.base / "wpa-events").read_text().splitlines(), ["scan", "scan", "scan_results"])

    def test_scan_authorization_ota_and_unowned_daemons(self):
        self.run_case('''wifi_edit_init
owned=no; echo 1000-42 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
owned=yes; mkdir -p "$BASE/esphome"; touch "$BASE/esphome/esphome.ota.new"
echo 1000-43 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
rm "$BASE/esphome/esphome.ota.new"
echo no > "$BASE/wifi_editor_enabled"
echo 1000-44 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
''')
        self.assertFalse((self.base / "wpa-events").exists())
        self.assertFalse((self.run / "scan-request").exists())

    def test_scan_cannot_delay_rollback_and_profile_request_takes_priority(self):
        self.run_case('''wifi_edit_init
echo 1000-42 > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
cp "$TPP06_BASE/../request-fixture" "$WIFI_EDIT_RUN/request"
now=1010; wifi_edit_tick
test "$(head -n 1 "$WIFI_EDIT_RUN/scan-status")" = refused || exit 1
echo 1010-42 > "$WIFI_EDIT_RUN/scan-request"
now=1130; wifi_edit_tick
test "$wifi_edit_phase" = rollback_release || exit 1
''')
        self.assertEqual((self.base / "wpa-events").read_text().splitlines(), ["scan", "reconfigure", "reconfigure"])
        self.assertFalse((self.run / "scan-request").exists())
        self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)

    def test_scan_malformed_requests_never_reach_wpa(self):
        self.run_case('''wifi_edit_init
for value in '1000-42;echo' 'wrong' '1-2-3'; do
  printf '%s\\n' "$value" > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
done
printf '1000-42\\n1000-43\\n' > "$WIFI_EDIT_RUN/scan-request"; wifi_edit_tick
''')
        self.assertFalse((self.base / "wpa-events").exists())

    def test_explicit_enable_and_persistent_mode_required(self):
        for key in ("wifi_editor_enabled", "persistent_confirmed", "boot_policy", "network_mode"):
            path = self.base / key
            old = path.read_text()
            path.write_text("no\n")
            self.run_case("prepare\n")
            self.assertFalse((self.base / "wpa-events").exists())
            self.assertFalse((self.run / "ready").exists())
            path.write_text(old)

    def test_stages_backup_before_try_and_keeps_pending_until_confirm(self):
        self.run_case("prepare; connect\n")
        self.assertEqual(self.status(), "confirm")
        self.assertTrue((self.net / "wifi-trial/pending").exists())
        self.assertEqual((self.net / "wifi-trial/previous.conf").read_text(), self.old)
        self.assertEqual((self.net / "wpa_supplicant.conf").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.base / "dhcp-events").read_text().splitlines(), ["USR2", "USR1"])

    def test_confirmation_commits_only_after_twenty_seconds(self):
        self.run_case('''prepare
address=no; now=1010; wifi_edit_tick
address=yes; now=1020; wifi_edit_tick
echo confirm:1000-42 > "$WIFI_EDIT_RUN/decision"
now=1030; wifi_edit_tick
test -f "$WIFI_EDIT_TRIAL/pending" || exit 1
now=1040; wifi_edit_tick
''')
        self.assertEqual(self.status(), "saved")
        self.assertFalse((self.net / "wifi-trial/pending").exists())
        self.assertEqual((self.net / "wifi-last-good.conf").read_text(), self.old)

    def test_stale_confirm_and_wrong_network_never_commit(self):
        self.run_case('''prepare; connect
echo confirm:900-1 > "$WIFI_EDIT_RUN/decision"
now=1050; wifi_edit_tick
test -f "$WIFI_EDIT_TRIAL/pending" || exit 1
status_token=wrong
echo confirm:1000-42 > "$WIFI_EDIT_RUN/decision"
now=1060; wifi_edit_tick
''')
        self.assertTrue((self.net / "wifi-trial/pending").exists())
        self.assertEqual(self.status(), "connecting")
        self.assertFalse((self.run / "decision").exists())

    def test_stale_ipv4_never_qualifies_without_observed_deconfiguration(self):
        self.run_case('''prepare
now=1040; wifi_edit_tick
echo confirm:1000-42 > "$WIFI_EDIT_RUN/decision"
now=1050; wifi_edit_tick
''')
        self.assertEqual(self.status(), "connecting")
        self.assertTrue((self.net / "wifi-trial/pending").exists())
        self.assertEqual((self.base / "dhcp-events").read_text().splitlines(), ["USR2"])

    def test_timeout_and_cancel_restore_without_client_connection(self):
        for trigger in ('now=1120', 'echo cancel:1000-42 > "$WIFI_EDIT_RUN/decision"'):
            with self.subTest(trigger=trigger):
                self.run_case('prepare; connect\n' + trigger + '''
wifi_edit_tick
address=no; wifi_edit_tick
address=yes; wifi_edit_tick
''')
                self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)
                self.assertEqual(self.status(), "restored")
                self.assertFalse((self.net / "wifi-trial/pending").exists())

    def test_boot_recovers_unconfirmed_profile_before_networking(self):
        self.run_case("prepare; connect\n")
        (self.base / "wpa-events").unlink()
        self.run_case("wifi_edit_init\n")
        self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)
        self.assertFalse((self.base / "wpa-events").exists())
        self.assertFalse((self.net / "wifi-trial/pending").exists())

    def test_new_network_when_old_ap_gone_requires_validated_local_policy(self):
        self.run_case("address=no; associated=no; prepare\n:")
        self.assertEqual(self.status(), "refused")
        self.assertFalse((self.base / "wpa-events").exists())
        (self.base / "local_control_confirmed").write_text("yes\n")
        self.run_case('''address=no; associated=no; prepare
now=1010; wifi_edit_tick
now=1120; wifi_edit_tick
now=1130; wifi_edit_tick
now=1170; wifi_edit_tick
''')
        self.assertEqual(self.status(), "restored_offline")
        self.assertFalse((self.net / "wifi-trial/pending").exists())
        self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)

    def test_missing_backup_fails_closed_and_retains_journal(self):
        self.run_case("prepare\n")
        (self.net / "wifi-trial/previous.conf").unlink()
        self.run_case("if wifi_edit_init; then exit 1; fi\n")
        self.assertEqual(self.status(), "recovery_failed")
        self.assertTrue((self.net / "wifi-trial/pending").exists())

    def test_unowned_daemons_ota_and_bad_requests_are_refused(self):
        for preparation in ('owned=no', 'mkdir -p "$BASE/esphome"; touch "$BASE/esphome/esphome.ota.new"'):
            self.run_case(preparation + "\nprepare\n:")
            self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)
            self.assertFalse((self.base / "wpa-events").exists())
        (self.base / "esphome/esphome.ota.new").unlink()
        original = request()
        for bad in (original + 'extra=option\n', original.replace('scan_ssid=1', 'scan_ssid=2'),
                    original.replace('ssid=66697874757265', 'ssid=abc'),
                    original.replace('1000-42', 'bad;command'),
                    original.replace('fixture-password', 'short'),
                    original.replace('fixture-password', 'p"ass#word')):
            (self.root / "request-fixture").write_text(bad)
            self.run_case("prepare\n:")
            self.assertEqual(self.status(), "refused")
            self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)

    def test_reconfigure_fail_does_not_claim_success(self):
        self.run_case("reconfigure_ok=no; prepare\n:")
        self.assertEqual(self.status(), "recovery_failed")
        self.assertEqual((self.net / "wpa_supplicant.conf").read_text(), self.old)
        self.assertTrue((self.net / "wifi-trial/pending").exists())

    def test_health_guard_skips_only_wifi_during_trial(self):
        self.run_case('''wifi_edit_init
engine_pid=424242
kill() { [ "$failure" != process ]; }
rescue_ports_listening() { [ "$failure" != rescue ]; }
netstat() { [ "$failure" != api ] && echo 'tcp 0 0 0.0.0.0:6053 LISTEN'; }
address=no; associated=no
failure=none
if persistent_health_ready; then exit 1; fi
wifi_edit_phase=connecting
persistent_health_ready || exit 1
for failure in process rescue api; do
  if persistent_health_ready; then exit 1; fi
done
wifi_edit_phase=idle; failure=none
if persistent_health_ready; then exit 1; fi
''')

    def test_shell_syntax_and_no_reboot_or_relay_commands(self):
        subprocess.run(["sh", "-n", str(HELPER)], check=True)
        text = HELPER.read_text()
        for forbidden in ('eval ', 'reboot', '/dev/mtd', 'KC_CTL', 'save_config', 'set -x'):
            self.assertNotIn(forbidden, text)
