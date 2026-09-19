# Network-disabled OSCAR relay design review

Status: implementation prepared and 29 in-memory host tests pass; execution
not authorized. Reviewed 2026-09-19. No relay, GUI or probe was started.

Current artifacts and execution steps: [Network-disabled diagnostic runbook](cpap-monitor-networkless-runbook.md).

Application proposal: `/Users/titocr/code/cpap-monitor/docs/networkless-candidate-design.md`.
This is a revised design, not permission to resume the earlier bridge candidate.

## Feasibility and decision

The proposed transport is plausible and preferable to assuming cross-kernel Unix
socket sharing. Docker documents that network none creates only loopback, while
exec starts a process through Docker's control plane. Thus an exec helper can
connect to container 127.0.0.1:3000 without a container network attachment.
Actual OrbStack behavior and interactive latency remain untested.

Sources: https://docs.docker.com/engine/network/drivers/none/ and
https://docs.docker.com/reference/cli/docker/container/exec/ .

Proceed with application helper and Infrastructure relay implementation for
review. Do not run either against Docker or bind the relay before the changed
execution scope is approved. Synthetic unit testing should use injected in-memory
transports/fake process adapters, not a real Docker connection or live host relay.

## Required corrections and security details

1. **Network inspection:** require NetworkMode=none, no published port bindings,
   no routable addresses and only loopback interfaces. Docker may report a named
   `none` entry in NetworkSettings.Networks; do not require the JSON map itself
   to be empty. Reject bridge/host/container namespace sharing, extra attachments,
   privileged mode, host namespace modes, devices and unexpected mounts. Inspect
   actual OrbStack domain/proxy paths before opening the browser. No disabling
   proxy label is necessary if the no-address isolation is demonstrated.
2. **Transport adapter:** use a maintained HTTP server AND client parser. Never
   validate the first request then blindly tunnel the remaining TCP connection:
   keep-alive/pipelined requests could bypass Host/Origin checks. Reconstruct every
   accepted HTTP request through the client parser over a custom Duplex backed by
   helper stdout/stdin. Initially use one backend exec per HTTP request, no pooling,
   and one persistent exec per accepted WebSocket. WebSocket upgrade occurs only
   after an upstream 101 with validated handshake; reject generic upgrades and
   CONNECT. Account for both parsers' already-read `head` bytes exactly once.
3. **Host/origin:** accept only exact authorities 127.0.0.1:8089 and localhost:8089,
   exactly one Host, origin-form request targets, no conflicting framing, and no
   credentials embedded in authority. Validate every supplied HTTP Origin too;
   reject null/cross-origin values, cross-site Fetch Metadata and cross-origin
   WebSockets. Require WebSocket Origin to equal the request's accepted origin.
   No CORS opt-in. Legacy requests with absent Origin/Fetch Metadata remain a
   limitation of the trusted-local-process model; do not claim authentication.
4. **Header handling:** discard untrusted Forwarded/X-Forwarded-* headers and
   connection-nominated hop-by-hop headers; regenerate framing and required
   WebSocket headers. Preserve the validated external Host/Origin consistently
   so Nginx/Selkies agree. Never follow backend redirects in the host process or
   fetch a URL supplied in a request. Do not rewrite arbitrary backend content.
5. **Docker authority:** relay is a trusted host process with access to the Docker
   daemon. Resolve/validate one absolute executable, fixed local OrbStack endpoint,
   full container ID and expected image/revision before binding. Explicitly select
   that local endpoint; a minimal environment alone does not prevent Docker config
   or context retargeting. No browser-controlled argv, environment, working directory,
   command, port or target; shell=false; no TTY. Helper runs as verified abc UID/GID
   with fixed working directory /, immutable executable outside /config and isolated
   interpreter imports (for Python, use isolated mode). Keep host Docker socket out
   of all candidate mounts.
6. **Lifecycle:** full container ID does not detect a restart of the same container.
   Capture StartedAt/restart count, observe Docker lifecycle events and revalidate
   before each exec. Stop on restart, exit, destroy, unexpected network attachment,
   identity drift or loss of monitoring; never reconnect automatically. External
   Docker administrators remain trusted; document the residual inspect/exec race.
7. **Cleanup:** killing the local docker CLI does not prove the remote exec process
   ended. The helper must exit on stdin EOF/transport failure and enforce a hard
   lifetime. Normal EOF should half-close its TCP write side and allow only a
   bounded response-drain interval. Relay closes stdin, waits, escalates local
   child termination and verifies helper exit. Stopping the dedicated candidate
   is the final cleanup if helper liveness cannot be established. Never use broad
   host process-name kills. Fail closed on parent death using helper deadlines.

## Proposed Infrastructure implementation

Files to prepare (not installed or launched):

- `scripts/cpap-relay.mjs`: Node HTTP/1.1 server, request-policy checks, HTTP client
  over exec Duplex, WebSocket upgrade, bounded lifecycle and shutdown.
- `tests/cpap-relay.test.mjs`: Node tests with injected fake transport/inspector;
  no binding or Docker daemon required for the initial suite.
- `compose.cpap-monitor-candidate.yaml`: exact newly reviewed image ID,
  network_mode none, no ports/networks, restart no, private fresh config and empty
  read-only card bind, no-new-privileges, inherited /init, 2 CPUs/2 GiB/256 MiB shm,
  bounded logs, explicit hardening environment and manual stop policy.
- A runbook and private run record with exact executable paths, image and source
  identity, mount paths, expected state, resource limits and stop commands.

Use an already installed supported Node release after inspection, not a silent
runtime installation. Keep helper path and protocol literal in the implementation.
Do not pass a user-provided command template. Never add a LaunchAgent or auto-start.

Proposed hard bounds for this short diagnostic:

| Resource | Limit |
| --- | --- |
| Listener | IPv4 127.0.0.1:8089 only; no reusePort |
| Client TCP connections | 32, including stalled/header-only sockets |
| Active backend execs | 16 total, including WebSockets; no unbounded waiting queue |
| Request/response headers | 16 KiB; strict parser; reject excessive header count |
| HTTP body | 1 MiB streamed maximum; larger need explicit review |
| Header completion | 10 seconds |
| Exec connect/response headers | 10 seconds |
| Ordinary request | 30-second total deadline |
| Stream buffers | 64 KiB high-water marks with backpressure; bound stderr separately |
| Desktop session | 15-minute hard deadline, then graceful stop; no respawn |
| Helper lifetime | 16-minute hard deadline, 10-second connect and EOF-drain deadlines |
| Shutdown | Stop accepting immediately; bounded 5-second child drain, then escalation |

Set HTTP request count per frontend connection to one initially to simplify
keep-alive and pipelining handling; additional requests must still be parsed and
rejected, never raw-forwarded. Do not impose short idle timeouts on the interactive
WebSocket; total session/helper deadlines bound abandoned sessions. Abort and
review if Selkies needs more connections or features. The 2-GiB container limit
does not cover host Node/docker CLI memory: measure and record aggregate host use.

## Application implementation contract

Application owns `/usr/local/bin/cpap-stream-bridge` (suggested fixed name), its
fixed interpreter invocation and focused tests. It accepts no target arguments,
connects only AF_INET 127.0.0.1:3000, bridges binary stdin/stdout with bounded
buffers and correct half-close/EOF, keeps stderr separate and bounded, and uses
nonzero exit status for failures. It must have no diagnostic banners on stdout.
No arbitrary file reads, command dispatch or environment-selected destinations.

Add hard lifecycle/connect/drain bounds as above; test truncation, partial writes,
binary bytes, backpressure in both directions, EOF, broken pipe, connect failure,
deadline and cleanup. Preserve graceful long-lived WebSocket operation until the
fixed session bound. Application updates its runtime contract, rebuilds and scans
the new immutable image. The previous scan/image ID is not acceptance of new bytes.

## Acceptance tests and authorized execution sequence

Before requesting execution, prepare and review both implementations and synthetic
test evidence: duplicate/invalid Host, wrong/null Origin, cross-site metadata,
absolute targets, CONNECT, invalid upgrades, malformed/ambiguous framing,
oversized headers/body, pipelining, failed/invalid upstream 101, response splitting,
head bytes, backpressure, resource caps, abrupt disconnect, stderr overflow,
daemon loss, same-ID restart, identity mismatch and orphan-helper cleanup.

After explicit authorization of this revised scope: refresh baseline and port
availability; start only the empty network-none GUI; verify isolation, listeners,
hardening and identity; launch temporary relay; test loopback HTTP/WebSocket and
empty GUI; test alternate OrbStack/LAN/IPv6 paths with no unapproved remote client;
verify no candidate egress; stop relay and candidate; verify zero helper processes,
closed port and original services. Record any tests that could not be performed.
Stop immediately on unintended exposure or host-service impact. No fallback to
bridge networking, sidecar, global changes or authentication exceptions.

## Approval scope to present when implementation is ready

Approve the reviewed network-none empty-data OSCAR candidate and temporary macOS
loopback relay using fixed Docker exec transport, for one bounded diagnostic
session. Permit only its private candidate directories, reviewed image, host
relay process and diagnostic checks; stop on unintended exposure and stop/reap
the relay/helpers and candidate at completion. No real card data, Wi-Fi changes,
global networking changes, existing-service modifications, production, downloader,
scheduled operation or persistent host agent.

Do not request approval yet: the helper and relay must first become concrete,
reviewable implementations with synthetic verification. The prior authorization
does not cover this changed host-relay architecture.
