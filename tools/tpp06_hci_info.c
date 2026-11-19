/* Read Linux's cached HCI information; never power, reset, scan or pair.
 * UAPI layout/reference:
 * https://github.com/bluez/bluez/blob/master/lib/bluetooth/hci.h
 * No libbluetooth dependency and no device addresses printed.
 */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

/* Linux HCIGETDEVINFO ABI; fixed-width fields, native alignment, not packed. */
struct controller_info {
  uint16_t index;
  char name[8];
  uint8_t address[6];
  uint32_t flags;
  uint8_t type;
  uint8_t features[8];
  uint32_t packet_type, link_policy, link_mode;
  uint16_t acl_mtu, acl_packets, sco_mtu, sco_packets;
  uint32_t statistics[10];
};
_Static_assert(sizeof(struct controller_info) == 92, "HCI ioctl ABI size mismatch");
_Static_assert(offsetof(struct controller_info, flags) == 16, "HCI flags ABI mismatch");
_Static_assert(offsetof(struct controller_info, features) == 21, "HCI features ABI mismatch");

int main(int argc, char **argv) {
  unsigned long index = 0;
  if (argc == 2 && strcmp(argv[1], "--help") == 0) {
    puts("Usage: tpp06-hci-info [controller-index]\nRead-only cached HCI status. No scan, reset or radio command.");
    return 0;
  }
  if (argc > 2) return 2;
  if (argc == 2) {
    char *end = NULL;
    if (argv[1][0] < '0' || argv[1][0] > '9') return 2;
    errno = 0;
    index = strtoul(argv[1], &end, 10);
    if (errno || *end || index > UINT16_MAX) return 2;
  }
  /* AF_BLUETOOTH / BTPROTO_HCI: a raw socket for the GET ioctl only.
   * No bind/send/write/setsockopt, so no HCI command reaches the controller. */
  int fd = socket(31, SOCK_RAW | SOCK_CLOEXEC, 1);
  if (fd < 0) {
    fprintf(stderr, "HCI_SOCKET_ERROR=%s\n", strerror(errno));
    return 1;
  }
  struct controller_info info = {0};
  info.index = (uint16_t) index;
  if (ioctl(fd, _IOR('H', 211, int), &info) < 0) {
    const int saved_errno = errno;
    close(fd);
    fprintf(stderr, "HCI_QUERY_ERROR=%s\n", strerror(saved_errno));
    return 1;
  }
  close(fd);
  unsigned int has_cached_features = 0;
  for (size_t i = 0; i < sizeof(info.features); ++i) has_cached_features |= info.features[i];
  printf("HCI_INDEX=%lu\nHCI_UP=%s\nHCI_RUNNING=%s\nLE_CACHED=%s\n",
         index, (info.flags & 1u) ? "yes" : "no",
         (info.flags & 4u) ? "yes" : "no",
         !has_cached_features ? "unknown" : (info.features[4] & 0x40) ? "yes" : "no");
  puts("SCAN_TESTED=no\nHA_FORWARDING_TESTED=no");
  return 0;
}
