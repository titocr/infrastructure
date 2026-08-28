# Operations

## Runtime

OrbStack supplies the Docker engine, Docker CLI, and Docker Compose. It should start at macOS login so services using `restart: unless-stopped` return with the runtime.

The initial Mac Studio bootstrap installed OrbStack with Homebrew and set these host-level defaults:

```sh
orb config set app.start_at_login true
orb config set docker.expose_ports_to_lan false
```

OrbStack placed its CLI tools under `~/.orbstack/bin`, which was not on the existing shell `PATH`. The `docker` and `docker-credential-osxkeychain` tools are therefore linked into `/opt/homebrew/bin`. `orb doctor` may continue to recommend adding the whole OrbStack directory to `PATH` for optional tools such as `kubectl`; Kubernetes is not enabled for this project.

Check the runtime before changing a stack:

```sh
orb status
docker context show
docker info
docker compose config
```

## Start and verify

```sh
docker compose pull
docker compose up -d
docker compose ps
curl --fail --show-error http://127.0.0.1:8088/
```

A successful HTTP response is necessary but not sufficient: `docker compose ps` must also report the service as healthy.

## Stop and recover

Stop this stack:

```sh
docker compose down
```

If the Docker engine is unavailable, start OrbStack and wait for `docker info` to succeed before bringing the stack up again:

```sh
orb start
docker info
docker compose up -d
```

## Image updates

Do not track mutable image tags during normal operation. To update a service:

1. Review the upstream release notes and architecture support.
2. Pull the intended image and resolve its repository digest.
3. Change the digest in `compose.yaml`.
4. Run `docker compose config`, `docker compose up -d`, and the service health checks.
5. Commit only after verification succeeds.

Automatic updates are not enabled. The smoke service also carries an explicit opt-out label as defense in depth if an updater is introduced later.

## Stateful services

Before adding a stateful service, document:

- Its bind mounts or named volumes.
- Backup contents, frequency, and destination.
- A tested restore procedure.
- Upgrade and rollback steps.
- Local, tailnet, or public network exposure.

Use `/Users/titocr/container-data/<service>` for host-managed persistent data. Confirm backup access before stopping a service for maintenance.
