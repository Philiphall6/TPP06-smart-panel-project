"""Real POSIX files, fault injection; no panel or user's preference directory."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = r'''
#include "preferences_file.h"
#include <cassert>
#include <fstream>
#include <iostream>
using namespace esphome::host::preference_file;
int write_failure=0, sync_failure=0, rename_failure=0;
extern "C" ssize_t __real_write(int, const void *, size_t);
extern "C" int __real_fsync(int);
extern "C" int __real_rename(const char *, const char *);
extern "C" ssize_t __wrap_write(int fd, const void *buf, size_t size) {
  if(write_failure==1) {errno=ENOSPC;return -1;}
  if(write_failure==2) {write_failure=0;errno=EINTR;return -1;}
  return __real_write(fd,buf,size>3?3:size); // Short writes must work too.
}
extern "C" int __wrap_fsync(int fd) {
  if(sync_failure && --sync_failure==0) {errno=EIO;return -1;}
  return __real_fsync(fd);
}
extern "C" int __wrap_rename(const char *from,const char *to) {
  if(rename_failure) {errno=EIO;return -1;}
  return __real_rename(from,to);
}
int main(int argc,char **argv) {
  assert(argc==2);std::string file=std::string(argv[1])+"/app.prefs.v2";
  Values first{{42,{1,2,3}}, {7,{}}}, second{{42,{4,5,6}}}, read;
  std::vector<uint8_t> bytes;
  assert(encode(first,bytes) && decode(bytes,read) && read==first);
  for(size_t i=0;i<bytes.size();++i) {
    auto damaged=bytes;damaged[i]^=1;Values sentinel=first;
    assert(!decode(damaged,sentinel) && sentinel==first);
  }
  for(size_t size=0;size<bytes.size();++size) {
    auto cut=bytes;cut.resize(size);assert(!decode(cut,read));
  }
  std::vector<uint8_t> legacy{42,0,0,0,3,1,2,3};
  assert(!decode(legacy,read));assert(decode(legacy,read,true));
  assert(read.at(42)==first.at(42));legacy.pop_back();assert(!decode(legacy,read,true));
  Values oversized{{1,std::vector<uint8_t>(256)}};assert(!encode(oversized,bytes));
  assert(save(file,first) && load(file,read) && read==first);
  struct stat st{};assert(stat(file.c_str(),&st)==0 && (st.st_mode&0777)==0600);
  write_failure=1;assert(!save(file,second));write_failure=0;
  assert(load(file,read) && read==first);
  sync_failure=1;assert(!save(file,second));assert(load(file,read) && read==first);
  rename_failure=1;assert(!save(file,second));rename_failure=0;
  assert(load(file,read) && read==first);
  write_failure=2;assert(save(file,second));assert(load(file,read) && read==second);
  assert(load(file+".bak",read) && read==first);
  // Corruption never replaces the last good backup.
  {std::ofstream damaged(file);damaged<<"bad";}
  assert(!load(file,read));assert(save(file,second));
  assert(load(file+".bak",read) && read==first);
  // Empty store is checksummed, not confused with a truncated file.
  assert(save(file,{}) && load(file,read) && read.empty());
  assert(load(file+".bak",read) && read==second);
  // Reject symlinks, FIFOs and oversized files before reading them.
  assert(symlink(file.c_str(),(file+".link").c_str())==0 && !load(file+".link",read));
  assert(mkfifo((file+".fifo").c_str(),0600)==0 && !load(file+".fifo",read));
  {std::ofstream huge(file+".huge");huge.seekp(MAX_FILE_SIZE);huge.put('x');}
  assert(!load(file+".huge",read));
  // Unchanged saves generate no flash write.
  write_failure=1;assert(save(file,{}));write_failure=0;
  // Failure after rename: complete new data may exist, but success is not reported.
  sync_failure=4;assert(!save(file,first));assert(load(file,read) && read==first);
  assert(save(file,first));
}
'''


class HostPreferencesTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_actual_manager_migration_recovery_and_reset(self):
        try:
            import esphome
        except ImportError:
            self.skipTest("ESPHome core headers required")
        core_header = Path(esphome.__file__).parent / "core/preference_backend.h"
        program = r'''
#include "preferences.h"
#include "esphome/core/application.h"
#include <cassert>
#include <cstdlib>
#include <fstream>
#include <string>
esphome::Application esphome::App;
int main(int argc,char **argv) {
 assert(argc==2);std::string dir=argv[1];assert(setenv("ESPHOME_PREFDIR",dir.c_str(),1)==0);
 const auto legacy=dir+"/panel.prefs", current=legacy+".v2";
 {std::ofstream file(legacy,std::ios::binary);const char bytes[]={42,0,0,0,1,7};file.write(bytes,6);}
 esphome::host::HostPreferences prefs;
 uint8_t value=0;assert(prefs.load(42,&value,1) && value==7 && prefs.sync());
 {std::ifstream file(legacy,std::ios::binary);std::string bytes((std::istreambuf_iterator<char>(file)),{});assert(bytes.size()==6 && bytes[5]==7);}
 value=8;assert(prefs.save(42,&value,1) && prefs.sync());
 {std::ofstream damaged(current);damaged<<"bad";}
 esphome::host::HostPreferences recovered;
 value=0;assert(recovered.load(42,&value,1) && value==7 && recovered.sync());
 assert(recovered.reset() && recovered.sync());
 esphome::host::HostPreferences empty;
 assert(!empty.load(42,&value,1));
 {std::ofstream damaged(current);damaged<<"bad";}
 {std::ofstream damaged(current+".bak");damaged<<"bad";}
 esphome::host::HostPreferences corrupt;
 assert(!corrupt.load(42,&value,1));
 value=9;assert(corrupt.save(42,&value,1) && corrupt.sync());
 esphome::host::HostPreferences fresh;
 assert(fresh.load(42,&value,1) && value==9);
 assert(setenv("ESPHOME_PREFDIR",legacy.c_str(),1)==0);
 esphome::host::HostPreferences wrong_directory;
 assert(!wrong_directory.save(42,&value,1) && !wrong_directory.sync());
 assert(setenv("ESPHOME_PREFDIR","",1)==0);
 esphome::host::HostPreferences empty_path;
 assert(!empty_path.save(42,&value,1) && !empty_path.sync());
}
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "esphome/core/preference_backend.h": core_header.read_text(),
                "esphome/components/host/preference_backend.h": (ROOT / "esphome-components/host/preference_backend.h").read_text(),
                "esphome/core/defines.h": "#pragma once\n",
                "esphome/core/helpers.h": "#pragma once\n#include <cstddef>\n#include <type_traits>\nnamespace esphome {using std::enable_if_t;using std::is_trivially_copyable;}\n",
                "esphome/core/log.h": "#pragma once\n#define ESP_LOGE(...) ((void)0)\n#define ESP_LOGW(...) ((void)0)\n#define ESP_LOGI(...) ((void)0)\n",
                "esphome/core/application.h": '#pragma once\nnamespace esphome {struct Application {const char *get_name(){return "panel";}};extern Application App;}\n',
                "test.cpp": program,
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            driver = ROOT / "esphome-components/host"
            subprocess.run(["g++", "-std=c++20", "-DUSE_HOST", "-I", str(root), "-I", str(driver),
                            str(root / "test.cpp"), str(driver / "preferences.cpp"),
                            "-o", str(root / "test")], check=True)
            subprocess.run([str(root / "test"), str(root)], check=True, timeout=10)

    @unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
    def test_atomic_files_legacy_migration_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.cpp").write_text(PROGRAM)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "esphome-components/host"),
                            str(root / "test.cpp"), "-Wl,--wrap=write", "-Wl,--wrap=fsync",
                            "-Wl,--wrap=rename", "-o", str(root / "test")], check=True)
            subprocess.run([str(root / "test"), str(root)], check=True, timeout=10)
            self.assertFalse(list(root.glob("*.tmp.*")))

    def test_no_live_truncate_and_no_legacy_overwrite(self):
        source = (ROOT / "esphome-components/host/preferences.cpp").read_text()
        self.assertNotIn('"wb"', source)
        self.assertIn('append(".v2")', source)
        self.assertIn("primary_missing && backup_missing", source)
        self.assertIn("this->dirty_ = false", source)
