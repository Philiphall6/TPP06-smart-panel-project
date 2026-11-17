#include "esphome/components/md5/md5.h"
#include "esphome/components/sha256/sha256.h"

#include <cstdio>
#include <cstring>

template<typename T> bool check(const char *input, const char *expected) {
  T hash;
  hash.init();
  hash.add(reinterpret_cast<const uint8_t *>(input), std::strlen(input));
  hash.calculate();
  uint8_t bytes[32];
  hash.get_bytes(bytes);
  char actual[65];
  static constexpr char HEX[] = "0123456789abcdef";
  for (size_t i = 0; i < hash.get_size(); i++) {
    actual[i * 2] = HEX[bytes[i] >> 4];
    actual[i * 2 + 1] = HEX[bytes[i] & 15];
  }
  actual[hash.get_size() * 2] = '\0';
  if (std::strcmp(actual, expected) == 0)
    return true;
  std::fprintf(stderr, "hash mismatch for '%s': %s != %s\n", input, actual, expected);
  return false;
}

int main() {
  bool ok = true;
  ok &= check<esphome::md5::MD5Digest>("", "d41d8cd98f00b204e9800998ecf8427e");
  ok &= check<esphome::md5::MD5Digest>("abc", "900150983cd24fb0d6963f7d28e17f72");
  ok &= check<esphome::sha256::SHA256>("", "e3b0c44298fc1c149afbf4c8996fb924"
                                          "27ae41e4649b934ca495991b7852b855");
  ok &= check<esphome::sha256::SHA256>("abc", "ba7816bf8f01cfea414140de5dae2223"
                                             "b00361a396177a9cb410ff61f20015ad");
  return ok ? 0 : 1;
}
