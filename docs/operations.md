# Routine operations

Run commands from `/Users/titocr/code/infrastructure` unless a section says otherwise.

## Read current state

```sh
git status --short
docker compose config
docker compose ps
docker compose images
```

The Git worktree should be clean during ordinary operation. A dirty tree means configuration or documentation may not match the recorded revision.

Repository hygiene monitoring is separate from application health monitoring, backups, and CI. See [Repository hygiene monitoring](repository-monitoring.md) for its Studio-local Git checks and Discord alerts.

## Build and update this manual

Edit the Markdown under `docs/`, then run:

```sh
docker compose build infrastructure-guide
docker compose up -d infrastructure-guide
docker compose ps
curl --fail --show-error http://127.0.0.1:8088/
```

The build runs `mkdocs build --strict`; broken internal links, invalid navigation, or documentation warnings fail the image build. Commit the source, not generated HTML.

## Logs, restart, and recovery

```sh
docker compose logs --tail=100 infrastructure-guide
docker compose restart infrastructure-guide
docker compose ps
curl --fail --show-error http://127.0.0.1:8088/
```

The service uses `restart: unless-stopped`. OrbStack is configured to start at login. After a host restart, confirm OrbStack is running and repeat the state and health checks.

Stop and start without removing the service:

```sh
docker compose stop infrastructure-guide
docker compose start infrastructure-guide
```

Remove only the running Compose resources, while retaining source and the local image:

```sh
docker compose down
```

Recreate them with `docker compose up -d`.

## Safe image updates

Base images are digest-pinned in `Dockerfile.guide`, and MkDocs is version-pinned in `requirements-docs.txt`. To update:

1. Identify the intended upstream release and digest.
2. Change one dependency deliberately.
3. Rebuild and verify health, navigation, logs, and restart.
4. Review and commit the exact source change.

Do not use an unattended updater for this service. Its Watchtower label is intentionally disabled.

## Operating an application service

Every added application needs a short runbook containing:

- source repository and tested commit;
- Compose service and image identity;
- local health and user endpoint;
- persistent host and container paths;
- secret source without secret values;
- backup command, resulting artifact, integrity check, and restore test;
- start, stop, restart, update, and log commands;
- exposure route and authentication boundary;
- migration gate;
- rollback trigger and exact procedure; and
- last verification date.

Before an update, confirm a clean infrastructure repository, current backup, free disk space, current health, and a known rollback image/configuration. Afterward, check application health, a real user flow, logs, restart, persistence, and Git cleanliness.

Documentation is part of the operation. Update the inventory, runtime contract reference, verification date, and changed commands in the same commit as the service definition.
