#include "wifi.h"
#ifdef USE_HOST
#include "profile.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

namespace esphome::tpp06_wifi {
static const std::string DIR = "/tmp/tpp06-wifi-editor/";
static bool private_dir() {
  struct stat st{};
  return geteuid() == 0 && lstat(DIR.substr(0, DIR.size() - 1).c_str(), &st) == 0 &&
         S_ISDIR(st.st_mode) && st.st_uid == 0 && (st.st_mode & 077) == 0;
}
static std::string read_private(const char *name, size_t limit = 159) {
  if (!private_dir()) return {};
  int fd = open((DIR + name).c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
  if (fd < 0) return {};
  struct stat st{};
  std::string result;
  if (fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_uid == 0 &&
      (st.st_mode & 077) == 0 && st.st_size > 0 && st.st_size <= static_cast<off_t>(limit)) {
    result.resize(st.st_size);
    size_t done = 0;
    while (done < result.size()) {
      ssize_t n = read(fd, &result[done], result.size() - done);
      if (n < 0 && errno == EINTR) continue;
      if (n <= 0) break;
      done += static_cast<size_t>(n);
    }
    if (done != result.size()) result.clear();
  }
  close(fd);
  return result;
}
static bool write_private(const char *name, const std::string &content) {
  if (!private_dir()) return false;
  std::string temporary = DIR + name + ".screen-new";
  int fd = open(temporary.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (fd < 0) return false;
  size_t done = 0;
  while (done < content.size()) {
    ssize_t n = write(fd, content.data() + done, content.size() - done);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) break;
    done += static_cast<size_t>(n);
  }
  bool ok = done == content.size() && fsync(fd) == 0;
  if (close(fd) != 0) ok = false;
  if (ok) ok = rename(temporary.c_str(), (DIR + name).c_str()) == 0;
  if (!ok) unlink(temporary.c_str());
  return ok;
}
bool WifiEditor::available() const {
  std::string ready = read_private("ready");
  if (ready.empty() || ready.back() != '\n') return false;
  ready.pop_back();
  if (ready.empty() || ready.size() > 10 || ready.find_first_not_of("0123456789") != std::string::npos)
    return false;
  timespec now{};
  if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return false;
  long long lease = std::strtoll(ready.c_str(), nullptr, 10);
  return lease <= now.tv_sec && now.tv_sec - lease <= 25 && access((DIR + "request").c_str(), F_OK) != 0;
}
bool WifiEditor::start(const std::string &ssid, const std::string &password) {
  error_.clear();
  if (!available()) { error_ = "Gestion Wi-Fi non active / essai en cours"; return false; }
  timespec now{};
  if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return false;
  std::string token = std::to_string(now.tv_sec) + "-" + std::to_string(now.tv_nsec);
  std::string request;
  if (!make_request(ssid, password, token, request)) {
    error_ = "SSID 1-32 octets. Cle 8-63 ASCII sans guillemets, ou 64 hex.";
    return false;
  }
  bool ok = write_private("request", request);
  // Best effort scrub: this buffer is never logged/published as an entity.
  volatile char *bytes = request.empty() ? nullptr : &request[0];
  for (size_t i = 0; i < request.size(); ++i) bytes[i] = 0;
  if (!ok) { error_ = "Ecriture refusee. Reseau inchange."; return false; }
  token_ = token;
  return true;
}
bool WifiEditor::decision_(const char *action) {
  std::string status = read_private("status");
  size_t end = status.find('\n');
  if (end == std::string::npos) return false;
  std::string state = status.substr(0, end);
  std::string token = status.substr(end + 1);
  if (token.empty() || token.back() != '\n') return false;
  token.pop_back();
  if (token.empty() || token.size() > 48 || token.find_first_not_of("0123456789-") != std::string::npos)
    return false;
  if (std::string(action) == "confirm" && state != "confirm") return false;
  if (std::string(action) == "cancel" && state != "confirm" && state != "connecting") return false;
  return write_private("decision", std::string(action) + ":" + token + "\n");
}
bool WifiEditor::confirm() { return decision_("confirm"); }
bool WifiEditor::cancel() { return decision_("cancel"); }
bool WifiEditor::scan_fresh_() const {
  timespec now{};
  return !scan_token_.empty() && clock_gettime(CLOCK_MONOTONIC, &now) == 0 &&
         now.tv_sec >= scan_started_ && now.tv_sec - scan_started_ <= 120;
}
bool WifiEditor::request_scan() {
  if (!available()) { scan_state_ = "unavailable"; return false; }
  timespec now{};
  if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return false;
  if (!scan_token_.empty() && now.tv_sec - scan_started_ < 30) return false;
  std::string token = std::to_string(now.tv_sec) + "-" + std::to_string(now.tv_nsec);
  if (!write_private("scan-request", token + "\n")) { scan_state_ = "failed"; return false; }
  scan_token_ = token; scan_started_ = now.tv_sec; scan_state_ = "waiting";
  scan_page_ = 0; networks_.clear(); scan_loaded_.clear();
  return true;
}
void WifiEditor::refresh_scan() {
  if (scan_token_.empty()) return;
  if (!scan_fresh_()) { networks_.clear(); scan_state_ = "expired"; return; }
  std::string status = read_private("scan-status");
  size_t nl = status.find('\n');
  if (nl == std::string::npos || status.substr(nl + 1) != scan_token_ + "\n") return;
  scan_state_ = status.substr(0, nl);
  if (scan_state_ != "available") { networks_.clear(); return; }
  if (scan_loaded_ == scan_token_) return;
  std::string data = read_private("scan-results", 12100);
  std::string prefix = scan_token_ + "\n";
  if (data.compare(0, prefix.size(), prefix) != 0) return;
  networks_ = parse_scan(data.substr(prefix.size()));
  scan_loaded_ = scan_token_; scan_page_ = 0;
}
void WifiEditor::next_scan_page() {
  if (!networks_.empty()) scan_page_ = (scan_page_ + 1) % ((networks_.size() + 3) / 4);
}
std::string WifiEditor::scan_status_text() const {
  if (scan_state_ == "unavailable" || !available()) return "Recherche indisponible / essai en cours";
  if (scan_state_ == "failed" || scan_state_ == "refused") return "Recherche refusee. Reessayez plus tard.";
  if (scan_state_ == "waiting" || scan_state_ == "scanning") return "Recherche... patientez environ 20 s";
  if (scan_state_ == "expired" || (!scan_token_.empty() && !scan_fresh_())) return "Liste expiree. Relancez la recherche.";
  if (scan_state_ == "available") {
    if (networks_.empty()) return "Aucun nom lisible. Reessayez ou saisissez-le.";
    return "Resultats disponibles (cache possible) " + std::to_string(scan_page_ + 1) + "/" +
           std::to_string((networks_.size() + 3) / 4);
  }
  return "Rechercher puis toucher votre reseau";
}
std::string WifiEditor::scan_row_text(size_t row) const {
  size_t index = scan_page_ * 4 + row;
  if (row >= 4 || index >= networks_.size() || !scan_fresh_()) return "-";
  const auto &n = networks_[index];
  return n.ssid + "\n" + (n.supported ? "WPA/WPA2" : "Non pris en charge") +
         (n.signal == -128 ? "" : " / " + std::to_string(n.signal) + " dBm");
}
std::string WifiEditor::scan_row_ssid(size_t row) const {
  size_t index = scan_page_ * 4 + row;
  if (row >= 4 || index >= networks_.size() || !scan_fresh_() || !available() ||
      scan_state_ != "available" || !networks_[index].supported) return {};
  return networks_[index].ssid;
}
std::string WifiEditor::status_text() const {
  std::string status = read_private("status");
  std::string code = status.substr(0, status.find('\n'));
  if (code == "connecting") return "Connexion... delai d'essai : 2 min";
  if (code == "confirm") return "Connecte. Confirmez pour garder ce reseau.";
  if (code == "saved") return "Nouveau reseau enregistre";
  if (code == "restoring") return "Retour a l'ancien reseau...";
  if (code == "restored") return "Ancien reseau restaure";
  if (code == "restored_offline") return "Ancien profil restaure, sans liaison. Nouvel essai possible.";
  if (code == "refused") return "Essai refuse. Reseau inchange.";
  if (code == "recovery_failed") return "Recuperation requise. Ne relancez pas.";
  if (!error_.empty()) return error_;
  if (!token_.empty() && !available()) return "Demande transmise au superviseur...";
  return available() ? "Wi-Fi WPA/WPA2 personnel. Pas de WPA3 seul." :
                       "Gestion Wi-Fi non active : preparation requise";
}
}  // namespace esphome::tpp06_wifi
#endif
