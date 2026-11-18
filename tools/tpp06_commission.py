#!/usr/bin/env python3
"""Experimental commissioning: configure, check, prepare, trial, verify.

Compilation stays in Home Assistant. No ADB overlay installation or NAND
writes. Only trial requests a reboot, once; an independent on-device guard
is designed to return an unconfirmed trial to stock. Hardware validation pending.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
import time
from zoneinfo import ZoneInfo

from tpp06_tuya_cutter import (
    CutterError, TuyaCutter, PROJECT_ROOT, MULTIBOOT_SCRIPT,
    NETWORK_PROFILE_HELPER, sha256_file, validate_backup_archive,
)

BASE = '/data/tpp06-cutter'
TARGET = '/data/etc/init.d/S99tuya-app'
VERSION = '0.1.5'
RESERVE = 2 * 1024 * 1024


class CommissionError(CutterError):
    """Safe static diagnostic, unlike raw remote/library error messages."""


def require(condition, message):
    if not condition:
        raise CommissionError(message)


def private_write(path, data, *, exclusive=False):
    """Private atomic journals; refuse symlinks and overwriting on creation."""
    path = Path(path)
    require(not path.is_symlink(), 'Lien symbolique refusé.')
    temporary = path if exclusive else path.with_name(path.name + '.new-' + secrets.token_hex(4))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(temporary, flags, 0o600), 'w') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def configure(directory, name, address, timezone):
    directory = Path(directory).absolute()
    require(not directory.exists(), 'Choisir un nouveau dossier privé, jamais un dossier existant.')
    require(PROJECT_ROOT != directory.resolve() and PROJECT_ROOT not in directory.resolve().parents,
            'Conserver la configuration privée hors du dépôt Git.')
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,30}', name), 'Nom technique invalide.')
    ip = ipaddress.IPv4Address(address)
    require(not (ip.is_multicast or ip.is_unspecified or ip.is_loopback), 'Adresse du panneau requise.')
    ZoneInfo(timezone)
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    template = (PROJECT_ROOT / 'esphome/tpp06-lvgl-mobile.yaml').read_text()
    for old, new in [('device_name: "tpp06-lvgl"', f'device_name: "{name}"'),
                     ('device_address: "${device_name}.local"', f'device_address: "{ip}"')]:
        require(template.count(old) == 1, 'Modèle modifié : génération refusée.')
        template = template.replace(old, new)
    directory.mkdir(mode=0o700)
    private_write(directory / f'{name}.yaml', template, exclusive=True)
    private_write(directory / 'secrets.yaml', f'tpp06_api_encryption_key: "{key}"\n', exclusive=True)
    private_write(directory / 'api-key.txt', key + '\n', exclusive=True)
    private_write(directory / 'connection.json', json.dumps({
        'format': 1, 'host': str(ip), 'name': name, 'timezone': timezone,
        'project_version': VERSION,
    }, indent=2) + '\n', exclusive=True)
    print('Configuration privée créée. Compiler le YAML dans HA, pas sur cet ordinateur.')


def load_connection(directory):
    directory = Path(directory).resolve()
    config = json.loads((directory / 'connection.json').read_text())
    require(config.get('format') == 1, 'Format de configuration inconnu.')
    ipaddress.IPv4Address(config['host'])
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,30}', config['name']), 'Nom invalide.')
    require(config.get('project_version') == VERSION, 'Version non prise en charge.')
    ZoneInfo(config['timezone'])
    key = (directory / 'api-key.txt').read_text().strip()
    require(len(base64.b64decode(key, validate=True)) == 32, 'Clé API invalide.')
    return config, key


def inspect_binary(path, readelf='readelf'):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        header = stream.read(52)
    require(len(header) == 52 and header[:7] == b'\x7fELF\x01\x01\x01', 'ELF32 little-endian requis.')
    require(struct.unpack_from('<H', header, 16)[0] == 2 and
            struct.unpack_from('<H', header, 18)[0] == 40, 'Exécutable ARM requis, pas ESP32/x86.')
    flags = struct.unpack_from('<I', header, 36)[0]
    require(flags & 0x200 and not flags & 0x400, 'ABI soft-float requise.')
    result = subprocess.run([readelf, '-A', '-l', str(path)], capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, 'readelf ne peut pas vérifier le programme.')
    require('Tag_CPU_arch: v5TE' in result.stdout and 'Tag_FP_arch:' not in result.stdout
            and 'INTERP' not in result.stdout, 'ARMv5TE statique sans VFP requis.')
    return {'sha256': sha256_file(path), 'bytes': path.stat().st_size}


def shell(session, script):
    require(max(map(len, script.splitlines()), default=0) < 500, 'Commande trop longue pour ash.')
    return session.run_root("sh <<'TPP06_COMMISSION'\nset -eu\n" + script +
                            '\nTPP06_COMMISSION', timeout=35)


def fields(session, script):
    text = shell(session, script).stdout
    pairs = re.findall(r'^CHECK_([A-Z_]+)=([^\r\n]*)\r?$', text, re.M)
    require(len({k for k, _ in pairs}) == len(pairs), 'Diagnostic ambigu.')
    return dict(pairs)


def snapshot(session):
    return fields(session, f'''echo CHECK_KERNEL=$(uname -r)
echo CHECK_ARCH=$(uname -m)
echo CHECK_MAC=$(cat /sys/class/net/wlan0/address)
echo CHECK_BOOT=$(cat /proc/sys/kernel/random/boot_id)
echo CHECK_UI=$(pidof voice_control_ak3760e || true)
echo CHECK_ESP=$(pidof esphome || true)
echo CHECK_ACTIVE=$(cat {BASE}/active_mode 2>/dev/null || true)
echo CHECK_MODE=$(cat {BASE}/mode 2>/dev/null || echo tuya)
echo CHECK_POLICY=$(cat {BASE}/boot_policy 2>/dev/null || echo one-shot)
echo CHECK_ASSOC=$(wpa_cli -iwlan0 status | grep -c '^wpa_state=COMPLETED$' || true)
echo CHECK_FREE=$(df -Pk /data | awk 'END {{print $4}}')
echo CHECK_DATA=$(readlink -f /data)
echo CHECK_API=$(netstat -lnt | grep -c ':6053 ' || true)
echo CHECK_ADB=$(netstat -lnt | grep -c ':5555 ' || true)
echo CHECK_RESCUE=$(netstat -lnt | grep -c ':8090 ' || true)
''')


def stock_gate(state, size):
    require(state.get('KERNEL') == '4.4.192V2.4' and state.get('ARCH') == 'armv5tejl',
            'Noyau/architecture non reconnus ; aucune écriture.')
    require(re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', state.get('MAC', ''))
            and state['MAC'] not in ('00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff'), 'MAC réelle requise.')
    require(re.fullmatch(r'[0-9a-f-]{36}', state.get('BOOT', '')), 'Identité de boot inconnue.')
    require(state.get('UI') and not state.get('ESP') and state.get('MODE') == 'tuya',
            'Tuya actif seul requis. Pour ESPHome déjà installé, utiliser OTA.')
    require(state.get('API') == '0', 'API concurrente présente : arrêt.')
    require(all(state.get(k) == '1' for k in ('ASSOC', 'ADB', 'RESCUE')), 'Réseau/secours incomplet.')
    require(state.get('DATA') in ('/data', '/tuya/data'), 'Montage /data non reconnu.')
    require(state.get('FREE', '').isdigit() and int(state['FREE']) * 1024 >= size + RESERVE,
            'Espace insuffisant sans effacer les fichiers existants.')


def healthy(state, before, trial_boot, previous=None):
    require(state.get('MAC') == before['MAC'] and state.get('BOOT') == trial_boot
            and trial_boot != before['BOOT'], 'Identité ou démarrage inattendu.')
    require(state.get('ESP', '').isdigit() and not state.get('UI'), 'ESPHome seul requis.')
    require(state.get('ACTIVE') == 'esphome-healthy' and state.get('POLICY') == 'persistent',
            'Superviseur non sain.')
    require(all(state.get(k) == '1' for k in ('ASSOC', 'API', 'ADB', 'RESCUE')), 'Perte de réseau/API/secours.')
    if previous:
        require(state['ESP'] == previous['ESP'] and state['BOOT'] == previous['BOOT'],
                'Redémarrage pendant la période de validation.')


async def authenticated_probe(config, key, expected_mac):
    from aioesphomeapi import APIClient
    logging.getLogger('aioesphomeapi').setLevel(logging.CRITICAL)
    client = APIClient(config['host'], 6053, None, noise_psk=key,
                      timezone=config['timezone'], client_info='TPP06 commissioning verification')
    try:
        async with asyncio.timeout(12):
            await client.connect(login=True, log_errors=False)
            info = await client.device_info()
            require(info.mac_address.lower() == expected_mac.lower(), 'Identité API différente du panneau.')
            require(info.name == config['name'] and info.project_name == 'philiphall6.tpp06'
                    and info.project_version == config['project_version'], 'Projet/nom/version inattendus.')
            await client.list_entities_services()
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), 5)
        except Exception:
            pass


class Commission:
    def __init__(self, directory, binary, adb='adb', readelf='readelf'):
        self.directory = Path(directory).resolve()
        self.config, self.key = load_connection(self.directory)
        self.binary = Path(binary).resolve()
        self.artifact = inspect_binary(self.binary, readelf)
        self.cutter = TuyaCutter(self.config['host'], self.directory / 'backups', adb=adb)
        self.journal = self.directory / 'commission.json'

    def save(self):
        private_write(self.journal, json.dumps(self.record, indent=2) + '\n')

    def load(self):
        self.record = json.loads(self.journal.read_text())
        require(self.record['artifact'] == self.artifact and self.record['host'] == self.config['host'],
                'Binaire ou adresse modifiés depuis la préparation.')
        require(re.fullmatch(r'[0-9a-f]{16}', self.record['job']), 'Journal invalide.')
        self.root = f"{BASE}/commission-{self.record['job']}"

    def check(self, staging=True):
        self.session = self.cutter.connected_session()
        state = snapshot(self.session)
        stock_gate(state, self.artifact['bytes'] if staging else 0)
        result = fields(self.session, NETWORK_PROFILE_HELPER.read_text() + '''
if profile=$(tpp06_active_wifi_profile); then echo CHECK_PROFILE=yes
else echo CHECK_PROFILE=no; fi
test -c /dev/fb0
test -c /dev/input/event1
test -c /dev/watchdog
test -x /usr/share/udhcpc/default.script
test -x /tuya/app/bin/tuya_factory
test -x /etc/init.d/S99tuya-app
for tool in nohup md5sum sh sync mv cp chmod mkdir wpa_cli wpa_supplicant udhcpc netstat; do
command -v "$tool" >/dev/null
done
owner=no
for pid in $(pidof ak_watchdog); do
for fd in /proc/$pid/fd/*; do
[ "$(readlink "$fd" || true)" != /dev/watchdog ] || owner=yes
done
done
echo CHECK_WATCHDOG=$owner
''')
        require(result.get('PROFILE') == 'yes' and result.get('WATCHDOG') == 'yes',
                'Profil Wi-Fi ou propriétaire watchdog non vérifié.')
        print('Précontrôles réussis, sans écriture. Ils ne prouvent pas un futur démarrage.')
        return state

    def prepare(self):
        require(not self.journal.exists(), 'Journal existant : inspecter, jamais réinstaller à l’aveugle.')
        before = self.check()
        self.record = {'format': 1, 'host': self.config['host'], 'job': secrets.token_hex(8),
                       'artifact': self.artifact, 'before': before, 'phase': 'prepare-intent'}
        private_write(self.journal, json.dumps(self.record, indent=2) + '\n', exclusive=True)
        self.load()
        # Device-wide exclusive claim. A stale lock requires diagnosis, not override.
        shell(self.session, f'mkdir -p {BASE}\nmkdir {BASE}/commission.lock\nmkdir -m 700 {self.root}')
        self.cutter.install('esphome', self.binary, None, None, True,
                            experimental_multiboot=True, keep_stock=True)
        self.session = self.cutter.connected_session()
        backups = sorted((self.directory / 'backups').glob('*.tar.gz'))
        require(len(backups) == 1, 'Sauvegarde absente ou ambiguë.')
        validate_backup_archive(backups[0])
        self.record['backup'] = str(backups[0])
        self.record['backup_sha256'] = sha256_file(backups[0])
        self.record['originals'] = {}
        for path in (f'{BASE}/S99tuya-app.stock', f'{BASE}/network/wpa_supplicant.conf'):
            checksum = self.session.remote_checksum(path)
            require(checksum is not None, 'Original ou profil de secours absent.')
            self.record['originals'][path] = checksum
        for name, source in [('supervisor.sh', MULTIBOOT_SCRIPT),
                             ('boot.sh', PROJECT_ROOT / 'device/tpp06-commission-boot.sh'),
                             ('guard.sh', PROJECT_ROOT / 'device/tpp06-commission-guard.sh')]:
            local = self.directory / name
            private_write(local, source.read_text().replace('@JOB_ROOT@', self.root), exclusive=True)
            self.session.upload(local, f'{self.root}/{name}')
            require(self.session._matches_local_checksum(local, self.session.remote_checksum(f'{self.root}/{name}')),
                    'Transfert non conforme.')
            shell(self.session, f'chmod 700 {self.root}/{name}\nsh -n {self.root}/{name}')
        require(self.session._matches_local_checksum(self.binary, self.session.remote_checksum(f'{BASE}/esphome/esphome')),
                'Programme installé non conforme.')
        self.profile_matches()
        self.record['launcher_checksum'] = self.session.remote_checksum(TARGET)
        self.record['phase'] = 'prepared'
        self.save()
        print('Préparé et sauvegardé. Tuya reste sélectionné. Aucun redémarrage envoyé.')

    def profile_matches(self):
        result = fields(self.session, NETWORK_PROFILE_HELPER.read_text() + f'''
profile=$(tpp06_active_wifi_profile)
tpp06_profiles_equal "$profile" {BASE}/network/wpa_supplicant.conf
echo CHECK_MATCH=yes
''')
        require(result.get('MATCH') == 'yes', 'Copie Wi-Fi non vérifiée.')

    def originals(self):
        for path, expected in self.record['originals'].items():
            require(self.session.remote_checksum(path) == tuple(expected), 'Original/profil modifié : arrêt.')
        require(sha256_file(Path(self.record['backup'])) == self.record['backup_sha256'],
                'Sauvegarde locale non conforme.')
        require(self.session._matches_local_checksum(self.binary, self.session.remote_checksum(f'{BASE}/esphome/esphome')),
                'Binaire distant différent.')

    def trial(self):
        self.load()
        require(self.record['phase'] == 'prepared', 'Essai déjà demandé ou état ambigu ; ne pas réessayer.')
        before = self.check(staging=False)
        require(before['MAC'] == self.record['before']['MAC'], 'Panneau différent.')
        self.originals()
        self.profile_matches()
        require(self.session.remote_checksum(TARGET) == tuple(self.record['launcher_checksum']), 'Lanceur modifié.')
        for name in ('supervisor.sh', 'boot.sh', 'guard.sh'):
            require(self.session._matches_local_checksum(self.directory / name, self.session.remote_checksum(f'{self.root}/{name}')),
                    'Script distant modifié.')
        self.record.update(phase='trial-intent', before=before)
        self.save()  # Persist intent BEFORE boot mutation; never resend on ambiguity.
        shell(self.session, f'''mkdir {self.root}/trial-requested
test ! -d {self.root}/attempted
cp {self.root}/boot.sh {TARGET}.commission
chmod 755 {TARGET}.commission
sh -n {TARGET}.commission
mv {TARGET}.commission {TARGET}
sync
''')
        require(self.session._matches_local_checksum(self.directory / 'boot.sh', self.session.remote_checksum(TARGET)),
                'Lanceur d’essai non conforme ; ne pas redémarrer.')
        self.record['phase'] = 'reboot-intent'
        self.save()
        shell(self.session, "nohup sh -c 'sleep 3; /sbin/reboot' >/tmp/tpp06-commission-reboot.log 2>&1 </dev/null &\necho CHECK_REQUESTED=yes")
        print('UN redémarrage demandé. Garde local de 10 minutes ; vérification automatique.')
        self.verify()

    def verify(self):
        self.load()
        require(self.record['phase'] in ('reboot-intent', 'verifying', 'commit-intent'),
                'Aucun essai à vérifier ; aucune action envoyée.')
        self.session = self.cutter.session or self.cutter.discover()
        # If the connection was lost after the commit marker, reconcile it
        # without sending another reboot or repeating the commit writes.
        if self.record['phase'] == 'commit-intent':
            self.session.connect()
            marker = fields(self.session, f'echo CHECK_COMMITTED=$(cat {self.root}/committed 2>/dev/null || true)')
            if marker.get('COMMITTED'):
                self.finish(marker['COMMITTED'])
                return
        deadline = time.monotonic() + 480
        stable_since = None
        previous = None
        samples = 0
        while time.monotonic() < deadline:
            try:
                try:
                    self.session.connect()
                except CutterError:
                    # Reconnect this panel only; never kill the shared ADB server.
                    self.session._adb('disconnect', self.session.serial)
                    self.session.connect()
                state = snapshot(self.session)
                trial = fields(self.session, f'''echo CHECK_TRIAL=$(cat {self.root}/trial-boot)
echo CHECK_STARTED=$(cat {self.root}/trial-start)
echo CHECK_NOW=$(cut -d. -f1 /proc/uptime)
test ! -d {self.root}/expired
''')
                elapsed = int(trial['NOW']) - int(trial['STARTED'])
                require(0 <= elapsed < 480, 'Fenêtre de confirmation expirée ; laisser le secours agir.')
                healthy(state, self.record['before'], trial['TRIAL'], previous)
                asyncio.run(authenticated_probe(self.config, self.key, self.record['before']['MAC']))
            except Exception:
                if stable_since is not None:
                    self.record['phase'] = 'verification-failed'
                    self.save()
                    raise CommissionError('Stabilité interrompue ; aucune confirmation. Le garde local reste actif.') from None
                print('Attente réseau/API authentifiée ; aucune relance du redémarrage.', flush=True)
                time.sleep(10)
                continue
            if stable_since is None:
                stable_since = time.monotonic()
                previous = state
            samples += 1
            self.record.update(phase='verifying', samples=samples, trial_boot=trial['TRIAL'])
            self.save()
            observed = int(time.monotonic() - stable_since)
            print(f'Validation chiffrée : {observed}s stables, {samples} contrôles.', flush=True)
            if observed >= 120 and samples >= 5:
                self.originals()
                self.commit(trial['TRIAL'], state)
                return
            time.sleep(10)
        raise CommissionError('Délai de validation dépassé ; aucune confirmation. Ne pas relancer trial.')

    def commit(self, boot, state):
        require(re.fullmatch(r'[0-9a-f-]{36}', boot), 'Identité boot invalide.')
        require(state['ESP'].isdigit(), 'PID invalide.')
        require(self.session._matches_local_checksum(self.directory / 'boot.sh', self.session.remote_checksum(TARGET)),
                'Lanceur non conforme.')
        self.record['phase'] = 'commit-intent'
        self.save()
        # Use monotonic uptime, never the wall clock supplied by HA.
        shell(self.session, f'''test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
test "$(cat {self.root}/trial-boot)" = {boot}
test ! -d {self.root}/expired
now=$(cut -d. -f1 /proc/uptime)
start=$(cat {self.root}/trial-start)
test "$((now - start))" -ge 0
test "$((now - start))" -lt 480
test "$(pidof esphome)" = {state['ESP']}
test -z "$(pidof voice_control_ak3760e || true)"
test "$(cat {BASE}/active_mode)" = esphome-healthy
printf 'yes\n' > {BASE}/persistent_confirmed.next
mv {BASE}/persistent_confirmed.next {BASE}/persistent_confirmed
sync
''')
        # The supervisor, not the PC, rearms mode after its local health checks.
        for _ in range(4):
            time.sleep(5)
            current = snapshot(self.session)
            healthy(current, self.record['before'], boot, state)
            if current['MODE'] == 'esphome':
                break
        require(current['MODE'] == 'esphome', 'Superviseur non réarmé ; garde conservé.')
        asyncio.run(authenticated_probe(self.config, self.key, self.record['before']['MAC']))
        shell(self.session, f'''test ! -d {self.root}/expired
test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
now=$(cut -d. -f1 /proc/uptime)
start=$(cat {self.root}/trial-start)
test "$((now - start))" -ge 0
test "$((now - start))" -lt 480
test "$(cat {BASE}/mode)" = esphome
printf '%s\n' {boot} > {self.root}/committed.next
mv {self.root}/committed.next {self.root}/committed
sync
''')
        self.finish(boot)

    def finish(self, boot):
        state = snapshot(self.session)
        healthy(state, self.record['before'], boot)
        require(state['MODE'] == 'esphome', 'Le prochain démarrage n’est pas ESPHome.')
        self.originals()
        asyncio.run(authenticated_probe(self.config, self.key, self.record['before']['MAC']))
        # Do not report completion merely because the remote write was accepted.
        for _ in range(3):
            proof = fields(self.session, f'''echo CHECK_COMMITTED=$(cat {self.root}/committed)
echo CHECK_DISARMED=$(grep -c '^committed-guard-disarmed$' {self.root}/guard.log || true)
test ! -d {self.root}/expired
''')
            if proof.get('COMMITTED') == boot and proof.get('DISARMED') == '1':
                break
            time.sleep(5)
        require(proof.get('COMMITTED') == boot and proof.get('DISARMED') == '1',
                'Confirmation non réconciliée ; inspecter avec verify, ne pas relancer trial.')
        self.record.update(phase='committed', physical_touch_verified=False,
                           power_cycle_verified=False, home_assistant_actions_verified=False)
        self.save()
        print('ESPHome principal confirmé après contrôles. Aucun second reboot demandé.')
        print('Tactile, coupure électrique, veille et commandes HA restent à vérifier sur place.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('configure')
    create.add_argument('--directory', type=Path, required=True)
    create.add_argument('--name', required=True)
    create.add_argument('--address', required=True)
    create.add_argument('--timezone', required=True, help='Fuseau de HA, par exemple Europe/Paris')
    for action in ('check', 'prepare', 'trial', 'verify'):
        item = sub.add_parser(action)
        item.add_argument('--directory', type=Path, required=True)
        item.add_argument('--binary', type=Path, required=True)
        item.add_argument('--adb', default='adb')
        item.add_argument('--readelf', default='readelf')
        if action in ('prepare', 'trial'):
            item.add_argument('--experimental', action='store_true')
            item.add_argument('--compatible-panel-confirmed', action='store_true')
            item.add_argument('--physical-recovery-ready', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.command == 'configure':
            configure(args.directory, args.name, args.address, args.timezone)
        else:
            if args.command in ('prepare', 'trial'):
                require(args.experimental and args.compatible_panel_confirmed and args.physical_recovery_ready,
                        'Options expérimentale, compatibilité et récupération physique obligatoires.')
            if args.command in ('trial', 'verify'):
                import aioesphomeapi  # Fail before mutation if authentication cannot be checked.
            job = Commission(args.directory, args.binary, args.adb, args.readelf)
            getattr(job, args.command)()
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Raw device/library output may contain credentials. Never dump it.
        message = str(error) if isinstance(error, CommissionError) else type(error).__name__
        print('Arrêt contrôlé : ' + message)
        print('Aucune relance automatique. Si un essai est en cours, laisser agir le garde local.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
