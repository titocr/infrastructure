# Options Finder

Personal research and paper-trade journaling application, owned by
`/Users/titocr/code/options-finder`. This is a native Python/Uvicorn service,
not a Docker workload. Runtime and source configuration checked **2026-09-21**.
Application workflows belong in the [owning project](../sources.md#home-assistant-and-options-finder).

| Item | Verified setup |
| --- | --- |
| Local browser | [Options Finder](http://127.0.0.1:8000/) |
| LaunchAgent | `com.titocr.options-finder`, loaded and running |
| Startup | At user login, `KeepAlive=true` |
| Listener | IPv4 `0.0.0.0:8000` / `*:8000`; potentially LAN-accessible |
| Entry point | Repository `scripts/run-server.sh`, using its `.venv` |
| Persistent data | Repository `data/options_finder.sqlite3`, as configured in `app/config.py` |
| Logs | Repository `logs/` |
| Backup coverage | Recurring backup and restore testing not verified |

The LAN listener is an existing exception to loopback defaults. This refresh did
not test off-host reachability or audit application authentication, and made no
exposure changes. Review those boundaries before expanding use.

## Operation and recovery

Inspect the user job and listener:

```sh
launchctl print gui/$(id -u)/com.titocr.options-finder
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Restart an already loaded job when needed:

```sh
launchctl kickstart -k gui/$(id -u)/com.titocr.options-finder
```

If unloaded, first review the retained plist and ensure another intended process
is not using port 8000. Restore the job with:

```sh
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.titocr.options-finder.plist"
```

Check the browser and local logs after recovery. Application updates and Python
dependencies belong in the owning repository. Establish a SQLite-consistent backup
and isolated restore procedure before a schema change; copying only a live database
file may miss WAL data. Do not reset or seed the database as a repair action.
