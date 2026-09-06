# GTD Mind owner-only remote access

Live and verified on 2026-09-06 at `https://gtd.purpletardis.xyz`.
Application revision `85d3214` passed guarded deployment; both containers run in
OrbStack. A real owner JWT received HTTP 200 for the public session and UI;
unauthenticated UI, session, inbox, and sync-health requests redirect to Access.
Direct loopback requests without a JWT receive HTTP 401. Responses use no-store.
App and connector restart recovery passed. The owner confirmed browser and
cellular access with Wi-Fi and Tailscale disabled.

Deployment record:
`/Users/titocr/container-data/gtd-mind/deployments/20260906T211541Z-6f324d69/record.json`.
The guarded release verified database integrity, schema preservation, restoration
on a private copy, owner session, UI, and a fresh successful Todoist poll. The
previous image/configuration and pre-upgrade backup are retained for recovery.
Session expiry and retained-edit behavior have automated coverage; actual
seven-day expiration has not yet elapsed.

Verified setup on 2026-09-06: the .xyz registry delegates to
`asa.ns.cloudflare.com` and `eric.ns.cloudflare.com`; Cloudflare reports the
zone active. The apex and `www` remain DNS-only CNAMEs to `titocr.github.io`,
and both existing ACME TXT records are retained.

Access application `GTD Mind` is saved for `gtd.purpletardis.xyz`, with only
email one-time PIN and the exact owner email allow policy. Application duration
is one week and global duration inherits the application. Application ID:
`4ee1d850-fc99-42dc-893a-44a9d83ff008`; issuer:
`https://hidden-pine-966b.cloudflareaccess.com`; audience:
`617da6da2e704077098615f950a106f59f376b4b10decd616b37738d27972c06`.
These identifiers are public configuration, not credentials.

The `gtd-mind-studio` tunnel (`1b957aa3-2bce-4b3c-8ca2-b6ea0d667b63`)
has a running connector. Its published route points the GTD hostname to
`http://production:3000`, requires the GTD Mind Access audience, and has a
default `http_status:404` route. A hostname-specific cache bypass is active.
An unauthenticated public request returns the Access login redirect.
The official connector image
has been downloaded and resolved to
`cloudflare/cloudflared@sha256:0aa26e284f05e6c77ae375b8c9c11d9eb6a448fb7bcd8d40f31cb6176189eb38`.
The credential handoff and interactive owner CLI login are complete. The built
application verifier accepted the real owner JWT against Cloudflare's public
signing keys. Never store either token in this document.

Deployment validation: 16 upgrade unit tests, three connector origin guard tests,
and a real isolated Docker upgrade/failed-verification rollback rehearsal pass.
The live test closes host SQLite connections before container lifecycle changes;
a transaction context alone does not close a Python SQLite connection.
The release archive extraction preserves Git file modes inside a private parent
directory, so the non-root image can read copied package manifests.

The intended hostname is `gtd.purpletardis.xyz`, protected by Cloudflare Access
email PIN restricted to the owner, with seven-day sessions. The application
independently validates the Access application JWT. Tailscale is administration
only. There are no family accounts or service-credential bypasses.

## Configuration and activation

Preserve existing DNS records and use DNS-only for the existing GitHub Pages site.
Protect the entire GTD hostname in Access before adding the tunnel route. Use
email one-time PIN only, the exact allowed owner, and seven-day application,
policy, and global sessions. Enable tunnel Access validation for the same audience.
The tunnel service is `http://production:3000`, with a default 404 route. Bypass
cache for this hostname. No wildcard ingress, direct port exposure, or router
forwarding is needed.

Keep production configuration under the existing private runtime config directory.
Add `AUTH_MODE=cloudflare`, `APP_ORIGIN=https://gtd.purpletardis.xyz`,
`CLOUDFLARE_ACCESS_ISSUER`, `CLOUDFLARE_ACCESS_AUDIENCE`, and
`CLOUDFLARE_OWNER_EMAIL`. Keep the existing owner actor and provider settings.
Use `GTD_MIND_TARGET_ENV_FILE` to select a prepared mode-0600 configuration during
a guarded upgrade; the previous configuration is saved alongside its deployment
record. Do not put JWTs in that configuration.

Cloudflare-mode release checks require a current owner application JWT in a
mode-0600 file referenced by `GTD_MIND_OWNER_TOKEN_FILE`. Obtain it through the
owner's interactive Access login and store it without terminal output. It is
used only for loopback verification; never add it to Git, command arguments,
logs, environment snapshots, or deployment records. Remove the temporary file
after verification. This is an operator session, not an unattended service identity.

After the application deployment succeeds, start the connector with
`scripts/gtd_mind_access.py`. It checks authentication mode, owner, origin,
health, loopback bindings, and unauthenticated denial before starting the
connector. Supply `GTD_MIND_IMAGE`, `GTD_MIND_TUNNEL_TOKEN_FILE`, and
`GTD_MIND_CLOUDFLARED_IMAGE` (official image pinned by digest), along with the
normal production environment/data paths. Keep the tunnel token mode 0600.

## Recovery and verification

The guarded upgrade restores the previous configuration with its image. When
restoring local mode it stops `gtd-mind-cloudflared` before switching the image.
Before intentional local-only recovery, also disable the public route in
Cloudflare. Schema drift stops automatic recovery. Current database writes are
retained, and the native LaunchAgent remains disabled.

Verify healthy origin, owner session, denied direct requests, fresh Todoist poll,
container restart, and database integrity. Test actual public login, sign-out,
expired AJAX sessions, retained edits, explicit retry, and a cellular client with
Tailscale and Wi-Fi off. Do not claim those checks from unit tests.

Access outage recovery uses private administration; it does not provide a second
live application URL. Revoke lost sessions in Cloudflare Access. Application
signature verification alone does not implement immediate token revocation;
Cloudflare's edge must remain the only public path.
