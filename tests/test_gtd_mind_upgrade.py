import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('upgrade', Path(__file__).parents[1] / 'scripts/gtd_mind_upgrade.py')
upgrade = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upgrade)


class UpgradeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'state').mkdir()
        self.engine = upgrade.Upgrade(self.root, self.root)
        with sqlite3.connect(self.engine.db) as db:
            db.executescript('CREATE TABLE __drizzle_migrations(id INTEGER, hash TEXT);'
                             'INSERT INTO __drizzle_migrations VALUES(1,"one");'
                             'CREATE TABLE work_items(id INTEGER PRIMARY KEY, title TEXT);'
                             'INSERT INTO work_items VALUES(1,"synthetic");')
        self.record = dict(schema=upgrade.fingerprint(self.engine.db), image='new',
                           previous_image='old', actor='owner', sync_configured=False)
        self.path = self.root / 'record.json'

    def test_success_preserves_database_and_records_verified_backup(self):
        with patch.object(upgrade, 'run'), patch.object(self.engine, 'switch') as switch, patch.object(self.engine, 'verify'):
            self.engine.apply(self.record, self.path)
        switch.assert_called_once_with('new')
        record = json.loads(self.path.read_text())
        self.assertEqual(record['status'], 'succeeded')
        self.assertEqual(upgrade.fingerprint(Path(record['backup'])), record['schema'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_failure_rolls_back_image_without_discarding_new_writes(self):
        def verify(record, image, fresh_sync=False):
            if image == 'new':
                with sqlite3.connect(self.engine.db) as db:
                    db.execute('INSERT INTO work_items VALUES(2,"new write")')
                raise RuntimeError('simulated unhealthy new image')
        with patch.object(upgrade, 'run'), patch.object(self.engine, 'switch') as switch, patch.object(self.engine, 'verify', side_effect=verify):
            with self.assertRaisesRegex(RuntimeError, 'unhealthy'):
                self.engine.apply(self.record, self.path)
        self.assertEqual([c.args[0] for c in switch.call_args_list], ['new', 'old'])
        with sqlite3.connect(self.engine.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM work_items').fetchone()[0], 2)
        self.assertEqual(json.loads(self.path.read_text())['status'], 'rolled-back')

    def test_schema_drift_stops_automatic_rollback(self):
        def switch(image):
            with sqlite3.connect(self.engine.db) as db:
                db.execute('ALTER TABLE work_items ADD COLUMN extra TEXT')
            raise RuntimeError('failed image')
        with patch.object(upgrade, 'run'), patch.object(self.engine, 'switch', side_effect=switch) as change:
            with self.assertRaisesRegex(RuntimeError, 'manual recovery'):
                self.engine.apply(self.record, self.path)
        change.assert_called_once_with('new')
        self.assertEqual(json.loads(self.path.read_text())['status'], 'manual-recovery-required')

    def test_fingerprint_detects_edited_migration_without_count_change(self):
        before = upgrade.fingerprint(self.engine.db)
        with sqlite3.connect(self.engine.db) as db:
            db.execute('UPDATE __drizzle_migrations SET hash="changed"')
        self.assertNotEqual(before, upgrade.fingerprint(self.engine.db))

    def test_failed_backup_recovers_old_container(self):
        with patch.object(upgrade, 'run'), patch.object(upgrade, 'backup', side_effect=OSError('disk full')), patch.object(self.engine, 'switch') as switch, patch.object(self.engine, 'verify'):
            with self.assertRaises(OSError):
                self.engine.apply(self.record, self.path)
        switch.assert_called_once_with('old')

    def test_rollback_can_recreate_a_missing_container(self):
        with patch.object(upgrade, 'run'), patch.object(self.engine, 'inspect', side_effect=RuntimeError('missing')), patch.object(self.engine, 'switch') as switch, patch.object(self.engine, 'verify'):
            self.engine.rollback(self.record, self.path)
        switch.assert_called_once_with('old')
        self.assertEqual(json.loads(self.path.read_text())['status'], 'rolled-back')


if __name__ == '__main__':
    unittest.main()
