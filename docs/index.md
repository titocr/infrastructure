# This Mac Studio

This **Mac Studio with Apple M2 Max** is a personal development workstation and
application host. It has a **12-core CPU, 30-core GPU, 32 GB unified memory, and a
500.28 GB internal SSD**. See [hardware and capacity](host-baseline.md) for the
verified specifications and dated measurements.

## What it is used for

- **Developing software:** local projects under `/Users/titocr/code`, with source
  control and development tools on macOS.
- **Personal productivity:** GTD Mind runs continuously in a container; Options
  Finder runs as a native service for personal research and paper-trade journaling.
- **OSCAR:** a browser-accessible desktop for importing and reviewing CPAP data,
  started manually when needed.
- **Home Assistant:** a local home-automation environment owned by `thinq-interface`.
  Application setup is documented in its owning project.
- **Repository monitoring:** scheduled checks flag forgotten Git work.

## What runs here

| Workload | Access | Operation |
| --- | --- | --- |
| GTD Mind | [Open GTD Mind](https://gtd.purpletardis.xyz) | Container plus Cloudflare connector; [runbook](projects/gtd-mind-runtime.md) |
| OSCAR | [Open OSCAR](http://127.0.0.1:8089/) | Manual-start container; [runbook](projects/cpap-monitor-runtime.md) |
| Home Assistant | [Open Home Assistant](http://127.0.0.1:8123/) | Container; [runbook](projects/home-assistant.md) |
| Options Finder | [Open Options Finder](http://127.0.0.1:8000/) | Native LaunchAgent; [runbook](projects/options-finder.md) |
| This manual | [Open manual](http://127.0.0.1:8088/) | Container; [publication and recovery](manual.md) |
| Repository monitoring | Scheduled, no web interface | Three LaunchAgents; [runbook](repository-monitoring.md) |

Loopback links open services on this Mac. They are not remote access URLs.
The [service inventory](services.md) records ownership, startup behavior and
retained candidates. Inventory verification: **2026-09-21**. This is a dated
manual, not a live dashboard; its build date is separate from service verification.

## Find the right procedure

Use [routine operations](operations.md) for checks, [host recovery](recovery.md)
when something fails, and [backup coverage](backups.md) before relying on a restore.
[Outstanding work](outstanding.md) records known gaps.

The household media platform is a separate host. See the
[Mac Mini media center](projects/media-center.md) for the host boundary, current
operating shape and links to its authoritative runbooks.

Source and offline instructions live in `/Users/titocr/code/infrastructure`.
If this website is down, start with `README.md` there. For a new task, read the
relevant service runbook and inspect its runtime before changing it.
