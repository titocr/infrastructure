# Add an application

This procedure takes an application from “works in its repository” to “operated safely on this Mac Studio.” Complete the stages in order. The first stage changes only the application repository; later stages change this infrastructure repository and host runtime.

## 1. Start a focused application task

Open the application's existing Codex project and create a new task. If it is a Git repository, use a worktree or task-specific branch for nontrivial work.

Paste this prompt, replacing bracketed names:

```text
Containerize [PRODUCT NAME] in this application repository. First inspect the repository instructions, current deployment documentation, build, runtime, data, authentication, health checks, and tests. Do not alter the live deployment.

Implement the smallest coherent application-owned containerization change: a production Dockerfile, a complete and minimal build context, an unprivileged runtime where practical, a meaningful health endpoint or command, and local build/run verification. Do not place host-specific ports, secrets, production data paths, Tailscale configuration, or Mac launch configuration in this repository.

Create docs/container-runtime-contract.md using the infrastructure manual's runtime-contract format. It must specify the image build command, architecture, internal port, startup command, environment variables with secrets marked, persistent container paths, migration behavior, health check, shutdown behavior, expected resource needs, candidate test procedure, and rollback considerations.

Before implementation, report the proposed design, risks, and exact production boundaries. Stop for my approval if data migration, authentication, exposure, or the existing production service could be affected. After implementation, run appropriate tests and commit the focused change. Give me the commit, verification results, unresolved issues, and the path to the runtime contract.
```

## 2. Review the application result

Confirm that:

- the ordinary application test suite still passes;
- the image builds for `linux/arm64` or a compatible multi-platform target;
- the container starts without the source tree mounted into it;
- a health check proves application readiness, not merely that a process exists;
- every durable file is named in the runtime contract;
- secrets are inputs and do not appear in the image, Compose file, logs, or Git;
- termination is graceful and documented;
- database migrations are explicit and rollback limitations are stated; and
- the live service and production data were untouched.

If anything is missing, reply in the application task. That task should revise its own implementation and contract.

## 3. Hand the contract to infrastructure

Return to a task in the `infrastructure` project. Paste:

```text
Prepare an isolated candidate deployment for [PRODUCT NAME]. Read this infrastructure manual, inspect current host state, and read the application runtime contract at [ABSOLUTE PATH]. Verify the referenced application commit exists. Propose the smallest coherent infrastructure change before implementing it.

The candidate must use a free loopback-only port and separate non-production data. It must not alter the live listener, production data, Tailscale routing, login service, or existing backups. Add a health check, restart policy, secret-delivery plan, backup/restore procedure, resource observations, and rollback instructions. Build and exercise the candidate end to end, update the service inventory, and commit the focused infrastructure change. Stop before production cutover.
```

The infrastructure task should record the application repository and commit, image identity, candidate port, data path, exact verification, and cleanup procedure.

## 4. Evaluate the candidate

Use the application through the candidate endpoint, not only a health URL. Test an important user flow, restart the container, and verify that data survives. If the application receives authentication information from a proxy, test that boundary explicitly.

Before approving production, answer:

1. Is the backup current, readable, and restorable?
2. Is the candidate using a copy rather than the only production data?
3. Are migrations reversible, forward-only, or safely compatible with rollback?
4. What exact procedure restores the old service?
5. How much downtime should be expected?
6. Will the public or private URL stay the same?

## 5. Authorize cutover separately

Only after accepting the candidate, paste:

```text
I approve planning the production cutover for [PRODUCT NAME]. Re-inspect the live service and candidate, confirm a fresh backup and tested rollback, and present the exact ordered cutover plan with expected downtime and approval boundaries. Do not execute the cutover until I explicitly approve that exact plan.
```

After reviewing the plan, authorize execution unambiguously. Retain the old deployment and backup until the new service passes health, restart, persistence, authentication, and real user-flow checks.

## 6. Clean up later

Cleanup is a separate destructive decision. Ask for an inventory of old launch configuration, releases, images, containers, and data first. Preserve at least one known-good rollback artifact and follow the relevant retention policy.

## Optional task coordination

Instead of manually moving the contract, you can ask the infrastructure task:

```text
Create a new “[ACTION]” task in the [PROJECT] project, include the complete handoff in its initial message, and start it in a worktree. Do not let it alter the live deployment. Tell me the task name and wait for its result.
```

The new task remains visible and user-owned. Repository files and commit references—not the cross-task message—remain the recovery record.
