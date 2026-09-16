# TODO — Self-contained Docker Image

## Goal

Production deployment and local development must require only Docker/Compose plus Git/editor/browser on the host.

Target production startup:

```bash
docker compose up -d
```

The user's local computer must never become part of the application runtime or project toolchain.

No host-side project execution:

- [ ] no host Python/pip/pytest/Ruff
- [ ] no host Node/npm/pnpm/yarn project tooling
- [ ] no host Graphify
- [ ] no host gisobuild execution
- [ ] no host IOS-XR ISO/RPM inspection tools
- [ ] no host staging/rehearsal scripts
- [ ] no host database migration/maintenance commands
- [ ] no host package installation for project dependencies
- [ ] no host release/build/security tooling

No external runtime dependencies:

- [ ] separate `ios-xr/gisobuild` checkout
- [ ] `.gisobuild-tool` bind mount
- [ ] `/var/run/docker.sock` in the final target architecture
- [ ] child Docker builder container in the final target architecture
- [ ] manual pull of a Cisco builder image

## Docker-only enforcement

Make the Docker-only rule enforceable rather than documentation-only.

- [ ] inventory every README, script, Makefile/task file, CI command, developer guide, and agent instruction for host-side project commands
- [ ] replace host `python`, `pytest`, staging, Graphify, lint, audit, frontend, and build examples with `docker compose run`, `docker compose exec`, or dedicated tooling-container commands
- [ ] add a documented developer command set for common operations
- [ ] add a dedicated tooling/test service or image where the application image is not appropriate
- [ ] ensure Graphify runs in Docker
- [ ] ensure staging/rehearsal runs in Docker
- [ ] ensure integration and unit tests run in Docker
- [ ] ensure linters/security scanners/dependency audits run in Docker or dedicated CI containers
- [ ] ensure database migrations run in Docker
- [ ] ensure all IOS-XR/gisobuild inspection and build commands run in Docker
- [ ] add CI/static checks that flag new documentation/scripts which invoke known project tooling directly on the host where practical
- [ ] document that missing container dependencies must be fixed in Dockerfiles rather than installed on the workstation

Host-side operations may be limited to Docker/Compose lifecycle, Git/source-control operations, editor/browser usage, and Git/worktree coordination helpers that are proven not to execute project runtime/tooling code.

## Build the image around upstream gisobuild requirements

Study:

- [ ] upstream `Dockerfile`
- [ ] `setup/prep_dependency.sh`
- [ ] `src/gisobuild.py`
- [ ] eXR dependencies
- [ ] LNT dependencies

Use a compatible Linux base.

## Multi-stage image

Suggested stages:

### Stage 1 — source

- [ ] pin upstream gisobuild commit
- [ ] record repository URL
- [ ] record commit SHA
- [ ] optionally verify expected source hash

### Stage 2 — dependencies

- [ ] install gisobuild system dependencies
- [ ] ISO utilities
- [ ] RPM utilities
- [ ] archive utilities
- [ ] Python/runtime dependencies
- [ ] include all test/runtime utilities needed so the host never needs them

### Stage 3 — application

- [ ] copy web app
- [ ] copy pinned gisobuild source
- [ ] install web Python dependencies
- [ ] add version metadata
- [ ] add health/readiness checks

### Optional Stage / Service — tooling

Provide a dedicated container where appropriate for development-only tooling that should not bloat production runtime.

- [ ] Graphify
- [ ] Ruff/linting
- [ ] dependency/security auditing
- [ ] staging/rehearsal
- [ ] developer utilities
- [ ] frontend tooling if applicable

The tooling container must use the repository through a controlled bind mount and must not install dependencies on the host.

## Runtime layout

Suggested:

```text
/opt/app
/opt/gisobuild
/data/uploads
/data/work
/data/archive
/data/state
```

- [ ] application files read-only
- [ ] persistent archive/state volumes
- [ ] temporary work separated
- [ ] uploads separated

## Replace nested Docker

Current architecture must be replaced with a local runner **inside the application/build container**, not on the host.

Implement `GisoBuildRunner`.

- [ ] version detection
- [ ] ISO inspection
- [ ] capability detection
- [ ] command generation
- [ ] execution
- [ ] stdout/stderr capture
- [ ] cancellation
- [ ] exit classification
- [ ] artifact discovery

Invocation concept inside the container:

```bash
python /opt/gisobuild/src/gisobuild.py ...
```

This command must never be required on the user's host.

## Security

- [ ] no Docker socket in the final architecture
- [ ] no `shell=True`
- [ ] sanitized environment
- [ ] explicit allowed paths
- [ ] process group isolation
- [ ] non-root where possible
- [ ] document root requirements if unavoidable
- [ ] `no-new-privileges`
- [ ] drop unnecessary capabilities
- [ ] read-only root filesystem where practical
- [ ] controlled writable mounts only
- [ ] no installation or modification of host system packages
- [ ] no dependency on host `/usr`, `/opt`, `/etc`, Python site-packages, Node modules, or shell configuration

## Cancellation

- [ ] graceful process-group termination
- [ ] timeout
- [ ] forced termination if needed
- [ ] no orphan processes
- [ ] cleanup work directory
- [ ] persist `cancelled`

## Version endpoint

Implement `/api/version`.

Return:

- [ ] app version
- [ ] app git SHA
- [ ] gisobuild repository
- [ ] gisobuild commit
- [ ] gisobuild version
- [ ] image version
- [ ] schema version

## Reproducibility

- [ ] pin base-image digest
- [ ] pin Python dependencies
- [ ] pin gisobuild commit
- [ ] image labels
- [ ] SBOM
- [ ] build timestamp
- [ ] source revision

## Compose

- [ ] one primary runtime service where practical
- [ ] dedicated tooling/test service if needed
- [ ] persistent volumes
- [ ] secrets mounted as files
- [ ] healthcheck
- [ ] readiness check
- [ ] no Docker socket in the final architecture
- [ ] no external tool checkout
- [ ] commands for test/lint/Graphify/staging that execute entirely inside containers
- [ ] no requirement for host Python, Node, RPM tools, ISO tools, or gisobuild dependencies

## Developer experience acceptance criteria

A new developer or AI coding agent with only Git and Docker available should be able to perform all supported project work without installing language runtimes or project tools on the host.

Expected patterns:

```bash
docker compose build
docker compose up -d
docker compose run --rm <tooling-service> <test-command>
docker compose run --rm <tooling-service> <graphify-command>
docker compose exec <service> <maintenance-command>
```

- [ ] document all common commands
- [ ] verify clean-machine workflow with no host Python/Node/project packages
- [ ] verify local test suite entirely in containers
- [ ] verify Graphify entirely in containers
- [ ] verify staging/rehearsal entirely in containers
- [ ] verify real gisobuild workflow requires no host tooling other than Docker

## Optional publishing

Prepare for:

- [ ] `ghcr.io/patricklind/gisobuild-gui:<version>`
- [ ] `ghcr.io/patricklind/gisobuild-gui:latest`
