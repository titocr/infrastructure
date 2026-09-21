# Mac Mini media center

The household media platform runs on the **Mac Mini**, not on this Mac Studio.
Its owning repository is `/Users/titocr/code/media-center-25` on the Studio and
`/Users/titocr/media-center-25` on the Mini. That repository owns the Compose
definition, native-service installers, monitoring, backup workflows and detailed
runbooks. This page records the host boundary and the minimum information needed
to find, assess and recover the other machine.

Verified **2026-09-21** with a read-only SSH inspection of `bluetardis`. The Mini
reported macOS 26.6.2 (25G83), a clean repository at `d8017aa`, Docker context
`orbstack`, the external data volume mounted, 21 running production containers,
native Jellyfin and Caddy processes, and an encrypted restic backup completed that
day. This is dated evidence, not a live health display.

## Responsibility boundary

| Concern | Owner and location |
| --- | --- |
| Development, review and Git publication | Studio checkout `/Users/titocr/code/media-center-25` |
| Production configuration checkout | Mini checkout `/Users/titocr/media-center-25` |
| Compose and operational scripts | `media-center-25/docker/docker-compose.yml` and `scripts/` |
| Live settings, credentials, application databases and logs | Mini `/Users/titocr/media-server`; never Git |
| Large media and download data | External MediaDrive mounted at `/Users/titocr/media-server/data` |
| Native Jellyfin state | Mini `~/Library/Application Support/Jellyfin` |
| Host-level orientation | This page; detailed operation remains in `media-center-25` |

The Studio is not a standby media server. Git contains desired configuration and
procedures, not sufficient runtime state for recovery. Do not copy secrets or
application databases into this infrastructure repository.

## What runs on the Mini

- Native Jellyfin is the primary player; native Caddy terminates public HTTPS and
  preserves client addresses. Plex remains available as a fallback.
- The Compose project provides Seerr, Sonarr, Radarr, Prowlarr, Jackett, SABnzbd,
  qBittorrent behind Gluetun, books/audiobooks services, operator tools, the private
  Purple Tardis portal and the status dashboard.
- Per-user LaunchAgents mount/check the data volume, start the container stack in
  bounded phases, run monitoring and status history, update media DNS, perform the
  nightly backup, and maintain native Caddy and Jellyfin.

The Mini has 8 GB of memory. A simultaneous cold start previously caused severe
memory compression and delayed or unhealthy services. Use
`scripts/start-container-stack.sh`; it verifies the MediaDrive and OrbStack, then
starts foundation, household and book/request workloads in phases.

## Access boundary

Household access is limited to watching and requesting. Public entry points are
`https://watch.purpletardis.xyz` for Jellyfin and
`https://request.purpletardis.xyz` for Seerr. Cloudflare provides DNS only; native
Caddy on the Mini handles TLS. Operator interfaces, SSH and the rest of the Arr and
download stack remain private.

The private portal is `https://bluetardis.tailb98869.ts.net/`. The owner-only
status dashboard is `https://bluetardis.tailb98869.ts.net:8443/`. Both are
Tailscale Serve proxies to loopback-only containers. Keep the public
`purpletardis.xyz` website and GTD Mind separate from the media services.

## Read-only checks

From the Studio, use the configured SSH alias:

```sh
ssh bluetardis 'cd ~/media-center-25 && ./scripts/status.sh'
```

For a development-to-production checkpoint, run from the Studio checkout:

```sh
cd /Users/titocr/code/media-center-25
./scripts/checkpoint.sh
```

The first command inspects the live Mini. The second also checks the Studio
checkout, Compose rendering, SSH and live stack status. Avoid printing rendered
environment configuration because it contains secrets.

## Startup and recovery order

After a Mini restart, the owner must log in because OrbStack, Tailscale and the
media services use the logged-in user session.

1. Confirm MediaDrive is mounted at `/Users/titocr/media-server/data`.
2. Confirm OrbStack is running and `docker context show` returns `orbstack`.
3. From `~/media-center-25`, run `./scripts/start-container-stack.sh` if automatic
   recovery did not complete. Do not replace it with an all-at-once Compose start.
4. Confirm native Jellyfin and `com.titocr.media-center.caddy` are running.
5. Run `./scripts/check-media-access.py` and `./scripts/status.sh`.
6. Verify Watch and Request from a real client. For remote acceptance, use cellular
   with Wi-Fi disabled; follow the owning runbook before changing exposure.

Do not restore over live state or start deleting Docker data when a service fails.
Identify whether the fault is the external mount, container engine, one application,
native proxy, DNS or access path first.

## Backup and restore boundary

The nightly workflow creates a consistent application-state staging copy and sends
encrypted, deduplicated restic data to Google Drive through rclone. It checks remote
repository access before stopping anything, defers when Jellyfin playback is active,
and records status under `/Users/titocr/media-server/logs`. Retention is 7 daily,
4 weekly and 12 monthly snapshots.

The protected minimum includes the live environment, application configuration,
native Jellyfin state, Compose files and the Calibre library. Ordinary movies, TV
and download payloads are excluded. The restic password and rclone OAuth material
are separate recovery requirements; GitHub alone cannot restore the server.

Use `notes/backup-and-secrets.md` and `scripts/restic-restore-check.sh` in the media
repository for authoritative scope and isolated restore verification. Never test a
restore over production storage.

## Authoritative runbooks

Open these in `/Users/titocr/code/media-center-25`:

| Need | Source |
| --- | --- |
| Day-to-day commands and service URLs | `notes/operations.md` |
| Update, reboot and post-login acceptance | `notes/update-reboot-runbook.md` |
| Public and household access controls | `notes/family-media-access.md` |
| Backup scope, credentials and restore model | `notes/backup-and-secrets.md` |
| OrbStack rollback history | `notes/docker-desktop-retirement.md` |
| Open media-platform work | `notes/todos.md` |

Before changing the Mini, inspect both Studio and Mini Git status. Preserve any
unrelated live changes, make a fresh verified backup for stateful work, use the
project's guarded scripts, and validate both local health and the intended user path.
