# Concepts and responsibilities

## The names in Codex

| Term | Meaning here | Example |
| --- | --- | --- |
| Project | The durable Codex workspace connected to a repository | `gtd-ai` at `/Users/titocr/code/gtd-ai` |
| Product | The application people use | GTD Mind |
| Task or chat | One focused conversation inside a project | “Containerize GTD Mind” |
| Repository | Files and Git history shared by tasks in that project | `/Users/titocr/code/gtd-ai` |
| Image | An immutable application package built from a Dockerfile | A tested GTD Mind image |
| Container | A running instance of an image with settings and storage | A candidate GTD Mind service |
| Compose service | The repeatable definition of a container | Image, ports, volumes, health check |

A task transcript is not the durable project record. Checked-in documentation, configuration, decisions, and Git history are. Different tasks in the same project see the same repository, although worktrees or branches may temporarily isolate their changes.

## Division of responsibility

| Participant | Owns |
| --- | --- |
| Application repository | Dockerfile, build context, startup behavior, application health, internal paths, and application-specific documentation and tests |
| Infrastructure repository | Host Compose definition, loopback port, persistent host paths, secrets delivery, restart policy, exposure, backup/restore, monitoring, and cutover/rollback record |
| Human operator | Approving architecture, secrets, data migration, exposure, production cutover, destructive cleanup, and acceptable downtime |
| Codex task | Inspecting evidence, implementing a bounded change, testing it, documenting exact results, and stopping at approval boundaries |

The application project creates the container-capable application. This project decides how that application is safely operated on this Mac Studio.

## Why the handoff exists

Application code should not need to know a host data path, which external port is free, or how Tailscale routes traffic. Infrastructure should not guess the build command, health semantics, migration behavior, or files the application must persist.

The [runtime contract](runtime-contract.md) records those facts at the boundary. It is a document, not a second implementation.

## The human in the middle

You do not need to relay every status update. You do need to approve choices with consequences. The normal approval points are:

1. **Application design:** Does the image, health check, and persistence model make sense?
2. **Candidate deployment:** May infrastructure build and run an isolated local candidate?
3. **Production cutover:** May the live listener, routing, and production data change?
4. **Cleanup:** May the previous deployment or obsolete data be removed?

You can move the handoff manually with copy and paste, or ask Codex to create and message a task in another project. Either way, the checked-in runtime contract is the durable source of truth.
