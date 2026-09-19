# OSCAR network-disabled diagnostic: execution review

Status: execution was authorized and attempted; **stopped at startup validation**.
See [live diagnostic record](cpap-monitor-diagnostic-20260919.md). Relay/browser
execution was not reached; do not rerun the current image without review.

The following implementation and planned procedure are retained for reference.
Verified synthetically: 2026-09-19, Node 24.18.0. No host listener, Docker command,
GUI candidate, network probe, Wi-Fi change or real card access was performed.

## Reviewed artifacts

- Application helper implementation: `27c2d794a42faeaa9e83033c3a06759e4a3c0afd`.
- Application contract and `docs/networkless-security-review.md` in
  `/Users/titocr/code/cpap-monitor`.
- Image/index inspect ID:
  `sha256:b52d47004e4a15029d3ff2080112471cc6cabf24b01e695e30d127537064deab`.
- ARM64 platform manifest:
  `sha256:c7642632b0a7d6a3f8a01d12fb08547021535e75a5b75ed4ec9b2b3a9d0adb0e`.
- Image config digest:
  `sha256:3f432e574e838c11b19ffe8d978c921ecc28fc6407c7e20212590d4f2d314ff1`.
- Host implementation: `scripts/cpap-relay.mjs`, `scripts/run-cpap-relay.mjs`.
- Candidate definition: `compose.cpap-monitor-candidate.yaml`.
- Host tests: `tests/cpap-relay.test.mjs` (29 passing).

Infrastructure checked the helper source against the fixed protocol and confirmed
the new raw scan hash
`4e9cc8763ac65a9e3291b6ee1a48a164fc38b97a9973b16942f429f0bce6e663`.
Comparison of advisory/package/version/severity tuples found zero added or removed
findings relative to the reviewed Selkies image. Seven critical and 295 high
occurrences remain: the previous narrow empty-data analysis applies, not a claim
of clean security or data-bearing suitability. No runtime helper behavior has
been independently demonstrated.

## Implemented controls and limits

The container has network_mode none, no published ports or sidecars, only fresh
private config and an empty read-only card directory, manual startup,
no-new-privileges, 2 CPUs/2 GiB and 256 MiB shared memory. It retains inherited
/init and explicitly disables the unused GUI features named in the contract.

The host relay binds only IPv4 127.0.0.1:8089. It uses Node's HTTP server and client
parsers over fixed exec byte streams; WebSockets become raw streams only after
validating both browser request and backend handshake. It rejects cross-origin
and rebinding requests, strips forwarding/hop-by-hop headers, disables HTTP
pooling, and never follows redirects or browser-supplied targets.

Limits: 32 client sockets, 16 backend slots including processes still draining,
16 KiB headers, 100 headers, 1 MiB request body, 64 KiB transport high-water marks,
4 KiB discarded stderr, 10-second header/backend startup, 30-second ordinary
request and 15-minute session. Application helper lifetime is 16 minutes. The
relay's Docker metadata commands have separate output/time bounds. Measure total
host relay/CLI memory during execution; the container memory limit does not cap it.

The exact full container ID, image identities, revision, mounts, environment,
privileges and resource settings are checked before listening and each backend
exec. Docker event monitoring and one-second inspection detect lifecycle/identity
changes. Restarting the same container invalidates the session. There is no
automatic reconnect/restart.

The fixed invocation is Docker exec with verified numeric abc UID/GID, workdir /,
and `/usr/bin/python3 -I /usr/local/bin/cpap-stream-bridge`. Numeric identity is
deliberate: preflight must establish that it is abc's actual identity. No shell,
TTY, user command, dynamic backend port or host socket mount is used.

On exit, timeout or safety failure the relay stops accepting connections, closes
streams, stops **only the dedicated candidate**, checks that it stopped and reaps
CLI processes. Remote-helper cleanup is not inferred merely from killing Docker
CLI. Ordinary request cleanup sends stdin EOF, allows five seconds to drain, then
TERM and another five seconds before KILL/failed-cleanup session stop. The helper
itself has a ten-second EOF drain bound. Cleanup uncertainty is a failure.
Only an un-escalated CLI close with exit code zero and no signal counts as normal
completion. Nonzero/signaled exits or any drain escalation force session shutdown
and candidate stop, even if the local CLI closes before the second timer.

## Synthetic evidence

Run from Infrastructure without Docker or a listening socket:

```sh
node --test tests/cpap-relay.test.mjs
node --check scripts/cpap-relay.mjs
node --check scripts/run-cpap-relay.mjs
```

The tests inject memory Duplex streams into Node's actual HTTP parser, fake
container inspection and lifecycle hooks. They cover malformed/oversized headers,
duplicate Host, cross-origin requests, CONNECT, framing ambiguity, HTTP pipelining,
body limits, valid/invalid WebSocket upgrade and both already-read byte buffers,
forwarding-header removal, disconnects, binary transfer/backpressure, concurrency
caps, backend failure, restart/monitor loss, deadlines, bounded stderr and cleanup
failure. They do not exercise Docker, the GUI, actual DNS/LAN routes or a browser.

## Ordered execution after explicit approval

1. Recheck host/service baseline, free 8089, current image/scan evidence, disk and
   memory. Record relevant healthy endpoints and network/DNS state without edits.
2. Create a fresh private run root under
   `/Users/titocr/container-data/cpap-monitor-candidate/<run-id>/` with mode 0700
   config and empty card directories. No imported data or existing profiles.
   Populate only the CPAP_CANDIDATE_* variables required by Compose. Record them
   privately and verify `docker compose ... config` has no ports/extra mounts.
3. Pin CPAP_CANDIDATE_IMAGE to the reviewed index identity above. Start only the
   diagnostic service using this dedicated Compose file and profile. Do not use
   the old bridge plan or change globals to make startup succeed.
4. Before starting the relay, inspect actual processes, abc identity, immutable
   helper permissions, runtime architecture/version, hardening and network
   namespace. Require only loopback, no routable address and no forwarded ports.
   Check OrbStack domain/HTTPS proxy paths and other unintended ingress. A named
   none network metadata entry is allowed; routable endpoints are not.
5. Reconcile the image/index/platform/config relationship. Record actual
   container.Image as `expected.imageId` ONLY after proving it belongs to the
   reviewed immutable artifact. Record Config.Image as `expected.sourceImageId`
   (the exact Compose index reference). Never replace checks with a mutable tag
   or accept an unexplained digest mismatch.
6. Create a mode-0600, current-user-owned, nonsymlink `run.json` in the private
   run root. Fields: `dockerPath` (verified absolute executable), `endpoint`
   (`unix:///Users/titocr/.orbstack/run/docker.sock`), and `expected` containing
   `containerId`, `sourceImageId`, `imageId`, `revision`, `uid`, `gid`, `configPath`,
   `cardPath`. UID/GID must match the current host owner and verified abc identity.
   Inspect the private config before invocation. The relay requires private
   canonical bind directories and an executable not writable by group/others.
7. Manually launch with reviewed Node 24 and
   `scripts/run-cpap-relay.mjs --approved-config /absolute/private/run.json`.
   This flag selects the reviewed run record; it is not itself user approval.
   Confirm only 127.0.0.1:8089 is listening, then evaluate empty GUI rendering and
   WebSocket interaction. No real profile/import, printing, remote links or files.
8. Test Studio LAN/IPv6 and OrbStack alternate paths and candidate egress, plus
   an unrelated disposable probe if needed. Off-host clients require existing
   authorization; explicitly record unavailable checks. Stop immediately on
   unintended exposure, unexpected input requirement or existing-service impact.
9. Stop via Ctrl-C/SIGTERM or session deadline. Verify relay port is closed,
   candidate and exec helpers stopped, original services unchanged; preserve the
   private empty config/evidence and image. Cleanup/deletion is separate.

## Failure recovery

If the relay cannot confirm cleanup, use only the dedicated project/file:

```sh
docker compose -f compose.cpap-monitor-candidate.yaml -p cpap-monitor-candidate --profile diagnostic stop -t 60 oscar
```

Verify the exact candidate ID is stopped and port 8089 is closed. Do not perform
broad process-name kills, restart OrbStack, stop other projects or delete data.
No fallback to a bridge, sidecar, extra published port or global networking edit.

## Remaining execution checks and approval

Live Docker stream behavior, GUI rendering, actual effective users, immutable
image identity mapping, network-none behavior under OrbStack, external exposure
and aggregate resources are unverified. The Compose file has been reviewed as
source but not passed to Docker Compose during this no-Docker implementation step.
Record the host implementation Git revision before execution.

Suggested approval after reviewing these artifacts:

> Approve one bounded empty-data OSCAR diagnostic using the reviewed network-none
> container and temporary macOS 127.0.0.1:8089 relay with fixed Docker exec transport.
> Allow the dedicated private candidate storage and diagnostic probes. Stop the
> relay, helpers and dedicated candidate on completion or unintended exposure.
> No real card data, Wi-Fi/global-network changes, existing-service changes,
> production, downloader, schedules or persistent host agent.

This is the changed architecture requested by the application design. The earlier
bridge-diagnostic authorization does not authorize this host relay.
