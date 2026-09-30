#!/usr/bin/env python3
"""Send one operational message from stdin. No queue or automatic retries."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

CONFIG = Path.home() / '.config/infrastructure/discord.json'
WEBHOOK = re.compile(r'https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_.-]+\Z')


def load_webhook(path=CONFIG):
    # Reject symlinks and other users' readable credentials.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW)) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('credentials must be an owned regular file with mode 600')
        value = json.load(stream)['webhook_url']
    if not isinstance(value, str) or not WEBHOOK.fullmatch(value):
        raise ValueError('invalid Discord webhook URL')
    return value


def deliver(webhook, message, run=subprocess.run):
    # curl config is passed through stdin: no webhook or content in process args.
    payload = json.dumps({'content': message, 'allowed_mentions': {'parse': []}}, ensure_ascii=True)
    config = 'url = ' + json.dumps(webhook) + '\ndata = ' + json.dumps(payload) + '\n'
    try:
        result = run(['/usr/bin/curl', '--disable', '--config', '-', '--silent',
                      '--proto', '=https', '--noproxy', '*', '--connect-timeout', '5',
                      '--max-time', '15', '--header', 'Content-Type: application/json',
                      '--output', '/dev/null', '--write-out', '%{http_code}'],
                     input=config, text=True, capture_output=True, timeout=18)
    except (OSError, subprocess.TimeoutExpired):
        return 1, 'transport unavailable or timed out; delivery unconfirmed'
    if result.returncode:
        return 1, f'transport failure (curl exit {result.returncode}); delivery unconfirmed'
    if result.stdout.strip() in ('200', '204'):
        return 0, 'Discord accepted notification'
    status = result.stdout.strip()
    status = status if re.fullmatch(r'[0-9]{3}', status) else 'unknown'
    return 1, f'Discord HTTP {status}; not delivered (no automatic retry)'


def main():
    if len(sys.argv) != 1:
        print('Usage: printf "%s" "operational message" | send-discord-notification.py', file=sys.stderr)
        return 2
    message = sys.stdin.read(2001)
    if not message.strip() or len(message.encode('utf-16-le')) // 2 > 2000:
        print('Notification must contain 1–2000 UTF-16 code units.', file=sys.stderr)
        return 2
    try:
        webhook = load_webhook()
    except (OSError, ValueError, KeyError, TypeError):
        print('Discord credentials missing or invalid: ~/.config/infrastructure/discord.json (owned, mode 600).', file=sys.stderr)
        return 2
    code, detail = deliver(webhook, message)
    print(detail, file=sys.stderr)
    return code


if __name__ == '__main__':
    sys.exit(main())
