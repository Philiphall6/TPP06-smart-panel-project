"""Local Unix sockets only; no Wi-Fi radio, scan or configuration changes."""
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
class WpaSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.binary = cls.root / "client"
        code = r'''
#include "wpa_signal.h"
#include "helpers.h"
#include <cassert>
#include <chrono>
#include <iostream>
#include <thread>
using namespace esphome::tpp06_health;
int main(int argc,char **argv) {
 assert(wpa_signal_summary("RSSI=-40\nLINKSPEED=150\nNOISE=9999\n")=="-40 dBm");
 assert(wpa_signal_summary("RSSI=-127\n")=="-127 dBm");
 for(const auto *bad:{"", "FAIL\n", "RSSI=-40", "RSSI=60\n", "RSSI=-0\n", "RSSI=-128\n",
                     "RSSI=-40.5\n", "RSSI=-40\nRSSI=-41\n", "RSSI=nan\n", "RSSI=-99999999\n",
                     "RSSI=-40junk\n", "RSSI=--40\n", "RSSI=-40\nTRUNCATED"})
   assert(wpa_signal_summary(bad)=="Indisponible");
 assert(wpa_signal_summary(std::string("RSSI=-40\n\0",10))=="Indisponible");
 assert(wpa_signal_summary(std::string(4096,'x'))=="Indisponible");
 assert(link_summary("up\n","1\n")=="Liaison active / Internet non teste");
 assert(link_summary("down\n","0\n")=="Liaison inactive");
 assert(link_summary("up\n","")=="Indisponible");
 assert(link_summary("unknown\n","1\n")=="Indisponible");
 WpaSignalPoll query;
 assert(!query.begin(std::string(200,'a'),0));
 assert(!query.begin(std::string("/tmp/hidden\0socket",18),0));
 assert(argc>=2);
 if(argc==3) {
   assert(query.begin(argv[1],UINT32_MAX-100));
   std::string value;
   assert(!query.finish(898,value));
   assert(query.finish(899,value) && value=="Indisponible");
   assert(!query.finish(900,value));
   return 0;
 }
 if(!query.begin(argv[1],0)) {std::cout<<"Indisponible";return 0;}
 auto started=std::chrono::steady_clock::now();
 std::string value;
 while(true) {
   auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count();
   if(query.finish(elapsed,value)) {std::cout<<value;return 0;}
   assert(elapsed<1500);
   std::this_thread::sleep_for(std::chrono::milliseconds(1));
 }
}
'''
        (cls.root / "client.cpp").write_text(code)
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pthread",
                        "-I", str(ROOT / "esphome-components/tpp06_health"),
                        str(cls.root / "client.cpp"), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def request(self, response, expected):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "wlan0")
            requests = []
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
                server.bind(path)
                server.settimeout(2)
                def respond():
                    payload, address = server.recvfrom(100)
                    requests.append(payload)
                    if response is not None:
                        server.sendto(response, address)
                thread = threading.Thread(target=respond)
                thread.start()
                start = time.monotonic()
                try:
                    result = subprocess.run([str(self.binary), path], text=True, capture_output=True, timeout=3)
                finally:
                    thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)
                self.assertEqual(requests, [b"SIGNAL_POLL"])
                self.assertLess(time.monotonic() - start, 2.5)
                self.assertEqual([p.name for p in Path(directory).iterdir()], ["wlan0"])

    def test_valid_signal_via_abstract_client_socket(self):
        self.request(b"RSSI=-40\nLINKSPEED=150\nNOISE=9999\n", "-40 dBm")

    def test_service_refusal_and_malformed_reply(self):
        for reply in (b"FAIL\n", b"UNKNOWN COMMAND\n", b"RSSI=60\n", b"RSSI=-40\nRSSI=-50\n", b"RSSI=-40"):
            with self.subTest(reply=reply):
                self.request(reply, "Indisponible")

    def test_oversized_datagram_not_accepted_as_partial_reply(self):
        self.request(b"RSSI=-40\n" + b"x" * 5000, "Indisponible")

    def test_slow_service_does_not_block_forever(self):
        self.request(None, "Indisponible")

    def test_missing_service(self):
        result = subprocess.run([str(self.binary), str(self.root / "missing")], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Indisponible")

    def test_timeout_handles_millisecond_wrap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "wlan0")
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
                server.bind(path)
                result = subprocess.run([str(self.binary), path, "wrap"], capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stderr)
