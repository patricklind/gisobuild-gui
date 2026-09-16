# TODO — State, Security & Observability

## Persistent state

SQLite is acceptable for a single-node appliance.

Persist:

- [x] jobs — `persist_job()`/`initialize_job_store()` in `giso-webui/app.py`
      write each job's full record (including its `build_plan` and
      `plan_fingerprint`) to the `jobs` table in `JOB_DB` (sqlite), capped at
      `MAX_JOB_HISTORY`.
- [ ] inventory — not stored in a database; deliberately recomputed live from
      the filesystem on every request (`inventory_files()`), which is itself
      a form of correctness (no cached copy can go stale relative to the
      files an operator actually uploaded/deleted). Genuinely no separate
      inventory index exists, so a restart cost is a rescan, not data loss.
- [ ] metadata cache — `checksum_cache` and `iso_architecture_cache` are
      in-memory dicts only; lost on restart and rebuilt lazily on next
      access (a cost, not a correctness bug).
- [ ] BuildPlans — a plan attached to a started job is persisted as part of
      that job's record (see "jobs" above); a plan reviewed via
      `/api/build-plan` but never submitted as a job is not persisted
      anywhere, by design (it is a stateless preview).
- [x] activity log — `append_activity()`/`/api/activity` read and write the
      `activity` table in `JOB_DB`, capped at 500 rows.
- [ ] artifact metadata — no separate table; `archive_list()` derives
      artifact listings directly from the `ARCHIVE` directory on disk, and
      per-job `artifacts` entries are persisted as part of the job record.
- [ ] inventory revision — not stored globally; recomputed on demand
      (`current_inventory_revision()`) and persisted per-job as
      `job["inventory_revision"]` once a build starts.

- [ ] schema migrations — the `jobs`/`activity` tables are created with
      `CREATE TABLE IF NOT EXISTS` and never altered; there is no migration
      mechanism, so a future schema change would need one.
- [x] restart recovery — `initialize_job_store()` marks any job restored
      from `JOB_DB` in an `ACTIVE_JOB_STATUSES` state as `"interrupted"`,
      redacts its log, and persists that transition, so no job is silently
      left `"running"` forever after a restart. Verified by
      `test_active_job_is_marked_interrupted_after_restart` and
      `test_expired_orphan_partial_upload_is_removed_after_restart` in
      `giso-webui/tests/test_app.py`.
- [ ] no critical state only in Python globals — partially true: jobs and
      activity are durable (sqlite), but `uploads`, `cisco_searches`, and
      `cisco_download_jobs` are process-local dicts with no persistence, so
      a restart mid-upload or mid-Cisco-download silently drops that
      in-progress state (the operator sees it as if it never started, rather
      than as a recorded failure).

## Job model

Explicit states:

- [x] queued
- [ ] analyzing — no distinct state; covered by `"queued"` with
      `phase="Validating inputs"` until `create_build_plan()` finishes.
- [ ] preflight — no distinct state; the BuildPlan check happens before a
      job is created at all (`/api/build-plan`/`create_job()`), not as a
      job-visible state.
- [x] building — implemented as `status="running"` plus a human-readable
      `phase` string that tracks real log milestones (`append_log()`'s
      `milestones` table: "Scanning update packages", "Building Golden ISO",
      etc.), not as a separate `status` enum value. Verified by
      `test_build_progress_follows_real_log_milestones`.
- [ ] verifying — no distinct state; artifact verification
      (`giso_artifact_candidates`/checksum comparison) happens synchronously
      inside the "finalizing"/"committing" transition, not as its own
      job-visible status.
- [ ] archiving — no distinct state; covered by `status="finalizing"` /
      `"committing"` in `run_job()`/`prepare_destructive_finalization()`.
- [x] success
- [x] failed
- [x] cancelling
- [x] cancelled
- [x] interrupted — set by `initialize_job_store()` on restart for any job
      found in an active status. Verified by
      `test_active_job_is_marked_interrupted_after_restart`.

The actual state machine (`queued` → `running` → `finalizing`/`committing` →
`success`/`failed`/`cancelled`/`interrupted`, with `cancelling` as a
transient request-to-cancel marker) uses a coarser `status` plus a free-text
`phase` for detail, rather than the finer-grained named states this list
originally proposed. This is a deliberate two-field design, not a partial
implementation of the list above — `analyzing`/`preflight`/`verifying`/
`archiving` were never built as literal `status` values and are not planned
to be; the `phase` field already carries that detail to the UI.

## Concurrency

Guarantee:

- [x] build/upload cannot corrupt same inventory — `upload_lock`, `job_lock`
      and `operation_lock` in `giso-webui/app.py` gate `create_job()`,
      `upload_init()`, `cisco_download_start()` and `delete_upload()` against
      each other. This holds because the `giso-webui` process is the only
      writer of `DATA`/`WORK`/`OUTPUT` — see the cross-process caveat below
      for the one directory (`ARCHIVE`) with a second writer.
- [x] cleanup cannot remove active inputs — `/api/cleanup` refuses while a
      job is in `ACTIVE_JOB_STATUSES`, an upload is in progress, or a Cisco
      download is running. Verified by `test_cleanup_rejects_active_upload`,
      `test_cleanup_rejects_running_build`.
- [ ] archive maintenance cannot delete active artifact — **not actually
      guaranteed; still open.** `enforce_archive_policy()` and
      `archive_giso_artifacts_and_cleanup()` synchronize against each other
      only via `archive_lock`, an in-process `threading.RLock()`. But
      `docker-compose.yaml` runs a second, separate OS process/container
      (`archive-maintenance`, `giso-webui/maintenance.py`) that imports and
      calls the same `enforce_archive_policy()` against the same `ARCHIVE`
      volume — a `threading.RLock()` provides zero mutual exclusion between
      two different processes. `archive_download()` (streaming a file to a
      browser) and `archive_checksums()`/`archive_delete()` also touch
      `ARCHIVE` without any lock a separate process would respect. In
      practice this means the maintenance container's hourly quota/retention
      sweep can run concurrently with the webui process archiving a
      just-finished build or a browser mid-download, with no coordination
      between them. The realistic failure mode is a corrupted/partial
      download or an eviction decision made from a torn directory listing,
      not silent data corruption of a completed archive file itself (writes
      only ever happen once, at archive time, before the file is exposed).
      A real fix needs a lock primitive both processes actually share (e.g.
      an `fcntl.flock()` on a file inside the shared `ARCHIVE` volume), which
      has not been implemented.
- [x] Cisco download cannot collide with cleanup — `cleanup()` and
      `create_job()`/`upload_init()` all check `cisco_download_running()`
      first; `cisco_download_start()` itself checks `uploads` and active
      jobs. Verified by `test_cleanup_rejects_active_cisco_download`. (This
      guarantee is process-local only, which is sufficient here: Cisco
      downloads and cleanup both touch only `DATA`, which — unlike
      `ARCHIVE` — has exactly one writer process, the webui itself.)
- [x] restart recovery is deterministic — see "restart recovery" above.

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
