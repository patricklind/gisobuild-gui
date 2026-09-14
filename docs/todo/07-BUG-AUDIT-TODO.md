# TODO — Concrete Bug Audit

This file tracks concrete bugs found in the current implementation. These are not merely architectural improvements. Each item should receive a regression test before or with the fix.

## P0/P1 — Build lifecycle and destructive cleanup

### Cancellation during image pull cannot reliably cancel the build

Current behavior:

- `run_job()` performs a blocking `docker pull` before the build container exists.
- `cancel_job()` always tries `docker stop giso-build-<job_id>`.
- If cancellation happens during the pull, that container does not exist yet.
- The stop fails and the job is put back into `running`.

TODO:

- [ ] Make cancellation work during every phase, including image preparation/pull.
- [ ] Track the actual process/process-group or runner task, not only a future container name.
- [ ] Add regression test: cancel while builder preparation is still running.

### Cancelled build may still archive output and delete inputs

Current behavior:

- `run_job()` decides whether the process succeeded.
- On success it calls `archive_giso_artifacts_and_cleanup()` before checking whether the job was concurrently changed to `cancelled`/`cancelling`.

Race:

1. build completes
2. user cancels near completion
3. build thread sees a valid ISO
4. artifacts are archived and cleanup runs
5. only afterwards job status is checked

TODO:

- [ ] Check cancellation state before verification, archive and destructive cleanup.
- [ ] Make finalization idempotent and state-machine driven.
- [ ] Add regression test for cancellation during finalization.

### Successful build deletes unrelated files from the entire upload workspace

Current behavior:

`archive_giso_artifacts_and_cleanup()` iterates over every top-level item in `DATA` and removes it after a successful build.

This can remove files that were present in the workspace but were not part of the BuildPlan, for example:

- another ISO
- another release's RPMs
- compatibility matrices
- configuration files intended for a later build

TODO:

- [ ] Cleanup only files owned by the completed BuildPlan/job.
- [ ] Preserve unrelated inventory entries.
- [ ] Track provenance/ownership of extracted files.
- [ ] Add regression test: build A must not delete unrelated inputs for build B.

## P1 — Wrong file/package selection

### Multiple ISOs can result in the frontend silently selecting the first ISO

Current behavior:

- Backend `discover()` correctly reports automatic recommendation as not ready when more than one ISO exists.
- Frontend `renderInputs()` still assigns `isoFiles[0]` to the build ISO field and marks the ISO readiness card as ready.

This creates an ambiguous state where an arbitrary first ISO can become the build input.

TODO:

- [ ] Never auto-select an ISO when more than one candidate exists.
- [ ] Require an explicit operator selection or metadata-based deterministic choice.
- [ ] Build button must stay blocked while base ISO identity is ambiguous.
- [ ] Add browser regression test with two uploaded ISOs.

### RPM processor architecture is not checked against the selected ISO

Current behavior:

`validate_smu_selection()` checks whether selected RPMs contain multiple architectures, but does not prove that the single RPM architecture matches the base ISO architecture.

A set of mutually consistent but wrong-architecture RPMs can therefore pass the local check.

TODO:

- [ ] Determine ISO architecture from metadata/upstream inspection.
- [ ] Compare every RPM architecture against the ISO/build architecture.
- [ ] Treat mismatch as a blocking error.
- [ ] Add x86_64 vs aarch64 mismatch regression tests.

### RPM selection uses a glob expression instead of an exact package identity

Current behavior:

`build_command()` resolves selected packages with `DATA.rglob(package)`.

`Path.rglob()` interprets glob metacharacters. A package value containing characters such as `*`, `?` or `[]` can therefore match files other than the intended RPM.

TODO:

- [ ] Never use user/package identifiers as glob patterns.
- [ ] Resolve packages through the canonical inventory ID/checksum model.
- [ ] Until the canonical model exists, require a strict RPM basename and exact basename lookup.
- [ ] Add regression tests for glob metacharacters.

### Manual package UI collapses duplicate RPM basenames before the operator can inspect them

Current behavior:

`manual-packages.js` builds:

```js
new Map(rpms.map(file => [basename(file.path), file]))
```

If two archives contain an RPM with the same basename, the later entry overwrites the earlier entry in the UI model. The backend may later detect differing hashes, but the operator does not get an accurate representation of inventory.

TODO:

- [ ] Represent RPMs by stable inventory ID, not basename.
- [ ] Show duplicate basename conflicts explicitly in the UI.
- [ ] Same name + same hash may be deduplicated with provenance retained.
- [ ] Same name + different hash must be a hard conflict.
- [ ] Add DOM regression tests for both duplicate cases.

## P1/P2 — Platform and compatibility validation

### Upgrade-matrix platform normalization is inconsistent

Current behavior:

`normalize_platform()` normalizes aliases and punctuation, but `check_upgrade_matrix()` compares matrix platform values using only a lowercase `ALIASES.get(...)` lookup.

Values such as friendly names, punctuation variants or normalized SKU aliases can fail to match even though the same value would be accepted elsewhere.

TODO:

- [ ] Route matrix platform values through the same canonical platform resolver.
- [ ] Do not maintain separate normalization rules in compatibility code.
- [ ] Add tests for aliases, case, punctuation and hardware PID variants.

### Bridge-SMU presence check can produce substring false positives

Current behavior:

`check_upgrade_matrix()` joins selected filenames into one text string and considers a bridge SMU present if its filename or extracted CSC token appears as a substring.

This can incorrectly accept a different filename/component that merely contains the same text fragment.

TODO:

- [ ] Compare exact canonical package IDs and exact CSC IDs.
- [ ] Do not use one concatenated free-text string for package presence checks.
- [ ] Add near-match regression tests.

### Filename heuristics can report confidence stronger than the evidence supports

Current platform/release/CSC checks are largely filename based. This is already covered by the metadata-first architecture TODO, but it is also a current correctness risk.

TODO:

- [ ] Label filename-only results as `INFERRED`, never `VERIFIED`.
- [ ] Do not block an upstream-valid platform solely because the local filename parser does not recognize it.
- [ ] Add unknown/future-platform regression fixture.

## P2 — Inventory consistency and races

### `/api/inputs` can race cleanup/deletion

Current behavior:

- `discover()` walks `DATA` and calls `stat()` without holding an authoritative inventory snapshot/lock.
- cleanup and delete operations can remove files concurrently.

A file disappearing between directory enumeration and `stat()` can cause a request failure/500.

TODO:

- [ ] Use the persistent inventory model instead of live filesystem walking for every request.
- [ ] Until then, synchronize discovery with destructive workspace operations or tolerate disappearing files safely.
- [ ] Add concurrency regression test: discover while cleanup/delete occurs.

### Target release can remain stale after the selected ISO changes

Current behavior:

`renderInputs()` only fills `target_release` when the field is empty. If an ISO for another release is later selected/uploaded, the old target release can remain in the form and produce misleading compatibility results.

TODO:

- [ ] Track whether release was automatically populated or manually overridden.
- [ ] Refresh auto-derived release when the base ISO changes.
- [ ] Preserve explicit manual override only when intentionally selected.
- [ ] Add browser regression test switching between two releases.

### Mandatory Docker pull makes builds depend on registry availability even when the builder image is already cached

Current behavior:

Every build runs `docker pull ...` with `check=True` before starting the builder.

A temporary registry/network outage can therefore block a build even when a valid local image already exists.

TODO:

- [ ] Remove this dependency as part of the self-contained image design.
- [ ] During migration, define an explicit pull policy and safe cached-image fallback.
- [ ] Pin builder identity by digest/commit rather than mutable tag semantics.
- [ ] Add offline/cached-builder regression test if nested Docker remains during transition.

## P2 — Graphify / repository correctness

### Tracked Graphify output is stale relative to current main

Current `graphify-out/GRAPH_REPORT.md` reports it was built from commit `3f2a3e04`, while current `main` is newer.

This means AI agents can be instructed to use Graphify while receiving an outdated dependency graph.

TODO:

- [ ] Refresh Graphify output after the current changes.
- [ ] Add a CI check comparing Graphify's recorded source revision with `HEAD` for code-changing PRs.
- [ ] Fail or clearly warn when `graphify-out/` is stale.
- [ ] Keep `.graphifyignore` protections for Cisco licensed/sensitive artifacts.

## Required regression-test additions

- [ ] cancel during builder preparation/pull
- [ ] cancel during finalization
- [ ] successful build preserves unrelated workspace inputs
- [ ] two ISOs never silently choose first candidate
- [ ] wrong RPM CPU architecture is blocked
- [ ] package glob characters cannot select unintended files
- [ ] duplicate basename / same hash
- [ ] duplicate basename / different hash
- [ ] upgrade matrix aliases normalize through one resolver
- [ ] bridge-SMU near-match does not count as exact presence
- [ ] discovery vs cleanup race
- [ ] target release refreshes when ISO changes
- [ ] Graphify freshness check
