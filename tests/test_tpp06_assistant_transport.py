"""Exercise the actual threaded transport against a synthetic local process."""
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tpp06_assistant_transport import AssistantSession, Console, TransportError


EMULATOR = r'''
import sys, re
def emit(text):
    sys.stdout.write(text)
    sys.stdout.flush()
emit("Tuya login: ")
assert sys.stdin.readline().strip() == "root"
emit("Password: ")
password = sys.stdin.readline().strip()
if password != "synthetic-secret":
    emit("Login incorrect\n")
    sys.exit(1)
emit("\nroot@fixture:~# ")
changing = 0
for line in sys.stdin:
    if changing:
        assert line.strip() == "New-1234"
        if changing == 1:
            emit("Retype password: ")
            changing = 2
        else:
            emit("\nPassword changed\nroot@fixture:~# ")
            changing = 0
    elif line == "passwd root\n":
        emit("New password: ")
        changing = 1
    elif line == "exit\n":
        break
    elif line.startswith("printf '\\n__ASSIST_"):
        marker = re.search(r"__ASSIST_[0-9a-f]+", line).group()
        # Echo the command first: transport must not accept the echo as success.
        emit(line + "\nASSIST_TEST=yes\n" + marker + "0\nroot@fixture:~# ")
'''


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = Path(self.tmp.name) / "console.py"
        self.fixture.write_text(EMULATOR)

    def process(self):
        return subprocess.Popen([sys.executable, "-u", str(self.fixture)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_login_command_and_interactive_password_use_pipes(self):
        process = self.process()
        console = Console(process, "synthetic-secret", timeout=3)
        try:
            result = console.command("echo fixture", timeout=3)
            self.assertEqual(result.returncode, 0)
            self.assertIn("ASSIST_TEST=yes", result.stdout)
            self.assertNotIn("synthetic-secret", result.stdout)
            console.passwd("New-1234")
            self.assertEqual(console.command("echo fixture", timeout=3).returncode, 0)
        finally:
            console.close()
        self.assertIsNotNone(process.poll())

    def test_wrong_password_fails_without_leaking_secret(self):
        process = self.process()
        with self.assertRaises(TransportError) as error:
            Console(process, "wrong-private-password", timeout=3)
        self.assertNotIn("wrong-private-password", str(error.exception))
        self.assertIsNotNone(process.poll())

    def test_oversize_shell_line_is_refused(self):
        console = Console(self.process(), "synthetic-secret", timeout=3)
        try:
            with self.assertRaises(TransportError):
                console.command("x" * 481)
        finally:
            console.close()

    def test_session_uses_argument_array_and_never_select(self):
        session = AssistantSession("192.0.2.1", "synthetic-secret", adb="adb.exe")
        process = self.process()
        with patch("tpp06_assistant_transport.subprocess.Popen", return_value=process) as launch:
            result = session.run_root("echo fixture")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(launch.call_args.args[0], ["adb.exe", "-s", "192.0.2.1:5555", "shell"])
        self.assertNotIn("shell", launch.call_args.kwargs)
        self.assertNotIn("synthetic-secret", str(launch.call_args))


if __name__ == "__main__":
    unittest.main()
