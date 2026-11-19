#ifdef USE_HOST

#include <cerrno>
#include <cstring>
#include <sys/stat.h>
#include "preferences.h"
#include "preferences_file.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"

namespace esphome::host {

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
      struct stat st {};
      if (::stat(current.c_str(), &st) != 0 || !S_ISDIR(st.st_mode))
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
  if (pref_path.empty() || !create_directories_legacy(pref_path)) {
    ESP_LOGE(TAG, "Failed to create preferences directory: %s (%s)", pref_path.c_str(), std::strerror(errno));
    return;
  }
  this->filename_ = pref_path;
  this->filename_.append("/");
  this->filename_.append(App.get_name());
  this->filename_.append(".prefs");
  const std::string legacy_filename = this->filename_;
  this->filename_.append(".v2");
  bool loaded = preference_file::load(this->filename_, this->data_);
  if (!loaded && preference_file::load(this->filename_ + ".bak", this->data_)) {
    loaded = true;
    ESP_LOGW(TAG, "Recovered preferences from previous valid copy");
    this->dirty_ = true;
  }
  struct stat st {};
  const bool primary_missing = ::lstat(this->filename_.c_str(), &st) != 0 && errno == ENOENT;
  const bool backup_missing = ::lstat((this->filename_ + ".bak").c_str(), &st) != 0 && errno == ENOENT;
  if (primary_missing && backup_missing && preference_file::load(legacy_filename, this->data_, true)) {
    // Leave the old format intact for an old application used as recovery.
    // Never resurrect legacy settings over a present but damaged v2 store.
    this->dirty_ = true;
    ESP_LOGI(TAG, "Migrating legacy preferences; original copy retained");
  } else if (!loaded && (!primary_missing || !backup_missing)) {
    ESP_LOGW(TAG, "No valid preference copy; defaults used, legacy not resurrected");
  }
  this->setup_complete_ = true;
}

bool HostPreferences::sync() {
  this->setup_();
  if (this->filename_.empty()) {
    ESP_LOGE(TAG, "Preferences filename not set, unable to save preferences");
    return false;
  }
  if (!this->dirty_)
    return true;
  if (!preference_file::save(this->filename_, this->data_)) {
    ESP_LOGE(TAG, "Atomic preference save failed; will retry");
    return false;
  }
  this->dirty_ = false;
  return true;
}

bool HostPreferences::reset() {
  this->setup_();
  if (!this->setup_complete_)
    return false;
  this->data_.clear();
  this->dirty_ = true;
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
