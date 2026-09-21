# OSCAR operations

A browser-accessible OSCAR desktop for CPAP card import and review. Application
owner: `/Users/titocr/code/cpap-monitor`; host Compose owner: `infrastructure`.
Runtime snapshot: **2026-09-21**. Application setup and use belong to the
[OSCAR project](../sources.md#oscar).

## Access, startup and storage

| Item | Current setup |
| --- | --- |
| Browser | [OSCAR](http://127.0.0.1:8089/); built-in browser authentication |
| Container / Compose | `cpap-monitor-standard-oscar-1`; `compose.cpap-monitor.yaml` |
| Image | `sha256:dbe5b3609e48f04c255c2f7692e53c79564aacab49f429a8d4472f075ee06fb7` |
| State | Running and healthy; manual startup, `restart: no` |
| Limits | 2 CPUs, 2 GiB RAM, 256 MiB shared memory |
| Private root | `/Users/titocr/container-data/cpap-monitor-candidate/standard-20260919` |
| Profile/settings | Private root `config`, mounted at `/config` |
| Card mirror | Private root `card`, mounted read-only at `/sdcard` |
| Settings and credentials | Private root `compose.env` and mode-0600 `browser.env`; never copy their contents here |

Despite `candidate` in its path, this storage contains real health data. It is not
disposable. Preserve the complete config and card directories during recovery.

## Operate

Run from `/Users/titocr/code/infrastructure`:

```sh
docker --host unix:///Users/titocr/.orbstack/run/docker.sock compose \
  --env-file /Users/titocr/container-data/cpap-monitor-candidate/standard-20260919/compose.env \
  -f compose.cpap-monitor.yaml ps
```

Use the same prefix with `start oscar`, `stop -t 60 oscar`, `restart oscar` or
`logs --tail 100 oscar`. Close OSCAR normally before stopping. Use `up -d oscar`
only after a deliberate image/configuration review. Image selection is an exact
identity in private `compose.env`; retain the matching previous image.

After startup, verify authentication and that the desktop opens.
Do not use the retired relay or network-disabled candidate as a recovery shortcut.

## Access limitations

Host port 8089 is published only on IPv4 loopback. Ordinary OrbStack bridge
networking still permits direct container access, and the internal Selkies backend
can bypass Nginx authentication through that path. This is a documented private-host
limitation, not strict isolation. No public desktop route is part of this setup.

## Backup, restore and cleanup

The original card backup is recorded at
`/Users/titocr/container-data/cpap-monitor-card-backups/20260919T101502/card`, with
an adjacent SHA256 manifest. It does not cover subsequent profile/settings changes.
Recurring backups, retention, an encrypted off-host copy and a complete profile
restore test remain unverified/outstanding.

Before migration or image replacement, close OSCAR, stop this service and copy the
complete `config` directory to protected backup storage, retaining the matching
image and card copy. Rehearse restoration into separate storage before relying on
it. Do not overwrite live profile storage to test recovery.
