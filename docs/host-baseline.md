# Hardware and capacity

Verified on **2026-09-21** using macOS hardware reports, Docker and OrbStack
configuration. No serial numbers or unique hardware identifiers are recorded.

## Physical host

| Item | Verified specification |
| --- | --- |
| Computer | Mac Studio, model Mac14,13 |
| Chip / architecture | Apple M2 Max / arm64 |
| CPU | 12 cores: 8 performance + 4 efficiency |
| GPU | 30 cores |
| Unified memory | 32 GB, shared by CPU and GPU |
| Internal SSD | APPLE SSD AP0512Z; 500.28 GB reported physical capacity |
| macOS | 26.6.2, build 25G83 |

The SSD capacity above is the physical device report, not available application
space. APFS volumes share container capacity; do not add their free-space figures.

## Container runtime

| Item | Verified value |
| --- | --- |
| Runtime | OrbStack 2.2.3 |
| Docker client / engine | 29.4.0 / 29.4.0 |
| Docker Compose | 5.1.2 |
| OrbStack allocation | Up to 12 CPUs and 16 GiB RAM |
| Start at login | Enabled |
| Docker LAN port exposure | Disabled in OrbStack settings |
| Kubernetes | Disabled |
| Pause in sleep | Enabled |

The 16 GiB runtime allocation is a configured ceiling, not the Mac's total memory
or reserved capacity for each service. macOS, desktop tools, builds and containers
share the machine. Sleep may interrupt service availability. Login startup is not
a guarantee of availability before the user logs in.

Loopback publication does not prove strict container isolation: OrbStack direct
container access remains possible. [OSCAR](projects/cpap-monitor-runtime.md)
documents its accepted access limitations. Options Finder is a native LAN listener
and is not governed by Docker's LAN setting.

## Capacity snapshot

On **2026-09-21**, `df -h /System/Volumes/Data` reported a 460 GiB filesystem,
245 GiB used and 194 GiB available. These are observations, not current free space.
Recheck before large builds, imports, backups or model downloads.

```sh
df -h /System/Volumes/Data
docker system df
docker stats --no-stream
```

Use Activity Monitor for memory pressure and CPU history. Do not infer headroom
from the configured runtime maximum or run global Docker cleanup to reclaim space.

## Refresh the baseline

```sh
sw_vers
uname -m
system_profiler SPHardwareDataType SPDisplaysDataType SPNVMeDataType
orb version
orb config list
docker version
docker compose version
```

Hardware reports can include serial numbers; transcribe only the fields above.
Update the verification date only for facts actually checked. The [inventory](services.md)
covers workloads; [recovery](recovery.md) covers restart behavior.
