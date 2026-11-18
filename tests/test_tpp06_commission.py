"""Offline tests only: fake sessions, temp files, mocked reboot and clock."""
import asyncio
import base64
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import tpp06_commission as c

BOOT = '11111111-1111-1111-1111-111111111111'
NEXT = '22222222-2222-2222-2222-222222222222'


def stock():
    return dict(KERNEL='4.4.192V2.4', ARCH='armv5tejl', MAC='02:00:00:00:00:01',
                BOOT=BOOT, UI='123', ESP='', ACTIVE='tuya', MODE='tuya',
                POLICY='one-shot', ASSOC='1', FREE='20000', DATA='/tuya/data',
                API='0', ADB='1', RESCUE='1')


def running():
    return dict(stock(), BOOT=NEXT, UI='', ESP='456', ACTIVE='esphome-healthy',
                MODE='tuya', POLICY='persistent', API='1')


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / 'private'

    def test_config_is_private_portable_and_does_not_overwrite(self):
        output = io.StringIO()
        with redirect_stdout(output):
            c.configure(self.folder, 'panel-example', '192.0.2.1', 'Europe/Paris')
        config, key = c.load_connection(self.folder)
        self.assertEqual(len(base64.b64decode(key)), 32)
        self.assertNotIn(key, output.getvalue())
        self.assertEqual(config['host'], '192.0.2.1')
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)
        for file in self.folder.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        yaml = (self.folder / 'panel-example.yaml').read_text()
        self.assertIn('device_name: "panel-example"', yaml)
        self.assertIn('device_address: "192.0.2.1"', yaml)
        self.assertNotIn(key, yaml)
        self.assertIn('reboot_timeout: 0s', yaml)
        with self.assertRaises(c.CutterError):
            c.configure(self.folder, 'other', '192.0.2.2', 'UTC')
        self.assertEqual(c.load_connection(self.folder)[1], key)

    def test_bad_inputs_never_create_directory(self):
        for name, address, tz in [('bad\nname', '192.0.2.1', 'UTC'),
                                  ('good', '127.0.0.1', 'UTC'),
                                  ('good', '224.0.0.1', 'UTC'),
                                  ('good', '192.0.2.1', 'Not/AZone')]:
            with self.subTest(name=name, address=address, tz=tz), self.assertRaises(Exception):
                c.configure(self.folder, name, address, tz)
            self.assertFalse(self.folder.exists())
        with self.assertRaises(c.CutterError):
            c.configure(ROOT / 'private-never-create', 'good', '192.0.2.1', 'UTC')

    def test_atomic_file_refuses_existing_and_symlinks(self):
        target = Path(self.tmp.name) / 'record'
        c.private_write(target, 'old', exclusive=True)
        with self.assertRaises(FileExistsError):
            c.private_write(target, 'new', exclusive=True)
        link = target.with_name('link')
        link.symlink_to(target)
        with self.assertRaises(c.CutterError):
            c.private_write(link, 'wrong')
        self.assertEqual(target.read_text(), 'old')
        c.private_write(target, 'new')
        self.assertEqual(target.read_text(), 'new')

    def test_binary_requires_arm32_static_softfloat_v5te(self):
        path = Path(self.tmp.name) / 'program'
        header = bytearray(52)
        header[:7] = b'\x7fELF\x01\x01\x01'
        struct.pack_into('<HH', header, 16, 2, 40)
        struct.pack_into('<I', header, 36, 0x5000200)
        path.write_bytes(header)
        with patch.object(c.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='Tag_CPU_arch: v5TE')):
            self.assertEqual(c.inspect_binary(path)['bytes'], 52)
        for output in ('Tag_CPU_arch: v7', 'Tag_CPU_arch: v5TE\nTag_FP_arch: VFPv2',
                       'Tag_CPU_arch: v5TE\nINTERP'):
            with patch.object(c.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=output)):
                with self.assertRaises(c.CutterError):
                    c.inspect_binary(path)
        struct.pack_into('<I', header, 36, 0x5000400)
        path.write_bytes(header)
        with self.assertRaises(c.CutterError):
            c.inspect_binary(path)
        path.write_bytes(b'not an ELF')
        with self.assertRaises(c.CutterError):
            c.inspect_binary(path)


class GateTests(unittest.TestCase):
    def test_stock_preflight_is_strict(self):
        c.stock_gate(stock(), 1000000)
        for key, value in [('KERNEL', 'other'), ('ARCH', 'aarch64'), ('MAC', ''),
                           ('BOOT', ''), ('UI', ''), ('ESP', '123'), ('MODE', 'esphome'),
                           ('API', '1'), ('ASSOC', '0'), ('ADB', '0'), ('RESCUE', '0'),
                           ('DATA', '/tmp'), ('FREE', '1024'), ('FREE', 'unknown')]:
            with self.subTest(key=key), self.assertRaises(c.CutterError):
                c.stock_gate(dict(stock(), **{key: value}), 1000000)

    def test_health_requires_identity_new_boot_exclusive_ui_and_all_listeners(self):
        c.healthy(running(), stock(), NEXT)
        for key, value in [('MAC', '02:00:00:00:00:02'), ('BOOT', BOOT), ('UI', '123'),
                           ('ESP', '123 456'), ('ACTIVE', 'esphome-starting'),
                           ('POLICY', 'one-shot'), ('API', '0'), ('ASSOC', '0'),
                           ('ADB', '0'), ('RESCUE', '0')]:
            with self.subTest(key=key), self.assertRaises(c.CutterError):
                c.healthy(dict(running(), **{key: value}), stock(), NEXT)
        with self.assertRaises(c.CutterError):
            c.healthy(dict(running(), ESP='789'), stock(), NEXT, running())

    def test_fields_reject_echo_duplicates_and_shell_lines_are_bounded(self):
        session = Mock()
        session.run_root.return_value.stdout = 'echo CHECK_A=yes\nCHECK_A=yes\n'
        self.assertEqual(c.fields(session, 'echo CHECK_A=yes'), {'A': 'yes'})
        session.run_root.return_value.stdout = 'CHECK_A=yes\nCHECK_A=no\n'
        with self.assertRaises(c.CutterError):
            c.fields(session, 'echo CHECK_A=yes')
        with self.assertRaises(c.CutterError):
            c.shell(session, 'x' * 500)

    def test_encrypted_probe_checks_identity_and_always_disconnects(self):
        config = dict(host='192.0.2.1', name='panel-example', timezone='UTC', project_version='0.1.5')
        info = dict(mac_address=stock()['MAC'], name=config['name'], project_name='philiphall6.tpp06',
                    project_version='0.1.5')
        for changed in ({}, {'mac_address': '02:00:00:00:00:02'}, {'project_version': '0.1.4'},
                        {'name': 'another'}, {'project_name': 'other.project'}):
            client = SimpleNamespace(connect=AsyncMock(), disconnect=AsyncMock(),
                                     device_info=AsyncMock(return_value=SimpleNamespace(**dict(info, **changed))),
                                     list_entities_services=AsyncMock())
            factory = Mock(return_value=client)
            with patch.dict(sys.modules, {'aioesphomeapi': SimpleNamespace(APIClient=factory)}):
                if changed:
                    with self.assertRaises(c.CutterError):
                        asyncio.run(c.authenticated_probe(config, 'private-test-key', stock()['MAC']))
                    client.list_entities_services.assert_not_awaited()
                else:
                    asyncio.run(c.authenticated_probe(config, 'private-test-key', stock()['MAC']))
                    client.list_entities_services.assert_awaited_once()
            client.disconnect.assert_awaited_once()
            self.assertEqual(factory.call_args.kwargs['timezone'], 'UTC')
            self.assertEqual(factory.call_args.kwargs['noise_psk'], 'private-test-key')


class WorkflowTests(unittest.TestCase):
    def make_job(self, phase='prepared'):
        job = c.Commission.__new__(c.Commission)
        job.record = {'phase': phase, 'before': stock(), 'launcher_checksum': ['md5', 'example']}
        job.load = Mock()
        job.save = Mock()
        job.root = '/data/tpp06-cutter/commission-0123456789abcdef'
        job.directory = Path('/private-example')
        job.config = dict(host='192.0.2.1', name='panel-example', timezone='UTC', project_version='0.1.5')
        job.key = 'private-test-key'
        job.session = Mock()
        job.cutter = SimpleNamespace(session=job.session)
        return job

    def test_prepare_saves_intent_and_backup_before_marking_prepared(self):
        with tempfile.TemporaryDirectory() as folder:
            job = self.make_job()
            job.directory = Path(folder)
            job.journal = job.directory / 'commission.json'
            job.binary = job.directory / 'program'
            job.binary.write_bytes(b'offline binary fixture')
            job.artifact = {'sha256': c.sha256_file(job.binary), 'bytes': job.binary.stat().st_size}
            job.check = Mock(return_value=stock())
            job.profile_matches = Mock()
            job.load = lambda: c.Commission.load(job)
            job.save = lambda: c.Commission.save(job)
            job.session.remote_checksum.return_value = ('md5', 'example')
            job.session._matches_local_checksum.return_value = True
            backup = job.directory / 'backups' / 'fixture.tar.gz'
            def install(*args, **kwargs):
                self.assertEqual(json.loads(job.journal.read_text())['phase'], 'prepare-intent')
                self.assertTrue(kwargs['keep_stock'])
                backup.parent.mkdir()
                backup.write_bytes(b'archive checked separately by archive unit tests')
            job.cutter = SimpleNamespace(install=Mock(side_effect=install),
                                         connected_session=Mock(return_value=job.session))
            with patch.object(c, 'shell') as execute, patch.object(c, 'validate_backup_archive') as validate:
                job.prepare()
            validate.assert_called_once_with(backup)
            record = json.loads(job.journal.read_text())
            self.assertEqual(record['phase'], 'prepared')
            self.assertEqual(record['backup_sha256'], c.sha256_file(backup))
            self.assertEqual(job.session.upload.call_count, 3)
            for call in execute.call_args_list:
                self.assertNotIn('/sbin/reboot', call.args[1])
            self.assertNotIn('@JOB_ROOT@', (job.directory / 'boot.sh').read_text())
            with self.assertRaises(c.CutterError):
                job.prepare()
            self.assertEqual(job.cutter.install.call_count, 1)

    def test_prepare_failure_keeps_intent_and_never_marks_prepared(self):
        with tempfile.TemporaryDirectory() as folder:
            job = self.make_job()
            job.directory = Path(folder)
            job.journal = job.directory / 'commission.json'
            job.binary = job.directory / 'program'
            job.artifact = {'sha256': 'fixture', 'bytes': 42}
            job.check = Mock(return_value=stock())
            job.load = lambda: c.Commission.load(job)
            job.cutter = SimpleNamespace(install=Mock(side_effect=c.CutterError('transfer interrupted')))
            with patch.object(c, 'shell') as execute:
                with self.assertRaises(c.CutterError):
                    job.prepare()
            self.assertEqual(json.loads(job.journal.read_text())['phase'], 'prepare-intent')
            self.assertEqual(execute.call_count, 1)
            self.assertNotIn('/sbin/reboot', execute.call_args.args[1])

    def test_trial_rejects_any_prior_intent_before_device_access(self):
        for phase in ('trial-intent', 'reboot-intent', 'verifying', 'committed', 'verification-failed'):
            job = self.make_job(phase)
            job.check = Mock()
            with self.assertRaises(c.CutterError):
                job.trial()
            job.check.assert_not_called()
            job.session.run_root.assert_not_called()

    def test_trial_records_intent_before_boot_write_and_reboot(self):
        job = self.make_job()
        job.check = Mock(return_value=stock())
        job.originals = Mock()
        job.profile_matches = Mock()
        job.verify = Mock()
        job.session.remote_checksum.return_value = ('md5', 'example')
        job.session._matches_local_checksum.return_value = True
        actions = []
        def execute(session, script):
            actions.append((job.record['phase'], script))
        with patch.object(c, 'shell', side_effect=execute):
            job.trial()
        self.assertEqual([phase for phase, _ in actions], ['trial-intent', 'reboot-intent'])
        self.assertEqual(sum('/sbin/reboot' in script for _, script in actions), 1)
        job.verify.assert_called_once()

    def test_ambiguous_reboot_is_never_repeated(self):
        job = self.make_job()
        job.check = Mock(return_value=stock())
        job.originals = job.profile_matches = Mock()
        job.session.remote_checksum.return_value = ('md5', 'example')
        job.session._matches_local_checksum.return_value = True
        with patch.object(c, 'shell', side_effect=[None, TimeoutError()]):
            with self.assertRaises(TimeoutError):
                job.trial()
        self.assertEqual(job.record['phase'], 'reboot-intent')
        with patch.object(c, 'shell') as execute, self.assertRaises(c.CutterError):
            job.trial()
        execute.assert_not_called()

    def test_network_failure_after_first_sample_never_commits(self):
        job = self.make_job('reboot-intent')
        job.commit = Mock()
        clock = [0]
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(c.time, 'sleep', side_effect=sleep), \
             patch.object(c, 'snapshot', side_effect=[running(), dict(running(), API='0')]), \
             patch.object(c, 'fields', return_value={'TRIAL': NEXT, 'STARTED': '0', 'NOW': '100'}), \
             patch.object(c, 'authenticated_probe', new=AsyncMock()):
            with self.assertRaises(c.CutterError):
                job.verify()
        job.commit.assert_not_called()
        self.assertEqual(job.record['phase'], 'verification-failed')

    def test_stable_encrypted_period_required_before_commit(self):
        job = self.make_job('reboot-intent')
        job.commit = Mock()
        job.originals = Mock()
        clock = [0]
        with patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(c.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
             patch.object(c, 'snapshot', return_value=running()), \
             patch.object(c, 'fields', return_value={'TRIAL': NEXT, 'STARTED': '0', 'NOW': '100'}), \
             patch.object(c, 'authenticated_probe', new=AsyncMock()) as probe:
            job.verify()
        self.assertGreaterEqual(clock[0], 120)
        self.assertGreaterEqual(probe.await_count, 5)
        job.originals.assert_called_once()
        job.commit.assert_called_once_with(NEXT, running())

    def test_resume_commit_marker_is_reconciled_without_reboot(self):
        job = self.make_job('commit-intent')
        job.finish = Mock()
        with patch.object(c, 'fields', return_value={'COMMITTED': NEXT}):
            job.verify()
        job.finish.assert_called_once_with(NEXT)
        job.session.run_root.assert_not_called()

    def test_wrong_key_never_confirms_and_wait_is_bounded(self):
        job = self.make_job('reboot-intent')
        job.commit = Mock()
        clock = [0]
        with patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(c.time, 'sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)), \
             patch.object(c, 'snapshot', return_value=running()), \
             patch.object(c, 'fields', return_value={'TRIAL': NEXT, 'STARTED': '0', 'NOW': '100'}), \
             patch.object(c, 'authenticated_probe', new=AsyncMock(side_effect=ValueError('secret'))), \
             redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(c.CutterError):
                job.verify()
        job.commit.assert_not_called()
        self.assertEqual(clock[0], 480)
        self.assertNotIn('secret', output.getvalue())

    def test_commit_requires_supervisor_rearm_before_commit_marker(self):
        job = self.make_job('verifying')
        job.session._matches_local_checksum.return_value = True
        job.finish = Mock()
        with patch.object(c, 'shell') as execute, patch.object(c.time, 'sleep'), \
             patch.object(c, 'snapshot', return_value=running()):
            with self.assertRaises(c.CutterError):
                job.commit(NEXT, running())
        self.assertEqual(job.record['phase'], 'commit-intent')
        self.assertEqual(execute.call_count, 1)
        self.assertIn('persistent_confirmed.next', execute.call_args.args[1])
        self.assertNotIn('/committed.next', execute.call_args.args[1])
        job.finish.assert_not_called()

    def test_commit_checks_deadline_on_device_before_each_write(self):
        job = self.make_job('verifying')
        job.session._matches_local_checksum.return_value = True
        job.finish = Mock()
        with patch.object(c, 'shell') as execute, patch.object(c.time, 'sleep'), \
             patch.object(c, 'snapshot', return_value=dict(running(), MODE='esphome')), \
             patch.object(c, 'authenticated_probe', new=AsyncMock()):
            job.commit(NEXT, running())
        self.assertEqual(execute.call_count, 2)
        for call in execute.call_args_list:
            self.assertIn('-lt 480', call.args[1])
            self.assertIn('/expired', call.args[1])
            self.assertNotIn('/sbin/reboot', call.args[1])
        job.finish.assert_called_once_with(NEXT)

    def test_finish_requires_guard_disarm_proof(self):
        job = self.make_job('commit-intent')
        job.originals = Mock()
        with patch.object(c, 'snapshot', return_value=dict(running(), MODE='esphome')), \
             patch.object(c, 'authenticated_probe', new=AsyncMock()), \
             patch.object(c.time, 'sleep'), \
             patch.object(c, 'fields', return_value={'COMMITTED': NEXT, 'DISARMED': '0'}):
            with self.assertRaises(c.CutterError):
                job.finish(NEXT)
        self.assertEqual(job.record['phase'], 'commit-intent')

    def test_cli_never_prints_raw_remote_errors(self):
        args = ['tool', 'check', '--directory', '/example', '--binary', '/example/program']
        with patch.object(sys, 'argv', args), \
             patch.object(c, 'Commission', side_effect=c.CutterError('secret-credentials')), \
             patch.object(c.os, 'umask'), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(c.main(), 1)
        self.assertNotIn('secret-credentials', output.getvalue())


class DeviceScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.job = self.base / 'job'
        self.job.mkdir()
        (self.base / 'boot-id').write_text(NEXT)
        (self.base / 'uptime').write_text('100.00 0.00\n')
        (self.job / 'trial-boot').write_text(NEXT)
        (self.job / 'trial-start').write_text('100')
        for name, value in [('mode', 'esphome'), ('persistent_confirmed', 'no')]:
            (self.base / name).write_text(value)
        for path, label in [(self.base / 'S99tuya-app.stock', 'stock'),
                            (self.job / 'supervisor.sh', 'supervisor')]:
            path.write_text(f'#!/bin/sh\nprintf "{label}\\n" >> "{self.base}/events"\n')
            path.chmod(0o700)
        (self.job / 'guard.sh').write_text('#!/bin/sh\nexit 0\n')

    def script(self, name):
        return (ROOT / 'device' / name).read_text().replace('@JOB_ROOT@', str(self.job)).replace(
            '/data/tpp06-cutter', str(self.base)).replace('/proc/sys/kernel/random/boot_id',
            str(self.base / 'boot-id')).replace('/proc/uptime', str(self.base / 'uptime'))

    def run_boot(self, action='start'):
        source = self.script('tpp06-commission-boot.sh')
        source = source.replace('#!/bin/sh', '#!/bin/sh\nsync() { :; }\nsleep() { :; }\nkill() { return 0; }\nnohup() { :; }', 1)
        return subprocess.run(['sh', '-c', source, 'test-boot', action], capture_output=True, text=True, timeout=5)

    def test_shutdown_does_not_erase_confirmation_and_restart_cannot_bypass_gate(self):
        (self.base / 'persistent_confirmed').write_text('yes')
        self.assertEqual(self.run_boot('stop').returncode, 0)
        self.assertEqual((self.base / 'persistent_confirmed').read_text(), 'yes')
        self.assertEqual((self.base / 'mode').read_text(), 'esphome')
        self.assertNotEqual(self.run_boot('restart').returncode, 0)
        self.assertFalse((self.job / 'attempted').exists())

    def test_boot_attempt_is_consumed_before_custom_launch_then_stock_on_next_boot(self):
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertTrue((self.job / 'attempted').is_dir())
        self.assertEqual((self.base / 'events').read_text(), 'supervisor\n')
        self.assertEqual((self.base / 'persistent_confirmed').read_text().strip(), 'no')
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertEqual((self.base / 'events').read_text(), 'supervisor\nstock\n')
        self.assertEqual((self.base / 'mode').read_text().strip(), 'tuya')

    def test_committed_boot_requires_matching_marker_and_confirmation(self):
        (self.job / 'attempted').mkdir()
        (self.job / 'committed').write_text(NEXT)
        (self.base / 'persistent_confirmed').write_text('yes')
        self.assertEqual(self.run_boot().returncode, 0)
        self.assertEqual((self.base / 'events').read_text(), 'supervisor\n')
        (self.job / 'committed').write_text(BOOT)
        self.run_boot()
        self.assertEqual((self.base / 'events').read_text(), 'supervisor\nstock\n')

    def run_guard(self):
        source = self.script('tpp06-commission-guard.sh')
        source = source.replace('/sbin/reboot', f'printf "reboot\\n" >> "{self.base}/events"')
        mock = f'''sync() {{ :; }}
sleep() {{
 now=$(cut -d. -f1 "{self.base}/uptime")
 printf '%s.00 0.00\\n' "$((now + 100))" > "{self.base}/uptime"
}}
'''
        return subprocess.run(['sh', '-c', mock + source], capture_output=True, text=True, timeout=5)

    def test_unconfirmed_guard_selects_stock_then_requests_reboot(self):
        self.assertEqual(self.run_guard().returncode, 0)
        self.assertTrue((self.job / 'expired').is_dir())
        self.assertEqual((self.base / 'mode').read_text().strip(), 'tuya')
        self.assertEqual((self.base / 'persistent_confirmed').read_text().strip(), 'no')
        self.assertEqual((self.base / 'events').read_text(), 'reboot\n')

    def test_confirmed_guard_disarms_without_reboot(self):
        (self.job / 'committed').write_text(NEXT)
        (self.base / 'persistent_confirmed').write_text('yes')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0)
        self.assertIn('committed-guard-disarmed', result.stdout)
        self.assertFalse((self.base / 'events').exists())
        self.assertFalse((self.job / 'expired').exists())
