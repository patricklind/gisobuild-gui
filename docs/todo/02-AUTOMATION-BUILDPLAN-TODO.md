# TODO — Automation, Inventory & BuildPlan

## Canonical inventory

Create one canonical inventory model.

- [x] every ready file receives a stable path-and-checksum ID
- [x] basename
- [x] relative path
- [ ] absolute path
- [x] size
- [x] SHA-256
- [ ] source (`upload`, `tar`, `cisco-download`)
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

- [ ] release
- [ ] platform identifier
- [ ] engine
- [ ] architecture
- [ ] detected_by
- [ ] confidence

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

- [ ] safe extraction
- [ ] reject traversal
- [ ] reject symlinks/hardlinks
- [ ] expansion-size limit
- [ ] member-count limit
- [ ] source provenance
- [ ] no duplicate extraction
- [ ] automatically inventory extracted RPMs

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
