#!/usr/bin/env python3
"""Rehearse and deploy schema-preserving GTD Mind container upgrades."""
import argparse
from contextlib import closing
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import shutil
import uuid


def run(*args, env=None):
    result = subprocess.run(args, env=env, capture_output=True, text=True)
    if result.returncode:
        # Do not echo command output: runtime configuration may contain secrets.
        raise RuntimeError(f'{args[0]} {args[1]} failed (exit {result.returncode})')
    return result.stdout.strip()


def database(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=30)


def fingerprint(path):
    with closing(database(path)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('Database integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Database foreign-key check failed')
        schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        migrations = db.execute('SELECT * FROM __drizzle_migrations ORDER BY id').fetchall()
    return hashlib.sha256(json.dumps([schema, migrations]).encode()).hexdigest()


def backup(source, target):
    with closing(database(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        # A standalone backup must not depend on transient WAL/SHM companions.
        dst.execute('PRAGMA journal_mode=DELETE')
    target.chmod(0o600)
    return fingerprint(target)


def write_record(path, data):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def get(origin, endpoint, headers=None):
    request = urllib.request.Request(origin + endpoint, headers=headers or {})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


def check_app(origin, actor, timeout=60, mode="local", headers=None):
    deadline = time.monotonic() + timeout
    while True:
        try:
            ready = get(origin, '/api/health/ready')
            session = get(origin, '/api/session', headers)
            if ready.get('status') != 'ready' or ready.get('checks', {}).get('database') != 'ok':
                raise RuntimeError('Not ready')
            if not session.get('authenticated') or session.get('actor', {}).get('source') != mode:
                raise RuntimeError('Owner authentication failed')
            if session['actor']['id'] != actor:
                raise RuntimeError('Owner identity changed')
            with urllib.request.urlopen(urllib.request.Request(origin + '/', headers=headers or {}), timeout=3) as response:
                if b'<app-root' not in response.read():
                    raise RuntimeError('Web application missing')
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise RuntimeError('Application readiness/session/UI verification failed') from None
            time.sleep(1)


class Upgrade:
    def __init__(self, app, root):
        self.app = app.resolve()
        self.root = root.resolve()
        self.db = self.root / 'state/gtd-ai.sqlite'
        self.env_file = self.root / 'config/gtd-mind.env'
        self.compose = Path(__file__).resolve().parents[1] / 'compose.gtd-mind.yaml'
        self.container = 'gtd-mind-production-1'
        self.origin = 'http://127.0.0.1:3000'
        self.target_env = Path(os.environ.get('GTD_MIND_TARGET_ENV_FILE', str(self.env_file)))

    def runtime_mode(self):
        values = dict(item.split('=', 1) for item in self.inspect()['Config']['Env'])
        mode = values.get('AUTH_MODE', 'local')
        if mode not in ('local', 'cloudflare'):
            raise RuntimeError('Unsupported production authentication mode')
        return mode

    def headers(self):
        if self.runtime_mode() != 'cloudflare':
            return {}
        name = os.environ.get('GTD_MIND_OWNER_TOKEN_FILE')
        if not name:
            raise RuntimeError('Cloudflare release checks require GTD_MIND_OWNER_TOKEN_FILE')
        path = Path(name)
        if path.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError('Owner token file must have mode 0600')
        token = path.read_text().strip()
        if not token or any(c.isspace() for c in token):
            raise RuntimeError('Invalid owner token file')
        return {'Cf-Access-Jwt-Assertion': token}

    def assert_direct_denied(self):
        if self.runtime_mode() != 'cloudflare':
            return
        for endpoint in ('/api/session', '/api/inbox', '/api/sync-health', '/'):
            try:
                get(self.origin, endpoint)
            except urllib.error.HTTPError as error:
                if error.code == 401:
                    continue
            raise RuntimeError('Direct origin authentication bypass detected')

    @staticmethod
    def auth_environment(path):
        if path.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError('Production configuration must have mode 0600')
        values = {}
        for line in path.read_text().splitlines():
            if line.startswith(('AUTH_MODE=', 'APP_ORIGIN=')):
                key, value = line.split('=', 1)
                values[key] = value.strip()
        mode = values.get('AUTH_MODE', 'local')
        origin = values.get('APP_ORIGIN', 'http://127.0.0.1:3000')
        if mode not in ('local', 'cloudflare') or (mode == 'cloudflare' and not origin.startswith('https://')):
            raise RuntimeError('Invalid production auth configuration')
        return dict(GTD_MIND_AUTH_MODE=mode, GTD_MIND_APP_ORIGIN=origin)

    def stop_tunnel(self):
        # Missing connector is safe. Any other Docker failure stops recovery.
        names = run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines()
        if 'gtd-mind-cloudflared' in names:
            run('docker', 'stop', 'gtd-mind-cloudflared')


    def inspect(self):
        return json.loads(run('docker', 'inspect', self.container))[0]

    @staticmethod
    def image_id(image):
        return run('docker', 'image', 'inspect', image, '--format', '{{.Id}}')

    def stop_container(self):
        try:
            run('docker', 'stop', self.container)
        except RuntimeError as error:
            # Probe names without printing runtime secrets to distinguish absence.
            if self.container in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines():
                raise error
        if self.db.exists():
            # Only after stopping the writer: checkpoint WAL so macOS read-only
            # backup/integrity connections do not need to create WAL/SHM files.
            with closing(sqlite3.connect(self.db.resolve().as_uri() + '?mode=rw', uri=True)) as db:
                result = db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                if result is not None and result[0] != 0:
                    raise RuntimeError('Database checkpoint remained busy after stop')
                if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0] != 'delete':
                    raise RuntimeError('Unable to prepare stopped database for backup')

    def preflight(self, revision):
        if not re.fullmatch('[0-9a-f]{40}', revision):
            raise RuntimeError('Use a full 40-character published application revision')
        if run('git', '-C', str(self.app), 'status', '--porcelain'):
            raise RuntimeError('Application checkout must be clean')
        head = run('git', '-C', str(self.app), 'rev-parse', 'HEAD')
        branch = run('git', '-C', str(self.app), 'branch', '--show-current')
        remote = run('git', '-C', str(self.app), 'ls-remote', 'origin', 'refs/heads/main').split()[0]
        if head != revision or remote != revision or branch != 'main':
            raise RuntimeError('Candidate must be clean local main and published remote main')
        if self.env_file.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError('Production configuration must have mode 0600')
        serve = json.loads(run('tailscale', 'serve', 'status', '--json'))
        if any(serve.get(key) for key in ('Web', 'TCP', 'AllowFunnel')):
            raise RuntimeError('Local production requires Tailscale Serve to remain absent')
        disabled = run('launchctl', 'print-disabled', f'gui/{os.getuid()}')
        if not re.search(r'"com\.titocr\.gtd-ai"\s*=>\s*disabled', disabled):
            raise RuntimeError('Legacy LaunchAgent must remain disabled')
        current = self.inspect()
        ports = current['HostConfig']['PortBindings']
        if ports != {'3000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '3000'}]}:
            raise RuntimeError('Unexpected production port binding')
        mounts = [m for m in current['Mounts'] if m['Destination'] == '/data']
        if len(mounts) != 1 or Path(mounts[0]['Source']).resolve() != self.db.parent:
            raise RuntimeError('Unexpected authoritative database mount')
        old_revision = current['Config']['Labels']['org.opencontainers.image.revision']
        for ref in (old_revision, revision):
            run('git', '-C', str(self.app), 'cat-file', '-e', ref + '^{commit}')
        # Compare the complete committed migration tree, not just its count.
        old_tree = run('git', '-C', str(self.app), 'rev-parse', old_revision + ':apps/server/drizzle')
        new_tree = run('git', '-C', str(self.app), 'rev-parse', revision + ':apps/server/drizzle')
        if old_tree != new_tree:
            raise RuntimeError('Migration files differ; schema-changing upgrades are not supported')
        session = get(self.origin, '/api/session', self.headers())
        actor = session.get('actor', {}).get('id')
        check_app(self.origin, actor, mode=self.runtime_mode(), headers=self.headers())
        self.assert_direct_denied()
        sync = get(self.origin, '/api/sync-health', self.headers())
        if sync.get('configured') and sync.get('status') != 'healthy':
            raise RuntimeError('Resolve existing Todoist degradation before deploying')
        return dict(previous_image=current['Config']['Image'], previous_image_id=current['Image'], previous_revision=old_revision,
                    revision=revision, schema=fingerprint(self.db), actor=actor,
                    sync_configured=sync.get('configured', False))

    def build(self, revision, directory):
        archive = directory / 'source.tar'
        run('git', '-C', str(self.app), 'archive', '--output', str(archive), revision)
        context = directory / 'source'
        context.mkdir()
        run('tar', '-xf', str(archive), '-C', str(context))
        tag = 'gtd-mind:' + revision[:12]
        print('Building exact application revision...', flush=True)
        run('docker', 'build', '--platform', 'linux/arm64', '--label',
            'org.opencontainers.image.revision=' + revision, '-t', tag, str(context))
        return tag

    def rehearse(self, image, directory, record):
        state = directory / 'candidate'
        state.mkdir(mode=0o700)
        copy = state / 'gtd-ai.sqlite'
        before = backup(self.db, copy)
        name = 'gtd-mind-rehearsal-' + uuid.uuid4().hex[:12]
        try:
            run('docker', 'run', '-d', '--name', name, '--init', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--tmpfs', '/tmp:rw,size=16m', '-p', '127.0.0.1::3000',
                '--user', f'{os.getuid()}:{os.getgid()}',
                '-v', str(state) + ':/data', '-e', 'AUTH_MODE=local',
                '-e', 'APP_ORIGIN=http://127.0.0.1:3000',
                '-e', 'OWNER_ACTOR_ID=' + record['actor'], image)
            info = json.loads(run('docker', 'inspect', name))[0]
            port = info['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
            origin = 'http://127.0.0.1:' + port
            check_app(origin, record['actor'])
            if get(origin, '/api/sync-health').get('configured'):
                raise RuntimeError('Rehearsal must not have provider credentials')
            run('docker', 'restart', name)
            info = json.loads(run('docker', 'inspect', name))[0]
            port = info['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
            origin = 'http://127.0.0.1:' + port
            check_app(origin, record['actor'])
            run('docker', 'stop', name)
            # macOS SQLite cannot reopen a WAL-mode file read-only after the
            # final writer removes WAL/SHM. Normalize this stopped private copy.
            with closing(sqlite3.connect(copy)) as candidate:
                candidate.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                candidate.execute('PRAGMA journal_mode=DELETE')
            if fingerprint(copy) != before or before != record['schema']:
                raise RuntimeError('Candidate changed schema or migration ledger')
            with closing(database(self.db)) as live, closing(database(copy)) as candidate:
                # No task content is printed or copied to repository artifacts.
                if candidate.execute('SELECT count(*) FROM work_items').fetchone()[0] == 0 and live.execute('SELECT count(*) FROM work_items').fetchone()[0] != 0:
                    raise RuntimeError('Candidate lost persisted records')
            backup(copy, directory / 'restore-check.sqlite')
        finally:
            run('docker', 'rm', '-f', name)

    def switch(self, image):
        env = dict(os.environ, GTD_MIND_IMAGE=image,
                   GTD_MIND_PRODUCTION_ENV_FILE=str(self.env_file),
                   GTD_MIND_PRODUCTION_DATA_ROOT=str(self.db.parent),
                   **self.auth_environment(self.env_file))
        run('docker', 'compose', '-f', str(self.compose), '--profile', 'production',
            'up', '-d', '--no-deps', '--force-recreate', 'production', env=env)

    def verify(self, record, image, fresh_sync=False):
        if self.inspect()['Image'] != self.image_id(image):
            raise RuntimeError('Running image differs from selected immutable image')
        check_app(self.origin, record['actor'], mode=self.runtime_mode(), headers=self.headers())
        self.assert_direct_denied()
        if fingerprint(self.db) != record['schema']:
            raise RuntimeError('Production schema changed unexpectedly')
        if fresh_sync and record['sync_configured']:
            deadline = time.monotonic() + 360
            print('Waiting for the first successful Todoist poll from the new container...', flush=True)
            started = self.inspect()['State']['StartedAt'][:19]
            while True:
                sync = get(self.origin, '/api/sync-health', self.headers())
                if sync.get('status') == 'healthy' and (sync.get('lastSucceededAt') or '')[:19] >= started:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('No fresh successful Todoist poll within six minutes')
                time.sleep(3)

    def apply(self, record, path):
        self.auth_environment(self.target_env)
        saved_env = path.parent / 'previous.env'
        shutil.copyfile(self.env_file, saved_env)
        saved_env.chmod(0o600)
        record['previous_env'] = str(saved_env)
        record['status'] = 'switching'
        write_record(path, record)  # Durable recovery information before stopping anything.
        try:
            self.stop_container()
            saved = path.parent / 'before-upgrade.sqlite'
            if backup(self.db, saved) != record['schema']:
                raise RuntimeError('Database schema drifted since rehearsal')
            record['backup'] = str(saved)
            write_record(path, record)
            if self.target_env.resolve() != self.env_file.resolve():
                shutil.copyfile(self.target_env, self.env_file)
                self.env_file.chmod(0o600)
            self.switch(record['image'])
            self.verify(record, record['image'], fresh_sync=True)
            record['status'] = 'succeeded'
            write_record(path, record)
        except BaseException:
            self.rollback(record, path)
            raise

    def rollback(self, record, path):
        # Preserve all current writes. Never restore an old database automatically.
        self.stop_container()
        if fingerprint(self.db) != record['schema']:
            record['status'] = 'manual-recovery-required'
            write_record(path, record)
            raise RuntimeError('Schema changed: container stopped; manual recovery required')
        previous_env = record.get('previous_env')
        if previous_env:
            saved = Path(previous_env)
            if saved.resolve().parent != path.resolve().parent:
                raise RuntimeError('Invalid rollback configuration path')
            if self.auth_environment(saved)['GTD_MIND_AUTH_MODE'] == 'local':
                self.stop_tunnel()
            shutil.copyfile(saved, self.env_file)
            self.env_file.chmod(0o600)
        self.switch(record['previous_image'])
        self.verify(record, record['previous_image'])
        record['status'] = 'rolled-back'
        write_record(path, record)
        print('Previous container image restored; current database writes retained.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', nargs='?')
    parser.add_argument('--apply', action='store_true', help='Switch production after rehearsal')
    parser.add_argument('--rollback', type=Path, help='Explicitly recover using a deployment record')
    parser.add_argument('--app-repo', type=Path, default=Path('/Users/titocr/code/gtd-ai'))
    args = parser.parse_args()
    os.umask(0o077)
    root = Path('/Users/titocr/container-data/gtd-mind')
    upgrade = Upgrade(args.app_repo, root)
    with (root / 'upgrade.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            if args.revision or args.apply:
                parser.error('Use --rollback alone')
            path = args.rollback.resolve()
            if not path.is_relative_to(root / 'deployments'):
                parser.error('Recovery record must be under production deployments')
            record = json.loads(path.read_text())
            try:
                current_image = upgrade.inspect()['Image']
            except RuntimeError:
                current_image = None
            if current_image is not None and current_image not in (record.get('image_id'), record.get('previous_image_id')):
                raise RuntimeError('Deployment record does not match current container')
            upgrade.rollback(record, path)
            return
        if not args.revision:
            parser.error('A revision is required')
        deployments = root / 'deployments'
        deployments.mkdir(mode=0o700, exist_ok=True)
        for path in deployments.glob('*/record.json'):
            if json.loads(path.read_text()).get('status') in ('switching', 'manual-recovery-required'):
                raise RuntimeError('Unfinished deployment requires explicit recovery: ' + str(path))
        record = upgrade.preflight(args.revision)
        directory = Path(tempfile.mkdtemp(prefix='gtd-mind-upgrade-'))
        # Private copies are retained for review; their path is printed for deliberate cleanup.
        print('Private rehearsal artifacts: ' + str(directory), flush=True)
        record['image'] = upgrade.build(args.revision, directory)
        record['image_id'] = upgrade.image_id(record['image'])
        upgrade.rehearse(record['image'], directory, record)
        print('Rehearsal passed: owner session, UI, restart, schema and restore.', flush=True)
        if not args.apply:
            return
        current = upgrade.preflight(args.revision)
        if any(current[k] != record[k] for k in current):
            raise RuntimeError('Production changed during rehearsal; retry')
        deployment = deployments / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
        deployment.mkdir(mode=0o700)
        record['at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        upgrade.apply(record, deployment / 'record.json')
        print('Deployment verified. Record: ' + str(deployment / 'record.json'))


if __name__ == '__main__':
    main()
