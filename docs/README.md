# Documentation

Use this index to find the right level of guidance.

Start with the [project README](../README.md). Operators should then read the
[Web UI guide](../giso-webui/README.md) and [operations runbook](operations.md).
Anyone preparing a router change must also use the
[GISO upgrade and rollback guide](../GISOBUILD-GUIDE.md).

| Document | Purpose |
| --- | --- |
| [Project README](../README.md) | Installation, first build, safety boundary, and project status |
| [Web UI guide](../giso-webui/README.md) | Configuration and application workflow |
| [GISO guide](../GISOBUILD-GUIDE.md) | Cisco IOS XR build, upgrade, validation, and rollback planning |
| [Platform support](platform-support.md) | Platform families, architectures, option rules, and USB expectations |
| [Operations](operations.md) | Start, stop, upgrade, backup, restore, retention, and troubleshooting |
| [Testing](testing.md) | Unit, staging, container, and licensed-ISO acceptance tests |
| [Release process](releasing.md) | Versioning and GitHub Container Registry publication |
| [Architecture](../ARCHITECTURE.md) | Components, trust boundaries, risks, and scaling decisions |
| [Security policy](../SECURITY.md) | Deployment boundary and vulnerability reporting |
| [Contributing](../CONTRIBUTING.md) | Worktrees, coordination, checks, and pull requests |

The staging simulator never contacts a router. For production changes, use the
exact Cisco documentation for the platform, source release, target release,
route processor, installed package set, and supported upgrade path.

Documentation describes application behavior on `main`. For an older deployed
version, select the matching Git tag before following its instructions.
