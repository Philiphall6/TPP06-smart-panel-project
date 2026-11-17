#pragma once

#include "esphome/core/defines.h"

#ifdef USE_MD5

#include "esphome/core/hash_base.h"

#include <cstddef>
#include <cstdint>

namespace esphome::md5 {

class MD5Digest final : public HashBase {
 public:
  MD5Digest() = default;
  ~MD5Digest() override = default;

  void init() override;
  void add(const uint8_t *data, size_t len) override;
  using HashBase::add;
  void calculate() override;
  size_t get_size() const override { return 16; }

 protected:
  void transform_(const uint8_t block[64]);

  uint32_t state_[4]{};
  uint64_t byte_count_{0};
  uint8_t buffer_[64]{};
  bool calculated_{false};
};

}  // namespace esphome::md5

#endif
