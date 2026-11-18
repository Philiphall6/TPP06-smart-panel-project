"""Offline checks for local links and network-first onboarding."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_product_images_remain_in_readmes(self):
        images = ('media/visuels-produit/01-panneau-blanc.png',
                  'media/visuels-produit/02-panneau-noir.png')
        for name in ('README.md', 'README.fr.md', 'README.en.md'):
            text = (ROOT / name).read_text()
            for image in images:
                self.assertIn(f'src="{image}"', text)
                self.assertTrue((ROOT / image).is_file())

    def test_local_markdown_links_exist(self):
        documents = list(ROOT.glob('README*.md')) + list((ROOT / 'docs').rglob('*.md'))
        for document in documents:
            for target in re.findall(r'\]\(([^\s)]+)\)', document.read_text()):
                if re.match(r'[a-zA-Z][\w+.-]*:', target) or target.startswith('#'):
                    continue
                path = unquote(target.split('#', 1)[0])
                with self.subTest(document=str(document.relative_to(ROOT)), target=target):
                    self.assertTrue((document.parent / path).exists())

    def test_beginner_guides_and_archives_are_discoverable(self):
        for name, guide in [('README.md', 'docs/fr/DEMARRER-ICI.md'),
                            ('README.fr.md', 'docs/fr/DEMARRER-ICI.md'),
                            ('README.en.md', 'docs/en/START-HERE.md')]:
            text = (ROOT / name).read_text()
            self.assertIn(guide, text)
            self.assertIn('docs/archive/README.md', text)
            self.assertIn('0.1.5', text)
        for lang, guide in [('fr', 'DEMARRER-ICI.md'), ('en', 'START-HERE.md')]:
            text = (ROOT / 'docs' / lang / guide).read_text()
            for term in ('ota-space-check', 'secrets.yaml', 'persistent_confirmed', '192.0.2.1'):
                self.assertIn(term, text)
        for name in ('uart.md', 'lecture-nand.md', 'remontage.md', 'materiel.md'):
            self.assertIn('archive/hardware/', (ROOT / 'docs' / name).read_text())
            self.assertTrue((ROOT / 'docs/archive/hardware' / name).is_file())

    def test_beginner_cutter_commands_parse_without_running(self):
        import shlex
        from tools.tpp06_tuya_cutter import build_parser
        parser = build_parser()
        for guide in ('docs/fr/DEMARRER-ICI.md', 'docs/en/START-HERE.md'):
            for line in (ROOT / guide).read_text().splitlines():
                if line.strip().startswith('python3 tools/tpp06_tuya_cutter.py '):
                    args = parser.parse_args(shlex.split(line.strip())[2:])
                    self.assertIn(args.command, ('status', 'backup', 'network-check', 'ota-space-check'))
