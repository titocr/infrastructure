# Troubleshooting

## Docker commands fail

Confirm OrbStack is open and healthy:

```sh
orb doctor
docker version
```

If `docker` is missing, check whether `/opt/homebrew/bin/docker` still points to OrbStack's command wrapper. Do not install a second Docker engine until the existing configuration is understood.

## The manual is unavailable

```sh
docker compose ps
docker compose logs --tail=100 infrastructure-guide
curl --verbose http://127.0.0.1:8088/
```

If stopped, run `docker compose start infrastructure-guide`. If missing or stale,
run `python3 scripts/publish-manual.py`. If unhealthy, read the first build or runtime error rather than repeatedly restarting it.

## Port 8088 is occupied

Identify the listener before changing anything:

```sh
lsof -nP -iTCP:8088 -sTCP:LISTEN
```

If it is an intended service, create `.env` from `.env.example`, choose a free loopback port with `GUIDE_PORT`, recreate the manual, and update its documented URL. Do not bind to all interfaces as a shortcut.

## The documentation build fails

```sh
python3 scripts/publish-manual.py
```

MkDocs strict mode reports the source page and problem. Correct navigation, links, Markdown, or configuration in the repository; do not edit generated HTML inside a container.

## A local health request fails only inside Codex

Some restricted task environments cannot reach host loopback even while the service is healthy. Check `docker compose ps`, run the request from a host-authorized terminal, and distinguish a sandbox restriction from an application failure before changing configuration.

## A candidate cannot start

Check image architecture, occupied ports, required settings and secrets, data-path ownership, application logs, health semantics, and dependency reachability—in that order. Do not point the candidate at production data to make it start.

## The repository is dirty

```sh
git status --short
git diff
```

Treat unknown changes as user work. Determine their owner and purpose; do not discard them. Stage only files belonging to the current change.

## Website differs from source

```sh
python3 scripts/publish-manual.py --check
```

A mismatch means the served revision or build inputs differ. Review source, then
use `python3 scripts/publish-manual.py`. A recent build still does not verify
service facts; check those separately.

## Recorded facts appear stale

Re-run the verification commands in [Host baseline and inventory](host-baseline.md), inspect actual service definitions, and update the snapshot date and values. Runtime evidence and Git history outrank an old prose claim.
