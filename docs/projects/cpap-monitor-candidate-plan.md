# OSCAR isolated candidate plan

Status: conditional empty-data execution authorized; preflight blocked; no candidate started.

The revised network-none/exec-relay implementation is now prepared with synthetic
tests. See [its runbook](cpap-monitor-networkless-runbook.md). The old bridge
preflight remains blocked; the revised host-relay scope awaits separate approval.

## Replacement review, 2026-09-19

This section supersedes the legacy image references below. Implementation
`b55951c332bf95c90d79afa0169ba9f931832bde` and handoff/review
`294d7396c0eb8243a1959cc1a11094a187cfa601` replace the rejected Kasm image.
The exact Selkies image is
`sha256:8a0036e1a75f1d7c938c53293fd26cb913bcbe5792dee808a94ca7690030885c`.
The application Dockerfile/container files match the implementation. Retained
image metadata matches that ID, ARM64 and revision. Raw Trivy report SHA256
`f0c2df5769a3f05e3033f6c6b95b7ff759d96fe1cd926da41f678632748179c0`
matches the checked-in summary. No live image execution was used to verify these.

Infrastructure agrees with the narrow security assessment for an empty-data
diagnostic only, conditional on the documented mitigations. The seven critical
occurrences concern libunbound, libxml2, kernel headers, OpenSSH client and
Xwayland; their relevant workloads/inputs are excluded by this test. This is not
general security acceptance, and 295 high occurrences remain. Runtime processes,
listener inventory, Xvfb arguments and effective hardening must still be checked.
The original image-age objection is addressed by the maintained September 2026
Selkies base; the exposure gate remains unresolved.

**Preflight blocker:** no supported per-container automatic-proxy disable control
was established from OrbStack's official domain and HTTPS documentation. The
documented `dev.orbstack.http-port` selects a backend port and skips detection;
it does not disable the proxy or direct-IP access. Disabling CA injection is also
not a proxy-disable control. Do not invent labels or point at an unused port and
call that containment. Global bridge/domain settings remain outside authorization.

Sources:
- https://docs.orbstack.dev/docker/domains
- https://docs.orbstack.dev/features/https
- https://docs.orbstack.dev/docker/network

The new source binds the Selkies backend to localhost (8082, optional 8083) and
disables X TCP. Nginx still listens on container 3000/3001. Thus fixing the former
6901 backend does not eliminate automatic proxy/direct-IP entry to the desktop.
The existing internal-bridge proposal does not establish that isolation.

Required next design work: either produce authoritative evidence of a supported
per-container control plus a direct-IP containment mechanism, or revise the
application/Infrastructure transport boundary. A concrete alternative to design
and review is a GUI container with `network_mode: none` and an HTTP/WebSocket Unix
socket, served by a narrowly scoped host relay bound to 127.0.0.1:8089. That would
need application socket support, macOS/OrbStack socket-mount compatibility tests,
relay lifecycle/security review, and authorization for the changed design before
execution. It is not implemented or claimed working. A networked proxy sidecar
alone would reintroduce the same direct-IP problem.

Do not start the existing bridged candidate while the preflight condition remains
unmet. No repeated authorization is needed for the unchanged diagnostic scope;
this is a technical blocker, not missing consent. Real data remains excluded.

## Original plan (historical image references superseded above)

Reviewed: 2026-09-19 UTC.
Application repository: `/Users/titocr/code/cpap-monitor`.
Implementation: `8d9dfb7eddfcede2091eb76fbf5d72f469de32c7`.
Handoff documentation: `953aa1b` (subsequent documentation-only commit).
Contract: application `docs/container-runtime-contract.md`, still draft.

## Review decision

Source matches the named implementation. The current Dockerfile, container files,
and runtime contract have no differences from that commit. It installs the
checksum-verified ARM64 OSCAR 2.0.1 package, disables nested Docker, and includes
no downloader. This review has not independently executed the built image.

The build is suitable for further review, not yet accepted for a data-bearing
candidate. Two gates precede real card data: GUI-base security review and verified
network containment. Neither a pinned digest nor a loopback publish proves these.

## Gate 1: image review without application startup

After execution authorization, inspect the existing local image and capture its
full image ID, linux/arm64 platform, revision label, build history and package
inventory. Require revision 8d9dfb7eddfcede2091eb76fbf5d72f469de32c7; do not use
current HEAD as the revision argument, since HEAD includes the later handoff.
If a rebuild is required, use an exported clean tree of the implementation commit
and that exact APP_REVISION. Preserve the resulting image; apt inputs are not
snapshot-pinned, so rebuilding need not reproduce identical bytes.

Review the July 2025 base's maintenance status and scan the final image using a
current vulnerability database. Record scanner/version/database date, findings,
and applicability to GUI, web transport and root initialization. Review bundled
components as well as OS packages; an OS-only scan is insufficient. A clean scan
does not prove the base is maintained. If maintenance cannot be established or
material exploitable findings remain, request a maintained compatible GUI base
from the application owner and review its new implementation commit before run.
Do not silently change the pinned base or upgrade packages in a running container.

## Gate 2: empty-data exposure diagnostic

Only after Gate 1 passes, prepare Infrastructure-owned
`compose.cpap-monitor-candidate.yaml` with these settings:

| Setting | Proposed value |
| --- | --- |
| Compose project / service | cpap-monitor-candidate / oscar |
| Image | Exact inspected image ID, never a mutable tag alone |
| Platform | linux/arm64 |
| Restart | no; manual start, no auto-heal |
| CPU / memory | 2 CPUs / 2 GiB |
| Shared memory | Initially 256 MiB, measure and record against overall memory use |
| Stop signal / grace | SIGTERM / 60 seconds; close OSCAR normally first |
| Logs | json-file, max-size 10m, max-file 3 |
| Host endpoint | 127.0.0.1:8089 to container 3000, recheck availability |
| Network | Dedicated internal bridge, no shared application networks |
| Environment | START_DOCKER=false; TZ=America/Los_Angeles; verified PUID/PGID |
| Privileges | No privileged mode, host network, host socket, devices or home mount |
| Labels | Watchtower disabled; disable OrbStack automatic proxy for this service using verified supported configuration |

Do not blindly impose an unprivileged Compose user, read-only root filesystem or
drop every capability: inherited root initialization may need specific operations.
Inspect and minimize required privileges, test no-new-privileges, and record any
exceptions. Do not override the inherited /init without application review.

Use new private directories under
`/Users/titocr/container-data/cpap-monitor-candidate/<run-id>/`:
`config` mounted at `/config`, and initially empty `card` at `/sdcard:ro`.
Resolve the host user's UID/GID rather than assuming Linux defaults. Require
pre-existing bind sources (disable automatic directory creation). Mount no real
health data in this phase. An internal bridge is a proposed egress constraint,
not proof that OrbStack direct ingress is blocked.

Before launch, record current listeners, container status, relevant local health
checks, routing/DNS and OrbStack exposure settings. Do not change global settings.
Inventory every listening socket and its process/user after launch. Test:

- Intended loopback browser access and health probe.
- Container IP access from macOS to 3000, 3001, 6901 and every discovered listener.
- Automatic OrbStack HTTP/HTTPS domain/proxy paths and explicit alternate ports.
- Studio Ethernet/Wi-Fi addresses, including IPv6 where applicable; validate
  off-host LAN access from an available independently authorized test client.
- Access from a disposable probe container on a separate network, without
  attaching or modifying existing application containers.
- Runtime outbound connectivity and denied egress assumptions.

The existing image is documented to bind unauthenticated transport on 6901.
Expect possible direct access during this explicitly authorized empty-data test;
stop immediately when demonstrated and preserve the result. Never label it
localhost-only merely because 8089 is bound to 127.0.0.1. EXPOSE metadata,
unpublished ports and disabling the automatic domain proxy are not firewalls.

If 6901 is reachable, return an application requirement to bind that backend only
to container loopback or disable it while preserving the browser proxy. Review
3001 and all other listeners too. If direct access to 3000 remains, strict
localhost-only acceptance also fails: prepare an enforceable per-candidate
ingress design and obtain approval before changing that design. Authentication
can reduce risk but is not equivalent to eliminating direct access. Any proposal
to accept authenticated direct local paths must be an explicit scope change, not
an implicit exception. Password changes also require adapting the health probe.

No global OrbStack, macOS firewall, LAN, Tailscale or Wi-Fi modifications are
authorized by this plan. If containment needs them, stop and return the concrete
change for review. Do not mount real data until all required exposure tests pass.

## Gate 3: real-data evaluation, separately authorized

Obtain the user's manually prepared card-copy path and permission to use it.
Never read the original card or an existing OSCAR profile implicitly. Copy into
the private candidate card directory, preserve names/bytes/tree, and mount it
read-only. Keep manifests and medical details outside Git and ordinary logs.

Create a fresh OSCAR profile under /config. Verify native execution, About version,
effective process users, actual SQL/database paths, health semantics and GUI
rendering. Import the copy, inspect detailed charts, repeat import and check for
duplicates. Measure startup, idle, import and chart CPU/memory/shared-memory use.
Change a harmless preference, close/stop/restart and verify persistence. Exercise
OSCAR integrity checks and record any durable writes outside /config.

Close OSCAR, stop the container, then archive the entire config and card copy with
ownership and matching image identity. Hash/check the archive and restore into
a second private root. Run the same image against the restored root sequentially
on the same endpoint, with the original stopped; verify charts, preferences and
integrity. Define encryption, off-host destination, schedule and retention before
production acceptance. A local candidate archive is not a production backup plan.

## Stop, rollback and records

After Compose exists, commands run only against the dedicated file/project:

```sh
docker compose -f compose.cpap-monitor-candidate.yaml -p cpap-monitor-candidate stop -t 60 oscar
docker compose -f compose.cpap-monitor-candidate.yaml -p cpap-monitor-candidate down
```

Never add --volumes or delete bind data/images. Stop on exposure, integrity,
persistence, shutdown, resource or existing-service regressions. Retain image,
private data and evidence; verify the original services. There is no production
cutover to reverse and no authorized Wi-Fi change to undo. Cleanup is separate.

Record Compose/config revision, exact image ID and application commit, security
review, port, mounts, ownership, tests, resource measurements, stop outcome and
unresolved blockers. Update the application contract with observed facts through
the application owner. Add the eventual runbook to MkDocs navigation and update
host inventory with candidate status; do not claim deployment from this plan.

## Requested authorization

Authorize Gate 1 image/security inspection and, only if it passes, Gate 2's
temporary empty-data diagnostic candidate on the Mac Studio. This includes writing
the dedicated Compose/runbook, creating isolated private directories and network,
using at most 2 CPUs/2 GiB, publishing only 127.0.0.1:8089, and running disposable
network probes. The known 6901 exposure may be observable during this diagnostic;
stop on discovery. Preserve existing services and all global networking settings.
Stop before mounting real card data, changing application code, production use,
Wi-Fi association, installing a downloader or enabling any schedule.

This authorization boundary comes from the user's current request and the
application handoff. Gate 3 needs a later authorization after the security and
exposure findings are resolved and a card-copy path is supplied.
