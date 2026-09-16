# TODO — Concrete Bug Audit

This file tracks concrete bugs found in the current implementation. These are not merely architectural improvements. Each item should receive a regression test before or with the fix.

## P1 — Misleading UI status

### The header "System ready" pill checked only bare liveness, not actual readiness (2026-09-16)

Current behavior (before this fix):

`health()` in `giso-webui/static/app.js` called `GET /api/health`, which
only proves the Flask process itself is responding (`{"ok": true}` — see
`app.py`, no dependency checks at all). The container's own `HEALTHCHECK`
in `giso-webui/Dockerfile` calls a *different*, deeper endpoint,
`GET /api/ready`, which also verifies Docker, the mounted `.gisobuild-tool`
checkout, all required storage directories, the job database, and free
disk space — but that endpoint was never called from the UI at all. An
operator could stare at a reassuring green "✓ System ready" pill while
Docker was unreachable, the tool checkout was missing, or a storage volume
had failed to mount — exactly the deployment states where every build
attempt would fail — with no visible signal until they tried a build and
read the failure, or dug into logs. This directly contradicts this
project's own "honest confidence/warning display" standard applied
everywhere else (confidence badges, BuildPlan warnings, the ownership
voucher/certificate warning, etc.).

TODO:

- [x] Make the header status pill call the same deep readiness check the
      container's own health check uses, not just bare liveness.
- [x] When not ready, show which specific check(s) are failing rather than
      a generic "not ready" message.
- [x] Make the failure detail available to touch and screen-reader users,
      not only as a mouse-hover tooltip.

Fix: `health()` now fetches `/api/ready` directly (not through the generic
`api()` helper, which throws away the response body on any non-2xx status
— and `/api/ready` legitimately answers "not ready" with HTTP 503). When
`ok` is false, it maps each failing check (`docker`/`tool`/`storage`/
`database`/`disk`) to a plain-English reason via `READY_CHECK_LABELS` and
shows it directly in the pill text (or "N checks failing" plus a `title`
tooltip and matching `aria-label` when more than one check fails), instead
of a static "System is not ready".

Verified by `test_system_status_pill_uses_the_deep_readiness_check` in
`giso-webui/tests/test_build_script.py` (source-level assertion, matching
this repo's existing JS-testing convention — no DOM/JS runner exists yet,
tracked separately in `05-TESTING-CI-TODO.md`), and confirmed live in a
browser against an isolated throwaway container (its own temp
`DATA_ROOT`/etc., docker socket and `.gisobuild-tool` deliberately not
mounted) — the pill correctly showed "⚠ System not ready (3 checks
failing)" with `title`/`aria-label` both reading "Docker is unavailable;
the gisobuild engine checkout is missing; a required storage directory is
missing". Full suite green (200 tests); ruff and Graphify clean. Caught and
fixed a second bug while verifying the first: the initial version called
`/api/ready` through `api()`, which meant the 503 response was thrown away
before any of this new detail could render, collapsing every failure back
into the old generic message — only actually testing it live surfaced this.

### "Detailed dependency check" defaulted to off for no real reason (2026-09-16)

Current behavior (before this fix):

The LNT "Detailed dependency check" checkbox (`verbose_dep_check`, maps to
gisobuild's `--verbose-dep-check`) defaulted to unchecked. Checking upstream
gisobuild's own `--help` text confirms this flag is "Verbose output for the
dependency check" — the dependency check itself is unconditional and always
runs; the flag only controls how much diagnostic detail its output includes.
There was no reason to make an operator opt in to more detail for a check
that was happening either way, and `giso-webui/README.md` already
(incorrectly, until now) claimed it "runs with the detailed dependency
option enabled by default."

TODO:

- [x] Default the checkbox to checked for LNT builds.
- [x] Confirm it is still correctly forced off (and hidden/disabled) for
      non-LNT platforms, matching every other LNT-only Expert control.

Fix: added `checked` to the template. `updatePlatformControls()` already
force-unchecks every LNT-only control (including this one) whenever the
detected/selected platform is not LNT, so the new default cannot leak into
an eXR build's command.

Verified by the updated `test_lnt_only_defaults_do_not_block_exr_builds` in
`giso-webui/tests/test_build_script.py`, and confirmed live in a browser
through three states: before any platform is known (checked, matching the
new default), after selecting a synthetic eXR platform (unchecked, disabled,
hidden), and after selecting a synthetic LNT platform on a fresh page load
(checked). Follow-up: the frontend checkbox default had no matching backend
test proving `--verbose-dep-check` (or any `BOOL_OPTIONS` flag) actually
reaches the real build command — added
`test_verbose_dep_check_is_passed_through_for_lnt_platforms` and
`test_verbose_dep_check_is_omitted_when_not_requested` in
`giso-webui/tests/test_app.py` to close that gap directly. Full suite green
(209 tests); ruff and Graphify clean.

### The "Start build" disabled hint could name a requirement that was already satisfied (2026-09-16)

Current behavior (before this fix):

`updateBuildAvailability()` in `giso-webui/static/app.js` always showed
"Waiting for an ISO and a customization…" while the button was disabled in
form mode, regardless of *which* of the two was actually missing. An
operator who had already selected an ISO and just needed to add a package,
config file or bridging fix was told the ISO was still missing too — a
minor but real dishonesty in a hint whose entire purpose is telling the
operator what to do next.

TODO:

- [x] Name exactly what is still missing: ISO only, customization only, or
      both.

Fix: split the disabled-button text into three specific messages based on
`hasIso`/`otherChanges`, instead of one message covering all three
"not ready" cases.

Verified by `test_start_build_button_names_exactly_what_is_missing` in
`giso-webui/tests/test_build_script.py`, and confirmed live in a browser
(isolated throwaway container) through all three states: no ISO and no
customization → "Waiting for an ISO and a customization…"; ISO present,
no customization → "Waiting for a customization (packages, config files,
or bridging fixes)…"; customization present, no ISO → "Waiting for an
ISO…". Full suite green (207 tests); ruff and Graphify clean.

### No free-space check exists for the volumes a build actually writes to (found 2026-09-16, not fixed here)

Current behavior:

Every existing `shutil.disk_usage(...).free < ... + MIN_FREE_BYTES` guard in
`giso-webui/app.py` (upload init, upload chunk, TAR/Cisco-archive extraction,
Cisco download) checks `DATA` (`DATA_ROOT`, the uploads volume) exclusively.
`giso-webui/compose.yaml` defines `giso-work`, `giso-output`, and
`giso-uploads` as three separate named Docker volumes. gisobuild actually
extracts and builds inside `WORK_ROOT` and writes the final Golden
ISO/USB image to `OUTPUT_ROOT` — neither of which any code path measures
free space on, before or during a build. A deployment that sizes those
volumes independently of the uploads volume (a real possibility once
`03-DOCKER-SELF-CONTAINED-TODO.md`'s volume-topology work lands, and even
today if an operator mounts them on different host paths/disks) can start
and run a build that has plenty of "free" uploads space but no room left to
actually write its own output, failing only mid-build with no advance
warning anywhere.

This was found while implementing the Step 2 "free disk estimate" display
(`06-UI-OPERATOR-TODO.md`, "Show: ... free disk estimate"): the new
`renderDiskEstimate()` in `giso-webui/static/app.js` compares an estimated
output size against `/api/storage`'s `disk_free_bytes`, which — honestly
labelled in the UI text as "free on the uploads volume" — has this same
blind spot, because it is the only free-space figure the backend computes
anywhere.

TODO:

- [ ] Measure free space on `WORK_ROOT` and `OUTPUT_ROOT` (in addition to
      `DATA_ROOT`) somewhere the operator can see it before starting a
      build, and in whatever pre-build gate is added.
- [ ] Consider adding a real `MIN_FREE_BYTES`-style guard against
      `WORK_ROOT`/`OUTPUT_ROOT` before `run_job()` starts a build, mirroring
      the existing upload-time guards, so a build that cannot possibly
      finish is refused up front instead of failing partway through.
- [ ] Add a regression test proving a build is refused (or at least clearly
      warned) when the output/work volume is nearly full, independent of
      how much free space the uploads volume has.
- [ ] Update `06-UI-OPERATOR-TODO.md`'s "free disk estimate" entry once this
      lands, since its own scope-limit note references this item.

## P1 — Misconfiguration can silently destroy archived artifacts

### `ARCHIVE_RETENTION_DAYS`/`MAX_ARCHIVE_BYTES` were never validated (2026-09-16)

Current behavior (before this fix):

`ARCHIVE_RETENTION_DAYS` and `MAX_ARCHIVE_BYTES` in `giso-webui/app.py` were
read straight from their environment variables with no range check. A
negative `ARCHIVE_RETENTION_DAYS` pushes `enforce_archive_policy()`'s cutoff
(`time.time() - ARCHIVE_RETENTION_DAYS * 86400`) into the *future*, so every
archive — including one just created — looks expired and is deleted on the
very next policy check (the `archive-maintenance` container runs this every
`ARCHIVE_CLEANUP_INTERVAL_SECONDS`, an hour by default). A zero or negative
`MAX_ARCHIVE_BYTES` makes every archive "over quota" the same way. A
deployment typo — an extra `-`, a decimal point turning `30` into `300000`
misread as `0`, or similar — would silently wipe out every completed Golden
ISO the next time the maintenance loop ran, with no warning beforehand.

TODO:

- [x] Reject a negative `ARCHIVE_RETENTION_DAYS` at startup.
- [x] Reject a zero or negative `MAX_ARCHIVE_BYTES` at startup.
- [x] Add regression tests for both.

Fix: extracted `validate_archive_retention_days()` and
`validate_max_archive_bytes()` (matching the existing
`validate_image_reference()`/`DOCKER_BIN`/`ISOINFO_BIN` pattern of failing
fast at module import time for a nonsensical config value) and wired them
into both globals' initialization. `maintenance.py` needed no change: it
imports `enforce_archive_policy` from `app`, so the same validation already
guards the separate `archive-maintenance` container.

Verified by `test_negative_archive_retention_days_is_rejected`,
`test_zero_archive_retention_days_is_accepted` (zero days is a legitimate,
if aggressive, explicit choice — only *negative* is nonsensical), and
`test_non_positive_max_archive_bytes_is_rejected` in
`giso-webui/tests/test_app.py`; full suite green (203 tests). Confirmed
live: `docker run -e ARCHIVE_RETENTION_DAYS=-5 ... python3 -c "import app"`
and the `MAX_ARCHIVE_BYTES=0` equivalent both fail immediately with the new,
clear `RuntimeError`, while a plain `import app` with no overrides still
succeeds. ruff and Graphify clean.

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
- [x] Add browser regression test with two uploaded ISOs — no JS/DOM test
      runner exists in this repo (see `05-TESTING-CI-TODO.md`), so this is
      a live-verification record rather than an automated test, matching
      how other browser-only regressions in this project are tracked.
      Confirmed 2026-09-16 against an isolated throwaway container: uploaded
      two real ISOs (`ncs5500-mini-x-26.1.1.iso`,
      `ncs5500-mini-x-26.1.2.iso`) through the actual `/api/uploads` flow,
      then read the live DOM — `[name=iso]` stayed empty (no arbitrary
      first-ISO auto-selection), `#start-build` stayed disabled ("Waiting
      for an ISO and a customization…"), and `#iso-check` explicitly read
      "Select one base ISO in Expert settings."

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

### A CSC group's "select all" checkbox could never show fully checked when the group had a conflicted duplicate (2026-09-16)

Current behavior (before this fix):

`syncManualPackageValue()` in `giso-webui/static/manual-packages.js` computed
each CSC group checkbox's checked/indeterminate state from *every* RPM
checkbox carrying that `data-csc`, including ones disabled by the
same-name/different-hash conflict handling above. The group checkbox's own
click handler already correctly skips disabled boxes
(`if (!box.disabled) box.checked = ...`), so a group with one conflicted
duplicate and two selectable RPMs could never reach `checked === 3`
(the conflicted RPM can never be checked) — checking both selectable RPMs
by hand left the group checkbox stuck showing `indeterminate` forever,
never `checked`, even though every box the group checkbox can actually
affect was already checked.

TODO:

- [x] Compute the group checkbox's checked/indeterminate state from only
      the members it can actually toggle (i.e. exclude disabled/conflicted
      RPMs from both the denominator and the checked count).

Fix: filter `members` to `!box.disabled` before computing `checked`/
`groupBox.checked`/`groupBox.indeterminate` in `syncManualPackageValue()`.

Verified live in a browser (isolated throwaway container, its own temp
`DATA_ROOT`/etc., never the shared persistent volumes): injected a fixture
with one CSC group of two selectable RPMs (`a.rpm`, `b.rpm`) plus a
same-basename-different-hash conflict pair (`c.rpm` ×2, both disabled),
called the real `renderManualPackages(data, plan)`, checked both selectable
boxes, called `syncManualPackageValue()`, and confirmed the group checkbox
reports `checked: true, indeterminate: false` (previously would have been
`checked: false, indeterminate: true` given 2 of 4 total members checked).
No DOM/JS test runner exists in this repo yet (tracked separately in
`05-TESTING-CI-TODO.md`), so this fix could not get an automated regression
test; the existing Python test suite (199 tests) is unaffected and still
passes, and ruff/Graphify remain clean.

## P1/P2 — Platform and compatibility validation

### Ownership vouchers/certificate could be submitted one without the other with no warning (2026-09-16)

Current behavior (before this fix):

`--ownership-vouchers` and `--ownership-certificate` were two independent
`PATH_OPTIONS` with no relationship check between them.
`.gisobuild-tool/src/lnt/builder/_coordinate.py:_validate_ovs_and_oc()`
confirms upstream's real rule: "Check that the input ISO either contains
both OVs and an OC, or neither" — raising `OVOCMismatchError` and failing
the build if violated. An operator supplying only one would get no signal
from `giso-webui` until the actual build failed.

Fix:

- [x] `create_build_plan()` in `giso-webui/app.py` now adds a warning
      (`"Ownership vouchers and an ownership certificate are normally
      supplied together..."`) whenever exactly one of the two payload
      fields is set, shown in the Review BuildPlan step via the same
      warnings-surfacing fix from earlier this session.
- [x] Deliberately a **warning, not a blocker**: upstream's check is against
      the *final image's* package groups, which can already contain one of
      the two from the base ISO before this build ever runs. `giso-webui`
      has no ISO-content inspection for existing ownership package groups
      (same `isols.py`/`image.py` dependency noted in
      `02-AUTOMATION-BUILDPLAN-TODO.md`'s ISO-inspection section), so a hard
      block here would produce false positives for a legitimate
      add-the-other-one-to-an-already-provisioned-ISO build — exactly the
      "do not invent a stricter interpretation than upstream" principle in
      `docs/AI-MASTER-PROMPT.md` section 1.

Verified by `test_build_plan_warns_when_only_ownership_vouchers_are_set`,
`test_build_plan_warns_when_only_ownership_certificate_is_set`, and
`test_build_plan_does_not_warn_when_both_or_neither_ownership_fields_are_set`
in `giso-webui/tests/test_app.py`. 180 tests pass, ruff clean, Graphify
refreshed.

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
- [x] Do not block an upstream-valid platform solely because the local
      filename parser does not recognize it — fixed 2026-09-16; see
      `01-PLATFORM-UPSTREAM-TODO.md` "Unknown-but-valid platforms"
      (`exr-generic`/`lnt-generic` manual fallback platforms) for the full
      writeup and evidence.
- [x] Add unknown/future-platform regression fixture — same fix;
      `test_unknown_upstream_platform_can_still_be_built_via_manual_override`
      and `test_generic_platform_fallbacks_are_never_inferred_from_a_filename`
      in `giso-webui/tests/test_platform_compatibility.py`.

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

### A single failed archive-policy cycle crashed the maintenance daemon entirely (2026-09-16)

Current behavior (before this fix):

- `maintenance.py`'s `main()` calls `enforce_archive_policy()` in a bare
  `while True:` loop with no exception handling around the call.
- `archive-maintenance` in `compose.yaml` has `healthcheck: disable: true`
  and `restart: unless-stopped` — a crash is silently retried by Docker with
  no external signal that anything is wrong beyond the container's own
  restart count.

Risk: any transient `OSError` from `enforce_archive_policy()` — a
permission hiccup, disk pressure, a flaky network-backed volume, a job
directory removed out from under `shutil.rmtree()` by something else on the
same host — kills the whole daemon for that cycle. If the underlying cause
is persistent rather than transient, the container crash-loops indefinitely
and archive retention/quota enforcement silently stops running, with
nothing but a rising restart count to notice it by.

TODO:

- [x] Catch `OSError` around the `enforce_archive_policy()` call, log it,
      and continue to the next interval instead of crashing the process.
- [x] Add a regression test proving one failed cycle doesn't stop the loop
      from reaching the next one.

Fix: wrapped the call in `maintenance.py:main()` in `try`/`except OSError`;
a failed cycle now prints `"Archive policy check failed, will retry next
interval: <error>"` and sleeps for the normal interval before trying again,
exactly like a successful "no files removed" cycle. `enforce_archive_policy()`
itself is unchanged — this only stops one bad cycle from taking down every
future cycle with it.

Verified by two new tests in `giso-webui/tests/test_maintenance.py`:
`test_transient_os_error_does_not_crash_the_loop` (asserts
`enforce_archive_policy()` is called again on the next interval after an
`OSError`, using a `time.sleep` side effect list to break out of the
infinite loop deterministically) and
`test_successful_cycle_reports_removed_jobs`. Full suite green (198 tests)
inside the built container; ruff and Graphify clean.

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

### `gisobuild_commit()` silently returned null due to git's ownership check (2026-09-16)

Found during a full post-change verification pass (not the initial feature
work): re-running the full test suite from a clean image build after adding
the `/api/version` feature earlier the same day showed
`test_version_reports_the_real_commit_of_a_git_checkout` failing —
`gisobuild_commit()` returned `None` instead of a real commit hash, even
though `.git` genuinely existed at the checked path.

Root cause: `git=2.54.0-r0` (added to `giso-webui/Dockerfile` for this same
feature) enforces the "dubious ownership" protection introduced in modern
git — it refuses to run `rev-parse` against a directory not owned by the
container's user, which is exactly what a bind-mounted `.gisobuild-tool`
checkout looks like from inside the container. Reproduced directly:
`git -C /project rev-parse --short HEAD` failed with `fatal: detected
dubious ownership in repository at '/project'`. `gisobuild_commit()`
already degrades gracefully (catches the non-zero exit, returns `None`
rather than raising), so this was never a crash — just a feature that would
have silently returned "unknown" far more often than intended, depending on
the host filesystem's exact ownership metadata for the mounted checkout.

The exact same issue, and the same fix, had already been identified and
applied to `docker/tooling.Dockerfile` for `scripts/check_graphify_freshness.py`'s
`git ls-files` call earlier the same day — this entry is that same class of
bug recurring in a second Dockerfile that happened to add `git` afterward,
which is exactly the kind of thing a full verification pass catches and an
isolated unit test of one new function does not.

Fix:

- [x] Added `git config --system --add safe.directory '*'` to
      `giso-webui/Dockerfile` right after installing `git`. Safe here: this
      container only ever reads a checkout mounted read-only by its own
      operator, never a shared multi-tenant one.

Verified: `git -C /project rev-parse --short HEAD` now succeeds inside the
rebuilt image, `test_version_reports_the_real_commit_of_a_git_checkout`
passes, full suite (182 tests) passes, hadolint stays clean.

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
- [x] Add a `pyproject.toml`/`ruff.toml` that explicitly selects the intended
      rule set, instead of relying on whatever ruff's shifting defaults are.
      Pinning the *version* (above) makes results reproducible across runs;
      this remaining item is about pinning the *rule selection* too. Fixed
      2026-09-16: added `ruff.toml` at the repo root with an explicit
      `[lint] select = [...]` listing all 413 rule codes that ruff 0.16.7
      actually enables with no config file present (confirmed via
      `ruff check --isolated --show-settings`, which is unaffected by any
      config discovery). Verified by diffing `ruff check --show-settings`'s
      resolved `linter.rules.enabled`/`linter.rules.should_fix` output
      before and after adding the file — byte-for-byte identical — and by
      re-running `ruff check` across every path the CI lint step covers
      (`giso-webui/app.py`, `cisco_download.py`, `maintenance.py`,
      `platform_validation.py`, `tests`, `staging`, `scripts`), which still
      reports "All checks passed!" with no behavior change. A future ruff
      upgrade can now only change what a given rule *code* checks for, not
      silently add or remove rules by changing its own defaults.

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

### A stale partial file from a crashed download made the next attempt fail too (2026-09-16)

Current behavior (before this fix):

`CiscoSoftwareClient.download()` in `giso-webui/cisco_download.py` writes to
`destination.with_name(f".{destination.name}.part")` opened with mode
`"xb"` (exclusive create — fails if the file already exists). If a previous
download was interrupted by something that skips the function's own
`except` cleanup — the process being killed, the host restarting — that
`.part` file is left on disk. The next download attempt for the same
destination then fails `open("xb")` with `FileExistsError`, which the
generic `except (OSError, ...)` handler at the bottom turns into "Cisco
download was interrupted" — a confusing failure for what is actually a
leftover from a *previous* attempt, not this one. That handler does delete
the stale file as a side effect before re-raising, so a second retry
happens to succeed — but only after one needlessly failed attempt.

Fix: `download()` now removes any existing `.part` file for this
destination before starting, since only one Cisco download runs at a time
(`cisco_download_running()`), so there is never a legitimate concurrent
writer to protect against — only ever a stale leftover from a dead attempt.

TODO:

- [x] Remove any pre-existing `.part` file before opening it exclusively.
- [x] Add a regression test using a real pre-created stale file, confirmed
      to fail against the old code (`FileExistsError` →
      `CiscoDownloadError: Cisco download was interrupted`) and pass with
      the fix.

Verified by `test_stale_partial_file_from_a_previous_crashed_attempt_is_overwritten`
in `giso-webui/tests/test_cisco_download.py`. Confirmed the regression test
actually exercises the bug by temporarily reverting the one-line fix and
re-running just that test in the built container — it failed with exactly
the predicted error — then restoring the fix and confirming the full suite
(199 tests) passes; ruff and Graphify clean.

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
