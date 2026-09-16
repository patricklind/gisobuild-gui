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

- [x] Make cancellation work during every phase, including image preparation/pull.
- [x] Track the actual process/process-group or runner task, not only a future container name.
- [x] Add regression test: cancel while builder preparation is still running.

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

- [x] Check cancellation state before verification, archive and destructive cleanup.
- [ ] Make finalization idempotent and state-machine driven. (State transitions are explicit; archive replay/idempotency remains.)
- [x] Add regression test for cancellation during finalization.

### Successful build deletes unrelated files from the entire upload workspace

Current behavior:

`archive_giso_artifacts_and_cleanup()` iterates over every top-level item in `DATA` and removes it after a successful build.

This can remove files that were present in the workspace but were not part of the BuildPlan, for example:

- another ISO
- another release's RPMs
- compatibility matrices
- configuration files intended for a later build

TODO:

- [x] Cleanup only files owned by the completed job request.
- [x] Preserve unrelated inventory entries.
- [x] Track provenance/ownership of extracted files. `archive_source_for_extraction()`
  and `top_level_extraction_dir()` in `giso-webui/app.py` recover which
  `.tar`/`.tgz` produced an extracted directory (deterministic from
  `extraction_path()`'s naming, no new stored state needed). Wired into:
  `archive_giso_artifacts_and_cleanup()` (a build-emptied extraction
  directory and its source archive are now removed instead of orphaned;
  a directory still holding other files is left alone), `delete_upload()`
  (deleting an archive now cascades to its extraction directory), and
  `inventory_files()` (each extracted file now reports `extracted_from`,
  not just a `source:"tar"` boolean).
- [x] Add regression test: build A must not delete unrelated inputs for build B.

### Post-build cleanup could delete an unselected duplicate-basename RPM (2026-09-16)

Current behavior (before this fix):

- `create_job()` resolves the operator's package selection by opaque
  inventory ID (`payload["pkglist"] = [item["id"] for item in
  plan["selected_packages"]]`), which correctly disambiguates two uploaded
  RPMs that share a basename but have different content — exactly the
  "conflict" duplicate case `resolve_rpm_identifiers()` exists to handle.
- `build_command()` then overwrites `payload["pkglist"]` in place with the
  resolved *basenames* (`payload["pkglist"] = selected_names`), discarding
  which specific file (by path/hash) was actually chosen.
- `build_cleanup_paths()` ran after `build_command()` and re-derived which
  RPM files to delete by globbing `DATA.rglob("*.rpm")` for a basename match
  against that now-basename-only `pkglist`. If a second, unselected RPM
  elsewhere in the workspace happened to share the same filename, it matched
  too and was scheduled for deletion post-build, even though it was never
  part of this build.

Fix:

- [x] `build_cleanup_paths()` now takes the already-resolved `selected_rpms`
      list (the same objects `create_build_plan()` produced via
      `resolve_rpm_identifiers()`) and cleans up each one's exact
      `relative_path`, never re-deriving RPM identity from a basename glob.

Verified with `test_cleanup_paths_do_not_include_an_unselected_duplicate_basename`
in `giso-webui/tests/test_app.py`, which fails against the pre-fix code
(the unrelated duplicate's path was present in `cleanup_paths`) and passes
after the fix.

## P1 — Wrong file/package selection

### Multiple ISOs can result in the frontend silently selecting the first ISO

Current behavior:

- Backend `discover()` correctly reports automatic recommendation as not ready when more than one ISO exists.
- Frontend `renderInputs()` still assigns `isoFiles[0]` to the build ISO field and marks the ISO readiness card as ready.

This creates an ambiguous state where an arbitrary first ISO can become the build input.

TODO:

- [x] Never auto-select an ISO when more than one candidate exists.
- [x] Require an explicit operator selection or metadata-based deterministic choice.
- [x] Build button must stay blocked while base ISO identity is ambiguous.
- [ ] Add browser regression test with two uploaded ISOs.

### app.js and manual-packages.js both defined the manual-package-list logic, one of them dead (2026-09-16)

Current behavior (before this fix):

- `giso-webui/static/app.js` defined its own top-level `renderManualPackages()`,
  `selectedManualPackages()`, and `syncManualPackageValue()` functions.
- `giso-webui/static/manual-packages.js` (loaded via a second `<script>` tag
  right after `app.js` in `templates/index.html`) defined its own
  `window.renderManualPackages`/`window.selectedManualPackages`/
  `window.syncManualPackageValue` — the real fix for the "manual RPM path vs
  basename bug" (opaque inventory IDs, duplicate-conflict grouping via
  `logicalRpms()`).
- Because both are plain, non-module `<script>` tags, top-level function
  declarations in `app.js` and the `window.x = ...` assignments in
  `manual-packages.js` write to the *same* global object. Loading second,
  `manual-packages.js` always overwrote `app.js`'s versions before anything
  ever called them — so `app.js`'s copies were 100% dead code, never
  executed, no matter what they contained. Every call site in `app.js` calls
  these functions by bare name at runtime (inside `renderInputs()`'s async
  callback and a change-event listener), which resolves dynamically to
  whatever the global currently is — always `manual-packages.js`'s version.
- The dead `app.js` copy of `renderManualPackages()` still used
  `box.value = file.path` — a raw workspace path, exactly the bug class
  `manual-packages.js` was written to fix. It never ran, so it was not an
  active bug, but it was a landmine: reordering the `<script>` tags, or
  `manual-packages.js` ever failing to load, would have silently reactivated
  the old, buggy behavior.
- Worse: `giso-webui/tests/test_build_script.py`'s
  `test_manual_package_mode_renders_uploaded_rpms_as_choices` asserted on
  literal source substrings (`"data.files.filter(file=>file.type === '.rpm')"`,
  `"box.type='checkbox'"`) that only existed in the *dead* `app.js` copy —
  the test passed by checking inert code, proving nothing about the code
  that actually runs in a browser.

Fix:

- [x] Deleted the dead `renderManualPackages()`/`selectedManualPackages()`/
      `syncManualPackageValue()` definitions from `app.js`, leaving a comment
      pointing to `manual-packages.js` and explaining why. Call sites in
      `app.js` are unchanged and now resolve to the only remaining
      definition.
- [x] Rewrote `test_manual_package_mode_renders_uploaded_rpms_as_choices` to
      assert on `manual-packages.js` (the file that actually runs) instead
      of `app.js`, and added `assertNotIn("function renderManualPackages",
      app_script)` so a future re-introduction of the duplicate would fail
      the test immediately.

Verified: 175 tests pass inside the built container (unchanged behavior —
this was a no-op at runtime by construction), ruff clean, Graphify
refreshed, and confirmed live in a browser: uploaded two RPMs, switched to
manual mode, saw "2 of 2 RPM packages selected", unchecked one, saw it
update to "1 of 2" — identical to pre-fix behavior, now backed by a test
that actually exercises the live code.

### RPM processor architecture is not checked against the selected ISO

Fixed. `giso-webui/app.py:inspect_iso_architecture()` shells out to `isoinfo`
(now bundled in the `giso-webui` image via Alpine's pinned `cdrkit` package)
to read the base ISO's own contents: for eXR images it reads the "x86_64
supported arch list" / "arm supported arch list" keys from
`iosxr_image_mdata.yml` (the same file upstream's
`src/exrmod/gisobuild_exr_engine.py` treats as authoritative); for LNT images,
which carry their RPM repository directly on the ISO, it falls back to
scanning the `isoinfo -R -l` file listing for the same
x86_64/aarch64/arm64/corei7_64 filename suffix used for operator-selected
RPMs. Both paths, and the user-selected RPM list, now resolve through one
canonical `normalize_architecture()` mapping in `platform_validation.py`
(mirroring `normalize_platform()`), so an eXR `corei7_64` RPM and an LNT
`x86_64` RPM are correctly recognized as the same processor family instead of
two unrelated tokens.

Result is cached by `(path, size, mtime_ns)`, matching the existing
`file_checksums()` cache, so it costs one `isoinfo` run per uploaded ISO, not
per poll. When isoinfo/genisoimage cannot read the ISO or find a recognizable
architecture, the result is an empty set treated as "unknown" — this never
blocks a build; it only blocks when a genuine mismatch is detected.

TODO:

- [x] Determine ISO architecture from metadata/upstream inspection.
- [x] Compare every RPM architecture against the ISO/build architecture.
- [x] Treat mismatch as a blocking error.
- [x] Add x86_64 vs aarch64 mismatch regression tests. See
  `test_platform_compatibility.py` (pure, filename/normalization-level) and
  `test_app.py:IsoArchitectureInspectionTests` (real ISO9660 images built with
  `genisoimage`, run only inside the `giso-webui` container where
  `isoinfo`/`genisoimage` are installed).

### The immutable BuildPlan preview did not apply the RPM/ISO architecture check

Current behavior (before this fix):

`create_build_plan()` (`POST /api/build-plan`, and the sole gate `create_job()`
uses before starting a build) called `recommend_smu_selection()` and
`validate_smu_selection()` without passing `iso_architectures`, unlike every
other caller of those functions (`discover()`, `/api/smu-recommendation`,
`/api/compatibility`, and `build_command()`). The result: `/api/build-plan`
could report `ready: true` for an architecture-mismatched selection, only for
`build_command()` to reject it afterward when the operator actually tried to
build — defeating the point of "one authoritative preflight decides whether
Build is enabled" (`06-UI-OPERATOR-TODO.md`).

TODO:

- [x] Call `inspect_iso_architecture()` in `create_build_plan()` and pass its
      result into both `recommend_smu_selection()` and `validate_smu_selection()`,
      matching every other call site.
- [x] Add a regression test building a real x86_64-only ISO with `genisoimage`
      and an aarch64 RPM, proving `/api/build-plan` now reports `ready: false`
      with an architecture blocker instead of `true`
      (`test_build_plan_blocks_rpm_architecture_mismatch_against_real_iso`).

Not done / follow-up:

- [ ] Confirm the exact `iosxr_image_mdata.yml` key names and "arm supported
  arch list" variant token vocabulary against a real Cisco eXR ISO — the
  parsing here is built from upstream source
  (`src/exrmod/gisobuild_exr_engine.py`) and a synthetic fixture, not a
  licensed image, per the repository's synthetic-fixture rule in `AGENTS.md`.
  Treat this as `INFERRED` until validated against a real eXR image.
- [ ] LNT images that ship no RPMs directly on the ISO (metadata-only /
  bundle-reference images, if any exist upstream) will report an empty,
  "unknown" architecture set and are not blocked — confirm whether upstream
  LNT ISOs always carry a same-architecture repo, or whether a second LNT
  metadata source should be added.
- [ ] Tracked Graphify output (`graphify-out/`) was **not** refreshed for this
  change. Incremental `graphify --update` in a fresh worktree could not reuse
  the primary checkout's gitignored manifest/semantic cache (0 of ~38 doc
  files hit cache even after copying `graphify-out/manifest.json` and
  `graphify-out/cache/` over), so it would have needed a near-full re-extraction
  of the docs corpus for a small change. Per `AI-INSTRUCTIONS.md`'s explicit
  allowance ("If Graphify cannot be run ... state that clearly ... do not
  pretend it was refreshed"), this is stated here instead. Follow-up: make
  `graphify --update` cache-portable across worktrees (the manifest/cache
  keys should not depend on the worktree's absolute path), then refresh
  `graphify-out/` for `app.py`/`platform_validation.py` in a later change.

### RPM selection uses a glob expression instead of an exact package identity

Current behavior:

`build_command()` resolves selected packages with `DATA.rglob(package)`.

`Path.rglob()` interprets glob metacharacters. A package value containing characters such as `*`, `?` or `[]` can therefore match files other than the intended RPM.

TODO:

- [x] Never use user/package identifiers as glob patterns.
- [x] Resolve packages through the canonical inventory ID/checksum model.
- [x] Until the canonical model exists, require a strict RPM basename and exact basename lookup.
- [x] Add regression tests for glob metacharacters.

### Manual package UI collapses duplicate RPM basenames before the operator can inspect them

Current behavior:

`manual-packages.js` builds:

```js
new Map(rpms.map(file => [basename(file.path), file]))
```

If two archives contain an RPM with the same basename, the later entry overwrites the earlier entry in the UI model. The backend may later detect differing hashes, but the operator does not get an accurate representation of inventory.

TODO:

- [x] Represent RPMs by stable inventory ID, not basename.
- [x] Show duplicate basename conflicts explicitly in the UI.
- [x] Same name + same hash is deduplicated with provenance retained.
- [x] Same name + different hash is a hard conflict until the unwanted copy is removed.
- [ ] Add DOM regression tests for both duplicate cases.

## P1/P2 — Platform and compatibility validation

### Upgrade-matrix platform normalization is inconsistent

Current behavior:

`normalize_platform()` normalizes aliases and punctuation, but `check_upgrade_matrix()` compares matrix platform values using only a lowercase `ALIASES.get(...)` lookup.

Values such as friendly names, punctuation variants or normalized SKU aliases can fail to match even though the same value would be accepted elsewhere.

TODO:

- [x] Route matrix platform values through the same canonical platform resolver.
- [x] Do not maintain separate normalization rules in compatibility code.
- [x] Add tests for aliases, case, punctuation and hardware PID variants.

### Bridge-SMU presence check can produce substring false positives

Current behavior:

`check_upgrade_matrix()` joins selected filenames into one text string and considers a bridge SMU present if its filename or extracted CSC token appears as a substring.

This can incorrectly accept a different filename/component that merely contains the same text fragment.

TODO:

- [x] Compare exact package basenames and exact CSC IDs.
- [x] Do not use one concatenated free-text string for package presence checks.
- [x] Add near-match regression tests.

### Hardware alias matching used loose substrings instead of word boundaries

Fixed. `infer_platform()`'s primary platform-ID loop already used a
word-boundary regex, but its `ALIASES` fallback loop used a bare `if alias in
name` substring check — the same class of bug as the bridge-SMU issue above.
An alias such as `"8800"` (→ Cisco 8000 family) could match inside an
unrelated numeric run, e.g. `router-188005-image.iso`.

TODO:

- [x] Use the same word-boundary matching for alias lookups as for direct
      platform-ID lookups.
- [x] Add a regression test for both the false-positive and the legitimate
      match case
      (`test_alias_matching_does_not_produce_false_positives_on_substrings`).

### Filename heuristics can report confidence stronger than the evidence supports

Current platform/release/CSC checks are largely filename based. This is already covered by the metadata-first architecture TODO, but it is also a current correctness risk.

**2026-09-16 update:** `create_build_plan()`, `discover()`, and
`/api/smu/recommendation` now all return a `confidence` block (via the shared
`confidence_report()` in `giso-webui/app.py`) labeling platform, release, ISO
architecture, RPM architecture, CSC grouping, and dependency closure as
`VERIFIED` / `INFERRED` / `UNKNOWN`, and the Review BuildPlan step in
`giso-webui/static/app.js` renders it as a badge grid
(`confidenceGrid()`/`.confidence-badge` in `giso-webui/static/upload.css`).
Verified by the four `test_build_plan_confidence_*` tests in
`giso-webui/tests/test_app.py`. Note: `docs/todo/06-UI-OPERATOR-TODO.md`'s
original examples claimed platform/release/RPM-architecture would be
`VERIFIED from ISO metadata` / `VERIFIED from RPM header` — that was
aspirational and not what the codebase does; those fields are filename-based
and are honestly reported as `INFERRED`. Only ISO architecture
(`inspect_iso_architecture()`, reading the ISO's own contents) earns
`VERIFIED` today.

TODO:

- [x] Label filename-only results as `INFERRED`, never `VERIFIED`.
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
- [x] Until then, synchronize discovery with destructive workspace operations or tolerate disappearing files safely.
- [x] Add concurrency regression test: discover while cleanup/delete occurs.

### Target release can remain stale after the selected ISO changes

Current behavior:

`renderInputs()` only fills `target_release` when the field is empty. If an ISO for another release is later selected/uploaded, the old target release can remain in the form and produce misleading compatibility results.

TODO:

- [x] Track whether release was automatically populated or manually overridden.
- [x] Refresh auto-derived release when the base ISO changes.
- [x] Preserve explicit manual override only when intentionally selected.
- [ ] Add browser regression test switching between two releases.

### Archive maintenance runs in a separate process with no cross-process lock (2026-09-16)

Current behavior:

- `enforce_archive_policy()` and `archive_giso_artifacts_and_cleanup()` in
  `giso-webui/app.py` synchronize with each other only via `archive_lock`, a
  `threading.RLock()` — mutual exclusion within one Python process only.
- `giso-webui/maintenance.py` (run as the separate `archive-maintenance`
  container in `giso-webui/compose.yaml`) imports and calls the very same
  `enforce_archive_policy()` on an hourly loop, against the same `ARCHIVE`
  volume, from a completely different OS process. `archive_lock` there is a
  different lock object in different process memory; it provides no
  coordination whatsoever with the webui process's own `archive_lock`.
- `archive_download()`, `archive_checksums()`, and `archive_delete()` read
  `ARCHIVE` without taking any lock a separate process would ever see.

Concretely, the maintenance container's retention/quota sweep could run at
the same moment the webui process was archiving a just-finished build, with
no coordination between the two processes on the mutating operations. The
realistic failure mode was a torn directory listing during an eviction
decision or a `mkdir(..., exist_ok=False)`/`rmtree()` collision — not
corruption of an already-archived file's *contents* (each file is written
once, verified by checksum, and only then exposed).

Fix (2026-09-16):

- [x] Added `cross_process_archive_lock()` in `giso-webui/app.py`: an
      `fcntl.flock()` on `ARCHIVE/.lock`, a file on the shared volume both
      processes actually mount, wrapping `enforce_archive_policy()`,
      `archive_giso_artifacts_and_cleanup()`, `archive_list()`,
      `archive_checksums()`, and `archive_delete()` — every place that
      previously took `archive_lock` directly. `maintenance.py` needed no
      changes: it calls `enforce_archive_policy()`, which now takes the file
      lock internally.
- [x] Handled `archive_lock`'s existing reentrancy (`archive_giso_artifacts_
      and_cleanup()` calls `enforce_archive_policy()` while already holding
      it): `cross_process_archive_lock()` keeps one persistent file handle
      per process and only actually flocks/unflocks at depth 0, with the
      depth counter itself protected by the pre-existing `archive_lock`
      (still held for the whole nested duration, exactly as before, so
      in-process thread-safety is unchanged).
- [x] Deliberately did **not** lock `archive_download()` (the byte-streaming
      response) — an exclusive flock held for an entire large-file download
      would serialize unrelated concurrent downloads against each other and
      against the maintenance sweep, a worse regression than the risk being
      fixed. A file already open for reading keeps working under POSIX even
      if unlinked/rmtree'd concurrently, so at worst a download in progress
      during eviction sees a directory entry disappear, not corrupted bytes.
      This residual gap is intentional, not an oversight.
- [x] Regression test: `test_cross_process_archive_lock_blocks_a_separate_os_process`
      in `giso-webui/tests/test_app.py` spawns a real second OS process (via
      `subprocess.Popen`) that holds the flock for 1.5s, then proves
      `cross_process_archive_lock()` in the test's own process actually
      blocks for that long before proceeding — a same-process `threading`
      test would have passed even with the old, unfixed code, so this
      specifically exercises the cross-process path.

Verified: full suite green (168 tests) inside the built container; also ran
the real `docker compose` stack with both `giso-webui` and
`archive-maintenance` containers up simultaneously against the shared
`giso-archive` volume, confirmed `archive-maintenance`'s log shows a clean
policy check with no errors, `/api/archive` responds normally, and
`ARCHIVE/.lock` is created on the writable volume without tripping the
`read_only: true` root filesystem hardening on either container.

### Mandatory Docker pull makes builds depend on registry availability even when the builder image is already cached

Current behavior:

Every build runs `docker pull ...` with `check=True` before starting the builder.

A temporary registry/network outage can therefore block a build even when a valid local image already exists.

TODO:

- [ ] Remove this dependency as part of the self-contained image design.
- [ ] During migration, define an explicit pull policy and safe cached-image fallback.
- [ ] Pin builder identity by digest/commit rather than mutable tag semantics.
- [ ] Add offline/cached-builder regression test if nested Docker remains during transition.

## P2 — Tooling reliability

### `ruff` is installed unpinned in CI, so its rule set can change without a code change

Current behavior:

`.github/workflows/ci.yml` runs `pip install ... ruff ...` with no version
pin, and the repository has no `pyproject.toml`/`ruff.toml`, so every CI run
lints with whatever `ruff` resolves to that day using its own default rule
set. Reproduced locally: `ruff check giso-webui/app.py ...` with a freshly
installed `ruff 0.16.7` flagged `PLW1510` (`subprocess.run` without an
explicit `check=` argument) on the two `isoinfo` calls added by the ISO
architecture-detection change — a real style issue, but a lint failure that
appeared with no corresponding code change is a process risk on its own.
Fixed the two flagged calls by adding `check=False` (matching their existing
manual `returncode` handling). Could not confirm live GitHub Actions status
for `main` from this sandbox (`gh` is installed but not authenticated here).

TODO:

- [x] Add explicit `check=False` to the two `isoinfo` `subprocess.run` calls
      in `giso-webui/app.py:inspect_iso_architecture()`.
- [x] Pin `ruff`'s version in CI (and locally) — fixed 2026-09-16 as part of
      adopting the Docker-only execution policy (`AGENTS.md`): added
      `docker/tooling.Dockerfile`, a small pinned image (`ruff==0.16.7`,
      `pip-audit==2.7.3`, `graphifyy==0.9.61`) that both CI
      (`.github/workflows/ci.yml`) and local development
      (`docs/testing.md`) now use identically, replacing the previous
      unpinned `pip install ruff pip-audit graphifyy==0.9.61` on the bare
      Actions runner. Verified: built the image, ran `ruff check`,
      `pip-audit`, `scripts/check_graphify_freshness.py`, and
      `staging/rehearse.py` all inside it with matching results, and
      confirmed the Dockerfile itself passes `hadolint`.
- [ ] Add a `pyproject.toml`/`ruff.toml` that explicitly selects the intended
      rule set, instead of relying on whatever ruff's shifting defaults are.
      Pinning the *version* (above) makes results reproducible across runs;
      this remaining item is about pinning the *rule selection* too.

## P2 — Graphify / repository correctness

### Tracked Graphify output is stale relative to current main

Current `graphify-out/GRAPH_REPORT.md` reports it was built from commit `3f2a3e04`, while current `main` is newer.

This means AI agents can be instructed to use Graphify while receiving an outdated dependency graph.

TODO:

- [x] Refresh Graphify output after the current changes.
- [x] Add a CI check that regenerates from the tracked `HEAD` tree and structurally compares the graph; commit metadata is excluded because generating it changes the commit.
- [x] Fail when `graphify-out/graph.json` is stale.
- [x] Keep and validate `.graphifyignore` protections for Cisco licensed/sensitive artifacts.

## P2 — CI process fidelity

### CI ran the unit test suite on the GitHub Actions host Python instead of inside the built container

Current behavior (before this fix):

- `AGENTS.md` and `docs/testing.md` both mandate that the `giso-webui` test
  suite run only inside the built `giso-webui-giso-webui` image, because the
  host lacks the pinned dependency versions and any OS-level tools the image
  provides.
- `.github/workflows/ci.yml` instead installed `giso-webui/requirements.txt`
  directly on the Actions runner and ran
  `python -B -m unittest discover -s tests -v` there, *before* the
  "Build production container" step even executed. CI therefore never proved
  the tests pass against the actual shipped image, contradicting the
  project's own documented verification process.
- Separately, `docs/testing.md` documents `bash -n build-giso.sh
  scripts/coord.sh scripts/worktree.sh`, but CI only ever ran `bash -n` on
  `build-giso.sh`.
- `docs/testing.md` and `AGENTS.md` also say workflow and Dockerfile changes
  "should also pass Actionlint and Hadolint", but CI had no such step.

Fix:

- [x] Reorder CI so the container image is built first, then tests run via
      `docker run ... giso-webui-giso-webui python -B -m unittest discover -s
      tests -v`, matching `docs/testing.md` exactly.
- [x] Drop the now-unnecessary host install of `giso-webui/requirements.txt`
      (ruff/pip-audit/graphify don't need the app's runtime deps installed).
- [x] Extend the shell syntax check to `scripts/coord.sh` and
      `scripts/worktree.sh`, matching `docs/testing.md`.
- [x] Add pinned `rhysd/actionlint:1.7.7` and `hadolint/hadolint:2.12.0`
      steps; verified locally against the current workflow files and both
      Dockerfiles with zero findings before adding them to CI.

Verification performed locally in this environment (Docker + network
available): built `giso-webui-giso-webui` from a clean image, ran the 130
tests in `giso-webui/tests` inside that container (130 passed, 2 skipped —
`bash` is intentionally absent from the minimal runtime image), ran `ruff`,
`graphify update`-based freshness check, `staging/rehearse.py`, `actionlint`,
and `hadolint` against the edited workflow — all clean. `pip-audit` could not
be exercised locally because this sandbox's host Python is 3.9 and
`giso-webui/requirements.txt` pins packages requiring 3.10+; CI itself pins
Python 3.12 via `actions/setup-python`, so this is a local sandbox limitation,
not a defect in the workflow change. The actual GitHub Actions run of this
workflow has not been observed — only the equivalent commands run locally.

### Superseded RPMs were silently dropped instead of being explained (2026-09-16)

`active_rpm_names()` in `giso-webui/app.py` reads Cisco supersedence readmes
and removes any RPM whose containing directory matches a superseded
identifier from the automatic-selection candidate list *before*
`recommend_smu_selection()` ever sees it. That meant a superseded SMU never
appeared in `selected` or `excluded` — it just vanished. `discover()` did
return the raw `superseded` identifier set as `data.superseded`, but
`giso-webui/static/app.js` never read that field, so the operator had no way
to learn a file they uploaded was excluded, let alone why.

Fix:

- [x] Add `add_superseded_exclusions()`, appending a
      `{"name": ..., "reason": "Superseded by a newer fix per Cisco
      supersedence notes"}` entry per dropped RPM to the `excluded` list.
- [x] Wire it into `discover()` (`/api/inputs`), `/api/smu/recommendation`,
      and `create_build_plan()`'s automatic-selection branch — the three
      places `active_rpm_names()`'s filtered candidate list reaches an
      operator-facing response.
- [x] No frontend change was needed: the excluded-packages list in
      `giso-webui/static/app.js` already renders `name — reason` for every
      entry generically.

Verified by `test_superseded_rpm_is_excluded_with_a_reason_not_silently_dropped`
and `test_build_plan_automatic_selection_explains_superseded_exclusions` in
`giso-webui/tests/test_app.py` (both fail against the pre-fix code — the
superseded RPM was absent from `excluded` entirely), and confirmed live: built
the image, ran it, placed a base ISO plus a current and a superseded RPM in
the container's upload volume, and saw "ncs5500-bgp-1.0.0.1-r2612.CSCold00001
... — Superseded by a newer fix per Cisco supersedence notes" render in the
Review BuildPlan step in a real browser.

## P3 — Cisco download hardening (residual, deferred)

### DNS-rebinding TOCTOU in the Cisco download SSRF guard (2026-09-16)

Current behavior:

`CiscoSoftwareClient._validate_download_url()` in `giso-webui/cisco_download.py`
resolves the download host and requires every resolved address to be a
global (non-private/non-loopback/non-link-local) IP before allowing the
request — a real, tested control (`test_cisco_download.py` injects a
resolver returning `127.0.0.1` and confirms rejection). But the actual HTTP
request that follows is made by `urllib.request`, which performs its own,
independent DNS resolution when it opens the connection. Between the
validation resolve and the connect, nothing pins the connection to the
address that was actually checked, so a host that resolves differently
between those two calls (classic DNS rebinding) could in principle bypass
the check.

Why this is deferred rather than fixed now: the URL being validated is not
attacker-supplied in the ordinary sense — it comes from Cisco's own
authenticated API response, already scoped to `cisco.com`-suffixed hosts.
The realistic threat this control defends against is a malformed or
unexpected URL in Cisco's own response, not an actively adversarial DNS
answer from Cisco's infrastructure. A correct fix means connecting directly
to the already-resolved IP with the original hostname preserved only for TLS
SNI/hostname verification (not simply "resolve then hope the same address is
used"), which is a non-trivial change to code that also has to keep working
through the existing redirect-following loop (up to 6 hops, each re-running
`_validate_download_url()`). Given the low realistic exploitability and the
size of a correct fix, this is recorded here rather than attempted under
these constraints — the pattern this session used to defer
`03-DOCKER-SELF-CONTAINED-TODO.md`.

TODO:

- [ ] If this trust model ever changes (e.g. download URLs sourced from
      somewhere less trusted than Cisco's own API), connect by IP with
      explicit SNI/hostname verification instead of resolve-then-request.

## Required regression-test additions

- [x] cancel during builder preparation/pull
- [x] cancel during finalization
- [x] successful build preserves unrelated workspace inputs
- [x] two ISOs never silently choose first candidate
- [x] wrong RPM CPU architecture is blocked
- [x] package glob characters cannot select unintended files
- [x] duplicate basename / same hash — `test_identical_duplicate_rpms_are_accepted`,
      `test_identical_duplicate_inventory_keeps_provenance`
- [x] duplicate basename / different hash — `test_different_duplicate_rpms_are_rejected`,
      `test_different_duplicate_inventory_is_a_visible_conflict`,
      `test_inventory_id_selects_exact_rpm`,
      `test_cleanup_paths_do_not_include_an_unselected_duplicate_basename`
- [x] upgrade matrix aliases normalize through one resolver
- [x] bridge-SMU near-match does not count as exact presence
- [x] discovery vs cleanup race
- [x] target release refreshes when ISO changes
- [x] Graphify freshness check
- [x] `extract_cisco_archive()` tar safety (traversal, symlink, member-count,
      happy path) — this function duplicates `upload_complete()`'s TAR
      safety checks for the Cisco-download path but had zero test coverage
      of its own until 2026-09-16:
      `test_cisco_archive_extraction_rejects_path_traversal`,
      `test_cisco_archive_extraction_rejects_symlink_members`,
      `test_cisco_archive_extraction_enforces_member_count_limit`,
      `test_cisco_archive_extraction_succeeds_for_a_safe_archive`
- [x] TAR member-count limit is actually enforced, not just present in code
      — `test_tar_member_count_limit_is_enforced` (upload path) and the
      `extract_cisco_archive()` test above (Cisco-download path)
