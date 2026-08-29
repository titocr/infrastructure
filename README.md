# Mac Studio infrastructure

Repository-owned configuration and operating notes for containerized applications on the Mac Studio.

OrbStack provides the Docker engine and Compose tooling. A local-only container builds the Markdown manual with MkDocs and serves the generated site with Nginx. It is not exposed to the LAN or internet.

## Prerequisites

- Apple Silicon Mac Studio
- Homebrew
- OrbStack configured to start at login

## Infrastructure Guide

The manual is available on the Mac Studio at [http://127.0.0.1:8088/](http://127.0.0.1:8088/). Its Markdown source is under [`docs/`](docs/index.md); `mkdocs.yml` defines the navigation.

Copy `.env.example` to `.env` only to change the default port. Build and start it with:

```sh
docker compose config
docker compose up --build -d
docker compose ps
curl --fail --show-error http://127.0.0.1:8088/
```

Stop the service without deleting its Compose definition:

```sh
docker compose down
```

See [Routine operations](docs/operations.md) for updates, verification, recovery, and troubleshooting.

## Conventions

- Compose configuration and documentation belong in Git.
- Secrets belong in an ignored `.env` file or a dedicated secret store, never in Git.
- Stateful application data belongs under `/Users/titocr/container-data/<service>`, not in this checkout.
- Host ports default to `127.0.0.1`; broader exposure must be an explicit, documented decision.
- Images are pinned to tested digests. Updates are reviewed and verified before the digest changes.
- Automatic container replacement is disabled unless a service receives an explicit, documented exception.
