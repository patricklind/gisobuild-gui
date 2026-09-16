# TODO — State, Security & Observability

## Persistent state

SQLite is acceptable for a single-node appliance.

Persist:

- [ ] jobs
- [ ] inventory
- [ ] metadata cache
- [ ] BuildPlans
- [ ] activity log
- [ ] artifact metadata
- [ ] inventory revision

- [ ] schema migrations
- [ ] restart recovery
- [ ] no critical state only in Python globals

## Job model

Explicit states:

- [ ] queued
- [ ] analyzing
- [ ] preflight
- [ ] building
- [ ] verifying
- [ ] archiving
- [ ] success
- [ ] failed
- [ ] cancelling
- [ ] cancelled
- [ ] interrupted

## Concurrency

Guarantee:

- [ ] build/upload cannot corrupt same inventory
- [ ] cleanup cannot remove active inputs
- [ ] archive maintenance cannot delete active artifact
- [ ] Cisco download cannot collide with cleanup
- [ ] restart recovery is deterministic

## Path security

Audit every:

- [ ] filename
- [ ] relative path
- [ ] archive member
- [ ] job ID
- [ ] artifact path

Protect against:

- [ ] `../`
- [ ] absolute paths
- [ ] symlink escapes
- [ ] Unicode normalization tricks
- [ ] duplicate aliases

## Cisco secrets

- [ ] never return secrets to browser
- [ ] never log secrets
- [ ] never store secrets in jobs
- [ ] never bake secrets into image
- [ ] prefer secret files
- [ ] browser sees only configured yes/no

## Structured logging

Every event should support:

- [ ] request_id
- [ ] job_id
- [ ] inventory_revision
- [ ] plan_fingerprint
- [ ] event
- [ ] duration
- [ ] result

## Error taxonomy

Implement codes such as:

- [ ] `UPLOAD_ERROR`
- [ ] `ARCHIVE_ERROR`
- [ ] `ISO_METADATA_ERROR`
- [ ] `PLATFORM_AMBIGUOUS`
- [ ] `RELEASE_MISMATCH`
- [ ] `RPM_METADATA_ERROR`
- [ ] `RPM_ARCH_MISMATCH`
- [ ] `CSC_INCOMPLETE`
- [ ] `DUPLICATE_CONFLICT`
- [ ] `DEPENDENCY_ERROR`
- [ ] `GISOBUILD_ERROR`
- [ ] `OUTPUT_VALIDATION_ERROR`
- [ ] `STORAGE_ERROR`
- [ ] `CISCO_AUTH_ERROR`

Return:

- [ ] code
- [ ] human_message
- [ ] technical_message
- [ ] recoverable
- [ ] suggested_action

## Health and readiness

Implemented: `/api/health` and `/api/ready` are now separate endpoints in
`giso-webui/app.py`. Previously a single `/api/health` conflated liveness
with dependency readiness, so a Docker/storage/tool hiccup looked like a
crashed process to an orchestrator. The Dockerfile `HEALTHCHECK` now points
at `/api/ready` (the container-restart-worthy check); `/api/health` is for a
liveness probe that should not trigger a restart on its own. Verified by
`test_health_is_pure_liveness_and_ignores_dependency_state` and
`test_ready_reports_database_and_disk_checks` in `giso-webui/tests/test_app.py`,
run inside the built container image, plus a live smoke test
(`curl /api/health` → `200` always; `curl /api/ready` → `503` with per-check
detail when a dependency, here the missing `.gisobuild-tool` checkout, is
unavailable).

### `/api/health`

- [x] process alive

### `/api/ready`

- [x] storage
- [x] gisobuild (checked via `TOOL/src/gisobuild.py`; this is the *current*
      external-checkout model, not the bundled runtime the self-contained
      image TODO targets)
- [x] binaries (`docker info` — the only external binary the current
      Docker-socket-based build runner depends on)
- [x] DB/state (`SELECT 1` against `JOB_DB`)
- [x] free disk (`shutil.disk_usage(DATA).free >= MIN_FREE_BYTES`, the same
      threshold already used before uploads/extraction)
- [ ] no fatal startup error (there is no dedicated startup-error flag to
      report yet; a truly fatal startup error currently prevents the process
      from serving requests at all, so `/api/ready` never gets called at all)

## Startup self-test

- [ ] gisobuild exists
- [ ] required binaries exist
- [ ] DB schema valid
- [ ] writable directories
- [ ] alias/config data valid
- [ ] minimum free storage
- [ ] architecture supported

## Caching

Cache expensive metadata by:

- [ ] path
- [ ] size
- [ ] mtime
- [ ] checksum where known

Do not repeatedly rehash multi-GB files on browser refresh.
