# Home Assistant

Local home-automation environment owned by `/Users/titocr/code/thinq-interface`.
Runtime snapshot: **2026-09-21**. Appliance setup and integrations belong in
the [owning project](../sources.md#home-assistant-and-options-finder).

| Item | Verified setup |
| --- | --- |
| Browser | [Home Assistant](http://127.0.0.1:8123/) |
| Container | `thinq-home-assistant-homeassistant-1`, running; no Docker health check |
| Image | `ghcr.io/home-assistant/home-assistant:2026.9.1` |
| Startup | OrbStack, `unless-stopped` |
| Exposure | Loopback 8123; no privileged mode or host networking in Compose |
| Persistent state | `/Users/titocr/code/thinq-interface/config`, mounted at `/config` |
| Backup coverage | No verified backup/restore procedure in the owning README |

The config directory contains private account/configuration/history data and is
excluded from Git. Its placement in the application checkout is an exception to
the preferred `/Users/titocr/container-data` convention.

## Operation and recovery

Run from `/Users/titocr/code/thinq-interface`:

```sh
docker compose ps
docker compose logs --tail 100 homeassistant
docker compose stop homeassistant
docker compose start homeassistant
```

If the container is missing, `docker compose up -d homeassistant` recreates it
using the existing config mount. Do not delete that directory to repair startup.
Verify the browser and expected configuration after recovery; Docker “running”
is not an application health check.

Updates belong in the owning repository. Before replacing its image, establish a
consistent config backup and a separate restore test, retaining the previous image.
Backups, tested restore, and image-update procedure remain [outstanding](../outstanding.md).
