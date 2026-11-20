"""Opt-in Tk smoke tests. Run on a desktop with TPP06_TEST_TK=1.

All windows stay withdrawn and network calls are forbidden by a mock.
"""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tpp06_assistant import Assistant


@unittest.skipUnless(os.environ.get("TPP06_TEST_TK") == "1", "Opt-in desktop test")
class GuiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.network = patch("socket.create_connection", side_effect=AssertionError("No device connections in GUI tests"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Assistant(self.root)
        self.addCleanup(self.dispose)
        self.root.update_idletasks()

    def dispose(self):
        self.root.after_cancel(self.app.timer)
        self.root.destroy()

    def wait_job(self):
        deadline = time.monotonic() + 3
        while self.app.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.app.busy)

    def test_password_never_logged_and_address_change_clears_it(self):
        self.app.host.set("192.0.2.1")
        self.app.start("Test", lambda: "synthetic-private-password", "password")
        self.wait_job()
        self.assertEqual(self.app.password.get(), "synthetic-private-password")
        self.assertNotIn("synthetic-private-password", self.app.log.get("1.0", "end"))
        self.assertNotEqual(self.app.password_entry.cget("show"), "")
        self.app.host.set("192.0.2.2")
        self.assertEqual(self.app.password.get(), "")

    def test_failed_worker_recovers_buttons_without_raw_exception(self):
        def fail():
            raise RuntimeError("synthetic-private-password")
        self.app.start("Test", fail)
        self.wait_job()
        self.assertNotIn("synthetic-private-password", self.app.log.get("1.0", "end"))
        for button, enabled in self.app.buttons:
            self.assertEqual(str(button.cget("state")), "normal" if enabled else "disabled")

    def test_busy_blocks_second_job_and_close(self):
        self.app.busy = True
        calls = []
        self.app.start("Must not run", lambda: calls.append(True))
        self.assertFalse(calls)
        with patch("tkinter.messagebox.showinfo") as warning:
            self.app.close()
        warning.assert_called_once()
        self.assertTrue(self.root.winfo_exists())

    def test_layout_does_not_request_a_tall_unscrollable_window(self):
        self.assertLessEqual(self.root.winfo_reqheight(), 800)

    def test_adb_form_uses_explicit_post_adb_consent_without_dump(self):
        data = {"parent": "synthetic-private-folder", "artifacts": "synthetic-tools"}
        with patch.object(self.app, "operation_form", return_value=data) as form, \
             patch("tpp06_assistant_jobs.activate_adb", return_value={"etat": "simulation"}) as activate:
            self.app.operation("adb")
            self.wait_job()
            fields = form.call_args.args[1]
            self.assertNotIn("dump", [field[0] for field in fields])
            self.assertIn("APRÈS ADB", form.call_args.args[2])
            self.assertTrue(activate.call_args.kwargs["accept_post_adb_reference"])

    def test_nand_button_routes_to_capture_not_partial_backup(self):
        data = {"parent": "synthetic-private-folder", "artifacts": "synthetic-tools"}
        with patch.object(self.app, "operation_form", return_value=data), \
             patch("tpp06_assistant_core.connect_adb", return_value="fake-session"), \
             patch("tpp06_assistant_nand.capture_reference", return_value={"etat": "simulation"}) as capture, \
             patch("tpp06_assistant_core.backup_panel") as partial:
            self.app.operation("nand")
            self.wait_job()
            capture.assert_called_once()
            self.assertEqual(capture.call_args.args[:3], ("fake-session", data["parent"], data["artifacts"]))
            partial.assert_not_called()


if __name__ == "__main__":
    unittest.main()
