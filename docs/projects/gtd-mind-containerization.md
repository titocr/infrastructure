# GTD Mind containerization handoff

Updated: 2026-08-28

Read [Application container onboarding](../application-containerization.md) first. This document adds GTD Mind-specific constraints. It is a migration brief, not permission to change the live service.

## Known deployment to revalidate

The latest known GTD Mind production shape is more than an Angular application:

- An Angular web application and Node server are packaged together for the private Mac Studio release.
- The server owns API routes, including `/api/health` and authenticated session behavior.
- SQLite state, protected configuration, logs, backups, and immutable release directories live under `~/Library/Application Support/GTD AI` outside the Git checkout.
- A LaunchAgent supervises the Node process on loopback port `3000`.
- Host-side Tailscale Serve proxies the private HTTPS name to `http://127.0.0.1:3000`.
- Tailscale identity headers are trusted only because the backend remains loopback-only.
- `npm run release:deploy` currently guards clean-source packaging, SQLite backup and integrity checks, migrations, health verification, release switching, and code rollback.

The GTD Mind project must revalidate all of these facts against its current code, documentation, runtime, Tailscale state, and data layout before designing the container.

## Migration intent

Containerize the coherent production runtime, not merely the Angular frontend. The project must decide whether the web build and Node API belong in one image or whether there is a well-supported reason for multiple services. Do not introduce a reverse proxy or database server solely because containers are being adopted.

The first container milestone is a parallel candidate. It must not replace the LaunchAgent, bind host port `3000`, change Tailscale Serve, or open the production SQLite database.

## Required application-project work

1. Trace the Angular build, server startup, static-asset serving, API routes, environment loading, SQLite path, migrations, session handling, and shutdown behavior.
2. Review the current guarded release path and preserve its safety properties in the proposed container workflow.
3. Add application-owned container artifacts only after that review.
4. Build natively for `linux/arm64`; do not rely on Rosetta for the production image.
5. Keep protected configuration and database contents out of the image.
6. Specify the container user and prove it can read and write the proposed SQLite bind mount without broad permissions.
7. Preserve `/api/health` or document a better readiness endpoint with an exact expected response.
8. Return the completed runtime contract from the general onboarding guide.

## Parallel validation boundary

- Use an unused loopback host port selected by the infrastructure project; production port `3000` remains untouched.
- Use a separate candidate data directory under `/Users/titocr/container-data/gtd-mind-candidate`.
- If representative data is required, create it through the existing guarded SQLite backup process and restore a copy. Never mount the live database into the candidate.
- Keep Tailscale Serve pointed at the current native release during validation.
- Verify migrations, persistence, backup, restore, health, authenticated owner behavior, graceful stop, and recovery after OrbStack restarts.
- Treat cutover, Tailscale route change, LaunchAgent retirement, and legacy release cleanup as later explicit steps.

## GTD Mind project request

> Review the repository before implementing containerization. GTD Mind is currently believed to be an Angular web application plus a Node API/server with SQLite state, guarded migrations and backups, loopback binding, LaunchAgent supervision, and owner-only host-side Tailscale Serve. Revalidate that entire topology from current code and runtime evidence.
>
> Propose the smallest coherent production image for native `linux/arm64`. Preserve the safety properties of the existing `npm run release:deploy` flow: clean committed inputs, protected configuration, SQLite backup and integrity checks, migration review, health verification, and recoverable rollback. The application repository owns its Dockerfile, `.dockerignore`, image build, startup and shutdown behavior, health endpoint, tests, and completed runtime contract. `/Users/titocr/code/infrastructure` will own the Mac Studio Compose stack, host paths, secrets, loopback host port, pinned digest, backup operations, and cutover.
>
> Do not alter the live LaunchAgent, port `3000`, Tailscale Serve configuration, or production data. Build and test a parallel candidate only. Use a production Angular build rather than `ng serve`, run natively on `linux/arm64`, avoid embedding secrets or state, and run as non-root where practical. Prove the proposed container user can safely use the SQLite mount.
>
> Run the repository's normal checks, production build, native image build, fresh container startup, `/api/health`, representative API and browser behavior, persistence, graceful stop, and clean Git checks. Finish with the completed runtime contract and a self-contained infrastructure handoff. Identify any backup, migration, restore, authentication, or rollback gaps that must be resolved before parallel deployment.

