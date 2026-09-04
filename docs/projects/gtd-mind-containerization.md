# GTD Mind worked example

This is the concrete handoff for GTD Mind. The Codex **project** is named `gtd-ai`; GTD Mind is the **product**. Create a focused task inside `gtd-ai` rather than looking for a separate “GTD Mind project.”

## Verified current deployment

Last verified: **2026-09-04**.

| Item                   | Current value                                               |
| ---------------------- | ----------------------------------------------------------- |
| Application repository | `/Users/titocr/code/gtd-ai`                                 |
| Process manager        | OrbStack and Docker Compose                                 |
| Listener               | `127.0.0.1:3000`                                            |
| Health                 | `http://127.0.0.1:3000/api/health`                          |
| Authentication mode    | Mac-local owner                                             |
| Private URL            | None; Tailscale follow-up deferred                          |
| Private routing        | None; Tailscale Serve disabled                              |
| Persistent database    | `/Users/titocr/container-data/gtd-mind/state/gtd-ai.sqlite` |
| Release                | `gtd-mind:edeee2ab870a`                                     |
| Rollback               | Retained native LaunchAgent and database                    |

The container deployment preserves guarded backup, SQLite integrity, health, migration, and
rollback behavior. The prior native deployment remains available for explicit rollback.

## 1. Create the application task

Completed at application revision `edeee2ab870a1d6abc69440b2b98fb30a1f62d16`. The runtime
contract is `docs/container-runtime-contract.md` in `gtd-ai`.

Open `gtd-ai` and create a task named **Containerize GTD Mind**. Start it in a worktree. Paste:

```text
Containerize GTD Mind in the gtd-ai repository. Read AGENTS.md, tasks/current.md, README.md, docs/operations/private-release.md, package manifests, server startup, web build, database code and migrations, authentication code, and health checks before proposing changes. Inspect actual code and tests; do not rely on this prompt for details that the repository can verify.

The current production service is a LaunchAgent on 127.0.0.1:3000, reached through Tailscale Serve. Its SQLite database and release files are under /Users/titocr/Library/Application Support/GTD AI. Do not stop or modify that service, change port 3000, change Tailscale Serve, run against the production database, or modify production backups.

First present a container design and risk review. Then, after resolving any necessary questions, implement the smallest coherent application-owned change: a production multi-stage Dockerfile for linux/arm64, a minimal build context, production startup with the built Angular client and Node server, a meaningful /api/health check, graceful shutdown, and local candidate verification using separate temporary data and a non-production port. Preserve the current authentication trust boundary or explain precisely what must change.

Create docs/container-runtime-contract.md. It must document the build command, internal port, startup command, all environment variables, secret inputs, persistent container paths, SQLite migration behavior, health check, shutdown behavior, candidate test procedure, resource observations, and rollback constraints. State which existing npm release safeguards remain application-owned and how container operation must provide equivalent backup, integrity, migration, health, and rollback protection.

Run the relevant application tests plus an end-to-end container build/start/health/restart/persistence check. Commit only the focused application changes. Return the commit, exact results, remaining risks, and runtime-contract path. Stop without altering production.
```

Alternatively, from this infrastructure task say:

```text
Create a new “Containerize GTD Mind” task in the gtd-ai project, include the complete infrastructure handoff in its initial message, and start it in a worktree. Do not let it alter the live deployment.
```

## 2. Bring the result back here

Completed. The isolated candidate and guarded automation are recorded in
[GTD Mind container operations](gtd-mind-runtime.md).

After the `gtd-ai` task commits its work, use this prompt in `infrastructure`:

```text
Prepare a GTD Mind candidate from /Users/titocr/code/gtd-ai at commit [COMMIT]. Read /Users/titocr/code/gtd-ai/docs/container-runtime-contract.md and verify it against the application files. Inspect the current LaunchAgent, port 3000, Tailscale Serve route, production paths, backups, and Docker services before changing anything.

Add an isolated Compose candidate using a free 127.0.0.1 port and a separate path under /Users/titocr/container-data/gtd-mind-candidate. Do not read or write the production SQLite database, stop the LaunchAgent, or change Tailscale. Add secret delivery, health, restart, backup/restore, and rollback procedures. Test build, health, real application behavior, restart, and persistence. Record the measured result and commit the focused infrastructure changes. Stop before cutover.
```

## 3. Production decision

Migration is complete only after:

- an application-aware backup and restore has been exercised;
- database migration compatibility with rollback is known;
- Tailscale Serve is saved and deliberately disabled before local mode starts;
- Mac-local owner access works at `http://127.0.0.1:3000`;
- candidate restart and host restart behavior are acceptable;
- the old LaunchAgent can be restored with a documented command; and
- the human operator approves the exact cutover plan.

Do not remove the native release tree, LaunchAgent definition, or last compatible database backup during initial cutover.
