#!/usr/bin/env python3
"""Reviewed, quarantined schema migration; normal upgrades continue rejecting schema changes."""
import argparse
from contextlib import closing
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import uuid
from gtd_mind_upgrade import Upgrade, backup, fingerprint, database, run, write_record, check_app


def validate_review(app, old, new, review):
    if review.get('previous_revision') != old or review.get('revision') != new:
        raise RuntimeError('Review does not match the exact previous and candidate commits')
    prefix = 'apps/server/drizzle/'
    changes = run('git', '-C', str(app), 'diff', '--name-status', old, new, '--', prefix).splitlines()
    actual = {}
    for line in changes:
        status, path = line.split('\t', 1)
        if status not in ('A', 'M') or not path.startswith(prefix):
            raise RuntimeError('Migration review permits additions and journal changes only')
        if status == 'M' and path != prefix + 'meta/_journal.json':
            raise RuntimeError('Previously committed migrations and snapshots must not change')
        contents = run('git', '-C', str(app), 'show', new + ':' + path)
        actual[path] = hashlib.sha256(contents.encode()).hexdigest()
    if not actual or actual != review.get('files'):
        raise RuntimeError('Review must contain SHA256 of every changed migration file (Git text, stripped)')


class MigrationUpgrade(Upgrade):
    def __init__(self, app, root, review):
        super().__init__(app, root)
        self.review = review

    def validate_migrations(self, old_revision, revision):
        validate_review(self.app, old_revision, revision, self.review)

    def rehearse(self, image, directory, record):
        state = directory / 'candidate'
        state.mkdir(mode=0o700)
        copy = state / 'gtd-ai.sqlite'
        backup(self.db, copy)
        name = 'gtd-mind-migration-rehearsal-' + uuid.uuid4().hex[:12]
        try:
            run('docker', 'run', '-d', '--name', name, '--init', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--tmpfs', '/tmp:rw,size=16m', '-p', '127.0.0.1::3000',
                '--user', f'{os.getuid()}:{os.getgid()}', '-v', str(state) + ':/data',
                '-e', 'AUTH_MODE=local', '-e', 'OWNER_ACTOR_ID=' + record['actor'],
                '-e', 'APP_ORIGIN=http://127.0.0.1:3000', '-e', 'MCP_ENABLED=false',
                '-e', 'TODOIST_POLLING_PAUSED=true', '-e', 'WRITE_QUARANTINE=true', image)
            info = json.loads(run('docker', 'inspect', name))[0]
            origin = 'http://127.0.0.1:' + info['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
            check_app(origin, record['actor'])
            run('docker', 'restart', name)
            info = json.loads(run('docker', 'inspect', name))[0]
            origin = 'http://127.0.0.1:' + info['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
            check_app(origin, record['actor'])
            run('docker', 'stop', name)
            with closing(sqlite3.connect(copy)) as db:
                db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                db.execute('PRAGMA journal_mode=DELETE')
                if db.execute('PRAGMA foreign_key_check').fetchall():
                    raise RuntimeError('Candidate has foreign-key violations')
            record['candidate_schema'] = fingerprint(copy)
            if record['candidate_schema'] == record['schema']:
                raise RuntimeError('Reviewed migration did not change the schema')
            with closing(database(self.db)) as live, closing(database(copy)) as candidate:
                for table in ('work_items', 'gtd_projects', 'change_sets', 'manual_commands', 'audit_events', 'source_observations', 'source_items', 'source_projections', 'work_item_gtd_states', 'local_creation_commands', 'local_completion_commands', 'today_memberships', 'today_membership_commands'):
                    # Hash retained original columns and all rows; never log personal content.
                    columns = [r[1] for r in live.execute(f'PRAGMA table_info({table})')]
                    query = 'SELECT ' + ','.join('"' + x + '"' for x in columns) + ' FROM ' + table + ' ORDER BY ' + ','.join('\"' + x + '\"' for x in columns)
                    if live.execute(query).fetchall() != candidate.execute(query).fetchall():
                        raise RuntimeError('Candidate changed retained rows in ' + table)
            restored = directory / 'restore-check.sqlite'
            backup(self.db, restored)
            if fingerprint(restored) != record['schema']:
                raise RuntimeError('Original schema could not be restored')
            record['review'] = self.review
        finally:
            run('docker', 'rm', '-f', name)

    def apply(self, record, path):
        if self.target_env.resolve() != self.env_file.resolve():
            raise RuntimeError('Perform configuration transitions separately from schema migrations')
        self.auth_environment(self.target_env)
        values = dict(line.split('=', 1) for line in self.target_env.read_text().splitlines() if '=' in line and not line.startswith('#'))
        if values.get('MCP_ENABLED') == 'true':
            raise RuntimeError('Initial migration must leave MCP disabled')
        original_env = self.env_file
        saved_env = path.parent / 'previous.env'
        shutil.copyfile(original_env, saved_env)
        saved_env.chmod(0o600)
        paused = path.parent / 'paused.env'
        paused.write_text(self.target_env.read_text() + '\nMCP_ENABLED=false\nTODOIST_POLLING_PAUSED=true\nWRITE_QUARANTINE=true\n')
        paused.chmod(0o600)
        record.update(status='switching', phase='quarantining', previous_env=str(saved_env), paused_env=str(paused), writes_resumed=False)
        write_record(path, record)
        try:
            record['connector_was_running'] = 'gtd-mind-cloudflared' in run('docker', 'ps', '--format', '{{.Names}}').splitlines()
            self.stop_tunnel()
            self.stop_container()
            saved = path.parent / 'before-migration.sqlite'
            if backup(self.db, saved) != record['schema']:
                raise RuntimeError('Production drifted since rehearsal')
            record['backup'] = str(saved)
            write_record(path, record)
            self.env_file = paused
            self.switch(record['image'])
            self.verify({**record, 'schema': record['candidate_schema']}, record['image'])
            record['phase'] = 'verified-quarantined'
            write_record(path, record)
        except BaseException:
            try:
                self.restore_quarantined(record, path)
            except BaseException:
                record['status'] = 'manual-recovery-required'
                write_record(path, record)
                raise
            raise
        finally:
            self.env_file = original_env

    def restore_quarantined(self, record, path):
        if record.get('writes_resumed'):
            record['status'] = 'manual-recovery-required'
            write_record(path, record)
            raise RuntimeError('Writes resumed; preserve data and use forward recovery')
        previous_env = Path(record['previous_env'])
        if previous_env.resolve().parent != path.resolve().parent:
            raise RuntimeError('Invalid migration configuration backup')
        if record.get('status') not in ('switching', 'manual-recovery-required'):
            raise RuntimeError('Only an unfinished migration can restore')
        if record.get('backup'):
            try:
                current = self.inspect()
            except RuntimeError:
                current = None
            if current:
                if current['Image'] not in (record.get('image_id'), record.get('previous_image_id')):
                    raise RuntimeError('Migration record does not match the current container')
                values = dict(v.split('=', 1) for v in current['Config']['Env'])
                if current['State']['Running'] and values.get('WRITE_QUARANTINE') != 'true':
                    record['status'] = 'manual-recovery-required'
                    write_record(path, record)
                    raise RuntimeError('Writer is active outside quarantine; preserve data and use forward recovery')
        self.stop_tunnel()
        self.stop_container()
        if record.get('backup'):
            saved = Path(record['backup'])
            if saved.resolve().parent != path.resolve().parent or fingerprint(saved) != record['schema']:
                raise RuntimeError('Invalid migration backup')
            backup(self.db, path.parent / 'failed-candidate.sqlite')
            backup(saved, self.db)
        self.env_file = Path(record['previous_env'])
        self.switch(record['previous_image'])
        self.verify(record, record['previous_image'])
        # Ingress stays stopped for deliberate owner recovery.
        record.update(status='rolled-back', phase='restored-ingress-closed')
        write_record(path, record)

    def resume(self, record, path):
        if record.get('phase') != 'verified-quarantined' or record.get('writes_resumed'):
            raise RuntimeError('Only a verified, quarantined migration can resume')
        current = self.inspect()
        if current['Image'] != record['image_id'] or fingerprint(self.db) != record['candidate_schema']:
            raise RuntimeError('Candidate changed since verification')
        env = dict(v.split('=', 1) for v in current['Config']['Env'])
        if env.get('TODOIST_POLLING_PAUSED') != 'true' or env.get('MCP_ENABLED') != 'false' or env.get('WRITE_QUARANTINE') != 'true':
            raise RuntimeError('Candidate is not quarantined')
        if 'gtd-mind-cloudflared' in run('docker', 'ps', '--format', '{{.Names}}').splitlines():
            raise RuntimeError('Ingress reopened before migration approval')
        saved = Path(record['previous_env'])
        if saved.resolve().parent != path.resolve().parent or saved.read_bytes() != self.env_file.read_bytes():
            raise RuntimeError('Production configuration changed during quarantine')
        record.update(writes_resumed=True, phase='resuming')
        write_record(path, record)  # From this point, automatic database restore is forbidden.
        try:
            self.switch(record['image'])
            self.verify({**record, 'schema': record['candidate_schema']}, record['image'], fresh_sync=True)
            if record.get('connector_was_running'):
                run('docker', 'start', 'gtd-mind-cloudflared')
            record.update(status='succeeded', phase='active')
            write_record(path, record)
        except BaseException:
            record['status'] = 'manual-recovery-required'
            write_record(path, record)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', nargs='?')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--restore-quarantined', type=Path)
    parser.add_argument('--app-repo', type=Path, default=Path('/Users/titocr/code/gtd-ai'))
    args = parser.parse_args()
    os.umask(0o077)
    root = Path('/Users/titocr/container-data/gtd-mind')
    review = json.loads(args.review.read_text()) if args.review else {}
    upgrade = MigrationUpgrade(args.app_repo, root, review)
    with (root / 'upgrade.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recovery = args.resume or args.restore_quarantined
        if recovery:
            if args.revision or args.review or args.apply or (args.resume and args.restore_quarantined):
                parser.error('Use exactly one recovery operation')
            path = recovery.resolve()
            if not path.is_relative_to(root / 'deployments'):
                parser.error('Record must be under production deployments')
            record = json.loads(path.read_text())
            try:
                current_image = upgrade.inspect()['Image']
            except RuntimeError:
                current_image = None
            if current_image is not None and current_image not in (record.get('image_id'), record.get('previous_image_id')):
                raise RuntimeError('Migration record does not match the current container')
            if args.resume: upgrade.resume(record, path)
            else: upgrade.restore_quarantined(record, path)
            return
        if not args.revision or not args.review:
            parser.error('Exact revision and --review are required')
        deployments = root / 'deployments'
        deployments.mkdir(mode=0o700, exist_ok=True)
        for path in deployments.glob('*/record.json'):
            if json.loads(path.read_text()).get('status') in ('switching', 'manual-recovery-required'):
                raise RuntimeError('Resolve unfinished deployment before migration')
        record = upgrade.preflight(args.revision)
        directory = Path(tempfile.mkdtemp(prefix='gtd-mind-migration-'))
        record['image'] = upgrade.build(args.revision, directory)
        record['image_id'] = upgrade.image_id(record['image'])
        upgrade.rehearse(record['image'], directory, record)
        print('Migration and restoration rehearsed. Private artifacts: ' + str(directory))
        if args.apply:
            current = upgrade.preflight(args.revision)
            if any(current[k] != record[k] for k in current):
                raise RuntimeError('Production changed since rehearsal')
            directory = deployments / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-migration-' + uuid.uuid4().hex[:8])
            directory.mkdir(mode=0o700)
            upgrade.apply(record, directory / 'record.json')
            print('Verified with ingress and polling stopped. Resume explicitly with record: ' + str(directory / 'record.json'))

if __name__ == '__main__':
    main()
