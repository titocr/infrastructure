#!/usr/bin/env python3
"""Review and enforce the 30-day bound for explicitly inventoried recovery roots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time

MAX_AGE = 30 * 86400

def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()

def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.new')
    with temporary.open('x') as target:
        os.chmod(temporary, 0o600)
        json.dump(value, target, sort_keys=True)
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)

def inventory(roots, protected, ledger, now=None):
    now = time.time() if now is None else now
    protected = {p.resolve() for p in protected}
    # SQLite sidecars are part of each protected live store.
    protected |= {Path(str(p) + suffix) for p in list(protected) for suffix in ('-wal', '-shm', '-journal')}
    protected_inodes = {(p.stat().st_dev, p.stat().st_ino) for p in protected if p.exists()}
    previous = ledger.get('copies', {})
    copies = {}
    for root in roots:
        if root.is_symlink():
            raise RuntimeError('Recovery inventory refuses symlinks')
        root = root.resolve()
        if root.stat().st_mode & 0o077:
            raise RuntimeError('Recovery roots require owner-only permissions')
        if not root.is_dir():
            raise RuntimeError('A configured recovery root is missing')
        for path in root.rglob('*'):
            if path.is_symlink():
                raise RuntimeError('Recovery inventory refuses symlinks')
            if not path.is_file() or path.resolve() in protected:
                continue
            metadata = path.stat()
            if (metadata.st_dev, metadata.st_ino) in protected_inodes:
                continue
            # Explicit recovery-only roots: unknown names and formats can contain
            # personal data too. Do not infer safe retention from an extension.
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise RuntimeError('A recovery copy is not protected with owner-only permissions')
            checksum = digest(path)
            prior_dates = [entry['created_at'] for entry in previous.values() if entry['sha256'] == checksum]
            created = min([getattr(metadata, 'st_birthtime', metadata.st_mtime), metadata.st_mtime, now] + prior_dates)
            copies[str(path.resolve())] = {'sha256': checksum, 'size': metadata.st_size, 'created_at': created,
                                          'expires_at': created + MAX_AGE}
    return {'version': 1, 'roots': [str(p.resolve()) for p in roots], 'protected': sorted(map(str, protected)),
            'reviewed_at': now, 'copies': copies,
            'expired': sorted(path for path, entry in copies.items() if entry['expires_at'] <= now)}

def enforce(review, now=None):
    now = time.time() if now is None else now
    if review.get('version') != 1 or now < review['reviewed_at']:
        raise RuntimeError('Invalid retention review')
    refreshed = inventory([Path(p) for p in review['roots']], [Path(p) for p in review['protected']], review, now)
    # New copies are harmless but require a fresh review: never silently widen deletion.
    if refreshed['copies'] != review['copies'] or refreshed['expired'] != review['expired']:
        raise RuntimeError('Recovery inventory changed; create a fresh review')
    for name in review['expired']:
        path = Path(name)
        if path.is_symlink() or digest(path) != review['copies'][name]['sha256']:
            raise RuntimeError('A reviewed recovery copy changed')
        path.unlink()
    return len(review['expired'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['review', 'enforce'])
    parser.add_argument('--configuration', type=Path)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--review-sha256')
    args = parser.parse_args()
    os.umask(0o077)
    if args.operation == 'review':
        if not args.configuration or not args.ledger or args.apply:
            parser.error('Review requires explicit configuration and ledger, without --apply')
        config = json.loads(args.configuration.read_text())
        prior = json.loads(args.ledger.read_text()) if args.ledger.exists() else {}
        report = inventory([Path(p) for p in config['roots']], [Path(config['live_database']), Path(config['erasure_register']), args.ledger, args.report, args.configuration] + [Path(p) for p in config.get('protected', [])], prior)
        write_private(args.ledger, report)
        write_private(args.report, report)
        print(json.dumps({'copies': len(report['copies']), 'expired': len(report['expired']), 'deleted': 0}))
    else:
        if not args.apply or not args.review_sha256 or digest(args.report) != args.review_sha256:
            parser.error('Enforcement requires explicit --apply approval after reviewing the private report')
        print(json.dumps({'deleted': enforce(json.loads(args.report.read_text()))}))

if __name__ == '__main__':
    main()
