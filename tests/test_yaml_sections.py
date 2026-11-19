from pathlib import Path
import unittest
import yaml
from tools.tpp06_yaml_sections import annotate, original_lines

ROOT = Path(__file__).resolve().parents[1]


class YamlSectionsTests(unittest.TestCase):
    def test_every_public_yaml_keeps_values_and_lines(self):
        for path in (ROOT / "esphome").rglob("*.yaml"):
            with self.subTest(path=path.name):
                before = path.read_text()
                after = annotate(before)
                self.assertEqual(original_lines(before), original_lines(after))
                self.assertEqual(yaml.load(before, Loader=yaml.BaseLoader),
                                 yaml.load(after, Loader=yaml.BaseLoader))
                self.assertEqual(annotate(after), after)

    def test_lambda_content_and_secret_reference_preserved(self):
        sample = 'api:\n  key: !secret private_key\nscript:\n  - id: test\n    then:\n      - lambda: |-\n          // Do not edit\n          const char *value = "# test";\n'
        self.assertEqual(original_lines(annotate(sample)), sample.splitlines(keepends=True))
