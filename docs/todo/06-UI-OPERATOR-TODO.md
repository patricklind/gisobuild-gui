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
- [ ] blockers — the persistent Step 2 panel shows `plan.message` (a single
      string) when automatic selection can't proceed, but the richer,
      itemized `blockers` array that `/api/build-plan` computes (e.g. a
      specific architecture mismatch, a stale-plan fingerprint conflict) is
      only ever seen at the final "Start build" confirmation, not during
      ongoing review. `discover()`/`/api/smu/recommendation` return
      `recommend_smu_selection()`'s shape, which has no `blockers` field at
      all — closing this gap means either calling `/api/build-plan` from the
      Review step too, or adding an equivalent field there.
- [ ] expected output — `expected_outputs` (ISO/USB) exists only in the
      `/api/build-plan` response, shown only in the final confirmation
      dialog text, not persistently during Step 2.
- [ ] free disk estimate — not implemented anywhere; no endpoint currently
      returns a projected build-output size versus available space (the
      backend only ever compares against `MIN_FREE_BYTES` internally when
      actually starting an upload/build/extraction, never exposes the
      numbers to the UI ahead of time).

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
- [ ] malformed metadata
- [ ] ambiguous metadata

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
- [ ] Compatible-only / selected-only / architecture / version filters —
      not implemented; only filename/CSC-ID substring search exists so far.
- [ ] Search/filter for the automatic-selection review or the Cisco search
      results list — not implemented; only the manual package list has
      this today.
