"""Offline-only shell tests: fake network programs, no hardware commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "device/tpp06-multiboot.sh"


class IsolatedBootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.base = self.root / "state"
        (self.base / "network").mkdir(parents=True)
        (self.base / "network/wpa_supplicant.conf").write_text(
            'network = {\nssid="test-only"\npsk="test-only"\n}\n')
        (self.root / "sys/class/net/wlan0").mkdir(parents=True)
        (self.root / "proc/42/fd").mkdir(parents=True)
        (self.root / "proc/42/fd/3").symlink_to("/dev/null")
        self.mock("pidof", '[ "$1" = ak_watchdog ] && { echo 42; exit 0; }; exit 1')
        self.mock("ifconfig", '[ "$2" = up ] && exit 0\n'
                  f'[ -f "{self.root}/associated" ] && echo "inet addr:192.0.2.2"')
        self.mock("wpa_supplicant", f'touch "{self.root}/associated"')
        self.mock("wpa_cli", 'echo wpa_state=COMPLETED')
        self.mock("udhcpc", f'printf "%s\\n" "$@" > "{self.root}/dhcp-args"')
        self.mock("netstat", 'echo "tcp 0 0 0.0.0.0:5555 LISTEN"\necho "tcp 0 0 0.0.0.0:8090 LISTEN"')
        self.mock("sleep", "exit 0")
        self.env = {**os.environ, "PATH": str(self.bin) + ":" + os.environ["PATH"],
                    "TPP06_BASE": str(self.base), "TPP06_SYS_ROOT": str(self.root / "sys"),
                    "TPP06_PROC_ROOT": str(self.root / "proc"),
                    "TPP06_FRAMEBUFFER_DEVICE": "/dev/null", "TPP06_TOUCH_DEVICE": "/dev/null",
                    "TPP06_WATCHDOG_DEVICE": "/dev/null", "TPP06_DHCP_SCRIPT": "/bin/true"}
        # Load functions only; never dispatch a supervisor start/stop action.
        self.functions = SCRIPT.read_text().rsplit('\ncase "$1" in', 1)[0]

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o700)

    def run_function(self, name, **environment):
        result = subprocess.run(["sh"], input=self.functions + "\n" + name + "\n",
                                env={**self.env, **environment}, text=True,
                                capture_output=True, timeout=5)
        self.assertNotIn("test-only", result.stdout + result.stderr)
        return result

    def test_prerequisites_accept_mocked_boot_devices(self):
        self.assertEqual(self.run_function("isolated_boot_prerequisites").returncode, 0)

    def test_missing_interface_display_touch_watchdog_or_dhcp_hook_refused(self):
        for variable in ("TPP06_SYS_ROOT", "TPP06_FRAMEBUFFER_DEVICE", "TPP06_TOUCH_DEVICE",
                         "TPP06_WATCHDOG_DEVICE", "TPP06_DHCP_SCRIPT"):
            with self.subTest(variable=variable):
                result = self.run_function("isolated_boot_prerequisites",
                                           **{variable: str(self.root / "missing")})
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "associated").exists())

    def test_watchdog_name_without_open_descriptor_is_not_enough(self):
        (self.root / "proc/42/fd/3").unlink()
        self.assertNotEqual(self.run_function("isolated_boot_prerequisites").returncode, 0)

    def test_rescue_requires_both_listeners(self):
        self.assertEqual(self.run_function("rescue_ports_listening").returncode, 0)
        for port in (5555, 8090, 16053):
            with self.subTest(port=port):
                self.mock("netstat", f'echo "tcp 0 0 0.0.0.0:{port} LISTEN"')
                self.assertNotEqual(self.run_function("rescue_ports_listening").returncode, 0)

    def test_network_requires_association_and_runs_explicit_dhcp_hook(self):
        result = self.run_function("start_independent_network")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = (self.root / "dhcp-args").read_text().splitlines()
        self.assertEqual(args[args.index("-s") + 1], "/bin/true")

    def test_interface_up_failure_prevents_daemons(self):
        self.mock("ifconfig", "exit 1")
        self.assertNotEqual(self.run_function("start_independent_network").returncode, 0)
        self.assertFalse((self.root / "associated").exists())
        self.assertFalse((self.root / "dhcp-args").exists())

    def test_address_without_association_is_rejected(self):
        self.mock("wpa_cli", "echo wpa_state=DISCONNECTED")
        self.assertNotEqual(self.run_function("start_independent_network").returncode, 0)
        self.assertIn("association or IPv4", (self.base / "diagnostics/multiboot.log").read_text())

    def test_dhcp_launch_failure_is_rejected(self):
        self.mock("udhcpc", "exit 1")
        self.assertNotEqual(self.run_function("start_independent_network").returncode, 0)

    def test_confirmed_local_boot_starts_without_access_point_or_lease(self):
        for name, value in {"local_control_confirmed": "yes", "persistent_confirmed": "yes",
                            "boot_policy": "persistent", "network_mode": "isolated"}.items():
            (self.base/name).write_text(value+"\n")
        self.mock("wpa_supplicant", "exit 0")  # Daemon starts, AP never appears.
        self.mock("wpa_cli", "echo wpa_state=DISCONNECTED")
        result = self.run_function("start_independent_network")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root/"associated").exists())
        self.assertTrue((self.root/"dhcp-args").exists())
        self.assertIn("recovery continues in background", (self.base/"diagnostics/multiboot.log").read_text())
        # A real daemon launch failure is still rejected.
        self.mock("wpa_supplicant", "exit 1")
        self.assertNotEqual(self.run_function("start_independent_network").returncode, 0)

    def test_ipv4_check_rejects_unconfigured_loopback_link_local_and_invalid(self):
        for address in ("0.0.0.0", "127.0.0.1", "169.254.1.2", "224.0.0.1",
                        "192.0.2.999", "unknown", "192.0.2"):
            with self.subTest(address=address):
                self.mock("ifconfig", f'echo "inet addr:{address}"')
                self.assertNotEqual(self.run_function("wlan_has_address").returncode, 0)
        for text in ("inet addr:192.0.2.2", "inet 192.0.2.2 netmask 255.255.255.0"):
            self.mock("ifconfig", f'echo "{text}"')
            self.assertEqual(self.run_function("wlan_has_address").returncode, 0)
