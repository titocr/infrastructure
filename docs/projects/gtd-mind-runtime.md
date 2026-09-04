# GTD Mind container operations

Last verified: **2026-09-04**.  
Application revision: `edeee2ab870a1d6abc69440b2b98fb30a1f62d16`.  
Runtime contract: `/Users/titocr/code/gtd-ai/docs/container-runtime-contract.md`.

## Current production

Production runs image `gtd-mind:edeee2ab870a` on host-loopback port 3000 with authoritative state
under `/Users/titocr/container-data/gtd-mind`. The image is healthy, local-owner authentication and
the compiled UI work, SQLite integrity and record counts match the native source snapshot, Todoist
polling is healthy, and a controlled restart completed with graceful `SIGTERM`. The former
LaunchAgent is unloaded, Tailscale Serve has no configuration, and the protected environment and
migration-state files have mode `0600`.

The isolated candidate is stopped after successful cutover; its data and image remain available.
Cutover disables the former LaunchAgent in the per-user launchd domain so it cannot race OrbStack
for port 3000 after login. Rollback explicitly re-enables the job before starting it.

The first post-cutover reboot prompted for one-time OrbStack setup and exposed that the former
LaunchAgent had only been unloaded for the current login session. OrbStack then passed `orbctl
doctor`, reported `app.start_at_login: true`, and restarted the production container. The native
job was persistently disabled, the container was restarted to reclaim port 3000, and health,
local-owner authentication, UI, SQLite integrity, record count, and a fresh Todoist poll passed.
A second reboot is still required to prove that the corrected path is fully unattended.

## Tested candidate

The isolated ARM64 candidate uses image `gtd-mind:edeee2ab870a`, host-loopback port 3100, and
`/Users/titocr/container-data/gtd-mind-candidate/edeee2ab870a`. It has no Todoist credentials.
Its verified local image ID is
`sha256:dcaa40d0904276ede44b6a1f97f89bbdd238142c5cfd93e7c4146b8bb439beb3`.
Build, health, local session, UI, wrong-origin denial, synthetic mutation, restart persistence, and
SQLite backup/integrity/restore checks passed before cutover.

Inspect it with:

```sh
GTD_MIND_IMAGE=gtd-mind:edeee2ab870a \
GTD_MIND_CANDIDATE_DATA_ROOT=/Users/titocr/container-data/gtd-mind-candidate/edeee2ab870a \
docker compose -f compose.gtd-mind.yaml --profile candidate ps
curl --fail --show-error http://127.0.0.1:3100/api/health/ready
curl --fail --show-error http://127.0.0.1:3100/api/session
```

Rebuild and re-exercise it with:

```sh
scripts/gtd-mind-container.sh candidate edeee2ab870a1d6abc69440b2b98fb30a1f62d16
```

## Guarded cutover

The first container production release is Mac-local. The cutover command refuses an untested
image, unhealthy candidate or native service, missing private configuration, corrupt database, or
migration-count difference. It saves Tailscale Serve configuration, removes the route, stops the
LaunchAgent, makes and verifies a SQLite backup, restores a separate container database, starts the
container, and verifies health, session, UI, sync health, restart, and integrity.

Run read-only preflight at any time:

```sh
scripts/gtd-mind-container.sh preflight edeee2ab870a1d6abc69440b2b98fb30a1f62d16
```

After explicit production approval only:

```sh
scripts/gtd-mind-container.sh cutover \
  edeee2ab870a1d6abc69440b2b98fb30a1f62d16 \
  --approve-production-cutover
```

Once approved, the command runs without intermediate prompts and automatically restores the
native service and saved Tailscale configuration if a required cutover check fails.

## Rollback

The native database is left untouched at cutover. A later explicit rollback first creates and
checks a backup of the container database, transfers current data back to the native path, starts
the LaunchAgent, recreates the verified `tailscale serve --bg 3000` route, and checks readiness:

```sh
scripts/gtd-mind-container.sh rollback --approve-production-rollback
```

Do not remove the native releases, LaunchAgent, native database, pre-cutover backup, or saved
Tailscale configuration until a separate cleanup decision.
