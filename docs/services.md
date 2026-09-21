# Service inventory

Verified **2026-09-21** by inspecting nonsecret Docker metadata, service definitions,
and the per-user launchd domain. “Running” is a process observation; it does not
claim a fresh interactive application test or a successful backup restore.

## Running containers

| Service and purpose | Owning repository | Access / exposure | Startup | Operations and recovery |
| --- | --- | --- | --- | --- |
| GTD Mind: personal capture and action management | `gtd-ai`; host deployment in `infrastructure` | Browser through Cloudflare; loopback 3000; MCP loopback 3001 | `unless-stopped`; healthy | [GTD Mind](projects/gtd-mind-runtime.md) |
| Cloudflare connector: GTD browser and delegated access | `infrastructure` | Outbound tunnel; no host port | `unless-stopped`; running, no Docker health check | [Access](projects/gtd-mind-access.md) |
| OSCAR: CPAP desktop | `cpap-monitor`; host deployment in `infrastructure` | Browser on loopback 8089; direct-container limitations apply | Manual, `restart: no`; healthy | [OSCAR](projects/cpap-monitor-runtime.md) |
| Home Assistant: local home-automation environment | `thinq-interface` | Loopback 8123 | `unless-stopped`; running, no Docker health check | [Home Assistant](projects/home-assistant.md) |
| Manual: host reference and runbooks | `infrastructure` | Loopback 8088 | `unless-stopped`; healthy | [Manual](manual.md) |

## Native jobs

| Job | Verified state | Purpose / ownership | Startup / schedule | Operations and recovery |
| --- | --- | --- | --- | --- |
| `com.titocr.options-finder` | Loaded and running; IPv4 `*:8000` listener | Personal research and paper-trade journal; `options-finder` | At login, `KeepAlive` | [Options Finder](projects/options-finder.md) |
| `com.titocr.repository-monitor.scan` | Loaded; last exit 0 | Git hygiene; `infrastructure` | Login and every four hours | [Repository monitoring](repository-monitoring.md) |
| `com.titocr.repository-monitor.daily` | Loaded; last exit 0 | Unresolved-condition digest | Daily 09:00 local | [Repository monitoring](repository-monitoring.md) |
| `com.titocr.repository-monitor.weekly` | Loaded; last exit 0 | Repository summary | Saturday 09:15 local | [Repository monitoring](repository-monitoring.md) |

A scheduled job normally shows “not running” between invocations. Its plist alone
does not prove it is loaded. Vendor updater and desktop-helper plists are outside
this application's service inventory; this is not a catalog of every macOS process.

## Retained, not active

- `gtd-mind-candidate-1`: stopped September candidate at `edeee2ab870a`; retains
  isolated state and a configured port 3100. It is not the current release candidate.
- `cpap-monitor-candidate-oscar-1`: stopped network-disabled diagnostic; see
  [retired-service note](projects/cpap-monitor-diagnostic-20260919.md).
- `com.titocr.gtd-ai`: retained native LaunchAgent, **unloaded and disabled**.
  Do not enable it alongside the production container or use it as an automatic
  rollback for the newer database schema.

Service pages identify persistent storage and backup limitations. See the
[backup coverage table](backups.md) before treating retained files as recovery.
