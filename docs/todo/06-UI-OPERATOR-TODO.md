# TODO — Operator UX

## Primary UX goal

The UI should immediately answer:

1. What base image did you find?
2. Which platform/release/build engine is it?
3. Which fixes will be included?
4. Is anything wrong?
5. Can I start the build?

## Normal workflow

### Step 1 — Files

- [x] drag/drop ISO — `#drop-zone` in `giso-webui/static/app.js` accepts any
      dropped file via `uploadFiles(event.dataTransfer.files)`; the backend
      accepts `.iso` in `upload_init()`.
- [x] drag/drop TAR/RPM/SMU — same drop handler; `.rpm`/`.tar`/`.tgz` are all
      in `upload_init()`'s allowed extension set, and `.tar`/`.tgz` are
      auto-extracted server-side in `upload_complete()`.
- [x] Cisco download integration — `#cisco-search-form`/`#cisco-results-form`/
      `#cisco-accept` in `app.js`, backed by `/api/cisco/search`,
      `/api/cisco/downloads`, and `/api/cisco/downloads/<id>/accept`.
- [x] automatic analysis starts immediately — `renderInputs()` calls
      `applySmuRecommendation(data.recommendation)` on every `loadInputs()`,
      and `uploadFile()` calls `loadInputs()` right after each upload
      completes, with no operator action required in between.

### Step 2 — Review BuildPlan

Show:

- [x] ISO — `smu-plan-flow` "Base ISO" field.
- [x] release — `smu-plan-flow` "IOS XR" field.
- [x] engine — added 2026-09-16: the flow now looks up the platform's
      `architecture` from `/api/platforms` and shows an "Engine" field
      (EXR/LNT) alongside Platform; previously this was only shown in the
      final "Start build?" confirmation dialog, not during ongoing review.
- [x] platform — `smu-plan-flow` "Platform" field.
- [x] confidence/source — see "Confidence display" below.
- [x] CSC groups — `smu-groups`/`csc-grid` section.
- [x] excluded packages — `excluded` `<details>` list, each with its reason.
- [x] warnings — fixed 2026-09-16: `recommend_smu_selection()` in
      `giso-webui/platform_validation.py` computed
      `validate_smu_selection()`'s `warnings` (e.g. "Filename checks cannot
      prove RPM dependencies; Cisco gisobuild performs the authoritative
      dependency check", or "supersedence data is required" for a
      multi-fix-per-component conflict) but never included them in its
      return value, so the automatic-selection preview used by `discover()`
      and `/api/smu/recommendation` — the actual default workflow — silently
      dropped every warning; only the separately-triggered, manually-run
      "Check compatibility" tool (`/api/compatibility`) ever showed them.
      Now rendered as a "Review before building" box in `app.js`. Verified
      by `test_automatic_selection_surfaces_dependency_check_warning` in
      `giso-webui/tests/test_platform_compatibility.py`, and confirmed live:
      uploaded a matching ISO+RPM pair to the running container and saw the
      warning render in a real browser.
- [x] blockers — fixed 2026-09-16: `recommend_smu_selection()` in
      `giso-webui/platform_validation.py` already ran `validate_smu_selection()`
      against the automatically-selected package set internally (to compute
      `package_groups`/`component_conflicts`) but discarded its `issues` list —
      the exact same "warnings" bug already fixed above, but for the blocking
      case. In practice this meant an automatic selection could pick two RPMs
      for the same component and CSC at different versions (both individually
      pass the platform/release filename filters that gate automatic
      selection) and the persistent Step 2 panel would still show a green
      "Calculated" pill and `plan.message` ("Selected N matching RPMs…") with
      no hint of the problem — the operator only found out when `/api/build-plan`
      rejected it at the final "Start build" click. `recommend_smu_selection()`
      now returns `analysis["issues"]` as a `blockers` field (same shape
      `/api/build-plan`'s own `blockers` already used); `discover()` and
      `/api/smu/recommendation` both return this shape unchanged, so no
      backend endpoint change was needed. `app.js`'s `applySmuRecommendation()`
      now renders a red "Fix before building" list via the existing
      `compatibilityList()` helper and switches the state pill to "Blocked"
      (red) instead of "Calculated" (green) whenever blockers are present.
      This does not (and does not need to) duplicate every blocker
      `/api/build-plan` can produce — the other blocker sources there (no ISO
      selected yet, platform/release undetectable, an Expert-settings manual
      platform override that fails validation) are either already visible via
      the existing not-ready pill/message, or only apply once the operator
      has left automatic selection, so they remain correctly gated at final
      confirmation. Verified by
      `test_automatic_selection_surfaces_a_real_blocking_issue` in
      `giso-webui/tests/test_platform_compatibility.py` (backend) and
      `test_smu_plan_blockers_are_shown_during_review_not_only_at_final_confirmation`
      in `giso-webui/tests/test_build_script.py` (frontend rendering); full
      217-test suite passes, ruff clean, Graphify refreshed.
- [x] expected output — fixed 2026-09-16: rather than duplicating
      `/api/build-plan`'s `expected_outputs` computation server-side (which
      needs the payload's `skip_usb_image` toggle, not available in the
      lighter-weight `/api/smu/recommendation`/`discover()` preview),
      `expectedOutputText()` in `giso-webui/static/app.js` computes the same
      ISO-vs-USB answer client-side from data the Step 2 review already has:
      the automatic plan's platform and each platform's `usb_image`
      capability from `/api/platforms`, folded with the live "Skip USB
      image" checkbox. Rendered as a persistent "Expected output" field
      (`#expected-output-value`) in the same `smu-plan-flow` row as
      Platform/Engine/IOS XR, and kept live afterwards: toggling "Skip USB
      image" or manually overriding the platform in Expert settings updates
      it in place via `refreshExpectedOutput()`, without recalculating the
      whole plan. Verified by
      `test_expected_output_is_shown_during_review_not_only_at_final_confirmation`
      in `giso-webui/tests/test_build_script.py`, and confirmed live: uploaded
      an NCS 5500 ISO to the running container and saw "ISO + USB" render
      immediately, then flip to "ISO only" the instant "Skip USB image" was
      checked, with no other action taken. Full 218-test suite passes, ruff
      clean, Graphify refreshed.
- [x] free disk estimate — fixed 2026-09-16, with a known scope limit noted
      below: `estimatedOutputBytes()` in `giso-webui/static/app.js` computes
      an honestly-labelled upper bound (base ISO size + every selected RPM's
      size, not gisobuild's actual repack size) entirely from `inputs.files`
      — the same inventory (with per-file `size`) already loaded for Step
      1's file list, so no new backend endpoint was needed. `renderDiskEstimate()`
      compares this against `/api/storage`'s `disk_free_bytes` (cached in a
      new `storageInfo` global so it can be recomputed whenever either the
      plan or the storage figure changes) and shows it as a persistent line
      under the Step 2 flow, turning red with an explicit warning when the
      estimate exceeds free space.
      **Former known limit, closed 2026-09-17**: this originally measured
      only the uploads volume (`DATA_ROOT`), while gisobuild actually
      extracts/builds in `WORK_ROOT` and writes its artifact to
      `OUTPUT_ROOT` — separate named Docker volumes a host can size
      independently, so a full build volume could still read as "enough
      space". `build_volume_free_bytes()` now measures all three and
      `build_space_blockers()` turns a short one into a real BuildPlan
      blocker (see `07-BUG-AUDIT-TODO.md`, "No free-space check exists for
      the volumes a build actually writes to"), so the estimate line lists
      each volume separately and a genuinely full working/output volume
      refuses the build up front instead of failing partway through.
      Originally verified by
      `test_disk_estimate_is_shown_during_review_and_uses_already_loaded_data`
      in `giso-webui/tests/test_build_script.py`, and confirmed live: booted
      a throwaway container, uploaded a real file, saw the estimate render
      with the real free-space figure, then forced `storageInfo.disk_free_bytes`
      below the estimate in the browser console and watched it switch to the
      red "may not be enough space" state. Full 219-test suite passes, ruff
      clean, Graphify refreshed.

### Step 3 — Build

- [x] clear progress — `#build-progress`/`#build-percent`, driven by real log
      milestones (`append_log()`'s `milestones` table in `giso-webui/app.py`),
      not a fake animation.
- [x] current phase — `#build-phase`, set from `job.phase`.
- [x] cancellation — `#cancel-build`, backed by `DELETE /api/jobs/<id>`.
- [x] friendly error — `#friendly-status` gives a plain-language message per
      job status (interrupted/failed/cancelled/success/running).
- [x] technical details collapsed by default — `<details class="technical-log">`
      in `giso-webui/templates/index.html` has no `open` attribute, so the
      raw build log is closed until the operator clicks "Show technical
      details".
- [x] artifact download — `#artifacts` links built from `job.artifacts`.
- [x] checksums — not shown inline on the job-completion card itself, but
      `loadArchive()` runs automatically right after a build finishes
      (`poll()`'s terminal branch) and each archived file has a "Show MD5 /
      SHA-256" button (`/api/archive/<job>/<name>/checksums`).
- [x] build report — added 2026-09-16: a "Show build report" `<details>` in
      Step 3 (`giso-webui/static/app.js`'s `renderBuildReport()`), populated
      from `job.build_plan` — already stored on every job and exposed by
      `GET /api/jobs/<id>` (`build_plan` is not in `PRIVATE_JOB_FIELDS`), so
      this was a pure frontend addition, no backend change. Shows base
      ISO/platform/engine/release/package count, inventory revision and
      BuildPlan fingerprint, a collapsible list of every input's SHA-256
      (ISO and each selected RPM — the "final checksums" `docs/AI-MASTER-PROMPT.md`
      section 17 asks for), the CSC fix groups included, excluded packages
      with reasons, and any BuildPlan warnings (e.g. the ownership
      voucher/certificate mismatch warning above). Confirmed by injecting a
      realistic `build_plan` shape into the running page in a browser and
      verifying every section rendered correctly.
- [x] generated command preview (`docs/AI-MASTER-PROMPT.md` section 10) —
      added 2026-09-16 alongside the build report: a "Show generated
      gisobuild command" `<details>` with a copy button. The real `command`
      list stays in `PRIVATE_JOB_FIELDS` — its `docker run ... -v <source>
      ...` prefix can contain the real host filesystem path or Docker
      volume name behind a bind mount, which is genuinely sensitive
      deployment detail, not something a build operator needs. A new
      `command_preview()` in `giso-webui/app.py` strips that prefix down to
      the actual `gisobuild.py` invocation and shows each absolute
      container path as its basename — accurate (the real arguments, not a
      guess), matching section 10's own example shape. Stored as a new,
      non-private `command_preview` job field, computed once at job
      creation. Verified by
      `test_command_preview_strips_docker_wrapper_and_shows_basenames` (a
      synthetic real-looking command proving the docker wrapper, a fake
      host path, and a fake Docker volume name are all absent from the
      output) and `test_created_job_exposes_a_safe_command_preview_but_not_the_real_command`
      in `giso-webui/tests/test_app.py`, and confirmed live in a browser.
- [x] preview text config files before building (`docs/AI-MASTER-PROMPT.md`
      "UI principles" — avoid unexplained flags, give operators enough
      information to trust a build without leaving the browser) —
      added 2026-09-16. The six Expert-settings file fields (XR config, ZTP
      ini, boot script, key request, ownership vouchers, ownership
      certificate) previously only offered a bare path `<input>` with
      autocomplete; an operator had no way to confirm *which* file they had
      picked without opening it outside the UI. Each field now has a
      "Preview" button next to it. `GET /api/file-preview?path=...` in
      `giso-webui/app.py` resolves the path through the existing
      `safe_data_path()` (the same traversal guard `discover()` and the
      build-plan endpoints already use), refuses anything over
      `MAX_FILE_PREVIEW_BYTES` (64 KiB — these are small text configs, never
      the multi-GB ISO/RPM inputs) or that fails to decode as UTF-8 (the
      ownership voucher/certificate fields are frequently binary PKCS7/DER,
      which must show a clear "not plain text" message rather than garbage
      or a raw exception), and otherwise returns the file's text. Verified
      by `test_file_preview_returns_text_content_of_a_small_config_file`,
      `test_file_preview_refuses_a_file_that_is_too_large`,
      `test_file_preview_refuses_a_binary_file`,
      `test_file_preview_rejects_a_path_outside_the_upload_directory`, and
      `test_file_preview_rejects_a_directory` in
      `giso-webui/tests/test_app.py`, and confirmed live against a
      throwaway, isolated container (its own temp `DATA_ROOT`/etc., never
      the shared persistent volumes) by fetching a real `router.cfg`
      through the running UI and by exercising the traversal-rejection and
      missing-file paths.
- [x] make every Expert-settings group collapsible, not just some of them —
      fixed 2026-09-16 after the operator opened "Expert settings" and found
      it hard to use: "1. Image identity" and "2. SMU compatibility" were
      plain always-expanded `<section>`s, so opening the outer "Expert
      settings" `<details>` dumped two large blocks of fields (including the
      whole SMU compatibility-check UI) on screen at once, while the other
      three groups (Additional files, LNT controls, Build behavior) were
      already collapsible `<details>`. That inconsistency, not any one
      field, was the actual "not easy to use" problem — matching
      `docs/AI-MASTER-PROMPT.md` "UI principles"' explicit "avoid giant
      forms" / "consistent typography and spacing" guidance. Converted both
      remaining `<section class="expert-group">` blocks in
      `giso-webui/templates/index.html` to `<details class="expert-group">`
      with a plain `<summary>` (dropping the now-redundant `<h3
      id="smu-compatibility-title">` / `aria-labelledby` pair, since a
      `<summary>` is already the accessible name for its `<details>`).
      Opening "Expert settings" now shows five short, equally-collapsed
      group headers instead of a wall of fields. No JS in `app.js` or
      `manual-packages.js` referenced `smu-compatibility-title` or depended
      on either group being a `<section>`; the 190-test suite still passes
      unchanged. Confirmed live in a browser: all five groups list as
      `DETAILS` elements, and each expands/collapses independently on
      click.

- [x] persist a `build-report.json` next to each archived artifact
      (`docs/AI-MASTER-PROMPT.md` "Artifacts and reproducibility": "every
      build should record" web UI/gisobuild version, all input/output
      checksums, the exact BuildPlan and the generated CLI) — added
      2026-09-16. The "Show build report" UI already rendered this
      information for a *running* job from in-memory state, but nothing
      persisted it once the job aged out of job history and the archive was
      all that remained. `build_report()` in `giso-webui/app.py` composes a
      plain JSON document (job id/label/timestamps, `web_ui_version`,
      `gisobuild_image`/`gisobuild_commit`, the safe `command_preview` as
      `generated_command`, the full `build_plan`, and `output_artifacts`),
      and `write_build_report()` writes it to
      `ARCHIVE/<job_id>/build-report.json` right after
      `archive_giso_artifacts_and_cleanup()` succeeds in `run_job()` — a
      write failure is swallowed (it's a convenience record, not something
      that should fail an otherwise-successful build). `archive_giso_artifacts_and_cleanup()`
      now also returns each artifact's `sha256` (reusing the digest already
      computed for archive-copy verification, no extra hashing pass) so the
      report's output checksums are real, not recomputed separately.
      `GET /api/archive` reports a new `has_report` flag per item (checked
      once, cheaply, by testing whether the file exists) and the archive
      list in `giso-webui/static/app.js` shows a "Build report" download
      link next to the ISO row when it's true — never for a job archived
      before this feature existed, so the UI never links to a 404. Verified
      by `test_archived_artifacts_report_their_sha256`,
      `test_build_report_captures_version_plan_and_output_checksums`,
      `test_write_build_report_persists_json_next_to_archived_artifacts`,
      `test_write_build_report_does_not_raise_when_archive_dir_is_missing`,
      and `test_archive_list_reports_has_report_only_when_the_file_exists`
      in `giso-webui/tests/test_app.py`, and confirmed live end-to-end
      (archive a fake artifact, write its report, then fetch both
      `/api/archive` and `/archive/<job>/build-report.json` over HTTP, and
      see the "Build report" link render in the browser) against a
      throwaway, isolated container — its own temp `DATA_ROOT`/etc., never
      the shared persistent volumes.

## Automatic by default

Do not ask for these unless ambiguous:

- [x] platform — `infer_platform()` from the ISO filename; the platform
      `<select>` is only meant to be touched when detection fails (see
      `test_unknown_iso_requires_platform_selection`).
- [x] architecture — `inspect_iso_architecture()` reads it from the ISO's
      own contents; never asked.
- [x] target release — `updateAutomaticTargetRelease()` auto-fills from the
      ISO filename and tracks whether the operator manually overrode it, so
      it only stays put once touched intentionally.
- [x] repo path — `auto_repo: true` is the default; `build_command()` stages
      selected RPMs into a repo directory automatically instead of asking
      for one.
- [x] package list — "Automatic — recommended" is the `checked` default
      radio in `giso-webui/templates/index.html`; manual package selection
      is the opt-in alternative.
- [x] build engine — derived from the detected/selected platform
      (`platform_profile()["engine"]`); never asked directly.

## Expert settings

Keep advanced controls, but:

- [x] capability-driven
- [x] hide unsupported settings
- [x] server validates everything
- [x] warn before unsafe/manual overrides — the final "Start Golden ISO
      build?" confirmation in `giso-webui/static/app.js` now shows a red
      ⚠ warning line, and switches the confirm button itself to the danger
      style, whenever manual package selection is active or the platform/
      ISO was manually overridden in Expert settings, instead of looking
      identical to a fully-automatic build. Confirmed live in a browser:
      switching to "Manual package list" and starting a build shows "⚠
      Manual package selection is active: automatic supersedence and
      CSC-group matching were bypassed for the packages you chose." with a
      red confirm button.

## Explain decisions

Every exclusion must explain why:

- [x] wrong release — `recommend_smu_selection()` reports `"Different IOS XR
      release"` per excluded RPM (`giso-webui/platform_validation.py`),
      rendered per-item in the Review BuildPlan excluded-packages list
      (`giso-webui/static/app.js`). Verified by
      `test_automatic_selection_keeps_matching_repository_and_excludes_mismatches`.
- [x] wrong platform — same mechanism, reason `"Different platform"`.
      Verified by the same test.
- [x] wrong architecture — same mechanism, reason `"Processor architecture
      does not match the base ISO"`. Verified by
      `test_automatic_selection_excludes_wrong_architecture_rpms`.
- [x] superseded — `add_superseded_exclusions()` in `giso-webui/app.py`
      explains RPMs `active_rpm_names()` already dropped from the automatic
      candidate list, with reason `"Superseded by a newer fix per Cisco
      supersedence notes"`, wired into `discover()`, `/api/smu/recommendation`,
      and `create_build_plan()`'s automatic-selection path. Before this fix,
      `active_rpm_names()` silently filtered these files out and
      `data.superseded` from `/api/inputs` was computed but never read by the
      frontend, so a superseded SMU just vanished with no explanation.
      Verified by `test_superseded_rpm_is_excluded_with_a_reason_not_silently_dropped`
      and `test_build_plan_automatic_selection_explains_superseded_exclusions`
      in `giso-webui/tests/test_app.py`, and confirmed live in a browser
      against the running container.
- [x] duplicate — `inventory_files()` tags each file `duplicate`/
      `duplicate_kind`/`provenance`, surfaced in
      `giso-webui/static/manual-packages.js`.
- [x] malformed metadata — metadata that is unreadable rather than wrong,
      which must never be explained as "different release"/"different
      platform" (that would assert a fact the filename does not actually
      carry). `recommend_smu_selection()` already excluded these with their
      own distinct reasons, `"Platform is missing from filename"` and
      `"Release is missing from filename"`, but only the platform half had a
      test; added
      `test_unparseable_rpm_metadata_is_excluded_with_a_specific_reason`
      (2026-09-17) in `giso-webui/tests/test_platform_compatibility.py`
      pinning both, including a wholly unparseable `totally-unparseable.rpm`.
- [x] ambiguous metadata — metadata that parses cleanly but yields more than
      one valid reading, where the honest answer is to say so rather than
      pick one. All three real cases were already implemented and are now
      each pinned by a test:
      • two base ISOs → `discover()` returns "More than one base ISO was
        found; keep one ISO or select it in Expert settings" and never
        auto-selects (`test_two_isos_are_reported_as_ambiguous_rather_than_silently_resolved`,
        added 2026-09-17, plus the live DOM verification in
        `07-BUG-AUDIT-TODO.md`);
      • same RPM filename, different content → "another RPM has the same
        filename but different content. Remove the unwanted copy."
        (`test_different_duplicate_rpms_are_rejected`, and the live
        duplicate-DOM verification);
      • two versions of one component for one CSC → "Multiple versions of
        {component} for {CSC} are selected; keep one RPM"
        (`test_multiple_versions_of_same_component_and_fix_are_rejected`).
      In every case the build is blocked until the operator resolves it —
      the system states the ambiguity instead of guessing past it.
- [x] dependencies that cannot be satisfied — added 2026-09-17, the
      *pre-build* counterpart to the entry below. Where that one explains a
      failure gisobuild already hit, this one prevents the build from
      starting: `missing_package_dependencies()` compares each selected
      RPM's own `Requires` (read from the RPM header) against the base
      image's own shipped package list (read from `iosxr_image_mdata.yml`),
      and a provably unsatisfiable exact-version requirement becomes a
      BuildPlan blocker shown in Step 2's "Fix before building" list, naming
      the requirement, which packages need it, what the base image actually
      ships, and what to do ("download the Cisco SMU that provides it, or
      remove the package that needs it"). Validated against the operator's
      own real content: their exact failing 24-RPM selection is now refused
      up front with the same five requirements their real gisobuild log
      reported, while a base-bundle-only build still passes with zero
      blockers. Full detail and the deliberate anti-false-positive rules are
      in `07-BUG-AUDIT-TODO.md`.
- [x] gisobuild's own RPM dependency-check failures — added 2026-09-16 after
      a real production build failed with a genuine missing-dependency error
      (Cisco's own GISO documentation: "the child RPM is dependent on the
      parent RPM. If only the child RPM is included, the Golden ISO build
      fails."). gisobuild's compatibility check runs RPM's own dependency
      resolution and reports unmet requirements as
      "`<requirement> is needed by <package>`" lines — RPM's standard
      transaction-check format (`.gisobuild-tool`'s own
      `gisobuild_exr_engine.py`/`_pkgchecks.py` look for this exact marker).
      Before this fix an operator had to open the raw build log and find
      these lines themselves. `parse_missing_dependencies()` in
      `giso-webui/app.py` extracts them (robust to the real
      `"YYYY-MM-DD HH:MM:SS::  \t"` log-line prefix, verified against a real
      1442-line failed-build log, not a synthetic guess) and `public_job()`
      exposes them as `missing_dependencies` on a failed job; the UI renders
      a dedicated "Missing dependencies found by gisobuild" panel above the
      technical log. This does not predict or prevent a failure — only
      gisobuild's real check against the actual base image can determine
      that — it only makes an already-real failure legible. Verified by five
      tests in `giso-webui/tests/test_app.py` (including one using the
      verbatim real log excerpt) and one in
      `giso-webui/tests/test_build_script.py`, and confirmed by parsing the
      complete real 1442-line `gisobuild.log` end-to-end (15 unique missing
      dependencies extracted correctly) and by injecting the resulting data
      into the real page in a browser.

## Confidence display

Use:

- [x] `VERIFIED`
- [x] `INFERRED`
- [x] `UNKNOWN`

Implemented as `confidence_report()` in `giso-webui/app.py`, shared by
`discover()` (`/api/inputs`), `/api/smu/recommendation`, and
`create_build_plan()` (`/api/build-plan`), and rendered as a badge grid in the
Review BuildPlan step (`confidenceGrid()` in `giso-webui/static/app.js`).
Verified by `test_build_plan_confidence_is_unknown_when_no_iso_is_selected`,
`test_build_plan_confidence_marks_filename_derived_fields_as_inferred`,
`test_build_plan_confidence_marks_manual_platform_as_operator_selected`, and
`test_build_plan_confidence_reports_verified_iso_architecture_from_real_iso`
in `giso-webui/tests/test_app.py`.

Honesty correction versus the examples originally written here: platform and
release are read from the **filename**, not from ISO metadata, so they are
reported as `INFERRED`, never `VERIFIED` — `iosxr_image_mdata.yml` only
exposes processor architecture, not platform or release. Likewise RPM
architecture is read from the **filename suffix**, not the RPM header (no RPM
header parser exists in this codebase), so it too is `INFERRED`. The only
field this codebase can honestly call `VERIFIED` today is ISO architecture,
because `inspect_iso_architecture()` reads it from the ISO's own contents.

- [x] Platform — INFERRED from ISO filename (not VERIFIED: no platform field
      is read from ISO metadata)
- [x] Release — INFERRED from ISO filename (not VERIFIED: no release field is
      read from ISO metadata)
- [x] RPM architecture — INFERRED from RPM filename suffix (not VERIFIED: no
      RPM header parsing exists)
- [x] ISO architecture — VERIFIED from the ISO's own contents
      (`inspect_iso_architecture()`)
- [x] CSC — INFERRED from filename
- [x] Dependency closure — UNKNOWN until gisobuild validation

Never present heuristic guesses as verified facts.

Future work, not implemented: parsing real RPM headers (e.g. via an `rpm`
binary in the container) to earn a genuine `VERIFIED` for RPM architecture,
and parsing ISO metadata for platform/release the same way architecture is
read today.

## Search and filtering (`docs/AI-MASTER-PROMPT.md` section 55)

- [x] Manual package list search by filename or CSC ID — added 2026-09-16:
      `#manual-package-filter` in `giso-webui/static/manual-packages.js`,
      only shown once there are 8+ RPMs (small lists don't need it). Filters
      by substring against each RPM's filename or its CSC group's legend
      text; matching the group name reveals every member. Purely a
      visibility toggle (`hidden`), so it never touches checkbox selection
      state. Verified live in a browser with 10 fixture RPMs: typing
      "pkg03" left exactly 1 of 10 options and its CSC group visible,
      clearing the filter restored all 10.
- [x] Compatible-only / selected-only filters — added 2026-09-16:
      `#manual-package-compatible-only`/`#manual-package-selected-only`
      checkboxes next to the existing text filter, shown/hidden together
      with it (8+ RPMs). `applyManualPackageFilter()` now composes three
      independent conditions (text match, `!incompatible` when
      compatible-only is checked, checkbox `.checked` when selected-only is
      checked) — an option is visible only when all active filters pass.
      "Selected only" updates live as boxes are checked/unchecked (wired
      through the existing `syncManualPackageValue()`, which already runs
      on every checkbox change), so unchecking a currently-visible item
      while the filter is active removes it from view immediately — the
      same behavior as a "starred items" filter elsewhere. Verified live in
      a browser with 8 fixture RPMs (6 compatible, a same-basename/
      different-hash conflict pair): compatible-only correctly hid both
      conflicted options; checking two compatible options then enabling
      selected-only showed exactly those two; unchecking one of them live
      narrowed the view to the other, with no page reload.
      Architecture/version filters remain unimplemented — RPM
      architecture is already shown in the checksums/build report but has
      no dedicated filter control yet.
- [x] Archive list search by filename — added 2026-09-16, same pattern as
      the manual package filter: `#archive-filter` in
      `giso-webui/templates/index.html`, only shown once there are 6+
      archived artifacts (each row is a full card with several buttons, so
      it takes more vertical space than a checkbox line — a lower
      visibility threshold than the manual package list's 8 makes sense).
      Filters `giso-webui/static/app.js`'s `#archive-list .archive-row`
      elements by substring against the artifact's own filename
      (`row.dataset.name`), a pure `hidden` visibility toggle that never
      touches the delete/checksum/build-report actions on any row.
      Verified live in a browser (isolated throwaway container, its own
      temp `ARCHIVE_ROOT`, never the shared persistent volumes) with 7
      fixture archived ISOs: typing "router-3" left exactly 1 of 7 visible,
      clearing the filter restored all 7.
- [x] Cisco search results filter by filename — added 2026-09-16, same
      pattern again: `#cisco-results-filter` in
      `giso-webui/templates/index.html`, shown once a search returns 6+
      results. Deliberately placed as a sibling *before*
      `<form id="cisco-results-form">`, not inside it — that form has its
      own submit button ("Download selected files"), and an `<input
      type="search">` inside a form submits on Enter by default, which
      would have made pressing Enter while typing a filter accidentally
      trigger a download request. Verified by
      `test_cisco_search_results_support_filtering_by_filename` in
      `giso-webui/tests/test_build_script.py` (asserts the filter element's
      position in the raw HTML is before the form's, in addition to the
      usual source-level function checks), and confirmed live in a browser
      by injecting 6 fixture results (real Cisco search needs configured
      API credentials this sandbox doesn't have) and calling the real
      `applyCiscoResultsFilter()`: filtering by a CSC ID left exactly 1 of
      6 visible, clearing restored all 6, and the filter element was
      confirmed to sit outside the form in the live DOM.
- [x] Search/filter for the automatic-selection review list — fixed
      2026-09-16: `#smu-review-filter` in `giso-webui/templates/index.html`
      sits right after `#smu-plan-message`, outside `#smu-plan-details` (that
      div is fully rebuilt via `replaceChildren()` on every automatic
      recalculation — a filter box living inside it would lose focus/value
      on every re-render, the same reasoning that placed the Cisco-results
      filter outside its form). `smuGroupCard()` (shared by the Step 2
      review, the manual "Check compatibility" result, and the Step 3 build
      report) now tags every CSC card with a lowercase `dataset.search` of
      its CSC ID, components and RPM filenames; the excluded-packages list
      in `applySmuRecommendation()` tags each row the same way with its name
      and reason. `applySmuReviewFilter()` hides/shows both against one
      query, mirroring `applyArchiveFilter()`/`applyCiscoResultsFilter()`.
      The filter only appears once there are 6+ combined CSC groups and
      excluded RPMs, matching the archive list's "only show when it's
      actually useful" threshold. Verified by
      `test_automatic_selection_review_list_supports_filtering` in
      `giso-webui/tests/test_build_script.py`, and confirmed live in a
      browser against an isolated throwaway container: uploaded a real ISO
      plus 6 RPMs (4 matching, 2 excluded for different reasons) through the
      actual upload API, saw the filter box appear, filtering by a CSC ID
      left exactly 1 of 4 CSC cards visible, filtering by an excluded
      RPM's filename left exactly that 1 of 6 total rows visible, and
      clearing the filter restored all 6. Full 220-test suite passes, ruff
      clean, Graphify refreshed.
