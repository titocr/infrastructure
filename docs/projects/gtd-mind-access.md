# GTD Mind access

The host runs an outbound Cloudflare connector for GTD Mind. Runtime snapshot:
**2026-09-21**. Application access procedures belong to `gtd-ai`; the connector
and host storage belong to `infrastructure`.

| Route | Destination on the host | Access boundary |
| --- | --- | --- |
| `https://gtd.purpletardis.xyz` | Browser origin, loopback port 3000 | Cloudflare Access and application identity validation |
| `https://gtd-mcp.purpletardis.xyz/mcp` | MCP listener, loopback port 3001 | Delegated application authentication |

Neither origin port is a public host listener. Keep the browser and MCP routes
separate when reviewing tunnel configuration. Setup, sign-in and connection
instructions are in the [application documentation](../sources.md#gtd-mind).

## Connector

| Item | Setup |
| --- | --- |
| Container | `gtd-mind-cloudflared` |
| Startup | `unless-stopped` |
| Host ports | None; outbound tunnel |
| Credential source | `/Users/titocr/container-data/gtd-mind/config/tunnel-token`, mounted read-only |

```sh
docker ps --filter name=gtd-mind-cloudflared
docker logs --tail 100 gtd-mind-cloudflared
```

If a restart is needed, use `docker restart gtd-mind-cloudflared`. Check local
application readiness first, then connector state, then browser access. A running
connector alone does not prove routing or authentication works.

If the connector is missing, review its definition and current application layout
before recreating it. The older `scripts/gtd_mind_access.py` accepts only a
port-3000 layout and rejects the additional MCP port. Correcting that bootstrap
path is [outstanding host work](../outstanding.md).

Keep authentication and routing intact during recovery. Use the application's
release procedure for configuration changes and [GTD host operations](gtd-mind-runtime.md)
for storage and lifecycle information.

## Release authentication

The [host release preparation](../deployment-reference.md#prepare-gtd-release-authentication)
provides the operator-token procedure used by deployment checks. This is separate
from normal application sign-in and MCP connection setup.
