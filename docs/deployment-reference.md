# Deployment and recovery reference

Use this page when replacing or recovering a hosted service. Routine status and
restart commands remain in the [service runbooks](services.md). Application
release decisions and data-migration plans remain with the [owning project](sources.md).
Commands below are procedures to use when needed, not a checklist to run in full.

## Service configuration map

Paths are relative to `/Users/titocr/code/infrastructure` unless stated otherwise.

| Service | Definition and configuration | Supported entry point |
| --- | --- | --- |
| Manual | `compose.yaml`; optional `.env` sets `GUIDE_PORT` | `python3 scripts/publish-manual.py`; [runbook](manual.md) |
| GTD production | `compose.gtd-mind.yaml` plus recovery and MCP overlays below; private `config/gtd-mind.env` under its persistent root | Application `npm run release:container`; see below |
| GTD recovery mount | `compose.gtd-mind-recovery.yaml` | Selected by guarded deployment from required runtime settings |
| GTD MCP mount and listener | `compose.gtd-mind-mcp.yaml` | Selected when MCP is enabled; retains loopback 3001 and read-only secrets |
| GTD integration-key mount | `compose.gtd-mind-integrations.yaml` | Conditional configuration, not an instruction to enable it |
| GTD tunnel | `compose.gtd-mind-access.yaml` with the base GTD file; private tunnel-token file | Existing-container operation in [access runbook](projects/gtd-mind-access.md); recreation guard needs correction |
| OSCAR | `compose.cpap-monitor.yaml`; private `compose.env` and `browser.env` | [Exact Compose prefix](projects/cpap-monitor-runtime.md#operate) |
| Home Assistant | `/Users/titocr/code/thinq-interface/compose.yaml` | [Owning-project commands](projects/home-assistant.md#operation-and-recovery) |
| Options Finder | `~/Library/LaunchAgents/com.titocr.options-finder.plist` | [launchd commands](projects/options-finder.md#operation-and-recovery) |
| Repository monitoring | Three `com.titocr.repository-monitor.*` LaunchAgents; private monitoring settings | [Installer and inspection](repository-monitoring.md) |

GTD's persistent root is `/Users/titocr/container-data/gtd-mind`. Read configuration
locally; do not print complete environment files or unfiltered Docker inspection.
Do not reconstruct a running application from a partial set of Compose files.

## Prepare GTD release authentication

Cloudflare-mode host checks require a current owner application JWT. In a private
local terminal with shell tracing disabled, log in through the existing browser
flow, then write the token directly to a protected temporary file:

```sh
umask 077
gtd_release_dir=$(mktemp -d "${TMPDIR:-/tmp}/gtd-release.XXXXXX")
export GTD_MIND_OWNER_TOKEN_FILE="$gtd_release_dir/owner.jwt"
cloudflared access login --quiet https://gtd.purpletardis.xyz
cloudflared access token --app https://gtd.purpletardis.xyz > "$GTD_MIND_OWNER_TOKEN_FILE"
chmod 600 "$GTD_MIND_OWNER_TOKEN_FILE"
test -s "$GTD_MIND_OWNER_TOKEN_FILE"
```

Stop if login or token retrieval fails. Use the same terminal for the release or
recovery command so it inherits the file path. Never print the token or paste it
into a task, Git, or a command argument. This authenticates the operator; it does
not change the application's access policy. The Cloudflare CLI also maintains its
own login cache; removing the temporary file does not revoke that session.

## Update GTD

From `/Users/titocr/code/gtd-ai`, use a clean, published `main` at the intended
revision and complete the application's release checks. The host entry points are:

| Command | Effect |
| --- | --- |
| `npm run release:container` | Builds and rehearses a private production-data copy; retains local artifacts, but does not replace production |
| `npm run release:container -- --apply` | Rehearses, then stops the writer, backs up and replaces production; requires deployment authorization |

Neither command is a read-only status check. The wrapper invokes Infrastructure's
`scripts/gtd_mind_upgrade.py`, which preserves the required overlays and refuses
migration-file changes. Keep normal configuration unchanged; use
`GTD_MIND_TARGET_ENV_FILE` only for a separately reviewed configuration transition.

An unfinished deployment or compatibility refusal is a recovery condition, not a
reason to bypass a guard. Schema-changing work uses `scripts/gtd_mind_migrate.py`
under the application's reviewed procedure. Its rehearsal also reads private data;
`--resume` and `--restore-quarantined` change runtime/data state and are not generic
restart commands.

## Find the matching GTD record

Records live at `/Users/titocr/container-data/gtd-mind/deployments/*/record.json`.
Start with the record path printed by the failed operation. If that is unavailable,
inspect the running immutable image ID and a small selection of record metadata:

```sh
docker inspect gtd-mind-production-1 --format '{{.Image}}'
python3 - <<'PY'
import json
from pathlib import Path
root = Path('/Users/titocr/container-data/gtd-mind/deployments')
for path in sorted(root.glob('*/record.json')):
    record = json.loads(path.read_text())
    fields = ('status', 'phase', 'revision', 'image_id', 'previous_image_id')
    print(path)
    print({key: record[key] for key in fields if key in record})
PY
```

These checks do not modify records or application data. Match the current image to
`image_id` or `previous_image_id`, then check the attempted operation, record status
and backup/configuration paths privately. A timestamp or image match alone is not
sufficient: multiple records may share an image. Do not automatically choose the
newest record. If the container is missing or the intended record is ambiguous,
resolve it from the failed operation's evidence before acting.

## Recover a compatible GTD image update

With release authentication prepared, from the Infrastructure repository:

```sh
python3 scripts/gtd_mind_upgrade.py --rollback \
  /Users/titocr/container-data/gtd-mind/deployments/RUN/record.json
```

Replace `RUN` with the reviewed matching **ordinary upgrade** record. This command
interrupts production, restores its previous image/configuration and preserves
current database writes. It is not a database restore or a migration rollback.
It verifies the resulting application before recording `rolled-back`.

Stop for application recovery review if the record concerns a migration, required
artifacts are missing, or image/schema checks disagree. Schema drift can leave the
container stopped with `manual-recovery-required`; do not force-start another image
or restore an old database to get past that state. An interrupted migration must
follow its own recovery rules, especially once writes have resumed.

After successful recovery, check readiness, browser access and connector state.
Keep the operation's record and backups under the applicable retention policy.
When release verification is finished, remove only the temporary token created above:

```sh
rm -- "$GTD_MIND_OWNER_TOKEN_FILE"
rmdir -- "$gtd_release_dir"
unset GTD_MIND_OWNER_TOKEN_FILE gtd_release_dir
```

## Recovery-copy retention

`scripts/gtd_mind_retention.py review` inventories the explicitly configured copy
roots and writes a private ledger/report; it does not delete copies.
`enforce --apply --review-sha256 …` deletes the reviewed expired copies and refuses
a changed inventory. Use the application's current retention requirements and a
reviewed configuration. This is not general disk cleanup; live data, recovery
state and retention records must remain protected. Coverage and scheduling gaps
are tracked under [outstanding host work](outstanding.md).
