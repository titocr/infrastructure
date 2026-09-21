# Outstanding host work

Reviewed **2026-09-21**. Application features, release plans and project backlogs
are maintained in their own repositories.

| Area | Host work to complete |
| --- | --- |
| GTD backups | Establish recurring protection for all required state and credentials; complete recovery-copy inventory and retention scheduling using the application's requirements |
| OSCAR backups | Cover complete config and card copy, with retention, encrypted off-host storage and verified restoration |
| Home Assistant backups | Establish config backup and tested recovery with `thinq-interface` |
| Options Finder | Verify the existing LAN access boundary and establish consistent backup/recovery with its owning project |
| GTD connector recreation | Update the port-3000-only bootstrap guard for the current browser/MCP layout without weakening access checks |
| Host recovery | Establish whole-host backup scope and availability expectations, including login, sleep and reboot behavior |

Use [backup coverage](backups.md) and [application documentation](sources.md) when
planning this work. These entries do not change service configuration or authorize
cleanup. Update them when the operational gap is actually resolved.
