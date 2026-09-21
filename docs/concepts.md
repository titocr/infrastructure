# Responsibilities and conventions

| Owner | Responsibility |
| --- | --- |
| Application repository | Build, startup, health semantics, schema, persistent container paths and application tests |
| Infrastructure repository | Host deployment, storage mounts, exposure, service operation and recovery documentation |
| Operator | Authorizing production changes, access changes, data migration and destructive cleanup |

The [runtime contract](runtime-contract.md) records the application/host boundary.
`gtd-ai` is the repository and workspace; GTD Mind is the product. A task is a
conversation, not the durable operations record.

## Shared conventions

Keep configuration and documentation in Git, and secrets out of Git, images and
logs. Prefer persistent application data under `/Users/titocr/container-data`;
record exceptions such as Home Assistant and Options Finder in their runbooks.
Publish ports on loopback by default and document each broader access decision.
Use reviewed image identities and deliberate updates, not unattended replacement.

Use separate candidate storage and verify backup restoration before migration.
Scope lifecycle commands to the intended service. Preserve existing work and
recovery artifacts until their owner and retention requirements are understood.

Proceed within the user's authorized scope. Present the concrete impact of a
production, access, migration or destructive action when additional authorization
is needed; routine inspection and isolated preparation do not need repeated gates.

## What belongs in this manual

Include a detail when it changes how this Mac hosts, starts, exposes, stores,
backs up or recovers a service. Keep application features, account workflows,
release chronology, migration design and acceptance reports in the owning project.
Link to the authoritative procedure instead of copying it into an Infrastructure
archive. [Application documentation](sources.md) lists those entry points.

Runtime evidence outranks stale prose. Record the date of host checks and update
facts after reconciling a difference; a site rebuild is not service verification.
