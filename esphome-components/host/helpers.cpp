#include "esphome/core/helpers.h"

#ifdef USE_HOST

#ifndef _WIN32
#include <net/if.h>
#include <netinet/in.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <net/if_arp.h>
#endif
#include <unistd.h>

#include "esphome/core/defines.h"
#include "esphome/core/log.h"

namespace esphome {

static const char *const TAG = "helpers.host";

bool random_bytes(uint8_t *data, size_t len) {
  FILE *fp = fopen("/dev/urandom", "r");
  if (fp == nullptr) {
    ESP_LOGW(TAG, "Could not open /dev/urandom, errno=%d", errno);
    exit(1);
  }
  size_t read = fread(data, 1, len, fp);
  if (read != len) {
    ESP_LOGW(TAG, "Not enough data from /dev/urandom");
    exit(1);
  }
  fclose(fp);
  return true;
}

// Host platform uses std::mutex for proper thread synchronization
Mutex::Mutex() { handle_ = new std::mutex(); }
Mutex::~Mutex() { delete static_cast<std::mutex *>(handle_); }
void Mutex::lock() { static_cast<std::mutex *>(handle_)->lock(); }
bool Mutex::try_lock() { return static_cast<std::mutex *>(handle_)->try_lock(); }
void Mutex::unlock() { static_cast<std::mutex *>(handle_)->unlock(); }

void get_mac_address_raw(uint8_t *mac) {  // NOLINT(readability-non-const-parameter)
#ifdef USE_ESPHOME_HOST_NETWORK_INTERFACE
  // Read on the target, never on the build server. Cache the identity for this
  // process lifetime so all API and DNS-SD records agree, even during DHCP loss.
  static uint8_t hardware_mac[MAC_ADDRESS_SIZE];
  static bool initialized = false;
  if (!initialized) {
    struct ifreq request {};
    strncpy(request.ifr_name, USE_ESPHOME_HOST_NETWORK_INTERFACE, IFNAMSIZ - 1);
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    bool valid = fd >= 0 && ioctl(fd, SIOCGIFHWADDR, &request) == 0 &&
                 request.ifr_hwaddr.sa_family == ARPHRD_ETHER;
    if (fd >= 0)
      close(fd);
    if (valid) {
      memcpy(hardware_mac, request.ifr_hwaddr.sa_data, MAC_ADDRESS_SIZE);
      uint8_t any = 0;
      for (uint8_t byte : hardware_mac)
        any |= byte;
      valid = any != 0 && (hardware_mac[0] & 1) == 0;
    }
    if (!valid) {
      // A shared fake MAC would silently merge unrelated devices in HA.
      // Fail closed; the external supervisor can retain the stock application.
      ESP_LOGE(TAG, "Cannot obtain a valid MAC from configured network interface");
      exit(1);
    }
    initialized = true;
  }
  memcpy(mac, hardware_mac, MAC_ADDRESS_SIZE);
#else
  static const uint8_t esphome_host_mac_address[MAC_ADDRESS_SIZE] = USE_ESPHOME_HOST_MAC_ADDRESS;
  memcpy(mac, esphome_host_mac_address, sizeof(esphome_host_mac_address));
#endif
}

}  // namespace esphome

#endif  // USE_HOST
