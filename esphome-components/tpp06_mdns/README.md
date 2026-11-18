# Experimental Linux mDNS adapter

This component publishes the records built by ESPHome's native `mdns`
component, whose host backend currently does not open any sockets. It uses
the target's IPv4 address on `host.network_interface`; it does not manage
Wi-Fi, change DHCP settings, or use the build server's MAC/address.

The template requires a unique `device_name`, a real interface MAC, and a
private API/OTA key in `secrets.yaml`. Each installation owns its own secret.
API encryption and OTA encryption are separate features. The tested older
binary already required encrypted OTA despite exposing a plaintext API.

Status: schema validation, code generation, and ARMv5 C++ syntax checks only.
Discovery by Home Assistant/Device Builder on a real panel is NOT yet
validated. Do not make this build the default boot before a bounded RAM trial.
Keep the known IP as `host.use_address` during migration, then switch to the
unique `.local` name only after resolution is verified from Home Assistant.
Changing from the old synthetic MAC changes HA device identity: retain the
old entry until the new identity and automations have been checked.

The adapter supports IPv4 on one interface, PTR/SRV/TXT/A queries, DNS-SD
enumeration, multicast and legacy unicast answers, startup probes, periodic
announcements, DHCP address changes, and orderly-shutdown goodbyes. Work per
loop and input packet sizes are bounded. Conflicting hostname/SRV records
stop publication, leaving IP access available; it does not silently rename
the hostname. IPv6 publication and full RFC interoperability tests remain
outside this initial implementation. SIGKILL/power loss cannot send a goodbye;
cached records expire by TTL.

`mdns_vendor.h` and `LICENSE.mdns` come unmodified from
https://github.com/mjansson/mdns at commit
`a569c4759bd47e0f2a7bfc4d4c19620445782806` (public domain/Unlicense).
No library is fetched at runtime. The adapter validates packet framing before
calling the vendored parser, and sets multicast TTL to 255.
