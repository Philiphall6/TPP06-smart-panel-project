"""Mock the Linux GET ioctl: no radio or nearby device access in these tests."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gcc"), "native C compiler required")
class HciInfoTests(unittest.TestCase):
    def test_cached_info_unknown_features_and_read_only_ioctl(self):
        code = r'''
#include <stdarg.h>
#include <assert.h>
#define socket mock_socket
#define ioctl mock_ioctl
#define close mock_close
#define main probe_main
#include "tpp06_hci_info.c"
#undef main
#undef socket
#undef ioctl
#undef close
static int socket_calls, ioctl_calls, close_calls, mode;
int mock_socket(int family, int type, int protocol) {
  ++socket_calls;
  assert(family == 31 && type == (SOCK_RAW | SOCK_CLOEXEC) && protocol == 1);
  if (mode == 3) { errno = EAFNOSUPPORT; return -1; }
  return 123;
}
int mock_close(int fd) { assert(fd == 123); ++close_calls; return 0; }
int mock_ioctl(int fd, unsigned long request, ...) {
  assert(fd == 123 && request == _IOR('H', 211, int));
  ++ioctl_calls;
  if (mode == 4) { errno = ENODEV; return -1; }
  va_list args;
  va_start(args, request);
  struct controller_info *info = va_arg(args, struct controller_info *);
  va_end(args);
  assert(info->index == 0);
  if (mode == 0) { info->features[4] = 0x40; info->flags = 5; }
  if (mode == 2) info->features[0] = 1;
  return 0;
}
int main(void) {
  char *normal[] = {"probe", NULL};
  for (mode = 0; mode < 5; ++mode) {
    assert(probe_main(1, normal) == (mode >= 3 ? 1 : 0));
  }
  assert(socket_calls == 5 && ioctl_calls == 4 && close_calls == 4);
  char *help[] = {"probe", "--help", NULL};
  assert(probe_main(2, help) == 0);
  char *bad[] = {"probe", NULL, NULL};
  char *values[] = {"-1", "65536", "", "0x01", "1oops", "9999999999999999999999999999"};
  for (size_t i=0; i < sizeof(values)/sizeof(values[0]); ++i) {
    bad[1] = values[i];
    assert(probe_main(2, bad) == 2);
  }
  assert(socket_calls == 5 && ioctl_calls == 4 && close_calls == 4);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "test.c").write_text(code)
            subprocess.run(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "tools"), str(folder / "test.c"),
                            "-o", str(folder / "test")], check=True)
            result = subprocess.run([str(folder / "test")], text=True, capture_output=True,
                                    check=True, timeout=5)
            for expected in ("LE_CACHED=yes", "LE_CACHED=no", "LE_CACHED=unknown",
                             "HCI_UP=yes", "HCI_UP=no", "HA_FORWARDING_TESTED=no"):
                self.assertIn(expected, result.stdout)
            self.assertNotIn("address", result.stdout.lower())
            self.assertIn("HCI_SOCKET_ERROR", result.stderr)
            self.assertIn("HCI_QUERY_ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
