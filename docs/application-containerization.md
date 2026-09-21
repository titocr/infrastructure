# Add an application

1. In the application repository, implement an ARM64-compatible image, startup,
   meaningful readiness check and graceful shutdown. Keep host-specific settings
   out of the application. Complete the [runtime contract](runtime-contract.md).
2. Review the named commit: build and run without mounting source, identify every
   durable path and secret input, and establish migration and rollback behavior.
3. In infrastructure, add a candidate with separate data and a free loopback port.
   Exercise a real user flow, restart persistence, backup and isolated restore.
4. Present the production change: current backup, exact image/configuration,
   downtime, routing, migration limits, recovery trigger and ordered steps.
   Obtain any authorization not already supplied before executing it.
5. Verify the resulting service, authentication, data and startup behavior. Add its
   inventory entry, current runbook and dated evidence. Retain recovery artifacts
   under an explicit retention policy; cleanup is a separate operation.

## Reusable task handoff

```text
Prepare [APPLICATION] for this Mac Studio from [REPOSITORY AND COMMIT]. Read its
instructions and the infrastructure runtime contract. Inspect the current runtime.
Implement and verify the application image, then an isolated candidate with its
own data. Record build, user-flow, restart, backup and restore evidence. Update the
service documentation. Present any production, exposure or data changes requiring
additional authorization before executing them.
```

A handoff needs repository/commit references, the contract path, verification and
remaining gaps. It does not require copying a conversation. See
[responsibilities](concepts.md) for the shared operating conventions.
