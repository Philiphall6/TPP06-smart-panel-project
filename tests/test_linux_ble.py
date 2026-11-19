"""Offline parser and asynchronous scanner tests; no real Bluetooth sockets."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("g++"), "native C++ compiler required")
class LinuxBleTests(unittest.TestCase):
    def test_wire_parser_commands_cancel_busy_and_session_stop(self):
        source = r'''
#include "linux_mgmt.h"
#include <cassert>
#include <vector>
using namespace esphome::bluetooth_proxy::linux_mgmt;
static std::vector<unsigned> commands;
static int closed=0, calls=0;
extern "C" int __wrap_socket(int family,int type,int protocol) {
 assert(family==31 && protocol==1 && (type&SOCK_NONBLOCK)); return 123;
}
extern "C" int __wrap_bind(int fd,const sockaddr *addr,socklen_t n) {
 assert(fd==123 && n==6); const auto *p=reinterpret_cast<const uint8_t *>(addr);
 assert(u16(p+2)==65535 && u16(p+4)==3); return 0;
}
extern "C" ssize_t __wrap_send(int fd,const void *data,size_t n,int flags) {
 assert(fd==123 && (flags&MSG_DONTWAIT)); const auto *p=static_cast<const uint8_t *>(data);
 assert(n>=6 && u16(p+2)==0 && u16(p+4)==n-6);
 unsigned op=u16(p); commands.push_back(op);
 assert(op==4 || op==5 || op==13 || op==35 || op==36);
 if(op==5 || op==13) assert(n==7 && p[6]==1); // Never power off/reset.
 if(op==35 || op==36) assert(n==7 && p[6]==6); // LE only.
 return n;
}
extern "C" ssize_t __wrap_recv(int,void *,size_t,int) {errno=EAGAIN;return -1;}
extern "C" int __wrap_close(int fd) {assert(fd==123);++closed;return 0;}
static std::vector<uint8_t> event(unsigned kind,const std::vector<uint8_t> &data) {
 std::vector<uint8_t> out(6);put16(out.data(),kind);put16(out.data()+4,data.size());
 out.insert(out.end(),data.begin(),data.end());return out;
}
static void feed(Scanner &s,unsigned kind,const std::vector<uint8_t> &data,unsigned time=2000) {
 auto packet=event(kind,data);s.consume(packet.data(),packet.size(),time);
}
static void ack(Scanner &s,unsigned op,const std::vector<uint8_t> &data,unsigned error=0) {
 std::vector<uint8_t> payload{uint8_t(op),uint8_t(op>>8),uint8_t(error)};
 payload.insert(payload.end(),data.begin(),data.end());feed(s,1,payload);
}
static std::vector<uint8_t> adv() {
 std::vector<uint8_t> p(17);p[0]=0x66;p[1]=0x55;p[2]=0x44;p[3]=0x33;p[4]=0x22;p[5]=0x11;
 p[6]=1;p[7]=uint8_t(-50);p[12]=3;p[14]=2;p[15]=1;p[16]=6;return p;
}
int main() {
 Advertisement decoded{};auto p=adv();
 assert(advertisement(p.data(),p.size(),decoded));
 assert(decoded.address==0x112233445566 && decoded.rssi==-50 && decoded.address_type==0 && decoded.size==3);
 p[6]=2;assert(advertisement(p.data(),p.size(),decoded)&&decoded.address_type==1);
 p[6]=0;assert(!advertisement(p.data(),p.size(),decoded));
 p=adv();p[14]=4;assert(!advertisement(p.data(),p.size(),decoded));
 p=adv();p[12]=4;assert(!advertisement(p.data(),p.size(),decoded));
 p=adv();p[7]=127;assert(!advertisement(p.data(),p.size(),decoded));
 p=adv();for(unsigned n=0;n<p.size();++n)assert(!advertisement(p.data(),n,decoded));
 p=adv();p[14]=0;assert(!advertisement(p.data(),p.size(),decoded));
 p[15]=p[16]=0;assert(advertisement(p.data(),p.size(),decoded));
 Scanner s;assert(s.open(1000));assert(commands.back()==4);
 std::vector<uint8_t> info(17);info[10]=2; // supported LE; initially powered down.
 ack(s,4,info);s.tick(2000);assert(commands.size()==1);
 s.set_enabled(true);s.tick(2001);assert(commands.size()==1); // No HA subscriber.
 s.set_subscriber(true);s.tick(2002);assert(commands.back()==13);
 ack(s,13,{0,2,0,0});s.tick(2003);assert(commands.back()==5);
 ack(s,5,{1,2,0,0});s.tick(2004);assert(commands.back()==35);
 s.set_enabled(false);ack(s,35,{6});assert(!s.running());
 s.tick(2005);assert(commands.back()==36);ack(s,36,{6});s.tick(2006);
 assert(s.state()==State::STOPPED);
 s.set_enabled(true);s.tick(3000);assert(commands.back()==35);ack(s,35,{6});assert(s.running());
 s.set_callback(nullptr,[](void *,const Advertisement &a){++calls;assert(a.address==0x112233445566);});
 feed(s,18,adv());assert(calls==1&&s.received()==1);
 p=adv();p[6]=0;feed(s,18,p);assert(calls==1&&s.rejected()==1);
 s.set_subscriber(false);feed(s,18,adv());assert(calls==1);
 s.tick(3100);assert(commands.back()==36);ack(s,36,{6});s.tick(3101);assert(!s.running());
 s.set_subscriber(true);s.tick(4000);assert(commands.back()==35);
 ack(s,35,{},10);assert(s.state()==State::FAILED&&!s.running());
 auto count=commands.size();s.tick(5000);assert(commands.size()==count); // No busy retry loop.
 s.close();assert(closed==1&&commands.size()==count); // Never stop another scanner.
 // Decoder fuzz: arbitrary truncated payloads must stay within bounds.
 uint32_t seed=1;
 for(unsigned i=0;i<10000;++i){
   std::vector<uint8_t> bytes(i%100);
   for(auto &v:bytes){seed=1664525*seed+1013904223;v=seed>>24;}
   advertisement(bytes.data(),bytes.size(),decoded);
 }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "test.cpp").write_text(source)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-I", str(ROOT / "esphome-components/bluetooth_proxy"),
                            str(folder / "test.cpp"), "-o", str(folder / "test"),
                            "-Wl,--wrap=socket,--wrap=bind,--wrap=send,--wrap=recv,--wrap=close"], check=True)
            subprocess.run([str(folder / "test")], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
