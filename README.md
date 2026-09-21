# Mac Studio infrastructure

Hardware inventory, workloads and operating procedures for the Mac Studio M2 Max.
The [manual](http://127.0.0.1:8088/) is built from [docs/index.md](docs/index.md).
Source and service definitions are durable; the website is a generated local copy.

## Read without the website

- [Hardware and capacity](docs/host-baseline.md)
- [Services and ownership](docs/services.md)
- [Host recovery](docs/recovery.md)
- [Deployment and recovery reference](docs/deployment-reference.md)
- [Backup coverage](docs/backups.md)
- [Outstanding work](docs/outstanding.md)

If the website is down, open this checkout at `/Users/titocr/code/infrastructure`.
Confirm OrbStack is running, then inspect only the guide:

```sh
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail 100 infrastructure-guide
```

If stopped, run `docker compose -f compose.yaml start infrastructure-guide`.
If missing or stale, publish from the reviewed source:

```sh
python3 scripts/publish-manual.py
```

Requires Git, Python 3.10+, Docker/Compose from OrbStack, and network access for
uncached build dependencies. The publisher builds and recreates only the guide,
checks metadata and preserves the previous image for recovery. It does not commit
or push. Verify freshness without changes:

```sh
python3 scripts/publish-manual.py --check
```

See [manual operation](docs/manual.md) for provenance, custom ports and rollback.
Plain `docker compose ps` here covers only the guide; use the service runbooks for
application-specific commands. Do not recreate GTD without its active overlays.

Keep secrets outside Git and build contexts. See [responsibilities](docs/concepts.md)
and the [runtime contract](docs/runtime-contract.md) before adding a service.
