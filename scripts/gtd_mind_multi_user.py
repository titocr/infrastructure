"""Explicit invite-only migration/recovery profile; invoked only by reviewed tooling."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid
from gtd_mind_upgrade import backup, run, fingerprint

PROFILE = 'invite-only-workspaces-v1'
CLI = 'dist/database/multi-user-cli.js'

def private_copy(source, target):
    shutil.copyfile(source, target)
    target.chmod(0o600)

def validate_inputs(review, actor):
    binding = Path(review['owner_binding_file']).resolve()
    if binding.stat().st_mode & 0o077:
        raise RuntimeError('Owner binding must be protected')
    if hashlib.sha256(binding.read_bytes()).hexdigest() != review.get('owner_binding_sha256'):
        raise RuntimeError('Owner binding differs from review')
    body = json.loads(binding.read_text())
    if body.get('actorId') != actor:
        raise RuntimeError('Owner binding must preserve the existing actor')
    return binding

def command(image, directory, operation, arguments, state=None, recovery=None):
    # No network, providers or default database selection. Bind only private
    # synthetic/approved rehearsal paths; the immutable baseline is read-only.
    mounts = ['-v', str(directory) + ':/rehearsal']
    if state is not None:
        mounts += ['-v', str(state) + ':/rehearsal/state']
    if recovery is not None:
        mounts += ['-v', str(recovery) + ':/rehearsal/recovery']
    baseline = directory / 'baseline.sqlite'
    if baseline.exists():
        mounts += ['-v', str(baseline) + ':/rehearsal/baseline.sqlite:ro']
    return run('docker', 'run', '--rm', '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
               '--tmpfs', '/tmp:rw,size=32m', '--user', f'{os.getuid()}:{os.getgid()}',
               *mounts, image, 'node', CLI, operation, '--offline', *arguments)

def check_isolated(name, actor):
    script = """const actor=process.argv[1]; Promise.all([fetch('http://127.0.0.1:3000/api/health/ready').then(r=>r.json()),fetch('http://127.0.0.1:3000/api/session').then(r=>r.json())]).then(([h,s])=>{if(h.status!=='ready'||s.actor?.id!==actor)process.exit(1)}).catch(()=>process.exit(1))"""
    for attempt in range(60):
        try:
            run('docker', 'exec', name, 'node', '-e', script, actor)
            return
        except RuntimeError:
            if attempt == 59:
                raise RuntimeError('Isolated image readiness/session failed')
            time.sleep(1)

def boot(image, state, recovery, actor, current):
    name = 'gtd-mind-synthetic-' + uuid.uuid4().hex[:12]
    try:
        args = ['docker', 'run', '-d', '--name', name, '--network', 'none', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--tmpfs', '/tmp:rw,size=32m', '--user', f'{os.getuid()}:{os.getgid()}',
                '-v', str(state) + ':/data', '-e', 'AUTH_MODE=local',
                '-e', 'OWNER_ACTOR_ID=' + actor, '-e', 'APP_ORIGIN=http://127.0.0.1:3000',
                '-e', 'MCP_ENABLED=false', '-e', 'TODOIST_POLLING_PAUSED=true', '-e', 'WRITE_QUARANTINE=true']
        if current:
            args += ['-v', str(recovery) + ':/recovery', '-e', 'ERASURE_REGISTER_PATH=/recovery/erasure.sqlite']
        run(*args, image)
        check_isolated(name, actor)
        run('docker', 'restart', name)
        check_isolated(name, actor)
    finally:
        run('docker', 'rm', '-f', name)

def compare_original(baseline, candidate):
    with closing(sqlite3.connect(baseline)) as before, closing(sqlite3.connect(candidate)) as after:
        tables = [r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name <> '__drizzle_migrations'")]
        for table in tables:
            quote = lambda value: '"' + value.replace('"', '""') + '"'
            columns = [r[1] for r in before.execute('PRAGMA table_info(' + quote(table) + ')')]
            query = 'SELECT ' + ','.join(map(quote, columns)) + ' FROM ' + quote(table) + ' ORDER BY ' + ','.join(map(quote, columns))
            if before.execute(query).fetchall() != after.execute(query).fetchall():
                raise RuntimeError('Original values changed in ' + table)
        if after.execute('PRAGMA foreign_key_check').fetchall() or after.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Candidate integrity failed')

def rehearse(engine, image, directory, record):
    image = record.get('image_id', image)
    binding = validate_inputs(engine.review, record['actor'])
    directory = directory.resolve()
    state = directory / 'state'
    recovery = directory / 'recovery'
    state.mkdir(mode=0o700)
    recovery.mkdir(mode=0o700)
    # Exactly one snapshot of the source. Every later comparison and restoration
    # uses this immutable baseline, never the potentially changing source.
    baseline = directory / 'baseline.sqlite'
    backup(engine.db, baseline)
    backup(baseline, state / 'gtd-ai.sqlite')
    private_copy(binding, directory / 'owner.json')
    protected = engine.root / 'recovery/erasure.sqlite'
    if protected.exists():
        copy_register(protected, recovery / 'erasure.sqlite')
    command(image, directory, 'manifest', ['--database', '/rehearsal/baseline.sqlite', '--output', '/rehearsal/baseline.json'])
    command(image, directory, 'migrate', ['--database', '/rehearsal/state/gtd-ai.sqlite', '--baseline', '/rehearsal/baseline.json',
        '--owner', '/rehearsal/owner.json', '--register', '/rehearsal/recovery/erasure.sqlite', '--output', '/rehearsal/migration.json'])
    boot(image, state, recovery, record['actor'], True)
    compare_original(baseline, state / 'gtd-ai.sqlite')
    record['candidate_schema'] = fingerprint(state / 'gtd-ai.sqlite')
    restored = directory / 'restored'
    restored.mkdir(mode=0o700)
    backup(baseline, restored / 'gtd-ai.sqlite')
    boot(record.get('previous_image_id', record['previous_image']), restored, recovery, record['actor'], False)
    compare_original(baseline, restored / 'gtd-ai.sqlite')
    if fingerprint(restored / 'gtd-ai.sqlite') != record['schema']:
        raise RuntimeError('Matching prior image changed restored schema')
    record['review'] = engine.review
    record['multi_user_rehearsal'] = {'immutable_baseline': True, 'original_values': True, 'candidate_restart': True, 'prior_image_restart': True, 'network': 'none'}


def validate_environment(engine):
    path = engine.target_env.resolve()
    if path.stat().st_mode & 0o077 or hashlib.sha256(path.read_bytes()).hexdigest() != engine.review.get('target_env_sha256'):
        raise RuntimeError('Candidate environment must match the protected reviewed file')
    values = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))
    if values.get('ERASURE_REGISTER_PATH') != '/recovery/erasure.sqlite':
        raise RuntimeError('Candidate must mount the protected external erasure register')
    engine.auth_environment(path)
    return path

def migrate_closed(engine, record, path):
    directory = path.parent.resolve()
    binding = validate_inputs(engine.review, record['actor'])
    private_copy(binding, directory / 'owner.json')
    # This is the fresh stopped production snapshot, not the old rehearsal copy.
    backup(engine.db, directory / 'baseline.sqlite')
    recovery = engine.root / 'recovery'
    recovery.mkdir(mode=0o700, exist_ok=True)
    command(record['image'], directory, 'manifest', ['--database', '/rehearsal/baseline.sqlite', '--output', '/rehearsal/baseline.json'])
    command(record['image'], directory, 'migrate', ['--database', '/rehearsal/state/gtd-ai.sqlite',
        '--baseline', '/rehearsal/baseline.json', '--owner', '/rehearsal/owner.json',
        '--register', '/rehearsal/recovery/erasure.sqlite', '--output', '/rehearsal/migration.json'],
        state=engine.db.parent, recovery=recovery)


def copy_register(source, target):
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        if not src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='erasures'").fetchone():
            raise RuntimeError('Protected erasure register is uninitialized')
        src.backup(dst)
    target.chmod(0o600)

def rehearse_existing(engine, image, directory, record):
    image = record.get('image_id', image)
    directory = directory.resolve()
    baseline = directory / 'baseline.sqlite'
    state, recovery, restored = directory / 'state', directory / 'recovery', directory / 'restored'
    for path in [state, recovery, restored]:
        path.mkdir(mode=0o700)
    backup(engine.db, baseline)
    backup(baseline, state / 'gtd-ai.sqlite')
    copy_register(engine.root / 'recovery/erasure.sqlite', recovery / 'erasure.sqlite')
    boot(image, state, recovery, record['actor'], True)
    compare_original(baseline, state / 'gtd-ai.sqlite')
    if fingerprint(state / 'gtd-ai.sqlite') != record['schema']:
        raise RuntimeError('Schema-preserving candidate changed schema')
    backup(baseline, restored / 'gtd-ai.sqlite')
    boot(record.get('previous_image_id', record['previous_image']), restored, recovery, record['actor'], True)
    compare_original(baseline, restored / 'gtd-ai.sqlite')
