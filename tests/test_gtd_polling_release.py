import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gtd_mind_upgrade as upgrade

class PollingReleaseTest(unittest.TestCase):
    def check(self, expected, actual):
        with tempfile.TemporaryDirectory() as temp:
            engine = upgrade.Upgrade(Path(temp), Path(temp))
            engine.env_file.parent.mkdir()
            engine.env_file.write_text('TODOIST_POLLING_PAUSED=' + expected + '\n')
            current = {'Image': 'image', 'Config': {'Env': ['AUTH_MODE=local', 'TODOIST_POLLING_PAUSED=' + actual]}, 'State': {'StartedAt': '2026-09-20T12:00:00Z'}}
            with patch.object(engine, 'inspect', return_value=current), patch.object(engine, 'image_id', return_value='image'), patch.object(engine, 'assert_runtime_layout'), patch.object(engine, 'assert_direct_denied'), patch.object(engine, 'headers', return_value={}), patch.object(upgrade, 'check_app') as app, patch.object(upgrade, 'fingerprint', return_value='schema'), patch.object(upgrade, 'get', return_value={'status': 'healthy', 'lastSucceededAt': '2026-09-20T12:00:01Z'}) as sync:
                engine.verify({'actor': 'synthetic', 'schema': 'schema', 'sync_configured': True}, 'image', fresh_sync=True)
                app.assert_called_once()
                return sync.call_count

    def test_explicit_pause_preserves_app_checks_without_provider_poll(self):
        self.assertEqual(self.check('true', 'true'), 0)

    def test_enabled_polling_still_requires_fresh_sync(self):
        self.assertEqual(self.check('false', 'false'), 1)

    def test_mismatched_polling_mode_fails_in_both_directions(self):
        for expected, actual in [('true', 'false'), ('false', 'true')]:
            with self.subTest(expected=expected), self.assertRaisesRegex(RuntimeError, 'polling mode'):
                self.check(expected, actual)

if __name__ == '__main__':
    unittest.main()
