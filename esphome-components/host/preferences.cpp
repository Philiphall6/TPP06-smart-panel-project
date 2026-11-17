#ifdef USE_HOST

#include <filesystem>
#include <fstream>
#include <cerrno>
#include <cstring>
#include <sys/stat.h>
#include "preferences.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"

namespace esphome::host {
namespace fs = std::filesystem;

static const char *const TAG = "preferences";

static bool create_directories_legacy(const std::string &path) {
  std::string current;
  size_t start = 0;
  if (!path.empty() && path[0] == '/') {
    current = "/";
    start = 1;
  }
  while (start <= path.size()) {
    const size_t end = path.find('/', start);
    const std::string part = path.substr(start, end == std::string::npos ? end : end - start);
    if (!part.empty()) {
      if (current.size() > 1 && current.back() != '/')
        current += '/';
      current += part;
      if (::mkdir(current.c_str(), 0755) != 0 && errno != EEXIST)
        return false;
    }
    if (end == std::string::npos)
      break;
    start = end + 1;
  }
  return true;
}

void HostPreferences::setup_() {
  if (this->setup_complete_)
    return;
  const char *prefdir = getenv("ESPHOME_PREFDIR");
  std::string pref_path;
  if (prefdir != nullptr) {
    pref_path = prefdir;
  } else {
    const char *home = getenv("HOME");
    if (home == nullptr) {
      ESP_LOGE(TAG, "ESPHOME_PREFDIR and HOME environment variables not set, unable to save preferences");
      return;
    }
    pref_path = std::string(home) + "/.esphome/prefs";
  }
  if (!create_directories_legacy(pref_path)) {
    ESP_LOGE(TAG, "Failed to create preferences directory: %s (%s)", pref_path.c_str(), std::strerror(errno));
    return;
  }
  this->filename_ = pref_path;
  this->filename_.append("/");
  this->filename_.append(App.get_name());
  this->filename_.append(".prefs");
  FILE *fp = fopen(this->filename_.c_str(), "rb");
  if (fp != nullptr) {
    while (!feof(fp)) {
      uint32_t key;
      uint8_t len;
      if (fread(&key, sizeof(key), 1, fp) != 1)
        break;
      if (fread(&len, sizeof(len), 1, fp) != 1)
        break;
      uint8_t data[len];
      if (fread(data, sizeof(uint8_t), len, fp) != len)
        break;
      std::vector vec(data, data + len);
      this->data_[key] = vec;
    }
    fclose(fp);
  }
  this->setup_complete_ = true;
}

bool HostPreferences::sync() {
  this->setup_();
  if (this->filename_.empty()) {
    ESP_LOGE(TAG, "Preferences filename not set, unable to save preferences");
    return false;
  }
  FILE *fp = fopen(this->filename_.c_str(), "wb");
  if (fp == nullptr) {
    ESP_LOGE(TAG, "Failed to open preferences file for writing: %s", this->filename_.c_str());
    return false;
  }

  for (auto &it : this->data_) {
    fwrite(&it.first, sizeof(uint32_t), 1, fp);
    uint8_t len = it.second.size();
    fwrite(&len, sizeof(len), 1, fp);
    fwrite(it.second.data(), sizeof(uint8_t), it.second.size(), fp);
  }
  fclose(fp);
  return true;
}

bool HostPreferences::reset() {
  host_preferences->data_.clear();
  return true;
}

ESPPreferenceObject HostPreferences::make_preference(size_t length, uint32_t type, bool in_flash) {
  auto *backend = new HostPreferenceBackend(type);
  return ESPPreferenceObject(backend);
};

static HostPreferences s_preferences;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)

HostPreferences *get_preferences() { return &s_preferences; }

void setup_preferences() {
  host_preferences = &s_preferences;
  global_preferences = &s_preferences;
}

bool HostPreferenceBackend::save(const uint8_t *data, size_t len) const {
  return host_preferences->save(this->key_, data, len);
}

bool HostPreferenceBackend::load(uint8_t *data, size_t len) const {
  return host_preferences->load(this->key_, data, len);
}

HostPreferences *host_preferences;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)

}  // namespace esphome::host

namespace esphome {
ESPPreferences *global_preferences;  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)
}  // namespace esphome

#endif  // USE_HOST
