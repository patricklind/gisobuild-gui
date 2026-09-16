# TODO — Automation, Inventory & BuildPlan

## Canonical inventory

Create one canonical inventory model.

- [x] every ready file receives a stable path-and-checksum ID
- [x] basename
- [x] relative path
- [ ] absolute path — deliberately not exposed: `inventory_id()`/`rel_data()`
      only ever return the checksum-based ID and the path relative to
      `DATA`, so the browser never learns the container's real filesystem
      layout. Treat this as intentionally out of scope, not an oversight.
- [x] size
- [x] SHA-256
- [ ] source (`upload`, `tar`, `cisco-download`) — partially implemented:
      `inventory_files()` only distinguishes `"tar"` (inside an extracted
      directory) from `"upload"` (a direct child of `DATA`). A
      Cisco-downloaded file also lands as a direct child of `DATA`
      (`run_cisco_download()`'s `target = DATA / name`), so it is
      indistinguishable from a manual upload today — there is no persistent
      record of which files came from a Cisco download. Low priority: no
      frontend code reads this field at all yet, so nothing currently
      depends on the distinction.
- [x] metadata source/confidence (currently explicit low-confidence filename metadata)
- [ ] lifecycle state

Suggested lifecycle:

- [ ] `UPLOADING`
- [x] `READY`
- [ ] `ANALYZING`
- [ ] `VALID`
- [ ] `INVALID`
- [ ] `IN_USE`
- [ ] `ARCHIVED`
- [ ] `DELETING`

## ISO inspection

Progress: `giso-webui/app.py:inspect_iso_architecture()` now performs real
`isoinfo`-based ISO inspection (see `07-BUG-AUDIT-TODO.md`), but only for the
single "architecture" field below, not the full release/platform/engine
model this section describes. Do not check off "upstream gisobuild
inspection/isoinfo" below until release and platform detection are also
metadata-driven instead of filename-driven.

Detection order:

- [ ] ISO metadata
- [ ] upstream gisobuild inspection/isoinfo
- [ ] image/package metadata
- [ ] known platform signatures
- [ ] hardware PID mapping
- [ ] filename inference
- [ ] manual override

Return:

- [x] release — `create_build_plan()`/`discover()` `"release"` field
- [x] platform identifier — `"platform"` field
- [x] engine — `"engine"` field (derived from platform, not independently
      detected — see `detected_by` below)
- [x] architecture — `"iso_architecture"` confidence entry plus
      `validate_smu_selection()`'s `"iso_architectures"` list
- [x] detected_by — implemented as `confidence.<field>.source` (added
      2026-09-16 alongside the confidence display fix): `"iso-filename-pattern"`
      for platform/release, `"iso-contents"` for architecture,
      `"operator-selected"` when the operator picked the platform manually.
      Engine and CSC grouping don't get an independent `detected_by` — engine
      is derived from platform's own detection, and CSC grouping's source is
      always `"rpm-filename-pattern"` (see `confidence_report()` in
      `giso-webui/app.py`).
- [x] confidence — `confidence_report()`, see "Confidence display" in
      `06-UI-OPERATOR-TODO.md` for the full honesty accounting of what is
      actually `VERIFIED` versus `INFERRED` today.

## RPM inspection

Prefer metadata over filename parsing.

- [ ] RPM name
- [ ] version
- [ ] release
- [ ] architecture
- [ ] provides
- [ ] requires
- [ ] signature metadata where available
- [ ] CSC ID
- [ ] component
- [ ] metadata confidence

## TAR/TGZ handling

Two independent implementations share these rules: `upload_complete()` (an
operator-uploaded `.tar`/`.tgz`) and `extract_cisco_archive()` (a
Cisco-downloaded archive). Both are now covered.

- [x] safe extraction (`test_chunked_upload_and_safe_tar_extraction`,
      `test_cisco_archive_extraction_succeeds_for_a_safe_archive`)
- [x] reject traversal (`test_tar_path_traversal_is_rejected`,
      `test_cisco_archive_extraction_rejects_path_traversal`)
- [x] reject symlinks/hardlinks (`test_tar_symlink_member_is_rejected`,
      `test_tar_hardlink_member_is_rejected`,
      `test_cisco_archive_extraction_rejects_symlink_members`)
- [x] expansion-size limit (`test_tar_expansion_size_limit_is_enforced`;
      `extract_cisco_archive()`'s equivalent `MAX_EXTRACTED_BYTES` check has
      no dedicated test yet, only the upload path does)
- [x] member-count limit — fixed 2026-09-16: `MAX_TAR_MEMBERS` had
      protective code in both implementations but neither was ever
      exercised by a test. Added `test_tar_member_count_limit_is_enforced`
      and `test_cisco_archive_extraction_enforces_member_count_limit`.
- [x] source provenance (`test_inventory_reports_extracted_from_source_archive`)
- [x] no duplicate extraction (`test_reupload_does_not_overwrite_existing_extracted_directory`)
- [x] automatically inventory extracted RPMs — `inventory_files()` walks all
      of `DATA` recursively with no special-casing for extracted
      directories, so an extracted RPM appears in `/api/inputs` the same as
      an uploaded one; exercised indirectly by every test that places an
      RPM inside a subdirectory (e.g. the duplicate-inventory tests).

## CSC grouping

- [ ] group packages by CSC
- [ ] select complete groups by default
- [ ] warn/block incomplete CSC groups
- [ ] show components
- [ ] preserve exclusion reason
- [ ] advanced RPM-level manipulation only in Expert mode

## Duplicate handling

- [x] same filename + same SHA → deduplicate with retained provenance
- [x] same filename + different SHA → hard error until the unwanted copy is removed
- [ ] multiple versions same component → conflict
- [ ] overlapping CSCs → show conflict/supersedence

## Supersedence

Create an explicit supersedence model.

- [ ] bundle metadata
- [ ] RPM metadata
- [ ] README metadata
- [ ] compatibility metadata
- [ ] gisobuild dependency output

Never silently exclude without a reason.

## Unified selection engine

- [ ] automatic mode and manual mode use the same backend model
- [ ] manual mode modifies BuildPlan
- [ ] no separate incompatible selection path
- [x] never submit workspace paths as package identifiers

## BuildPlan

Create backend-owned immutable BuildPlan.

Implemented in `giso-webui/app.py` as `create_build_plan()`, exposed at
`POST /api/build-plan`, and re-derived (never trusted from the client) inside
`create_job()` before any build starts.

Required content:

- [x] base ISO metadata/checksum
- [x] engine
- [x] release
- [x] platform
- [x] selected packages
- [x] selected CSC groups
- [x] excluded packages + reasons (populated when automatic selection excludes a
      candidate; see `recommend_smu_selection()` in `platform_validation.py`)
- [x] capabilities
- [x] options
- [x] blockers
- [x] warnings
- [x] inventory revision
- [x] plan fingerprint

Verified by `test_build_plan_is_backend_owned_and_checksum_fingerprinted`,
`test_build_plan_returns_blockers_instead_of_enabling_invalid_build`, and
`test_created_job_records_authoritative_build_plan` in
`giso-webui/tests/test_app.py`, run inside the built container image.

## BuildPlan fingerprint

Hash together:

- [x] ISO checksum
- [x] selected RPM checksums
- [ ] configuration files (build option paths such as `xrconfig`/`ztp_ini` are
      included as literal values in `options`, but their *content* is not
      independently checksummed into the fingerprint yet)
- [ ] gisobuild version/commit (only the builder container image tag is
      captured today; the pinned upstream `gisobuild` source revision inside
      that image is not separately tracked)
- [x] application version (`APP_VERSION` env var, defaults to `0.0.1`)
- [x] build options

## Inventory revision

`current_inventory_revision()` fingerprints the exact set of ready inventory
items (id + lifecycle) rather than an incrementing counter, so any mutation of
the ready inventory changes the revision without needing separate counters
per event type:

- [x] increment after upload (any new ready file changes the hashed item set)
- [x] increment after extraction (extracted files become ready inventory items)
- [x] increment after delete (removing a file changes the hashed item set)
- [x] increment after cleanup (same mechanism as delete)
- [x] increment after Cisco download (downloaded files become ready inventory
      items)
- [x] invalidate BuildPlan if revision changes — `create_job()` rejects
      `POST /api/jobs` with 409 when the client's `confirmed_plan_fingerprint`
      (captured from a prior `/api/build-plan` review) no longer matches the
      freshly recomputed plan, verified by
      `test_stale_confirmed_plan_is_rejected_when_inventory_changes` and
      `test_confirmed_plan_matching_current_inventory_is_accepted`
- [x] frontend never owns authoritative build state — `create_job()` always
      recomputes the BuildPlan itself from current inventory; a client-supplied
      plan is only ever used to detect staleness, never trusted as the plan

Only individual "increment after X" scenarios beyond upload/delete (extraction,
Cisco download) are verified indirectly through the shared revision mechanism
and existing tests for those features, not by a dedicated per-event regression
test — a good target for follow-up coverage if the revision computation
strategy ever changes from content-hash to an explicit counter.

## Automatic refresh

After upload/download:

- [ ] classify
- [ ] checksum
- [ ] extract if needed
- [ ] inspect metadata
- [ ] refresh inventory
- [ ] refresh recommendation
- [ ] regenerate BuildPlan
- [ ] update UI automatically

"Check files again" and "Recalculate" become troubleshooting controls only.

## Preflight

One authoritative preflight must decide whether Build is enabled.

- [ ] base image valid
- [ ] engine known
- [ ] release known
- [ ] compatible package set
- [ ] duplicate conflicts resolved
- [ ] CSC completeness checked
- [ ] disk space sufficient
- [ ] gisobuild available
- [ ] required tools available
- [ ] no conflicting job
- [ ] expected outputs supported
