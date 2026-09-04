# Host baseline and inventory

This page records a verified snapshot. Re-run the checks before a deployment or capacity decision.

## Host baseline

Last verified: **2026-09-04**.

| Item                     | Verified value            |
| ------------------------ | ------------------------- |
| Host                     | `Mac-Studio.attlocal.net` |
| Architecture             | Apple Silicon `arm64`     |
| macOS                    | 26.6.2 (build 25G83)      |
| OrbStack                 | 2.2.3                     |
| Docker engine/client     | 29.4.0                    |
| Docker Compose           | 5.1.2                     |
| OrbStack at login        | Enabled                   |
| Docker LAN port exposure | Disabled                  |
| Kubernetes               | Disabled                  |
| OrbStack allocation      | 12 CPUs, 16 GiB memory    |

OrbStack settings describe an upper allocation, not a promise that every service may consume it. Review CPU history, memory pressure, free disk space, backup freshness, and application-specific needs before adding a significant workload.

## Managed services

| Service               | Source                     | Listener         | Data                 | Exposure        | State at verification |
| --------------------- | -------------------------- | ---------------- | -------------------- | --------------- | --------------------- |
| Infrastructure manual | This repository            | `127.0.0.1:8088` | None                 | Mac Studio only | Healthy               |
| GTD Mind production   | `gtd-ai` at `edeee2ab870a` | `127.0.0.1:3000` | Authoritative SQLite | Mac Studio only | Healthy               |

The tested GTD Mind candidate is stopped but its data and image are retained. See its
[container operations](projects/gtd-mind-runtime.md).

## Host conventions

- Bind published ports to `127.0.0.1` unless broader exposure is explicitly approved and documented.
- Put stateful application data under `/Users/titocr/container-data/<service>`.
- Keep configuration and documentation in Git.
- Keep secrets out of Git and images. Document their source and required permissions, not their values.
- Pin tested base images to digests and review updates.
- Do not enable automatic container replacement by default.
- Give candidates distinct ports and data paths; never “test” against the only production copy.

## Verification commands

```sh
sw_vers
uname -m
orb version
docker version
docker compose version
docker compose ps
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
```

Check the manual directly:

```sh
curl --fail --show-error http://127.0.0.1:8088/
```

If these results differ materially, update this page in the same change that adopts the new baseline.
