"""Check provenance and generated-link failures before publishing a manual."""
import importlib.util
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from pathlib import Path


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load('publisher', 'publish-manual.py')
build = load('manual_build', 'manual_build.py')


class ManualTests(unittest.TestCase):
    def test_fingerprint_includes_local_edits_and_renames_but_not_secrets(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for filename in publisher.SINGLE_FILES:
                p = root / filename
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture')
            (root / 'docs').mkdir()
            p = root / 'docs/index.md'
            p.write_text('one')
            first = publisher.fingerprint(root)
            (root / '.env').write_text('SECRET=never-in-build')
            self.assertEqual(first, publisher.fingerprint(root))
            p.write_text('two')
            second = publisher.fingerprint(root)
            self.assertNotEqual(first, second)
            p.rename(root / 'docs/renamed.md')
            self.assertNotEqual(second, publisher.fingerprint(root))

    def test_stale_revision_hash_and_dirty_state_are_rejected(self):
        expected = dict(source_revision='abc', source_sha256='123', source_modified=True, built_at_utc='now')
        publisher.verify_metadata(expected, expected, exact=True)
        for key in expected:
            actual = dict(expected, **{key: 'wrong'})
            with self.assertRaises(RuntimeError):
                publisher.verify_metadata(actual, expected, exact=True)
        publisher.verify_metadata(dict(expected, built_at_utc='earlier'), expected)
        with self.assertRaises(RuntimeError):
            publisher.verify_metadata({}, expected)

    def test_read_only_check_never_builds_or_restarts(self):
        config = {'services': {publisher.SERVICE: {'image': publisher.IMAGE,
                  'ports': [{'host_ip': '127.0.0.1', 'target': 80, 'published': '8088'}]}}}
        import json
        with patch.object(publisher, 'run', return_value=json.dumps(config)) as command, \
             patch.object(publisher, 'metadata', return_value={}), \
             patch.object(publisher, 'read_metadata', return_value={}), \
             patch.object(publisher, 'verify_metadata') as verify, \
             patch('sys.argv', ['publish-manual.py', '--check']), \
             patch('builtins.print'):
            # Supply complete metadata so success output is exercised too.
            expected = dict(source_revision='abc', source_sha256='123', source_modified=False)
            with patch.object(publisher, 'metadata', return_value=expected):
                publisher.main()
            self.assertEqual(command.call_count, 1)
            self.assertEqual(command.call_args.args[-3:], ('config', '--format', 'json'))
            verify.assert_called_once()

    def test_failed_replacement_restores_only_the_guide(self):
        import json
        config = {'services': {publisher.SERVICE: {'image': publisher.IMAGE,
                  'ports': [{'host_ip': '127.0.0.1', 'target': 80, 'published': '8088'}]}}}
        calls = []
        ups = 0

        def command(*args, **kwargs):
            nonlocal ups
            calls.append(args)
            if 'config' in args:
                return json.dumps(config)
            if 'ps' in args:
                return 'old-guide'
            if args[:2] == ('docker', 'inspect'):
                return 'sha256:old'
            if 'up' in args:
                ups += 1
                if ups == 1:
                    raise subprocess.CalledProcessError(1, args)
            return ''

        expected = dict(source_revision='abc', source_sha256='123', source_modified=True, built_at_utc='now')
        with patch.object(publisher, 'run', side_effect=command), \
             patch.object(publisher, 'metadata', return_value=expected), \
             patch.object(publisher, 'fingerprint', return_value='123'), \
             patch.object(publisher, 'other_containers', return_value={'app': 'unchanged'}), \
             patch('sys.argv', ['publish-manual.py']), patch('builtins.print'):
            with self.assertRaises(subprocess.CalledProcessError):
                publisher.main()
        self.assertIn(('docker', 'tag', 'sha256:old', publisher.IMAGE), calls)
        lifecycle = [args for args in calls if 'up' in args]
        self.assertEqual(len(lifecycle), 2)
        for args in lifecycle:
            self.assertEqual(args[-1], publisher.SERVICE)
            self.assertIn('--no-deps', args)
            self.assertIn('--no-build', args)

    def test_local_pages_and_fragments(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'service').mkdir()
            (root / 'service/index.html').write_text('<h1 id="recovery">Recover</h1>')
            index = root / 'index.html'
            index.write_text('<a href="service/#recovery">Go</a><a href="https://example.com/">External</a>')
            build.validate_links(root)
            for href in ['missing/', 'service/#missing', '../outside']:
                index.write_text(f'<a href="{href}">Broken</a>')
                with self.assertRaises(RuntimeError):
                    build.validate_links(root)


if __name__ == '__main__':
    unittest.main()
