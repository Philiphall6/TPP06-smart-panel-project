#include "md5.h"

#ifdef USE_MD5

#include <algorithm>
#include <cstring>

namespace esphome::md5 {

namespace {

inline uint32_t rotl(uint32_t value, uint32_t bits) { return (value << bits) | (value >> (32U - bits)); }

constexpr uint32_t K[64] = {
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
    0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
    0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
    0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
    0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
    0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
    0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
    0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391,
};

constexpr uint8_t S[64] = {
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
};

}  // namespace

void MD5Digest::init() {
  this->state_[0] = 0x67452301;
  this->state_[1] = 0xefcdab89;
  this->state_[2] = 0x98badcfe;
  this->state_[3] = 0x10325476;
  this->byte_count_ = 0;
  this->calculated_ = false;
  std::memset(this->buffer_, 0, sizeof(this->buffer_));
  std::memset(this->digest_, 0, sizeof(this->digest_));
}

void MD5Digest::transform_(const uint8_t block[64]) {
  uint32_t words[16];
  for (uint8_t i = 0; i < 16; i++) {
    const uint8_t *p = block + i * 4;
    words[i] = static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
               (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
  }

  uint32_t a = this->state_[0], b = this->state_[1], c = this->state_[2], d = this->state_[3];
  for (uint8_t i = 0; i < 64; i++) {
    uint32_t f;
    uint8_t g;
    if (i < 16) {
      f = (b & c) | (~b & d);
      g = i;
    } else if (i < 32) {
      f = (d & b) | (~d & c);
      g = static_cast<uint8_t>((5 * i + 1) & 15);
    } else if (i < 48) {
      f = b ^ c ^ d;
      g = static_cast<uint8_t>((3 * i + 5) & 15);
    } else {
      f = c ^ (b | ~d);
      g = static_cast<uint8_t>((7 * i) & 15);
    }
    const uint32_t next_d = d;
    d = c;
    c = b;
    b += rotl(a + f + K[i] + words[g], S[i]);
    a = next_d;
  }
  this->state_[0] += a;
  this->state_[1] += b;
  this->state_[2] += c;
  this->state_[3] += d;
}

void MD5Digest::add(const uint8_t *data, size_t len) {
  if (this->calculated_)
    return;
  size_t used = static_cast<size_t>(this->byte_count_ & 63U);
  this->byte_count_ += len;
  while (len > 0) {
    const size_t take = std::min(len, 64U - used);
    std::memcpy(this->buffer_ + used, data, take);
    used += take;
    data += take;
    len -= take;
    if (used == 64) {
      this->transform_(this->buffer_);
      used = 0;
    }
  }
}

void MD5Digest::calculate() {
  if (this->calculated_)
    return;
  const uint64_t bit_count = this->byte_count_ * 8U;
  uint8_t padding[72] = {0x80};
  const size_t used = static_cast<size_t>(this->byte_count_ & 63U);
  const size_t pad_len = used < 56 ? 56 - used : 120 - used;
  this->add(padding, pad_len);
  uint8_t length[8];
  for (uint8_t i = 0; i < 8; i++)
    length[i] = static_cast<uint8_t>(bit_count >> (i * 8));
  this->add(length, sizeof(length));
  for (uint8_t i = 0; i < 4; i++) {
    this->digest_[i * 4] = static_cast<uint8_t>(this->state_[i]);
    this->digest_[i * 4 + 1] = static_cast<uint8_t>(this->state_[i] >> 8);
    this->digest_[i * 4 + 2] = static_cast<uint8_t>(this->state_[i] >> 16);
    this->digest_[i * 4 + 3] = static_cast<uint8_t>(this->state_[i] >> 24);
  }
  this->calculated_ = true;
}

}  // namespace esphome::md5

#endif
