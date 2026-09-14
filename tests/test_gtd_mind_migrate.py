import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gtd_mind_migrate as migration
from gtd_mind_upgrade import fingerprint, backup

class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'state').mkdir()
        (self.root / 'config').mkdir()
        self.engine = migration.MigrationUpgrade(self.root, self.root, {})
        self.engine.env_file.write_text('AUTH_MODE=local\n')
        self.engine.env_file.chmod(0o600)
        self.saved = self.root / 'previous.env'
        self.saved.write_text('AUTH_MODE=local\n')
        self.saved.chmod(0o600)
        with sqlite3.connect(self.engine.db) as db:
            db.executescript('CREATE TABLE __drizzle_migrations(id INTEGER, hash TEXT); CREATE TABLE work_items(id INTEGER PRIMARY KEY, title TEXT); INSERT INTO work_items VALUES(1,"original");')
        self.path = self.root / 'record.json'
        self.before = self.root / 'before.sqlite'
        backup(self.engine.db, self.before)
        self.record = dict(schema=fingerprint(self.engine.db), backup=str(self.before), previous_env=str(self.saved), previous_image='old', status='switching', writes_resumed=False)

    def test_restore_is_forbidden_after_writes_resume(self):
        self.record['writes_resumed'] = True
        with patch.object(self.engine, 'stop_container') as stop:
            with self.assertRaisesRegex(RuntimeError, 'preserve data'):
                self.engine.restore_quarantined(self.record, self.path)
            stop.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text())['status'], 'manual-recovery-required')

    def test_quarantined_restore_retains_failed_copy(self):
        with sqlite3.connect(self.engine.db) as db:
            db.execute('ALTER TABLE work_items ADD COLUMN added TEXT')
        with patch.object(self.engine, 'inspect', side_effect=RuntimeError('missing')), patch.object(self.engine, 'stop_tunnel'), patch.object(self.engine, 'stop_container'), patch.object(self.engine, 'switch'), patch.object(self.engine, 'verify'):
            self.engine.restore_quarantined(self.record, self.path)
        self.assertEqual(fingerprint(self.engine.db), self.record['schema'])
        self.assertTrue((self.root / 'failed-candidate.sqlite').exists())

    def test_restore_rejects_an_unrecorded_live_writer(self):
        self.record['image_id'] = 'candidate'
        current = {'Image': 'candidate', 'Config': {'Env': ['WRITE_QUARANTINE=false']}, 'State': {'Running': True}}
        with patch.object(self.engine, 'inspect', return_value=current), patch.object(self.engine, 'stop_container') as stop:
            with self.assertRaisesRegex(RuntimeError, 'preserve data'):
                self.engine.restore_quarantined(self.record, self.path)
            stop.assert_not_called()

    def test_rejects_unreviewed_or_edited_migrations(self):
        with self.assertRaisesRegex(RuntimeError, 'exact'):
            migration.validate_review(self.root, 'old', 'new', {})
        review = dict(previous_revision='old', revision='new', files={})
        with patch.object(migration, 'run', return_value='M\tapps/server/drizzle/0001_old.sql'):
            with self.assertRaisesRegex(RuntimeError, 'Previously committed'):
                migration.validate_review(self.root, 'old', 'new', review)

    def test_resume_rejects_unverified_or_already_resumed_record(self):
        with self.assertRaisesRegex(RuntimeError, 'verified'):
            self.engine.resume(self.record, self.path)
        self.record.update(phase='verified-quarantined', writes_resumed=True)
        with self.assertRaisesRegex(RuntimeError, 'verified'):
            self.engine.resume(self.record, self.path)

if __name__ == '__main__': unittest.main()

class McpLayoutTest(unittest.TestCase):
    def test_listener_and_secret_mount_are_exact(self):
        upgrade = migration.Upgrade(Path('/tmp/app'), Path('/tmp/gtd-test'))
        current = {'Config': {'Env': ['MCP_ENABLED=true', 'AUTH_MODE=cloudflare']},
                   'HostConfig': {'PortBindings': {'3000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '3000'}], '3001/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '3001'}]}},
                   'Mounts': [{'Destination': '/data', 'Source': str(upgrade.db.parent)}, {'Destination': '/run/gtd-mcp', 'Source': str(upgrade.root / 'config/mcp'), 'RW': False}]}
        upgrade.assert_runtime_layout(current)
        current['HostConfig']['PortBindings']['3001/tcp'][0]['HostIp'] = '0.0.0.0'
        with self.assertRaisesRegex(RuntimeError, 'port binding'): upgrade.assert_runtime_layout(current)
        current['HostConfig']['PortBindings']['3001/tcp'][0]['HostIp'] = '127.0.0.1'
        current['Mounts'][1]['RW'] = True
        with self.assertRaisesRegex(RuntimeError, 'secret mount'): upgrade.assert_runtime_layout(current)
