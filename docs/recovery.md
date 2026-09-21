# Host recovery

Use the service runbooks for changes. The checks below are read-only unless a step
explicitly starts or restarts a service. They do not need the website to be available;
source is under `/Users/titocr/code/infrastructure/docs`.

## After restart or loss of all container services

1. Log into the Mac. OrbStack is configured to launch at login. Confirm it opens
   and `docker version` reaches the engine; use `orb doctor` if it does not.
2. Run `docker ps -a`. GTD, its connector, Home Assistant and the guide use
   `unless-stopped`; deliberately stopped containers may remain stopped.
3. OSCAR is manual-start. Start it through its [own Compose prefix](projects/cpap-monitor-runtime.md)
   only when needed. Leave historical candidates stopped.
4. Check [native jobs](services.md). Options Finder should be loaded and running;
   repository-monitor jobs may be idle between their scheduled invocations.
   The old GTD LaunchAgent must stay disabled.
5. Verify local readiness, then user-facing access. Check GTD through Cloudflare,
   Home Assistant in the browser and OSCAR authentication/profile when started.
   Preserve credentials and data if a check fails.

## Manual unavailable

From the infrastructure repository:

```sh
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail 100 infrastructure-guide
```

If stopped, use `docker compose -f compose.yaml start infrastructure-guide`.
If missing or outdated, follow [publication](manual.md). The README has the same
offline entry point. Do not stop all Docker services to repair this website.

## One service fails

Identify its owner and exact container/job in the [inventory](services.md). Inspect
its state and local logs before restarting. Use that service's recovery instructions:
[GTD](projects/gtd-mind-runtime.md), [access](projects/gtd-mind-access.md),
[OSCAR](projects/cpap-monitor-runtime.md), [Home Assistant](projects/home-assistant.md),
[Options Finder](projects/options-finder.md), or [monitoring](repository-monitoring.md).
For a failed deployment, use the [deployment reference](deployment-reference.md)
to identify its record and recovery path. If a loopback check fails only inside a restricted task, verify from a host terminal
before changing networking.

## Disk pressure or loss of the machine

Check `df -h /System/Volumes/Data` and `docker system df`. Do not prune containers,
volumes, images or private rehearsal directories indiscriminately: some are recovery
artifacts or contain real data. Review the owning service and retention policy first.

For host loss, recover source, matching images, private configuration and consistent
application data together. [Backup coverage](backups.md) records what is and is not
established. A complete bare-machine restoration has not been verified; retained
local files alone cannot recover a failed or lost disk.
