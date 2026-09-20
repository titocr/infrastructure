from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gtd_mind_multi_user as profile

class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
    def test_requires_exact_private_owner_binding(self):
        path = self.root / 'owner.json'
        path.write_text(json.dumps({'actorId': 'stable-owner'}))
        path.chmod(0o600)
        review = {'owner_binding_file': str(path), 'owner_binding_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.assertEqual(profile.validate_inputs(review, 'stable-owner'), path)
        with self.assertRaisesRegex(RuntimeError, 'preserve'):
            profile.validate_inputs(review, 'different')
        path.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            profile.validate_inputs(review, 'stable-owner')
    def test_container_tool_is_networkless_and_baseline_read_only(self):
        baseline = self.root / 'baseline.sqlite'
        baseline.touch()
        with patch.object(profile, 'run') as run:
            profile.command('exact-image', self.root, 'manifest', ['--database','/rehearsal/baseline.sqlite','--output','/rehearsal/manifest.json'])
        args = run.call_args.args
        self.assertIn('none', args)
        self.assertIn(str(baseline) + ':/rehearsal/baseline.sqlite:ro', args)
        self.assertIn('--offline', args)
        self.assertNotIn('--env-file', args)
    def test_comparison_uses_all_original_tables_and_columns(self):
        before, after = self.root / 'before.sqlite', self.root / 'after.sqlite'
        for path in [before, after]:
            with closing(sqlite3.connect(path)) as db:
                db.executescript('CREATE TABLE source_evidence(id TEXT, body TEXT); INSERT INTO source_evidence VALUES("one","synthetic"); CREATE TABLE unrelated(id INTEGER);')
        with closing(sqlite3.connect(after)) as db:
            db.execute('ALTER TABLE source_evidence ADD workspace_id TEXT')
        profile.compare_original(before, after)
        with closing(sqlite3.connect(after)) as db:
            db.execute('UPDATE source_evidence SET body="changed"')
            db.commit()
        with self.assertRaisesRegex(RuntimeError, 'source_evidence'):
            profile.compare_original(before, after)
    def test_register_copy_requires_existing_schema(self):
        source, target = self.root / 'register.sqlite', self.root / 'copy.sqlite'
        with closing(sqlite3.connect(source)) as db:
            db.execute('CREATE TABLE erasures(userId TEXT)')
        profile.copy_register(source, target)
        with closing(sqlite3.connect(target)) as db:
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='erasures'").fetchone())
    def test_reviewed_environment_cannot_change_between_review_and_apply(self):
        from types import SimpleNamespace
        path = self.root / 'candidate.env'
        path.write_text('ERASURE_REGISTER_PATH=/recovery/erasure.sqlite\n')
        path.chmod(0o600)
        engine = SimpleNamespace(target_env=path, review={'target_env_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},auth_environment=lambda _:None)
        self.assertEqual(profile.validate_environment(engine), path)
        path.write_text('ERASURE_REGISTER_PATH=/data/unsafe.sqlite\n')
        with self.assertRaisesRegex(RuntimeError, 'reviewed'):
            profile.validate_environment(engine)
    def test_closed_migration_reads_fresh_stopped_source_and_keeps_register_separate(self):
        from types import SimpleNamespace
        state = self.root / 'live-state'
        state.mkdir()
        source = state / 'gtd-ai.sqlite'
        with closing(sqlite3.connect(source)) as db:
            db.executescript('CREATE TABLE __drizzle_migrations(id INTEGER,hash TEXT); CREATE TABLE work_items(id INTEGER); INSERT INTO work_items VALUES(2);')
        binding = self.root / 'owner.json'
        binding.write_text(json.dumps({'actorId':'stable-owner'}));binding.chmod(0o600)
        output = self.root / 'deployment'
        output.mkdir()
        engine = SimpleNamespace(db=source,root=self.root,review={'owner_binding_file':str(binding),'owner_binding_sha256':hashlib.sha256(binding.read_bytes()).hexdigest()})
        with patch.object(profile,'command') as command:
            profile.migrate_closed(engine,{'actor':'stable-owner','image':'exact-candidate'},output/'record.json')
        with closing(sqlite3.connect(output/'baseline.sqlite')) as db:
            self.assertEqual(db.execute('SELECT id FROM work_items').fetchall(),[(2,)])
        self.assertEqual(command.call_args.kwargs,{'state':state,'recovery':self.root/'recovery'})
