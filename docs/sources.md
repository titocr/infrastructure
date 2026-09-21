# Application documentation

This manual describes the Mac and the services it hosts: access, startup, storage,
health, backups and host recovery. Application behavior, feature rollout, migration
design and release evidence belong in the owning project.

The locations below are local files to open in the named repository. Their contents
are not copied into this website.

## GTD Mind

Repository: `/Users/titocr/code/gtd-ai`.

| Need | Document in that repository |
| --- | --- |
| Application release prerequisites and verification | `docs/operations/container-release.md` |
| Runtime requirements | `docs/container-runtime-contract.md` |
| Delegated MCP setup and connection | `docs/operations/delegated-capture.md` |
| Application rollout and recovery evidence | `docs/operations/multi-user-rollout.md` |

[Host operations](projects/gtd-mind-runtime.md) and
[tunnel operation](projects/gtd-mind-access.md) remain in this manual.
The [host deployment reference](deployment-reference.md) owns operator preparation,
configuration mapping and recovery using deployment records.

## OSCAR

Repository: `/Users/titocr/code/cpap-monitor`.

| Need | Document in that repository |
| --- | --- |
| Application setup and operation | `docs/standard-runtime.md` |
| Runtime requirements | `docs/container-runtime-contract.md` |
| Application security review | `docs/selkies-security-review.md` |
| Earlier diagnostic evidence | `docs/diagnostic-20260919.md` |

[Host operation and storage](projects/cpap-monitor-runtime.md) remain here.

## Home Assistant and Options Finder

Use `/Users/titocr/code/thinq-interface/README.md` for Home Assistant project
setup, and `/Users/titocr/code/options-finder/README.md` for Options Finder.
Their [host inventory](services.md) records how those services run on this Mac.

## Household media

Media operations belong to `/Users/titocr/code/media-center-25`, including
`notes/family-media-access.md`, `notes/update-reboot-runbook.md` and
`notes/media-access-history.md`. The [Mac Mini host page](projects/media-center.md)
records the cross-host boundary, startup order, backup model and entry points. A
local checkout does not make those media services workloads on the Studio.
