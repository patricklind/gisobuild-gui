# TODO — Self-contained Docker Image

## Goal

Production deployment should require only:

```bash
docker compose up -d
```

No:

- [ ] separate `ios-xr/gisobuild` checkout
- [ ] `.gisobuild-tool` bind mount
- [ ] `/var/run/docker.sock`
- [ ] child Docker builder container
- [ ] manual pull of a Cisco builder image

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

### Stage 3 — application

- [ ] copy web app
- [ ] copy pinned gisobuild source
- [ ] install web Python dependencies
- [ ] add version metadata
- [ ] add health/readiness checks

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

Current architecture must be replaced with a local runner.

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

Invocation concept:

```bash
python /opt/gisobuild/src/gisobuild.py ...
```

## Security

- [ ] no Docker socket
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

- [ ] one primary service
- [ ] persistent volumes
- [ ] secrets mounted as files
- [ ] healthcheck
- [ ] readiness check
- [ ] no Docker socket
- [ ] no external tool checkout

## Optional publishing

Prepare for:

- [ ] `ghcr.io/patricklind/gisobuild-gui:<version>`
- [ ] `ghcr.io/patricklind/gisobuild-gui:latest`
