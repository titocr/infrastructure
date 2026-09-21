#!/usr/bin/env python3
"""Build/publish only the local manual, or --check its served source fingerprint."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SERVICE = 'infrastructure-guide'
IMAGE = 'studio-infrastructure-guide:local'
SINGLE_FILES = (
    'Dockerfile.guide', 'requirements-docs.txt', 'mkdocs.yml', 'compose.yaml',
    'config/nginx-guide.conf', 'scripts/manual_build.py', 'scripts/publish-manual.py',
)


def run(*args, capture=True):
    result = subprocess.run(args, cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def source_files(root=ROOT):
    files = [root / name for name in SINGLE_FILES]
    files += [p for p in (root / 'docs').rglob('*') if p.is_file() and p.name != '.DS_Store']
    if any(p.is_symlink() for p in files):
        raise RuntimeError('Manual build inputs must not be symlinks')
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def fingerprint(root=ROOT):
    digest = hashlib.sha256()
    for path in source_files(root):
        data = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode() + b'\0')
        digest.update(str(len(data)).encode() + b'\0' + data)
    return digest.hexdigest()


def metadata(root=ROOT):
    paths = [*SINGLE_FILES, 'docs']
    return {
        'source_revision': run('git', 'rev-parse', 'HEAD'),
        'source_sha256': fingerprint(root),
        'source_modified': bool(run('git', 'status', '--porcelain', '--', *paths)),
        'built_at_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def verify_metadata(actual, expected, exact=False):
    keys = expected.keys() if exact else ('source_revision', 'source_sha256', 'source_modified')
    mismatch = [key for key in keys if actual.get(key) != expected[key]]
    if mismatch:
        raise RuntimeError('Published manual is stale or mismatched: ' + ', '.join(mismatch))


def read_metadata(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url + 'build-info.json', timeout=10) as response:
        return json.load(response)


def other_containers():
    ids = run('docker', 'ps', '-aq').split()
    if not ids:
        return {}
    # Keep only nonsecret identity and state. Never emit full Docker inspect output.
    rows = json.loads(run('docker', 'inspect', *ids))
    return {row['Name']: {'id': row['Id'], 'image': row['Image'],
                         'started': row['State']['StartedAt'], 'status': row['State']['Status']}
            for row in rows if row['Config'].get('Labels', {}).get('com.docker.compose.service') != SERVICE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only comparison of source and served build')
    args = parser.parse_args()
    compose = ['docker', 'compose', '-f', str(ROOT / 'compose.yaml')]
    config = json.loads(run(*compose, 'config', '--format', 'json'))
    service = config['services'][SERVICE]
    ports = service.get('ports', [])
    if (service.get('image') != IMAGE or len(ports) != 1
            or ports[0].get('host_ip') != '127.0.0.1' or ports[0].get('target') != 80):
        raise RuntimeError('Guide must use its expected image and one IPv4 loopback port')
    url = f"http://127.0.0.1:{int(ports[0]['published'])}/"
    expected = metadata()
    if args.check:
        verify_metadata(read_metadata(url), expected)
        print(f'Manual source matches {url} ({expected["source_sha256"][:12]})')
        return
    before = other_containers()
    old = run(*compose, 'ps', '-q', SERVICE)
    old_image = run('docker', 'inspect', old, '--format', '{{.Image}}') if old else None
    if old_image:
        print('Previous guide image (retained for recovery): ' + old_image, flush=True)
    # Immutable, allowlisted context excludes .env, .git and other private host files.
    with tempfile.TemporaryDirectory(prefix='studio-manual-') as name:
        context = Path(name)
        for source in source_files():
            target = context / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        if fingerprint(context) != expected['source_sha256']:
            raise RuntimeError('Source changed while preparing build')
        command = ['docker', 'build', '-t', IMAGE]
        for key, value in expected.items():
            arg = {'source_revision': 'GUIDE_SOURCE_REVISION', 'source_sha256': 'GUIDE_SOURCE_SHA256',
                   'source_modified': 'GUIDE_SOURCE_MODIFIED', 'built_at_utc': 'GUIDE_BUILD_TIME'}[key]
            command += ['--build-arg', f'{arg}={str(value).lower() if isinstance(value, bool) else value}']
        run(*command, '-f', str(context / 'Dockerfile.guide'), str(context), capture=False)
    verify_metadata(metadata(), expected)  # Refuse to deploy if inputs changed during build.
    try:
        run(*compose, 'up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60', SERVICE,
            capture=False)
        verify_metadata(read_metadata(url), expected, exact=True)
        current = run(*compose, 'ps', '-q', SERVICE)
        bindings = json.loads(run('docker', 'inspect', current, '--format', '{{json .HostConfig.PortBindings}}'))
        if bindings != {'80/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(ports[0]['published'])}]}:
            raise RuntimeError('Unexpected live manual binding')
    except Exception:
        if old_image:
            print('Restoring previous guide image after failed publication.', flush=True)
            run('docker', 'tag', old_image, IMAGE)
            run(*compose, 'up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60', SERVICE,
                capture=False)
        raise
    finally:
        if other_containers() != before:
            raise RuntimeError('Another container changed during publication; inspect before claiming success')
    print(f'Published and verified {url} at {expected["source_revision"]} '
          f'(source SHA-256 {expected["source_sha256"]}). Other containers unchanged.')


if __name__ == '__main__':
    main()
