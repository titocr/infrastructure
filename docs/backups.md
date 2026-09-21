# Backup coverage

Coverage reviewed **2026-09-21**. No restore was performed for this documentation
review. A retained local copy does not protect against loss of the host or disk.

| Service | Data to protect | Known coverage / gap |
| --- | --- | --- |
| GTD Mind | Entire private root: application state, separate recovery state, configuration and credentials | Per-deployment backups exist; recurring coverage and operational retention need completion |
| OSCAR | Complete config plus card copy | Original card backup exists; complete recurring backup, retention, off-host copy and restore test remain outstanding |
| Home Assistant | Private config directory in `thinq-interface` | Backup and isolated restore not verified |
| Options Finder | SQLite state under owning repository `data/` | Consistent backup and isolated restore not verified |
| Repository monitoring | Private settings and notification state | Scripts are in Git; settings/state backup not verified |
| Manual | Repository source | Rebuildable from source; see [manual recovery](manual.md) |

Storage locations are in the [service runbooks](services.md). Application-specific
consistency, restore and retention requirements belong to the
[owning project](sources.md); a file copy is not automatically a usable backup.

No host-wide backup schedule, external destination or whole-machine restore has
been verified here. OrbStack reports `data_allow_backup: false`; its VM store
should not be assumed to have backup coverage.

## Host recovery requirements

For each service, establish the complete data set, required credentials, matching
application image, consistent backup method, destination and retention schedule.
Verify restoration into separate private storage. Keep recovery evidence with the
owning project and record coverage here. Do not test a restore over live storage.
