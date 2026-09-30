# Shared Discord notifications

Infrastructure owns the Mac Studio sender at
`/Users/titocr/code/infrastructure/scripts/send-discord-notification.py`.
It is an on-demand command, with no daemon, listener or schedule. Multiple local
projects can call it as the same macOS user. Verified **2026-09-29**: Discord
accepted a generic operational test sent directly from the Studio, using the
existing Mini monitoring destination. The owner confirmed seeing the test message
in Discord on **2026-09-29**.

## Calling interface

Send plain operational text on stdin:

```sh
printf '%s' 'Example service: maintenance completed. No action required.' | \
  /Users/titocr/code/infrastructure/scripts/send-discord-notification.py
```

Requires Python 3 and macOS `/usr/bin/curl`. Exit 0 means Discord accepted the
request; 1 means delivery failed or is unconfirmed; 2 means invalid input or
private configuration. Stderr reports only a status or sanitized failure category.
Messages must contain 1–2000 UTF-16 code units. Mentions are disabled.
Never send health measurements, personal records, filenames containing private
information, credentials or raw application logs. Callers own alert thresholds,
deduplication and whether to retry.

One attempt uses a five-second connection timeout, a 15-second transfer deadline
and an 18-second outer deadline. There are no automatic retries, redirects,
proxy use or durable queue. HTTP 429 is reported as failure; retry later, not in
a tight loop. A timeout can occur after acceptance, so retrying may duplicate a
message. Concurrent callers have independent attempts; this is not a rate limiter.

## Credentials and recovery

Private settings: `~/.config/infrastructure/discord.json`, owned by the invoking
user, mode 600. Its sole required field is `webhook_url`, an HTTPS Discord webhook.
The sender rejects symlinks, insecure modes and non-Discord endpoints. It passes
credentials and content through stdin to curl, never command arguments or logs.

To provision or rotate, use a trusted local editor to save the webhook from your
password manager into that JSON field. Keep the parent directory mode 700 and the
file mode 600. Never paste the webhook into shell history, Git, tickets or this
manual. The initial Studio credential was transferred privately from the existing
Mini settings; those settings were not changed. Rotating that shared webhook can
affect both hosts and other consumers.

If delivery fails, check the private file's existence and permissions, then the
reported status: 401/403/404 usually require credential/destination review; 429
requires waiting; transport errors require connectivity checks. Run a generic test
only when intended, as it sends a real message. Recovery requires this repository,
Python, curl and the private credential. Credential backup coverage is unverified;
recover through the password manager or provision a replacement webhook.

## Consumers

The device collector in `/Users/titocr/code/cpap-monitor/scripts/collect_devices.py`
tries this sender first, then retains its previous Mini SSH fallback. The collector
owns the three-consecutive-failure threshold, suppression and quiet handling of
expected ring timeouts. Its hourly Codex heartbeat and collection behavior are
unchanged. See its owning repository's `docs/device-collection.md`.

Repository monitoring still uses its existing separate sender and private settings;
it has not been migrated. New consumers should use the shared command above.
