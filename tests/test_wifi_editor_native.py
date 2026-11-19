"""Native mailbox tests redirect every device path into a temporary directory."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "esphome-components/tpp06_wifi"


class WifiNativeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native compiler required")
    def test_profile_and_mailbox_with_redirected_filesystem(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "esphome/core").mkdir(parents=True)
            (root / "esphome/core/component.h").write_text("#pragma once\nnamespace esphome { class Component {}; }\n")
            (root / "test.cpp").write_text(NATIVE_TEST)
            wrappers = ['open','lstat','fstat','access','rename','unlink','geteuid','clock_gettime']
            subprocess.run(['g++', '-std=c++17', '-DUSE_HOST', '-Wall', '-Wextra', '-Werror',
                '-I', str(root), '-I', str(DRIVER), str(root / 'test.cpp'), str(DRIVER / 'wifi.cpp'),
                *['-Wl,--wrap='+name for name in wrappers], '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test'), str(root / 'mailbox')], check=True, timeout=5)


NATIVE_TEST = r'''
#include "wifi.h"
#include "profile.h"
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstring>
#include <fstream>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
using namespace esphome::tpp06_wifi;
std::string root;
long test_now=1000;
std::string map(const char *p) {
  std::string s=p, prefix="/tmp/tpp06-wifi-editor";
  assert(s.compare(0,prefix.size(),prefix)==0);
  return root+s.substr(prefix.size());
}
extern "C" {
int __real_open(const char *,int,...);
int __real_lstat(const char *,struct stat *);
int __real_fstat(int,struct stat *);
int __real_access(const char *,int);
int __real_rename(const char *,const char *);
int __real_unlink(const char *);
int __wrap_open(const char *p,int flags,...) {
  mode_t mode=0;
  if(flags&O_CREAT) {va_list a;va_start(a,flags);mode=va_arg(a,int);va_end(a);}
  return __real_open(map(p).c_str(),flags,mode);
}
int __wrap_lstat(const char *p,struct stat *st) {int r=__real_lstat(map(p).c_str(),st);if(!r)st->st_uid=0;return r;}
int __wrap_fstat(int fd,struct stat *st) {int r=__real_fstat(fd,st);if(!r)st->st_uid=0;return r;}
int __wrap_access(const char *p,int m) {return __real_access(map(p).c_str(),m);}
int __wrap_rename(const char *a,const char *b) {return __real_rename(map(a).c_str(),map(b).c_str());}
int __wrap_unlink(const char *p) {return __real_unlink(map(p).c_str());}
uid_t __wrap_geteuid() {return 0;}
int __wrap_clock_gettime(clockid_t clock,timespec *ts) {assert(clock==CLOCK_MONOTONIC);ts->tv_sec=test_now;ts->tv_nsec=42;return 0;}
}
void put(const char *file,const std::string &value) {
  std::ofstream(root+"/"+file)<<value;
  chmod((root+"/"+file).c_str(),0600);
}
int main(int argc,char **argv) {
  assert(argc==2);root=argv[1];std::string result;
  assert(make_request("test", "password", "1000-42", result));
  assert(result.find("ssid=74657374")!=std::string::npos);
  assert(make_request("réseau", "p#ass\\word", "1000-42", result));
  assert(result.find("psk=\"p#ass\\word\"")!=std::string::npos);
  assert(make_request("test", std::string(64,'a'), "1000-42", result));
  for (const char *pass:{"short", "bad\npassword", "bad\rpassword", "p\"ass#word"})
    assert(!make_request("test",pass,"1000-42",result));
  assert(!make_request("test",std::string(64,'z'),"1000-42",result));
  for (const char *ssid:{"", "bad\nssid"}) assert(!make_request(ssid,"password","1000-42",result));
  assert(!make_request(std::string(33,'a'),"password","1000-42",result));
  for (const char *token:{"", "-1", "1-", "1-2-3", "1;echo-2"})
    assert(!make_request("test","password",token,result));
  assert(scan_ssid("Caf\\xc3\\xa9") == "Café");
  assert(scan_ssid("safe\\\\path\\\"name") == "safe\\path\"name");
  assert(scan_ssid("$(touch nope); #text") == "$(touch nope); #text");
  for (const char *ssid:{"bad\\x00", "bad\\x0a", "bad\\n", "bad\\x7f", "bad\\xc0\\xaf",
                        "bad\\xed\\xa0\\x80", "bad\\xe2\\x80\\xae", "bad\\xf4\\x90\\x80\\x80",
                        "bad\\xc3", "bad\\xzz", "bad\\"}) assert(scan_ssid(ssid).empty());
  assert(scan_ssid(std::string(33,'a')).empty());
  const std::string header="bssid / frequency / signal level / flags / ssid\n";
  const std::string scan=header+
    "00:11:22:33:44:55\t2412\t-75\t[WPA2-PSK-CCMP][ESS]\tCaf\\xc3\\xa9\n"
    "00:11:22:33:44:56\t2412\t-45\t[WPA2-PSK-CCMP][ESS]\tCaf\\xc3\\xa9\n"
    "00:11:22:33:44:57\t2412\t-50\t[ESS]\tGuest\n"
    "00:11:22:33:44:58\t2412\t-55\t[WPA2-SAE-CCMP][ESS]\tOnlyWPA3\n"
    "00:11:22:33:44:59\t2412\t-60\t[WPA2-EAP-CCMP][ESS]\tEnterprise\n"
    "00:11:22:33:44:60\t2412\t-65\t[WPA2-PSK+SAE-CCMP][ESS]\tMixed\n"
    "00:11:22:33:44:61\t2412\t-30\t[ESS]\t\n"
    "00:11:22:33:44:62\t2412\t-30\t[ESS]\tbad\\x0aname\n"
    "00:11:22:33:44:63\t2412\t-30\t[ESS]\ttruncated";
  auto networks=parse_scan(scan);
  assert(networks.size()==5 && networks[0].ssid=="Café" && networks[0].signal==-45);
  assert(networks[0].supported && !networks[1].supported && !networks[2].supported);
  assert(!networks[3].supported && networks[4].supported);
  assert(parse_scan("FAIL\n").empty() && parse_scan(std::string(12001,'a')).empty());
  std::string many=header;
  for (int n=0;n<60;++n) many+="00:11:22:33:44:55\t2412\t-50\t[ESS]\tGuest"+std::to_string(n)+"\n";
  assert(parse_scan(many).size()==24);
  WifiEditor editor;
  assert(!editor.available() && !editor.start("test","password"));
  mkdir(root.c_str(),0700);
  put("ready","900\n");assert(!editor.available());
  put("ready","1001\n");assert(!editor.available());
  put("ready","1000 garbage\n");assert(!editor.available());
  put("ready","1000\n");assert(editor.available());
  assert(editor.request_scan());
  assert(!editor.request_scan());  // Cooldown, no duplicate request.
  put("scan-status","available\n999-42\n");
  put("scan-results","999-42\n"+scan); editor.refresh_scan();
  assert(editor.scan_row_ssid(0).empty());  // Old result cannot satisfy new request.
  put("scan-status","available\n1000-42\n");
  put("scan-results","1000-42\n"+scan); editor.refresh_scan();
  assert(editor.scan_row_ssid(0)=="Café" && editor.scan_row_ssid(1).empty());
  assert(editor.scan_row_text(1).find("Non pris en charge")!=std::string::npos);
  editor.next_scan_page(); assert(editor.scan_row_ssid(0)=="Mixed");
  assert(editor.scan_row_ssid(1).empty());
  editor.next_scan_page(); assert(editor.scan_row_ssid(0)=="Café");
  put("request","pending");assert(editor.scan_row_ssid(0).empty());
  __real_unlink((root+"/request").c_str());
  test_now=1121; editor.refresh_scan(); assert(editor.scan_row_ssid(0).empty());
  assert(editor.scan_row_text(0)=="-");
  test_now=1000;
  chmod((root+"/ready").c_str(),0644);assert(!editor.available());
  chmod((root+"/ready").c_str(),0600);
  assert(!editor.start("test","short"));
  assert(__real_access((root+"/request").c_str(),F_OK)!=0);
  assert(editor.start("test","password"));assert(!editor.available());
  assert(!editor.start("test","another-password"));
  struct stat st{};__real_lstat((root+"/request").c_str(),&st);assert((st.st_mode&0777)==0600);
  put("status","connecting\n1000-42\n");assert(!editor.confirm());assert(editor.cancel());
  put("status","confirm\n1000-42\n");assert(editor.confirm());
  std::ifstream file(root+"/decision");std::string line;std::getline(file,line);assert(line=="confirm:1000-42");
  put("status","confirm\nmalicious;token\n");assert(!editor.confirm());
  chmod(root.c_str(),0755);assert(!editor.available() && !editor.cancel());
}
'''
