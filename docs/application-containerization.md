# Application container onboarding

Updated: 2026-08-28

Use this document when preparing any application repository for deployment as containers on the Mac Studio. The application repository owns the image; this infrastructure repository owns how the image runs on this host.

## Mac Studio host contract

- Target platform: Apple Silicon, `linux/arm64`.
- Runtime: OrbStack 2.2.3, Docker Engine 29.4.0, Docker Compose 5.1.2.
- Kubernetes is not enabled.
- OrbStack starts at macOS login.
- OrbStack's global Docker LAN exposure is disabled.
- Published ports bind to `127.0.0.1` unless broader access is explicitly reviewed and documented.
- Runtime images are pinned to a tested repository digest.
- Image updates are reviewed and applied deliberately; unattended container replacement is disabled.
- Secrets stay out of Git and out of image layers.
- Host-managed persistent data belongs under `/Users/titocr/container-data/<service>`.
- Existing production deployments remain intact until a parallel container candidate passes verification and has an explicit rollback plan.

Revalidate versions and available capacity before relying on this snapshot for a future deployment.

## Ownership boundary

### Application repository owns

- `Dockerfile` or Dockerfiles and `.dockerignore`.
- Production compilation and runtime entry point.
- Base-image selection and supported architecture.
- Container-internal port and meaningful health endpoint.
- Environment-variable, secret, volume, and migration contract.
- Graceful shutdown behavior.
- Application tests and container build verification.
- Documentation sufficient for an operator to build and run the image without reading implementation code.

### Infrastructure repository owns

- Mac Studio Compose definitions and project naming.
- Loopback host-port assignment and any Tailscale Serve integration.
- Production environment and secret injection.
- Host bind-mount paths and directory preparation.
- Tested image digest.
- Backup, restore, update, rollback, and health-check operations.
- Parallel deployment, cutover, and removal of superseded host services.

Do not maintain competing production Compose definitions in both repositories. An application repository may include a development-only Compose file, but it must be clearly labeled and must not claim ownership of Mac Studio paths or secrets.

## Runtime contract template

The application project must return a completed version of this contract:

```text
Application:
Image name:
Supported architecture:
Build command:
Container startup command:
Container port:
Health endpoint:
Expected healthy response:
Environment variables:
Secrets:
Persistent mounts:
Container user and file ownership:
Migration command and ordering:
Backup and restore requirements:
Graceful shutdown expectations:
Verification commands:
Known rollback constraints:
```

Unknown items must be called out rather than silently omitted.

## Application review checklist

Before writing a Dockerfile, inspect the real production topology:

- Is it a static web application, or does production also require a server, API, database, worker, scheduler, or migration process?
- Does one image contain the coherent runtime, or are multiple services required?
- Can it build and run natively on `linux/arm64`?
- Which process should serve built frontend assets? A development server is not a production runtime.
- Which files must persist across container replacement?
- Which configuration values are secrets, and when are they read?
- What proves readiness beyond a process merely listening on a port?
- What happens on `SIGTERM`, and how long may graceful shutdown take?
- Can the image run as a non-root user without breaking bind-mounted data?
- Do schema migrations preserve rollback compatibility?

## Delivery sequence

1. Review the application and propose the smallest coherent containerization slice.
2. Add and test application-owned image artifacts without changing the live deployment.
3. Return the completed runtime contract.
4. Add the host Compose stack, secrets, data paths, and runbook in this repository.
5. Start the candidate on a separate loopback port with non-production or safely copied data.
6. Verify health, representative application behavior, restart recovery, backup, restore, and rollback.
7. Cut over host routing only after the candidate passes and the prior deployment remains recoverable.
8. Remove the superseded deployment in a separate, explicit cleanup step.

## Verification standard

At minimum, record evidence for:

- Normal repository formatting, linting, type checking, tests, and production build.
- A native `linux/arm64` image build.
- Clean container startup from a newly created instance.
- Health endpoint success and representative application behavior.
- Secrets absent from the image history and committed files.
- Graceful stop and automatic recovery after an OrbStack restart.
- Correct persistence across container replacement.
- A successful backup and restore rehearsal for stateful services.
- Loopback-only reachability unless another exposure boundary was approved.
- Clean Git state in both repositories after the deployment.

## Reusable request for an application project

> Review this repository's actual runtime architecture before making changes. The target is a Mac Studio running OrbStack on Apple Silicon, so production images must run natively on `linux/arm64`.
>
> Start with a review, revision, and planning step. Determine the complete production topology and propose the smallest coherent containerization change. The application repository owns its Dockerfile, `.dockerignore`, production image, startup command, health endpoint, tests, and runtime contract. A separate infrastructure repository owns host-specific Compose configuration, paths, secrets, loopback ports, image digests, backups, and cutover.
>
> Use a production runtime rather than a development server. Pin base-image versions, keep secrets out of image layers, run as non-root where practical, document persistent state and migrations, and preserve graceful shutdown. Keep the existing deployment intact while testing the container candidate in parallel. Do not change live routing or production data during the application-containerization task.
>
> Verify the normal repository checks, production build, native `linux/arm64` image build, fresh container startup, health endpoint, representative behavior, and graceful stop. Finish with the completed runtime contract from the Mac Studio infrastructure guide, plus remaining host-integration and cutover work.

