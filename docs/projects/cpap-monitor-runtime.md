# OSCAR on the Mac Studio

The current approach uses ordinary OrbStack Compose networking and the image's
built-in browser authentication. The user explicitly accepted trusted local/LAN
container access and requested this simpler setup. The custom relay and
network-disabled diagnostic are retired experiments, not the operating path.

## Access and storage

- Browser: http://127.0.0.1:8089/ . Username: `oscar`.
- Password: private file
  `/Users/titocr/container-data/cpap-monitor-candidate/standard-20260919/browser.env`
  (mode 0600). Do not copy its contents into Git, logs or task messages.
- Compose: `compose.cpap-monitor.yaml`, project `cpap-monitor-standard`.
- Nonsecret host settings: same private root, `compose.env`.
- Entire GUI/profile state: same root, `config`, mounted at `/config`.
- Empty card-copy directory: same root, `card`, mounted read-only at `/sdcard`.
- Startup: manual (`restart: no`); no login agent, schedule or auto-updater.
- Limits: 2 CPUs, 2 GiB RAM, 256 MiB shared memory; bounded container logs.

This is an isolated candidate. Disposable test profiles are authorized; actual
card data and Wi-Fi integration have not been introduced. The prior stopped
network-disabled candidate and its evidence remain separate and retained.

## Ordinary commands

From the Infrastructure repository, use the same prefix for every operation:

```sh
docker --host unix:///Users/titocr/.orbstack/run/docker.sock compose \
  --env-file /Users/titocr/container-data/cpap-monitor-candidate/standard-20260919/compose.env \
  -f compose.cpap-monitor.yaml ps
```

Replace `ps` with `start oscar`, `stop -t 60 oscar`, `restart oscar`, or
`logs --tail 100 oscar` as needed. Use `up -d oscar` after a deliberate image/config
update. Close OSCAR normally before stopping when possible. Do not use the retired
relay entry point or its automatic candidate-stop behavior.

Image changes belong in the private `compose.env` as exact image identities.
Application builds and startup behavior belong in `/Users/titocr/code/cpap-monitor`.
Keep a known working image and complete stopped config copy before an update.

## Exposure and known limitations

Only host IPv4 loopback 8089 is published. No public tunnel, router forwarding,
Wi-Fi or global OrbStack configuration was added. Normal bridge networking means
OrbStack direct container paths remain available; this is accepted within the
user's private-host threat model, not described as strict loopback-only isolation.

Initial live verification on 2026-09-19: loopback browser endpoint returned 401
without credentials and 200 with credentials. Direct container port 3000 also
returned 401. Requests through the Studio's Ethernet/Wi-Fi addresses on port 8089
did not connect. These were host-side checks, not an off-host or internet scan.
Existing GTD Mind, guide and Home Assistant endpoints retained 401/200/200 responses.

The image's internal Selkies backend can bypass Nginx authentication through direct
container access. Feature defaults (including file transfers) are not assumed
disabled merely because the sidebar is hidden or environment flags request it.
No sensitive data is present; do not expose this desktop publicly. The prior scan
still contains findings. These are recorded limitations for subsequent review,
not a clean-scan claim or a reason to keep rebuilding the private empty GUI.

## Test-state backup and reset

Disposable test state is confined to the candidate config directory. Before
resetting, close OSCAR and stop only this Compose service. Preserve or rename the
complete config directory, create a fresh private config directory with matching
ownership, then start the candidate. Do not delete the card directory, earlier
diagnostic evidence or unrelated container data. Actual deletion is a separate
explicit choice; no reset/deletion has been performed by this setup.

Before real-data use, specify backup retention and an encrypted off-host
destination and demonstrate restoration of the whole stopped config plus card
copy. A copy of card files alone does not preserve OSCAR preferences/annotations.

## Current verification

Selected application implementation: `874d22b7e0819a3cd728915371b28a3f76eaf052`.
Image: `sha256:dbe5b3609e48f04c255c2f7692e53c79564aacab49f429a8d4472f075ee06fb7`.
Container: `13311583753c3f0b639af69cf965dcffa03200d0ba19cd35598458d892c3da46`.

The application fixed a missing Qt network library and corrected persistent
Openbox autostart. After recreation, OSCAR20 runs (observed PID 401), the container
is healthy, and authenticated browser HTTP returns 200. Interactive browser
verification passed in native Chrome at the same endpoint with normal Basic
authentication: OSCAR 2.0.1 completed first-run setup, skipped old-data migration,
and opened the Welcome screen with CPAP Importer available.

The application task created `Disposable-Test` with no personal details or real
CPAP data. Its folder is `disposable-test`; the data root is
`/config/Documents/OSCAR20_Data`, and `oscar.db` plus the profile were verified on
the persistent host bind mount. Remove this disposable profile through OSCAR's
Profile screen using **Destroy Profile** when it is no longer needed. No deletion
has been performed. Whole-config reset remains available as described above.

The candidate remains running for use. This verifies empty/test-profile GUI
operation and on-disk persistence, not real card import or a completed backup
restore test. Early resource sample before the application repair: approximately
577 MiB of the 2 GiB budget and 4.4% CPU. ez Share/card collection is the next
separate integration step; no Wi-Fi or card access has been configured.
