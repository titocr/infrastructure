# Routine operations

## Inspect the whole host

```sh
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
docker stats --no-stream
df -h /System/Volumes/Data
launchctl print gui/$(id -u)/com.titocr.options-finder
launchctl print gui/$(id -u)/com.titocr.repository-monitor.scan
launchctl print-disabled gui/$(id -u)
```

These checks have different meanings: Docker health is service-defined, a running
process may still fail a user flow, and scheduled jobs may be idle. Compare with
the dated [inventory](services.md), not an assumption that every retained job runs.

## Inspect one Compose project

From `/Users/titocr/code/infrastructure`, plain `docker compose ps` selects the
manual's default Compose project only. It does not inventory GTD, OSCAR or Home
Assistant. Use each [service runbook](services.md) for the right file, private
settings, overlays and directory. Avoid printing rendered application environment
configuration because it can expose secrets.

## Change and verify

Before a service update, establish the exact image/configuration, consistent backup,
rollback constraints and expected interruption. Use the owning guarded workflow.
Afterward verify readiness, authentication, a real user flow and persistent state as
appropriate. Update the runbook's facts and evidence date in the same change.

Use [manual publication](manual.md) for documentation changes. Git status records
source changes; build metadata identifies what the website actually serves.
Repository hygiene alerts are [separate](repository-monitoring.md) from application
health, backups and CI. Recovery starts with [host recovery](recovery.md).
