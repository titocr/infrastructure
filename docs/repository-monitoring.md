# Repository hygiene monitoring

The Mac Studio checks the direct child repositories in `/Users/titocr/code` for forgotten Git work. It is deliberately read-only apart from refreshing remote-tracking references during its daily `git fetch --prune`: it never commits, pulls, pushes, stashes, cleans, or changes branches.

## Current state and ownership

Verified **2026-09-21**: all three `com.titocr.repository-monitor.*` jobs are loaded
in the user launchd domain, idle between runs, and each reports last exit code 0.
The owning repository is `/Users/titocr/code/infrastructure`; there is no web UI.
Scan runs at login/every four hours, daily digest at 09:00, weekly summary Saturday
09:15 local time. This refresh did not send a test notification.

Private settings are `~/.config/repository-monitoring/monitoring.env`; state and
snapshots live under `~/Library/Application Support/Repository Monitoring/`.
Scripts are in Git; private settings/state backup coverage was not verified.
If scheduling disappears, inspect the three jobs and retained plists first:

```sh
launchctl print gui/$(id -u)/com.titocr.repository-monitor.scan
launchctl print gui/$(id -u)/com.titocr.repository-monitor.daily
launchctl print gui/$(id -u)/com.titocr.repository-monitor.weekly
```

For authorized recovery, rerun the installer below with existing private settings.
It reloads jobs and may trigger the login scan; do not reinstall merely to inspect.
Retain state to preserve notification continuity. Check logs locally for failures.

## Install

Store the existing Media center Discord webhook from 1Password in a Studio-local settings file. Do not copy the settings file from the Mini and do not commit it.

```sh
mkdir -p ~/.config/repository-monitoring
cp config/repository-monitoring.env.example ~/.config/repository-monitoring/monitoring.env
chmod 600 ~/.config/repository-monitoring/monitoring.env
# Edit monitoring.env and set DISCORD_WEBHOOK_URL.
./scripts/install-repository-monitor.sh
```

The installer creates three user LaunchAgents:

- a scan at login and every four hours;
- a daily unresolved-conditions digest at 09:00; and
- a weekly all-repositories summary on Saturday at 09:15.

Logs are under `~/Library/Logs/repository-monitoring/`. Current state and the machine-readable snapshot are stored under `~/Library/Application Support/Repository Monitoring/` with mode 600.

## What alerts mean

The monitor identifies uncommitted tracked changes, untracked files, branch commits ahead of an upstream, branches behind or diverged from an upstream, missing upstreams, and Git or fetch failures. A condition must persist for 24 hours before it first appears in the daily digest. The digest repeats once per day until resolved; a recovery notification is sent only for a previously alerted condition.

The weekly summary always lists every discovered repository, including clean ones. A failed fetch is reported separately and does not make cached ahead/behind information appear current.

Changing the number of files in an existing dirty working tree does not reset its 24-hour clock.

## Inspect and remove

Run a non-notifying scan directly:

```sh
./scripts/check-repositories.py
jq . "$HOME/Library/Application Support/Repository Monitoring/current.json"
```

To remove scheduled jobs, unload the three `com.titocr.repository-monitor.*` LaunchAgents with `launchctl bootout`, then delete their plist files if no longer wanted. The monitor does not remove its state or logs automatically; retain them for diagnosis or delete them manually when intentional.
