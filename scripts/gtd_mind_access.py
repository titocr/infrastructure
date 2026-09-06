#!/usr/bin/env python3
"""Start the GTD connector only after verifying the protected origin."""
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request


def validate_origin(info):
    env = dict(value.split('=', 1) for value in info['Config']['Env'])
    if env.get('AUTH_MODE') != 'cloudflare':
        raise RuntimeError('Refusing public connector for non-Cloudflare authentication')
    if env.get('APP_ORIGIN') != 'https://gtd.purpletardis.xyz':
        raise RuntimeError('Unexpected production origin')
    if env.get('CLOUDFLARE_OWNER_EMAIL', '').lower() != 'titocruz@gmail.com':
        raise RuntimeError('Unexpected allowed owner')
    if info['HostConfig']['PortBindings'] != {'3000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '3000'}]}:
        raise RuntimeError('Unexpected origin port exposure')
    if info['State'].get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('Production is not healthy')


def main():
    root = Path(__file__).resolve().parents[1]
    info = json.loads(subprocess.check_output(['docker', 'inspect', 'gtd-mind-production-1']))[0]
    validate_origin(info)
    for route in ('/', '/api/session', '/api/sync-health', '/api/inbox'):
        try:
            urllib.request.urlopen('http://127.0.0.1:3000' + route, timeout=3).close()
        except urllib.error.HTTPError as error:
            if error.code == 401:
                continue
        raise RuntimeError('Origin does not reject unauthenticated requests')
    token = Path(os.environ['GTD_MIND_TUNNEL_TOKEN_FILE'])
    if token.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError('Tunnel token must have mode 0600')
    if token.stat().st_uid != os.getuid():
        raise RuntimeError('Tunnel token must belong to the current operator')
    image = os.environ['GTD_MIND_CLOUDFLARED_IMAGE']
    if not image.startswith('cloudflare/cloudflared@sha256:'):
        raise RuntimeError('Use an official cloudflared image pinned by digest')
    subprocess.run(['docker', 'compose', '-f', str(root / 'compose.gtd-mind.yaml'),
                    '-f', str(root / 'compose.gtd-mind-access.yaml'), '--profile', 'access',
                    'up', '-d', '--no-deps', 'cloudflared'], check=True,
                   env=dict(os.environ, GTD_MIND_CONNECTOR_UID=str(os.getuid()),
                            GTD_MIND_CONNECTOR_GID=str(os.getgid())))


if __name__ == '__main__':
    main()
