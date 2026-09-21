# This manual

The infrastructure repository owns this Markdown reference, MkDocs build and Nginx
container. Read it at [http://127.0.0.1:8088/](http://127.0.0.1:8088/).
It uses `restart: unless-stopped`, publishes only loopback, and has no application
data volume. Its source is the recovery artifact; generated HTML is rebuildable.

## Publish and verify

From `/Users/titocr/code/infrastructure`, after reviewing source changes:

```sh
python3 scripts/publish-manual.py
```

This takes an allowlisted snapshot of the guide's build inputs, builds with MkDocs
strict mode and generated-link validation, and recreates only `infrastructure-guide`.
It waits for health, verifies the served build metadata and loopback binding, and
checks that other containers' identities/start times/status did not change.
If health or metadata verification fails, it restores the previous guide image
when one exists. The old image remains available; no application container is restarted.

Each page shows the source Git revision and UTC build time. A source SHA-256 in
`build-info.json` identifies the exact build inputs, including uncommitted edits.
“+ local changes” explicitly distinguishes that build from the named commit.
Commit and publish source through the normal repository workflow for durable recovery;
a local website publication does not itself commit or push changes.

Check whether the website matches the current checkout without rebuilding:

```sh
python3 scripts/publish-manual.py --check
```

The command exits unsuccessfully if revision, input hash or modified-source status
differs, or the endpoint cannot be read. Build time is provenance, not the date each
service was verified. Edit facts and verification dates only after actual checks.
Direct `docker compose build` remains possible but does not supply verified build
provenance; use the publication command for an operational release.

## Inspect and recover

```sh
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs --tail 100 infrastructure-guide
docker compose -f compose.yaml restart infrastructure-guide
curl --fail --show-error http://127.0.0.1:8088/build-info.json
```

If stopped, use `docker compose -f compose.yaml start infrastructure-guide`.
If absent, publish from the checked-out source. To restore a retained guide image,
use its printed image ID with `docker tag IMAGE_ID studio-infrastructure-guide:local`,
then `docker compose -f compose.yaml up -d --no-deps --no-build --wait infrastructure-guide`.
Check the restored metadata; an older build may correctly fail the freshness check.

The default port is 8088. `.env` may set `GUIDE_PORT` to another free loopback port;
update documented URLs when adopting that change. The publication check derives
the actual configured port. Base images and MkDocs are pinned; review dependency
updates and verify the resulting manual before publishing them.

## Navigation layout

The manual uses a small local template and stylesheet under `docs/overrides` and
`docs/assets`. Page links stay in fixed groups; section headings are available
through “On this page” above the document. The mobile Menu opens in the page flow,
with no overlay. Search uses MkDocs' local index. Fonts, styles and scripts are
served locally; the layout needs no external theme package or CDN.
