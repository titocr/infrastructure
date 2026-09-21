# GTD Mind

Personal capture and action management, hosted in OrbStack. Application owner:
`/Users/titocr/code/gtd-ai`; host deployment owner: `infrastructure`.
Runtime snapshot: **2026-09-21**.

## Host setup

| Item | Setup |
| --- | --- |
| Open | [GTD Mind](https://gtd.purpletardis.xyz) |
| Container | `gtd-mind-production-1` |
| Startup | OrbStack, `unless-stopped` |
| Access | Cloudflare tunnel; loopback 3000 for the browser origin and 3001 for MCP |
| Persistent root | `/Users/titocr/container-data/gtd-mind` |
| Storage | `state` mounted at `/data`; `recovery` mounted separately at `/recovery` |
| Private configuration | `config/gtd-mind.env`; read-only MCP secrets in `config/mcp` |
| Deployment records and backups | `deployments` under the persistent root |

The retained native LaunchAgent is disabled and unloaded. Keep it that way while
the container owns port 3000. Retained candidates are not production services.

## Check or restart

```sh
docker ps --filter name=gtd-mind-production-1
docker logs --tail 100 gtd-mind-production-1
curl --fail --show-error http://127.0.0.1:3000/api/health/ready
```

For a service restart, use `docker restart gtd-mind-production-1`. If deliberately
stopped, use `docker start gtd-mind-production-1`. Check readiness and browser
access afterward. Logs should be inspected locally.

## Update and recover

Use the [host deployment and recovery reference](../deployment-reference.md) for
release preparation, supported commands and matching deployment records.
Application release decisions remain in [GTD Mind documentation](../sources.md#gtd-mind).
Do not recreate production from the base Compose file alone; the reference maps
its required overlays.

Preserve the whole persistent root. Database backups alone do not cover the
separate recovery state or credentials. Deployment backups are not a recurring
backup service; see [backup coverage](../backups.md).

For a failed update, follow [record-based recovery](../deployment-reference.md#recover-a-compatible-gtd-image-update). Do not restore an arbitrary older database or start the native
release as a shortcut. Application release history and data-migration decisions
belong in `gtd-ai`.

For tunnel failures, see [GTD access](gtd-mind-access.md).
