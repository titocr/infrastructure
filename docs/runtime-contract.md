# Runtime contract

An application repository creates `docs/container-runtime-contract.md` before infrastructure deploys it. Use the template below. Replace every bracketed item; write “none” with a reason rather than leaving a section blank.

```markdown
# [Product] container runtime contract

Last verified: [DATE]
Application repository: [ABSOLUTE PATH OR REMOTE]
Application commit: [FULL COMMIT]

## Image
- Build command: [EXACT COMMAND]
- Dockerfile and context: [PATHS]
- Supported platform: [FOR EXAMPLE linux/arm64]
- Expected image identity/tag: [VALUE]
- Runtime user: [UID/NAME AND PRIVILEGES]

## Process and network
- Startup command: [COMMAND]
- Internal port and protocol: [VALUE]
- Readiness/health check: [COMMAND OR URL AND SUCCESS SEMANTICS]
- Graceful shutdown signal and timeout: [VALUE]

## Configuration and secrets
| Variable | Required | Secret | Purpose | Safe default |
| --- | --- | --- | --- | --- |
| [NAME] | yes/no | yes/no | [PURPOSE] | [VALUE OR NONE] |

State how secrets are supplied without including their values.

## Persistent data
| Container path | Contents | Backup consistency requirement | Restore notes |
| --- | --- | --- | --- |
| [PATH] | [CONTENTS] | [REQUIREMENT] | [NOTES] |

List temporary/cache paths separately. State file ownership and permissions.

## Database and migrations
- Database engine and version: [VALUE]
- Migration trigger: [STARTUP, EXPLICIT COMMAND, OR NONE]
- Compatibility with the previous version: [DETAILS]
- Backup/integrity requirement: [DETAILS]
- Rollback limitations: [DETAILS]

## External dependencies and trust boundaries
- Required services: [LIST]
- Authentication/proxy assumptions: [DETAILS]
- Outbound network needs: [DETAILS]

## Resource expectations
- Idle and normal CPU/memory observed: [VALUES AND TEST]
- Storage growth: [ESTIMATE]
- Startup time: [VALUE]

## Candidate verification
1. [BUILD]
2. [START WITH ISOLATED DATA]
3. [HEALTH]
4. [REAL USER FLOW]
5. [RESTART AND PERSISTENCE]
6. [SHUTDOWN]

## Operations and rollback
- Logs: [LOCATION/COMMAND]
- Backup: [APPLICATION-AWARE PROCEDURE]
- Restore test: [PROCEDURE]
- Known-good rollback image/commit: [VALUE]
- Rollback procedure and trigger: [DETAILS]
- Irreversible actions: [DETAILS OR NONE]
```

## Review rule

The contract is accepted only after infrastructure verifies it against the named commit and candidate behavior. If the implementation and contract disagree, the implementation is not ready for deployment.
