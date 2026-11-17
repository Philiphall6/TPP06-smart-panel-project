#pragma once

#include "esphome/core/hash_base.h"

#include <cstddef>
#include <cstdint>
#include <string>

namespace esphome::sha256 {

class SHA256 final : public esphome::HashBase {
 public:
  SHA256() = default;
  ~SHA256() override = default;

  void init() override;
  void add(const uint8_t *data, size_t len) override;
  using HashBase::add;
  void add(const std::string &data) { this->add(reinterpret_cast<const uint8_t *>(data.data()), data.size()); }
  void calculate() override;
  size_t get_size() const override { return 32; }

 protected:
  void transform_(const uint8_t block[64]);

  uint32_t state_[8]{};
  uint64_t byte_count_{0};
  uint8_t buffer_[64]{};
  bool calculated_{false};
};

}  // namespace esphome::sha256
