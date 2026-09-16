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
- [x] archive maintenance cannot delete active artifact — fixed 2026-09-16.
      `cross_process_archive_lock()` in `giso-webui/app.py` takes an
      `fcntl.flock()` on `ARCHIVE/.lock`, a file on the volume both the
      `giso-webui` and `archive-maintenance` containers actually mount, and
      wraps `enforce_archive_policy()`, `archive_giso_artifacts_and_cleanup()`,
      `archive_list()`, `archive_checksums()`, and `archive_delete()`.
      `maintenance.py` needed no changes since it only calls
      `enforce_archive_policy()`, which now takes the lock internally.
      `archive_download()` (the byte-streaming response) is deliberately
      left unlocked — see the dated entry in `07-BUG-AUDIT-TODO.md` for why
      locking a large in-flight download would be a worse regression than
      the risk it removes. Verified by
      `test_cross_process_archive_lock_blocks_a_separate_os_process`, which
      spawns a real second OS process to prove this (a same-process
      threading test could not have caught the original bug), and by running
      the actual `docker compose` stack with both containers live against
      the shared volume.
- [x] Cisco download cannot collide with cleanup — `cleanup()` and
      `create_job()`/`upload_init()` all check `cisco_download_running()`
      first; `cisco_download_start()` itself checks `uploads` and active
      jobs. Verified by `test_cleanup_rejects_active_cisco_download`. (This
      guarantee is process-local only, which is sufficient here: Cisco
      downloads and cleanup both touch only `DATA`, which — unlike
      `ARCHIVE` — has exactly one writer process, the webui itself.)
- [x] restart recovery is deterministic — see "restart recovery" above.

## Path security

Audited 2026-09-16 against the real code (not a fresh implementation — this
formalizes protections that already existed, several with their own
regression tests already in `giso-webui/tests/test_app.py`):

Every path check in `giso-webui/app.py` follows the same pattern:
`(BASE / user_value).resolve()`, then containment via `.parents`/`==` on the
*resolved* `Path` object — never a naive string prefix check
(`str(path).startswith(str(BASE))`). That distinction matters for Unicode
normalization tricks below: `Path.resolve()` asks the real filesystem to
resolve the path, so whatever normalization/case-folding the OS itself
applies is already baked into both sides of the comparison before it
happens — there's no separate string-matching step for a crafted byte
sequence to slip past.

Audit every:

- [x] filename — `upload_name()` rejects any value where
      `value != Path(value).name` (i.e. anything containing a path
      separator) or that has a control character; `upload_complete()`
      auto-renames on any collision with an existing file or extraction
      directory rather than overwriting it.
- [x] relative path — `safe_data_path()` (used by `discover()`,
      `create_build_plan()`, `/api/file-preview`, ISO/RPM resolution) does
      `(DATA / value).resolve()` then requires `DATA in path.parents` (or
      `path == DATA`).
- [x] archive member — tar extraction in `upload_complete()` resolves each
      `member.name` against the destination and requires containment,
      rejects `member.issym()`/`member.islnk()` outright, and caps member
      count (`MAX_TAR_MEMBERS`) and expanded size (`MAX_EXTRACTED_BYTES`).
      The Cisco-download tar path (`cisco_download.py`) applies the same
      checks. Covered by `test_cisco_archive_extraction_rejects_path_traversal`,
      `test_cisco_archive_extraction_rejects_symlink_members`,
      `test_cisco_archive_extraction_enforces_member_count_limit`.
- [x] job ID — never used for direct filesystem access by itself; every
      route that takes a `<job_id>` (`/archive/<job_id>/...`,
      `/download/<job_id>/...`, `/api/archive/<job_id>/...`) joins it under
      `ARCHIVE`/`OUTPUT`, resolves, and checks parents before touching disk
      — a `job_id` of `..` simply resolves outside `ARCHIVE`/`OUTPUT` and
      fails the containment check, same as any other traversal attempt.
      `/api/jobs/<job_id>` only ever does a `jobs.get(job_id)` dict lookup,
      no filesystem access at all.
- [x] artifact path — `archive_download`/`download`/`archive_delete`/
      `archive_checksums` all resolve the requested name under
      `ARCHIVE`/`OUTPUT` and check parents before calling
      `send_from_directory()` or touching the file; `archive_delete` and
      `archive_checksums` additionally restrict to `.iso`/`.zip` suffixes.
      Covered by `test_archive_delete_rejects_path_traversal`,
      `test_symlink_build_artifact_is_rejected`.

Protect against:

- [x] `../` — every check above compares the *resolved* path, so `../`
      anywhere in the input collapses during `.resolve()` before the
      containment check runs; it can't produce a false "contained" result.
- [x] absolute paths — `safe_data_path()` does `value.lstrip("/")` first;
      `upload_name()` separately rejects any value that isn't a bare
      filename (which includes absolute paths, since `Path(value).name`
      would strip everything but the last segment).
- [x] symlink escapes — tar/zip extraction rejects symlink/hardlink
      members outright (see "archive member" above); archived build
      artifacts are rejected if `source.is_symlink()`
      (`archive_giso_artifacts_and_cleanup`), covered by
      `test_symlink_build_artifact_is_rejected`.
- [x] Unicode normalization tricks — not handled by a dedicated check, but
      not exploitable either: every containment check compares fully
      *resolved* `Path` objects (see above), so there is no string-equality
      step for two differently-normalized-but-equivalent byte sequences to
      disagree on.
- [x] duplicate aliases — `upload_complete()` auto-renames
      (`{stem}-{uuid8}{suffix}`) on any filename collision with an existing
      file or in-progress extraction directory, so an upload can never
      silently overwrite or shadow another file by name; package identity
      in `resolve_rpm_identifiers()`/`recommend_smu_selection()` is
      SHA-256-based, not filename-based, so two files with the same or
      confusable names are never treated as the same package unless their
      contents actually match.

## Cisco secrets

Audited 2026-09-16 — all already true, no code change needed:

- [x] never return secrets to browser — no route ever `jsonify()`s
      `client_id`/`client_secret`/an OAuth token; `CiscoSoftwareClient`
      keeps its `_access_token` as a private instance attribute, never
      copied into a `jobs`/`cisco_download_jobs` dict or a response body.
- [x] never log secrets — every `log_event("cisco_*", ...)` call
      (`cisco_search_failed`, `cisco_search_completed`,
      `cisco_download_completed`, `cisco_download_failed`) passes only
      counts/ids/error types, never a credential or token value.
- [x] never store secrets in jobs — `cisco_download_jobs[job_id]` holds
      `id`/`status`/`progress`/`files`/`error`/`created` only; the OAuth
      token lives solely on the `CiscoSoftwareClient` instance
      (`cisco_download.py`), not in any persisted job dict.
- [x] never bake secrets into image — `giso-webui/compose.yaml` passes
      `CISCO_CLIENT_ID`/`CISCO_CLIENT_SECRET` (and their `_FILE`
      counterparts) through `${VAR:-}` with empty defaults; the Dockerfile
      declares no `ARG`/`ENV` default for either.
- [x] prefer secret files — `secret_value()` in `cisco_download.py` reads
      `<NAME>_FILE` first (a mounted Docker secret file) and only falls
      back to the plain `<NAME>` env var; `compose.yaml` mounts
      `${CISCO_SECRETS_DIR:-./secrets}` at `/run/secrets` for this.
- [x] browser sees only configured yes/no — the only client-visible signal
      is `enabled = bool(secret_value("CISCO_CLIENT_ID") and
      secret_value("CISCO_CLIENT_SECRET"))`, never the values themselves.

## Structured logging

Every event should support:

- [x] event — every `log_event()` call names itself (`build_started`,
      `http_request`, `upload_completed`, ...); it's the log line's own
      `event=` field.
- [x] request_id — `after_request` in `giso-webui/app.py` logs
      `event=http_request ... request_id=<id>` for every HTTP request
      (echoed back as the `X-Request-ID` response header too); verified by
      `test_request_log_uses_endpoint_and_safe_correlation_id`. Background
      job events (`build_started`, etc.) have no HTTP request to hang a
      request_id off of — `job_id` is their correlating key instead, which
      is a genuine difference in kind, not a gap.
- [x] job_id — every job/upload/download-lifecycle `log_event()` call
      already passes it (`build_started`, `build_progress`,
      `build_finished`, `build_cancelled`, `build_failed`,
      `build_setup_failed`, `upload_started`, `cisco_download_completed`,
      ...).
- [x] inventory_revision / plan_fingerprint — added 2026-09-16.
      `create_job()` already computed both per `create_build_plan()`'s
      immutable BuildPlan, but they weren't on the build-lifecycle log
      events themselves, only inside job state — so a log-based audit
      trail couldn't tie a given build's logs back to the exact inventory
      snapshot and BuildPlan it ran against. `run_job()` now reads both
      once from the job dict at entry and attaches them to
      `build_started`/`build_finished`/`build_cancelled`/`build_failed`;
      `build_setup_failed` (raised in `create_job()`, before `run_job()`
      starts) gets them directly from the just-computed `plan`. Verified by
      `test_build_events_are_logged_with_inventory_revision_and_plan_fingerprint`
      in `giso-webui/tests/test_app.py`, which asserts on the real captured
      log lines from a simulated successful build.
- [x] duration — added 2026-09-16 alongside the above: `build_finished`,
      `build_cancelled` and `build_failed` now log `duration_ms` (wall
      time since the job's `created` timestamp). `http_request` already
      logged `elapsed_ms` for the same purpose on every HTTP request.
- [x] result — `build_finished` already logs `status=` (`success`/
      `failed`); `http_request` already logs `status=` (the HTTP status
      code); `build_failed`/`build_setup_failed`/`cisco_search_failed`/
      `cisco_download_failed`/`upload_archive_failed` already log
      `error_type=`.

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
