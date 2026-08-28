# Mac Studio infrastructure

Repository-owned configuration and operating notes for containerized applications on the Mac Studio.

The first milestone is intentionally small: OrbStack provides the Docker engine and Compose tooling, and a local-only Nginx container proves image pulls, networking, health checks, and restart behavior. It is not exposed to the LAN or internet.

## Prerequisites

- Apple Silicon Mac Studio
- Homebrew
- OrbStack configured to start at login

## Smoke test

Copy `.env.example` to `.env` only if you want to change the default port. Then run:

```sh
docker compose config
docker compose pull
docker compose up -d
docker compose ps
curl --fail --show-error http://127.0.0.1:8088/
```

Stop the service without deleting its Compose definition:

```sh
docker compose down
```

See [docs/operations.md](docs/operations.md) for routine operation and recovery notes.

## Conventions

- Compose configuration and documentation belong in Git.
- Secrets belong in an ignored `.env` file or a dedicated secret store, never in Git.
- Stateful application data belongs under `/Users/titocr/container-data/<service>`, not in this checkout.
- Host ports default to `127.0.0.1`; broader exposure must be an explicit, documented decision.
- Images are pinned to tested digests. Updates are reviewed and verified before the digest changes.
- Automatic container replacement is disabled unless a service receives an explicit, documented exception.

