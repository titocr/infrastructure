# OSCAR empty-data diagnostic — stopped at startup validation

Execution authorized by user and relayed from the application task. Ran on the
Mac Studio from **2026-09-19 06:18:10 to 06:18:49 UTC** (about 39 seconds).
Result: **not accepted; stopped before host relay or browser startup**.

## Exact candidate

- Infrastructure implementation: `8de966334be21fb955792baf1ec512d1155b7b7c`.
- Application implementation: `27c2d794a42faeaa9e83033c3a06759e4a3c0afd`.
- Image and actual container.Image:
  `sha256:b52d47004e4a15029d3ff2080112471cc6cabf24b01e695e30d127537064deab`.
- Config.Image also matched that exact Compose reference. Current Docker image
  store used the index identity directly; no config-digest substitution was needed.
- Container ID: `66add58d8829198bb8f25bf618a8dbc9bf67d07465cf2febaf80b56ad975a428`.
- Compose project/service: `cpap-monitor-candidate` / `oscar`.
- Private evidence and empty candidate state retained at
  `/Users/titocr/container-data/cpap-monitor-candidate/20260919T061700Z`.

Compose configuration passed inspection: network none, no published ports,
reviewed exact image, two bind mounts, 2 CPUs/2 GiB/256 MiB shared memory,
no-new-privileges and no automatic restart. An independent 15-minute stop guard
was active before startup; the diagnostic stopped early on the findings below.

## Live observations and blockers

The container had only `lo`, with 127.0.0.1 and ::1, and no IPv4 routes. Metadata
contained only the non-routable `none` network and empty host port bindings.
The helper was root-owned mode 0555. User abc resolved to UID 501/GID 20.
Installed OSCAR package was `2.0.1-Debian13`; the inspected image was ARM64.

Runtime behavior contradicted the reviewed application hardening assumptions:

1. `ss -lntup` showed the Selkies data service listening on **0.0.0.0:8082**,
   despite its process arguments containing `--addr=localhost --mode=websockets`.
   Nginx listened on IPv4/IPv6 wildcard ports 3000/3001, as expected. With only
   loopback present, no external ingress was demonstrated, but source arguments
   did not establish the promised backend binding.
2. Effective Selkies startup settings contained
   **`file_transfers: ['upload', 'download']`** despite
   `SELKIES_FILE_TRANSFERS=""`. Hiding the Files sidebar is not a substitute for
   disabling the capability. The narrow reviewed mitigation was therefore unmet.
3. Gamepad Unix sockets/objects initialized despite effective gamepad_enabled
   false. This does not prove gamepad forwarding was usable, but requires an
   application-side explanation or correction. Clipboard and sharing settings
   remained enabled; their suitability needs explicit review before browser use.
4. OSCAR20 was absent from the initial process snapshot and liveness probes
   returned exit 1. Startup was terminated early; this is an unresolved startup
   observation, not a definitive diagnosis of why OSCAR did not launch.

The observed Xvfb command used a single protocol screen with `-nolisten tcp`.
Logs reported sudo and terminal hardening. These successful observations do not
override the failed effective-runtime settings.

## Stop and final verification

No host relay was launched, so port 8089 was never opened. No browser, helper
transport, imported profile or real card file was used. Candidate card directory
remained empty. On discovering the mismatch, the stop guard was signaled and the
exact candidate was stopped with a 60-second grace period. Both stop operations
returned success; final state was exited, exit code 0, PID 0, OOMKilled false.
The guard process also exited. The stopped container, empty state and image are
retained for evidence; none are configured to restart automatically.

| Existing service/check | Before | After |
| --- | --- | --- |
| GTD Mind local HTTP root | 401 | 401 |
| Infrastructure guide HTTP root | 200 | 200 |
| Home Assistant HTTP root | 200 | 200 |
| Existing running container IDs | Four recorded | Same four |
| GTD Mind and guide health | Healthy | Healthy |
| Default route | Ethernet en0 | Exact output unchanged |
| DNS resolver configuration | Recorded | Exact output unchanged |
| Port 8089 listener | None | None |

No Wi-Fi, global network, existing service, production or scheduled-operation
changes were made. No candidate process remains running.

## Checks not reached

Automatic OrbStack domain/proxy probes, off-host LAN/IPv6 access tests, disposable
container ingress probes, live egress attempts, host-relay/Docker exec streaming,
browser GUI/WebSocket rendering, effective runtime resource measurements and
graceful in-application close were not reached. No successful result is inferred
for these. Real-data import/persistence/restore was outside the authorized scope.

## Required application follow-up

Correct or explain the actual Selkies bind behavior; enforce disabled file
transfers using a value/mechanism that the pinned runtime actually honors; assess
gamepad initialization and clipboard/sharing defaults; diagnose OSCAR autostart.
Update the runtime contract with observed behavior, rebuild and scan the new
immutable image, and return the named commit/image for review. Do not restart the
current candidate or silently relax containment/hardening to finish the test.

Application task received the findings and private evidence path. This authorized
diagnostic is complete with a failed startup gate; another execution must follow
review of the correction and an explicit scope decision.
