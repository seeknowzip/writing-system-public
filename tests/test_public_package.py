"""Public packaging and synthetic smoke checks; not model-quality evaluation."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PublicPackageTests(unittest.TestCase):
    def test_markdown_links_resolve(self):
        for path in ROOT.rglob('*.md'):
            if 'local' in path.relative_to(ROOT).parts:
                continue
            text = re.sub(r'```.*?```|`[^`]+`', '', path.read_text(), flags=re.S)
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if '://' not in target and not target.startswith('#'):
                    with self.subTest(path=path, target=target):
                        self.assertTrue((path.parent / target.split('#')[0]).exists())

    def test_clean_install_needs_no_private_samples(self):
        # This executes every normal validator path with only included synthetic files.
        commands = [
            ['validate_brief.py', 'examples/brief.json'],
            ['validate_copy.py', '--brief', 'examples/brief.json', '--copy', 'examples/source.md'],
            ['validate_rewrite_output.py', '--source', 'examples/source.md', '--output', 'examples/source.md', '--diag', 'examples/diagnosis.json'],
        ]
        for args in commands:
            result = subprocess.run([sys.executable, str(ROOT/'scripts'/args[0]), *args[1:]], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_personalization_is_optional_and_fact_bounded(self):
        guide = (ROOT/'references/personalization.md').read_text()
        self.assertIn('글이 없어도 기본 작성·재작성은 동일하게 동작한다', guide)
        self.assertIn('사용자가 지정한 자기 글만 읽는다', guide)
        self.assertIn('샘플의 고유 문장·일화·고객·금액을 새 글로 옮기지 않는다', guide)
        self.assertIn('local/', (ROOT/'.gitignore').read_text())

    def test_no_private_payloads_or_absolute_home_paths(self):
        for folder in ('research', 'evals'):
            self.assertFalse((ROOT/folder).exists(), folder)
        for path in [ROOT/'SKILL.md', *list((ROOT/'references').glob('*.md'))]:
            self.assertNotRegex(path.read_text(), r'/Users/|notion\.so/|RP-|author-sources/')

if __name__ == '__main__':
    unittest.main()
