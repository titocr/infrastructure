import os
import time
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gtd_mind_retention import inventory, enforce, MAX_AGE

class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root / 'live.sqlite'
        self.register = self.root / 'erasure.sqlite'
        self.copy = self.root / 'old.sqlite'
        for path in [self.live, self.register, self.copy]:
            with sqlite3.connect(path) as db:
                db.execute('create table synthetic(id)')
            path.chmod(0o600)
        self.now = time.time() + 1
        for path in [self.live, self.register, self.copy]:
            os.utime(path, (self.now - MAX_AGE - 1, self.now - MAX_AGE - 1))
    def test_protected_live_and_register_are_never_deleted(self):
        report = inventory([self.root], [self.live, self.register], {}, self.now)
        self.assertEqual(report['expired'], [str(self.copy.resolve())])
        self.assertTrue(self.copy.exists())
        self.assertEqual(enforce(report, self.now), 1)
        self.assertTrue(self.live.exists())
        self.assertTrue(self.register.exists())
    def test_changed_copy_requires_new_review(self):
        report = inventory([self.root], [self.live, self.register], {}, self.now)
        with sqlite3.connect(self.copy) as db:
            db.execute('insert into synthetic values(1)')
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            enforce(report, self.now)
        self.assertTrue(self.copy.exists())
    def test_young_copy_is_retained_and_symlinks_refused(self):
        self.copy.unlink()
        with sqlite3.connect(self.copy) as db:
            db.execute('create table synthetic(id)')
        self.copy.chmod(0o600)
        report = inventory([self.root], [self.live, self.register], {}, self.now)
        self.assertEqual(report['expired'], [])
        (self.root / 'linked.sqlite').symlink_to(self.live)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            inventory([self.root], [self.live, self.register], {}, self.now)
    def test_unknown_formats_expire_but_live_sidecars_do_not(self):
        secret = self.root / 'old-token-without-extension'
        secret.write_text('synthetic secret')
        secret.chmod(0o600)
        os.utime(secret, (self.now - MAX_AGE - 1, self.now - MAX_AGE - 1))
        sidecar = Path(str(self.live) + '-wal')
        sidecar.write_text('synthetic live sidecar')
        sidecar.chmod(0o600)
        os.utime(sidecar, (self.now - MAX_AGE - 1, self.now - MAX_AGE - 1))
        report = inventory([self.root], [self.live, self.register], {}, self.now)
        self.assertIn(str(secret.resolve()), report['expired'])
        self.assertNotIn(str(sidecar.resolve()), report['copies'])
        enforce(report, self.now)
        self.assertTrue(sidecar.exists())
