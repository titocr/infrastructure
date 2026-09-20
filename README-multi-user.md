# Invite-only GTD Mind migration and recovery

This is local implementation tooling, not rollout authorization. The application
plan at `gtd-ai/docs/multi-user-implementation-plan.md` controls release gates.
No production data or configuration was used while developing this profile.

## Review and migration

The `invite-only-workspaces-v1` migration profile requires an exact application
revision, an explicit initial-owner binding file and its SHA-256, and a reviewed
target environment file and SHA-256. The binding contains stable user, workspace
and actor IDs, verified issuer/subject, email, time zone and migration timestamp.
Never infer these identities from arbitrary login claims or generate new IDs for
existing authorship. Review all private files without putting them in Git.

Even a command without `--apply` reads a private production copy. Obtain separate
approval before using `gtd_mind_migrate.py` with this profile; it requires
`--approve-private-copy`. Synthetic development must call the helpers with its
own disposable paths, never the production CLI defaults.

Rehearsal takes one immutable SQLite baseline, compares every original value and
relationship, boots and restarts the exact candidate with networking disabled,
and restores the baseline with the matching previous image. Reviewed trigger and
index changes are explicit. Production apply remains separately authorized: close
ingress and stop writers, back up the latest database, then migrate that stopped
database. Never replace it with an older rehearsal copy. Existing MCP consent is
preserved while writes are quarantined. Resume retains a durable writes-resumed
marker; failures after that marker require forward recovery, not an old restore.

## Protected recovery register and credentials

The erasure register lives at `/recovery/erasure.sqlite` on a separate directory
mount, outside `/data` snapshots. Directory mode is 0700 and file mode is 0600.
Only the initial migration may initialize it. Subsequent startup and restore fail
if it is missing or uninitialized. Back up and recover this content-free register
independently; never replace it with an older application snapshot's register.
Reconcile it before exposing a restored database to traffic or provider workers.

Personal Todoist configuration uses `TODOIST_OAUTH_CLIENT_ID`,
`TODOIST_OAUTH_CLIENT_SECRET`, `APP_ORIGIN`, and
`TODOIST_CREDENTIAL_KEY_FILE=/run/gtd-integrations/todoist.key`. The key is 32
random bytes encoded as base64, in the protected `config/integrations` directory
mounted read-only by the integration overlay. Configuration and provider OAuth
registration require separate operator approval. Do not print tokens or keys.
The offline application `dist/todoist/import-legacy-cli.js` accepts explicit
private token/key files and existing user, connection and provider-account IDs;
it preserves the legacy intake policy and checkpoint and cannot revive a revoked
connection. Remove the redundant environment token only in the reviewed rollout.
Keep encryption-key recovery separate from application snapshots and inventory
any data-bearing credential copies under the same retention policy.

## Retention

Configure every protected data-bearing copy root: recurring backups, deployment
backups, rehearsal directories, retained native releases and temporary artifacts.
The configuration must identify the live database and protected erasure register;
these, the inventory ledger and review reports are excluded from deletion. Copy
roots must be private and symlink-free. Review inventories files and age without
deleting them. Enforcement requires both `--apply` and the exact review SHA-256,
rechecks every file and refuses changed or added copies. Copies expire within 30
days; live erasure and backup expiry are separate guarantees. Arrange an approved
operational run often enough to meet that maximum. Never delete existing backups
under development authorization. Register all copy roots before rollout, including
private rehearsal output; no indefinite recovery-copy exceptions are implied.

## Lost-email recovery

Independently verify the person and new provider issuer/subject before preparing
a protected JSON input for `dist/accounts/recover-identity-cli.js`. Stop all
writers and provide explicit database/register/input/output paths, `--offline`
and `--confirm-user` matching the exact stable user ID. Input includes expected
old email, verified new identity, a content-free `operator:REFERENCE`, and UTC
`now`. The operation reconciles erasure first, replaces the old login binding,
revokes integration consent and invalidates stale application contexts while
preserving actor and workspace identity. Pending or disabled accounts cannot use
this operation to bypass their status. Cloudflare policy changes and live recovery
still require operator authorization; no admin screen can rebind another user.

## Release gates

Complete synthetic application, browser and infrastructure evidence first. Then
seek private-copy rehearsal approval, present exact-revision preservation evidence,
schedule downtime, and review recovery before production migration. Observe the
owner alone after resume. Invitations and real second-account Cloudflare, Todoist
and MCP checks follow owner acceptance and separate admission approval.
