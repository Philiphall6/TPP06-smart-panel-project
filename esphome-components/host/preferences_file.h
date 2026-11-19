#pragma once

// Small POSIX-only persistence layer: usable with the panel's old Linux ABI.
// Keep the legacy key/length/value reader for existing installations.
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <map>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace esphome::host::preference_file {
using Values = std::map<uint32_t, std::vector<uint8_t>>;
static constexpr size_t MAX_FILE_SIZE = 1024 * 1024;
static constexpr uint8_t MAGIC[] = {'T', 'P', 'P', 'R', 'E', 'F', '2', 0};

inline void append_u32(std::vector<uint8_t> &out, uint32_t value) {
  for (unsigned shift = 0; shift < 32; shift += 8)
    out.push_back(static_cast<uint8_t>(value >> shift));
}
inline uint32_t read_u32(const uint8_t *data) {
  return uint32_t(data[0]) | (uint32_t(data[1]) << 8) | (uint32_t(data[2]) << 16) |
         (uint32_t(data[3]) << 24);
}
inline uint32_t checksum(const uint8_t *data, size_t length) {
  uint32_t crc = 0xffffffffU;
  for (size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (unsigned bit = 0; bit < 8; ++bit)
      crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
  }
  return ~crc;
}
inline bool decode(const std::vector<uint8_t> &bytes, Values &values, bool allow_legacy = false) {
  if (bytes.size() > MAX_FILE_SIZE)
    return false;
  size_t offset = 0;
  if (bytes.size() >= sizeof(MAGIC) && memcmp(bytes.data(), MAGIC, sizeof(MAGIC)) == 0) {
    if (bytes.size() < 16 || read_u32(bytes.data() + 8) != bytes.size() - 16 ||
        read_u32(bytes.data() + 12) != checksum(bytes.data() + 16, bytes.size() - 16))
      return false;
    offset = 16;
  } else if (!allow_legacy) {
    return false;
  }
  Values parsed;
  while (offset < bytes.size()) {
    if (bytes.size() - offset < 5)
      return false;
    const uint32_t key = read_u32(bytes.data() + offset);
    const size_t length = bytes[offset + 4];
    offset += 5;
    if (length > bytes.size() - offset || parsed.count(key) != 0)
      return false;
    parsed[key] = std::vector<uint8_t>(bytes.begin() + offset, bytes.begin() + offset + length);
    offset += length;
  }
  values.swap(parsed);  // Never expose a partially parsed file.
  return true;
}
inline bool encode(const Values &values, std::vector<uint8_t> &bytes) {
  std::vector<uint8_t> payload;
  for (const auto &entry : values) {
    if (entry.second.size() > 255 || payload.size() + 5 + entry.second.size() > MAX_FILE_SIZE - 16)
      return false;
    append_u32(payload, entry.first);
    payload.push_back(static_cast<uint8_t>(entry.second.size()));
    payload.insert(payload.end(), entry.second.begin(), entry.second.end());
  }
  bytes.assign(MAGIC, MAGIC + sizeof(MAGIC));
  append_u32(bytes, static_cast<uint32_t>(payload.size()));
  append_u32(bytes, checksum(payload.data(), payload.size()));
  bytes.insert(bytes.end(), payload.begin(), payload.end());
  return true;
}
inline bool read_file(const std::string &path, std::vector<uint8_t> &bytes) {
  int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
  if (fd < 0)
    return false;
  struct stat st {};
  bool ok = ::fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_size >= 0 &&
            static_cast<uint64_t>(st.st_size) <= MAX_FILE_SIZE;
  std::vector<uint8_t> result;
  if (ok) {
    result.resize(static_cast<size_t>(st.st_size));
    size_t offset = 0;
    while (offset < result.size()) {
      const ssize_t count = ::read(fd, result.data() + offset, result.size() - offset);
      if (count < 0 && errno == EINTR)
        continue;
      if (count <= 0) {
        ok = false;
        break;
      }
      offset += static_cast<size_t>(count);
    }
  }
  if (::close(fd) != 0)
    ok = false;
  if (ok)
    bytes.swap(result);
  return ok;
}
inline bool load(const std::string &path, Values &values, bool allow_legacy = false) {
  std::vector<uint8_t> bytes;
  return read_file(path, bytes) && decode(bytes, values, allow_legacy);
}
inline bool atomic_write(const std::string &path, const std::vector<uint8_t> &bytes) {
  const size_t slash = path.rfind('/');
  const std::string parent = slash == std::string::npos ? "." : (slash == 0 ? "/" : path.substr(0, slash));
  int dir = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (dir < 0)
    return false;
  std::string temp = path + ".tmp.XXXXXX";
  int fd = ::mkstemp(&temp[0]);  // Unique, same filesystem, mode 0600.
  if (fd < 0) {
    ::close(dir);
    return false;
  }
  bool ok = true;
  size_t offset = 0;
  while (offset < bytes.size()) {
    const ssize_t count = ::write(fd, bytes.data() + offset, bytes.size() - offset);
    if (count < 0 && errno == EINTR)
      continue;
    if (count <= 0) {
      ok = false;
      break;
    }
    offset += static_cast<size_t>(count);
  }
  if (ok && ::fsync(fd) != 0)
    ok = false;
  if (::close(fd) != 0)
    ok = false;
  if (ok && ::rename(temp.c_str(), path.c_str()) != 0)
    ok = false;
  if (ok && ::fsync(dir) != 0)
    ok = false;  // A rename may already have committed; report uncertain durability.
  ::close(dir);
  ::unlink(temp.c_str());
  return ok;
}
inline bool sync_parent(const std::string &path) {
  const size_t slash = path.rfind('/');
  const std::string parent = slash == std::string::npos ? "." : (slash == 0 ? "/" : path.substr(0, slash));
  int fd = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (fd < 0) return false;
  const bool synced = ::fsync(fd) == 0;
  const bool closed = ::close(fd) == 0;
  return synced && closed;
}
inline bool save(const std::string &path, const Values &values) {
  std::vector<uint8_t> next, previous;
  if (!encode(values, next))
    return false;
  Values checked;
  if (read_file(path, previous) && decode(previous, checked)) {
    if (previous == next)
      return sync_parent(path);  // Retry a previously uncertain directory sync.
    // Re-encode legacy data as checksummed data in the backup too.
    if (!encode(checked, previous) || !atomic_write(path + ".bak", previous))
      return false;
  } else if (!load(path + ".bak", checked)) {
    // First migration also gets a durable second copy before the primary.
    if (!atomic_write(path + ".bak", next))
      return false;
  }
  // Never replace the good backup with a corrupt primary file.
  return atomic_write(path, next);
}
}  // namespace esphome::host::preference_file
