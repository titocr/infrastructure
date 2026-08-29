# Mac Studio Infrastructure Manual

This is the durable operating guide for containerized applications on this Mac Studio. It is written to stand on its own if a Codex conversation disappears. The Markdown files, configuration, and change history live together in `/Users/titocr/code/infrastructure`.

Use this manual to understand what is running, ask an application project to become container-ready, review the result, add it safely to this host, or recover enough context to continue in a new Codex task.

## If the chat history is gone

1. Open the Codex project named `infrastructure`, or open this repository at `/Users/titocr/code/infrastructure`.
2. Start a new task and paste:

   ```text
   Read README.md and the complete manual under docs/. Inspect the repository and current runtime before changing anything. Summarize the current host, services, pending work, and safety boundaries, then propose the smallest coherent next step.
   ```

3. For GTD Mind work, open the Codex project `gtd-ai`, connected to `/Users/titocr/code/gtd-ai`. Start a focused task there rather than treating “GTD Mind” as a separate project.
4. Confirm live state using [Host baseline and inventory](host-baseline.md). Dates in this manual are evidence snapshots, not a live dashboard.

## Current position

Last verified: **2026-08-28**.

- OrbStack supplies Docker and Compose and starts at login.
- The infrastructure manual is the only container service currently managed by this repository.
- It listens only on `127.0.0.1:8088`.
- Docker ports are not exposed to the LAN by default.
- GTD Mind is a live, private, native Node/LaunchAgent deployment. It has **not** been migrated to a container.
- Containerizing an application begins in that application's repository. Production deployment and host integration are completed here only after review.

## Recommended path

1. Read [Concepts and responsibilities](concepts.md).
2. Follow [Add an application](application-containerization.md).
3. Use the [Runtime contract](runtime-contract.md) as the application-to-infrastructure handoff.
4. For the known application, follow the [GTD Mind worked example](projects/gtd-mind-containerization.md).
5. Use [Routine operations](operations.md) after deployment.

!!! warning
    Do not point a candidate container at production data, replace a live listener, change Tailscale routing, or remove an old service until its backup, health, and rollback procedure have been tested.
