"""Offline checks only; never connect to or modify a panel."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DropbearDocumentationTests(unittest.TestCase):
    def test_shell_examples_parse(self):
        text = (ROOT / 'docs/fr/19-ssh-dropbear.md').read_text()
        examples = re.findall(r'```sh\n(.*?)```', text, re.S)
        self.assertGreater(len(examples), 10)
        for example in examples:
            with self.subTest(example=example.splitlines()[0]):
                result = subprocess.run(['sh', '-n'], input=example, text=True,
                                        capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_service_has_no_boot_or_password_mutations(self):
        path = ROOT / 'device/dropbear/service.sh'
        subprocess.run(['sh', '-n', str(path)], check=True)
        text = path.read_text()
        for forbidden in ('passwd ', '/etc/shadow', 'rc.local', 'S99tuya-app',
                          'killall ', 'reboot', 'iptables'):
            self.assertNotIn(forbidden, text)
        self.assertIn('-l wlan0', text)
        self.assertIn('readlink -f "$BASE/dropbearmulti"', text)

    def test_public_files_have_no_instance_credentials(self):
        for name in ('docs/fr/19-ssh-dropbear.md', 'device/dropbear/service.sh',
                     'device/dropbear/localoptions.h'):
            text = (ROOT / name).read_text()
            self.assertNotRegex(text, r'192\.168\.\d+\.\d+')
            self.assertNotIn('/home/mint', text)
            self.assertNotIn('BEGIN OPENSSH PRIVATE KEY', text)
        text = (ROOT / 'docs/fr/19-ssh-dropbear.md').read_text()
        self.assertIn('IP_DU_PANNEAU', text)
        self.assertIn('time64', text)
        self.assertIn('huit premiers caractères', text)
        self.assertIn("n'est pas activé", ' '.join(text.split()))

    def test_minimal_features_are_explicit(self):
        options = (ROOT / 'device/dropbear/localoptions.h').read_text()
        for feature in ('DROPBEAR_SVR_LOCALTCPFWD', 'DROPBEAR_SVR_REMOTETCPFWD',
                        'DROPBEAR_X11FWD', 'DROPBEAR_SVR_AGENTFWD',
                        'DROPBEAR_SFTPSERVER'):
            self.assertIn(f'#define {feature} 0', options)


if __name__ == '__main__':
    unittest.main()
