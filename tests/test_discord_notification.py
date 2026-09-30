import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sender', Path(__file__).resolve().parents[1] / 'scripts/send-discord-notification.py')
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)


class DiscordTests(unittest.TestCase):
    def test_private_config_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config'
            path.write_text(json.dumps({'webhook_url': 'https://discord.com/api/webhooks/123/test'}))
            path.chmod(0o600)
            self.assertTrue(sender.load_webhook(path).endswith('/test'))
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                sender.load_webhook(path)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                sender.load_webhook(link)

    def test_delivery_contract(self):
        def run(args, **kwargs):
            self.assertNotIn('secret', ' '.join(args))
            self.assertEqual(kwargs['timeout'], 18)
            lines = kwargs['input'].splitlines()
            payload = json.loads(json.loads(lines[1].split(' = ', 1)[1]))
            self.assertEqual(payload['allowed_mentions'], {'parse': []})
            self.assertEqual(payload['content'], '@everyone "test"\nnext')
            return subprocess.CompletedProcess(args, 0, '204', '')
        self.assertEqual(sender.deliver('secret', '@everyone "test"\nnext', run)[0], 0)

    def test_failures_are_sanitized(self):
        for rc, status in [(0, '429'), (0, '401'), (0, '302'), (28, '000')]:
            code, detail = sender.deliver('secret', 'private', lambda *a, **kw: subprocess.CompletedProcess(a, rc, status, 'secret private'))
            self.assertEqual(code, 1)
            self.assertNotIn('secret', detail)
            self.assertNotIn('private', detail)
        def timeout(*a, **kw):
            raise subprocess.TimeoutExpired('secret', 18)
        self.assertEqual(sender.deliver('secret', 'private', timeout)[0], 1)


if __name__ == '__main__':
    unittest.main()
