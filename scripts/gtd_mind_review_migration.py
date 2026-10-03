"""Guarded additive review migration for the already deployed workspace model."""
import hashlib
from pathlib import Path
from gtd_mind_upgrade import backup, fingerprint
import gtd_mind_multi_user as workspaces

PROFILE = 'conversational-review-v1'

def validate_environment(engine):
    path = engine.target_env.resolve()
    if path != engine.env_file.resolve():
        raise RuntimeError('Review migration preserves the existing production configuration')
    if path.stat().st_mode & 0o077 or hashlib.sha256(path.read_bytes()).hexdigest() != engine.review.get('target_env_sha256'):
        raise RuntimeError('Production configuration differs from the protected review')
    values = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))
    if values.get('ERASURE_REGISTER_PATH') != '/recovery/erasure.sqlite':
        raise RuntimeError('Review migration requires the existing protected erasure register')
    engine.auth_environment(path)

def rehearse(engine, image, directory, record):
    image = record.get('image_id', image)
    directory = directory.resolve()
    baseline = directory / 'baseline.sqlite'
    state, recovery, restored = directory / 'state', directory / 'recovery', directory / 'restored'
    for path in (state, recovery, restored):
        path.mkdir(mode=0o700)
    backup(engine.db, baseline)
    backup(baseline, state / 'gtd-ai.sqlite')
    workspaces.copy_register(engine.root / 'recovery/erasure.sqlite', recovery / 'erasure.sqlite')
    workspaces.command(image, directory, 'manifest', ['--database', '/rehearsal/baseline.sqlite', '--output', '/rehearsal/baseline.json'])
    workspaces.command(image, directory, 'review-migrate', ['--database', '/rehearsal/state/gtd-ai.sqlite', '--baseline', '/rehearsal/baseline.json', '--register', '/rehearsal/recovery/erasure.sqlite', '--output', '/rehearsal/migration.json'])
    workspaces.boot(image, state, recovery, record['actor'], True)
    workspaces.compare_original(baseline, state / 'gtd-ai.sqlite')
    record['candidate_schema'] = fingerprint(state / 'gtd-ai.sqlite')
    if record['candidate_schema'] == record['schema']:
        raise RuntimeError('Review migration did not change schema')
    backup(baseline, restored / 'gtd-ai.sqlite')
    workspaces.boot(record.get('previous_image_id', record['previous_image']), restored, recovery, record['actor'], True)
    workspaces.compare_original(baseline, restored / 'gtd-ai.sqlite')
    if fingerprint(restored / 'gtd-ai.sqlite') != record['schema']:
        raise RuntimeError('Matching prior image changed restored schema')
    record['review'] = engine.review
    record['review_rehearsal'] = {'immutable_baseline': True, 'original_values': True, 'candidate_restart': True, 'prior_image_restart': True, 'network': 'none', 'guard_replacements': 'exact committed migration SQL'}

def migrate_closed(engine, record, path):
    directory = path.parent.resolve()
    backup(engine.db, directory / 'baseline.sqlite')
    workspaces.command(record['image'], directory, 'manifest', ['--database', '/rehearsal/baseline.sqlite', '--output', '/rehearsal/baseline.json'])
    workspaces.command(record['image'], directory, 'review-migrate', ['--database', '/rehearsal/state/gtd-ai.sqlite', '--baseline', '/rehearsal/baseline.json', '--register', '/rehearsal/recovery/erasure.sqlite', '--output', '/rehearsal/migration.json'], state=engine.db.parent, recovery=engine.root / 'recovery')
