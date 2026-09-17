# TODO — Testing & CI

## Unit tests

Cover:

- [x] platform alias normalization (`test_ncs57c3_inventory_sku_normalizes_to_ncs57`,
      `test_ncs57c3_filename_is_inferred_as_ncs57`,
      `test_alias_matching_does_not_produce_false_positives_on_substrings`,
      `test_exr_arm_variant_token_normalizes_to_aarch64`,
      `test_upgrade_matrix_uses_canonical_platform_normalization` — covers
      both correct resolution and the false-positive-avoidance direction)
- [x] eXR capability discovery
- [x] LNT capability discovery
- [x] ISO metadata detection (`IsoArchitectureInspectionTests` in
      `test_app.py`: `test_detects_dual_arch_exr_image_from_metadata`,
      `test_detects_x86_64_only_exr_image_from_metadata`)
- [x] filename fallback detection (`test_falls_back_to_rpm_repository_listing_for_lnt_image`,
      `test_unreadable_iso_reports_unknown_rather_than_raising`)
- [x] RPM metadata parsing — implemented 2026-09-17 (`rpm_dependency_metadata()`,
      one read-only `rpm -qp --qf` per file):
      `test_rpm_header_query_parses_identity_and_exact_dependencies`,
      `test_renamed_rpm_is_excluded_with_the_name_its_header_gives`,
      `test_unreadable_rpm_header_and_source_rpms_are_never_excluded_by_name`,
      `test_inventory_reports_where_each_rpm_identity_comes_from`.
- [x] CSC grouping (`test_csc_package_groups_show_components_that_belong_together`,
      `test_overlapping_csc_fixes_are_explained`,
      `test_multiple_fixes_for_same_component_require_supersedence_data`,
      `test_multiple_versions_of_same_component_and_fix_are_rejected`)
- [x] duplicate checksums
- [x] same filename/different content
- [x] release mismatch (`test_mixed_release_is_rejected` and the
      `"Different IOS XR release"` exclusion-reason tests)
- [x] architecture mismatch (`test_rpm_architecture_mismatched_with_iso_is_rejected`,
      `test_rpm_architecture_matching_iso_is_accepted`,
      `test_unknown_iso_architecture_does_not_block_selection`; this was
      already implemented and tested by the merged ISO/RPM architecture
      change, just left unchecked here)
- [x] incomplete CSC — fixed 2026-09-16: `validate_smu_selection()` in
      `giso-webui/platform_validation.py` gained an optional
      `full_candidate_packages` parameter (the complete uploaded RPM
      inventory, not just the selection) — when a multi-component CSC bundle
      in the selection is missing one or more of its own files from that
      full inventory, it is now a blocking issue naming exactly which
      file(s) are missing, not just `manual-packages.js`'s pre-existing
      indeterminate-checkbox *visual* hint. Wired into all three real
      compatibility gates: `create_build_plan()` (`/api/build-plan`),
      `build_command()`'s final pre-execution re-check, and
      `/api/compatibility` (the manual "Check compatibility" tool).
      Automatic selection cannot trigger this by construction (it always
      selects a bundle's matching files completely or not at all), so this
      only ever fires for Manual package list mode — exactly where the gap
      was real. Verified by `test_partial_multi_component_bundle_selection_is_rejected`,
      `test_complete_multi_component_bundle_selection_is_accepted`, and
      `test_bundle_completeness_is_not_checked_without_full_candidate_packages`
      in `giso-webui/tests/test_platform_compatibility.py` (unit level), and
      `test_manual_selection_of_a_partial_multi_component_bundle_is_rejected`
      / `test_build_plan_flags_a_partial_multi_component_bundle_as_a_blocker`
      in `giso-webui/tests/test_app.py` (integration level, through the real
      endpoints). Confirmed live end-to-end: uploaded a real ISO and a real
      3-RPM "keep together" bundle through the actual upload API to an
      isolated throwaway container, submitted `/api/build-plan` with only 2
      of the 3 selected → `"ready": false` naming the missing file; all 3
      selected → `"ready": true`.
- [x] supersedence (`test_superseded_rpm_is_excluded_with_a_reason_not_silently_dropped`,
      `test_build_plan_automatic_selection_explains_superseded_exclusions`,
      `test_oversized_text_is_not_loaded_as_supersedence_metadata`)
- [x] BuildPlan generation (`test_build_plan_is_backend_owned_and_checksum_fingerprinted`,
      `test_created_job_records_authoritative_build_plan`)
- [x] BuildPlan fingerprint (same tests; fingerprint changes when inventory
      content changes)
- [x] inventory revision invalidation (`test_stale_confirmed_plan_is_rejected_when_inventory_changes`,
      `test_confirmed_plan_matching_current_inventory_is_accepted`)
- [x] command generation (`test_platform_is_inferred_and_invalid_option_rejected`,
      `test_build_recalculates_automatic_smu_selection_server_side`,
      `test_package_glob_characters_cannot_select_unintended_files`, and
      others in the `build_command()` test group)
- [x] artifact verification (`test_success_archive_is_verified_before_sources_are_removed`
      — checksum comparison between source and archived copy)
- [x] cleanup (extensive coverage — see "Regression tests" below)
- [x] restart recovery (`test_active_job_is_marked_interrupted_after_restart`,
      `test_expired_orphan_partial_upload_is_removed_after_restart`)
- [x] malicious paths (TAR traversal/symlink/hardlink/absolute-path members,
      `safe_data_path` traversal, and archive-delete traversal — see
      Security tests below for the specific tests)

## Representative platform fixtures

Use synthetic/mocked fixtures, not licensed Cisco artifacts.

Implemented 2026-09-17 in `giso-webui/tests/test_platform_fixtures.py`: every
profile goes through the real `create_build_plan()` with automatic selection
and Cisco-style synthetic names (eXR `<platform>-mini-x-<release>.iso` +
`-rNNN.CSC…` SMUs; LNT `<platform>-x64-<release>.iso` + upstream-README
`xr-cdp-24.3.1v1.0.0-1.x86_64.rpm` packages). Each asserts detected platform
and engine, the matching package selected, a foreign one excluded with its
reason, platform capabilities, expected USB output and - for platforms
without automatic USB - the blocker when "Skip USB image" is not set. Writing
the LNT cases exposed that automatic selection excluded every real-style LNT
package (see "Select LNT SMU packages automatically" in
`01-PLATFORM-UPSTREAM-TODO.md`), now fixed.

- [x] ASR9000 (`asr9k`, incl. `migration`)
- [x] NCS1000-class where applicable (`ncs1k`, `ncs1001`, `ncs1004` eXR;
      `ncs1010` LNT)
- [x] NCS5000 (`ncs5k`, no USB)
- [x] NCS540 (`ncs540` eXR; `ncs540l` LNT)
- [x] NCS5500
- [x] NCS560
- [x] NCS6000 where pinned upstream supports it (`ncs6k`, no USB)
- [x] NCS5700 / NCS57C3 class (`ncs57` via `ncs5700` ISO name)
- [x] Cisco 8000-class LNT (`8000`)
- [x] XRv9000 (`xrv9k`, incl. `full_iso`, no USB)
- [x] whitebox variants where upstream supports them (`iosxrwb`, `iosxrwbd`)
- [x] unknown/future upstream-supported platform
      (`test_unknown_future_platform_pauses_automatic_selection_until_overridden`:
      automatic selection pauses with a named reason; the `lnt-generic`
      override builds a ready plan reported `MANUAL`)

## Regression tests

Mandatory regression coverage for:

- [x] manual RPM path vs basename bug (`test_inventory_id_selects_exact_rpm`,
      `test_manual_package_ui_uses_ids_and_renders_duplicate_conflicts` —
      manual selection submits opaque inventory IDs, never a bare basename
      that could collide with a duplicate)
- [x] manual mode empty-selection bug — verified 2026-09-16, not a bug:
      `create_build_plan()` correctly returns `ready: true` for a manual
      build with an empty `pkglist` and no other customization, since
      gisobuild itself does not require `--pkglist` at all (relabeling the
      ISO, or only adding a config file, are real use cases upstream
      supports) — inventing a backend restriction upstream doesn't have
      would repeat exactly the "independent support matrix" mistake this
      project's own `AI-INSTRUCTIONS.md` warns against. The actual guard
      against an accidental no-op submission is client-side and already
      existed: `updateBuildAvailability()` in `giso-webui/static/app.js`
      disables "Start build" until at least one package or other
      customization is present (already covered by
      `test_start_build_button_names_exactly_what_is_missing`). Added
      `test_manual_mode_with_zero_packages_is_a_valid_ready_plan` in
      `giso-webui/tests/test_app.py` to pin the backend half of that split
      responsibility, since nothing did before.
- [x] CSC group selection mismatch — same gap as "incomplete CSC" above, now fixed; see that entry.
      2026-09-17: the harder case - a companion RPM that was never uploaded
      at all - is now covered too, from each Cisco SMU README's `RPMS:`
      manifest (with MD5), in all three gates; see "CSC grouping" in
      `02-AUTOMATION-BUILDPLAN-TODO.md`.
- [x] "No RPM packages uploaded" despite inventory containing compatible
      RPMs — verified 2026-09-16, not a live bug: `templates/index.html`'s
      static "No RPM packages uploaded." text is only ever a pre-JS
      placeholder — `renderInputs()` unconditionally calls
      `renderManualPackages()` on every `/api/inputs` load regardless of
      whether Manual mode is even selected, and that function's own
      empty-state gate is "zero RPM files of any kind" (`!rpms.length`),
      never a "zero compatible RPMs" check — a workspace with RPMs that are
      merely wrong-platform/wrong-release/excluded still renders them
      (disabled, with a reason), it never falls back to an empty-state
      message. Added `test_manual_package_summary_never_gets_stuck_on_the_static_placeholder`
      in `giso-webui/tests/test_build_script.py` to pin this, since nothing
      did before.
- [x] NCS-57C3 SKU normalization (`test_ncs57c3_inventory_sku_normalizes_to_ncs57`,
      `test_ncs57c3_filename_is_inferred_as_ncs57`)
- [x] cancel during builder preparation/pull
- [x] cancel during finalization
- [x] successful build preserves unrelated workspace inputs
- [x] two uploaded ISOs never silently select the first candidate
      (`test_discover_pauses_automatic_selection_when_multiple_isos_exist`)
- [x] RPM CPU architecture must match the selected ISO/build architecture
      (`test_build_plan_blocks_rpm_architecture_mismatch_against_real_iso`,
      `test_rpm_architecture_mismatched_with_iso_is_rejected`)
- [x] package names containing glob metacharacters cannot select unintended files
- [x] duplicate basename + same hash is deterministic and keeps provenance
- [x] duplicate basename + different hash is a blocking conflict
- [x] upgrade-matrix aliases use the canonical platform resolver
- [x] bridge-SMU near-match does not satisfy exact package/CSC presence
- [x] discovery remains safe while cleanup/delete runs concurrently
- [x] auto-derived target release refreshes when base ISO changes
- [x] cached builder behavior is defined when registry access fails during the migration period
      - defined and implemented 2026-09-17. Before, any failed or timed-out
      `docker pull` failed the build even with the builder image already on
      the host. Now `run_job()` falls back to the local copy
      (`local_builder_image_id()`, `docker image inspect --format {{.Id}}`),
      logs a WARNING that says whether the reference is digest-pinned
      (identical content) or a tag (may lag the registry), and records
      `builder_image: {reference, id, source: "registry"|"cache"}` on the
      job; with no cached copy the build fails naming both facts and the
      engine never runs. Tests: `test_image_pull_timeout_uses_a_cached_builder_image`,
      `test_image_pull_timeout_marks_build_failed`,
      `test_registry_outage_builds_with_the_cached_builder_image`,
      `test_registry_outage_without_a_cached_image_fails_clearly`. Checked
      against the real Docker daemon: the cached
      `ciscogisobuild/cisco-xr-gisobuild:2.3.4` resolves to
      `sha256:be282c7a76b0…` and a missing reference to `None`. The build
      report in the UI shows the builder reference, whether it was pulled or
      the cached copy, and its ID
      (`test_build_report_shows_a_cached_builder_fallback`, browser).

See `07-BUG-AUDIT-TODO.md` for the implementation details and failure scenarios behind these tests.

## Integration test

Synthetic workflow:

```text
upload
→ extract
→ inspect
→ inventory
→ BuildPlan
→ mocked gisobuild
→ output verification
→ archive
```

Implemented 2026-09-17 in `giso-webui/tests/test_integration_build.py` (runs
in the normal unit-test discovery, ~1 s). Everything from the upload
endpoints to the archive is real code; only the docker CLI is a small fake
executable that answers `inspect`/`ps`/`pull`/`stop` and, for `run`, records
its arguments and behaves like gisobuild (streams output, writes a Golden ISO
to `--out-directory`, fails the RPM dependency check, or runs until stopped).
Running it also exposed a real leak, now fixed: `run_job()` never closed the
build container's stdout pipe (one descriptor per build, left to the garbage
collector).

- [x] eXR integration - `test_exr_build_runs_the_plan_archives_the_image_and_cleans_inputs`:
      ISO and a Cisco-style SMU tar (RPM + README manifest) through
      `/api/uploads`, extraction, `/api/inputs` recommendation, `POST
      /api/jobs`, engine arguments (`--iso`, staged `--repo`, `--label`,
      `--out-directory`, volume mounts, no docker.sock), success, archive,
      input cleanup, and job state restored from SQLite after dropping
      memory. Failure path: `test_exr_dependency_failure_is_reported_and_inputs_are_kept`.
- [x] LNT integration - `test_lnt_build_passes_lnt_only_options_to_the_engine`
      (`8000` platform, `--xrconfig`, `--remove-packages`, engine `lnt`,
      nothing staged when nothing is selected).
- [x] cancellation state-machine integration -
      `test_cancelling_a_running_build_stops_the_container_and_keeps_inputs`
      (running → `DELETE` → `docker stop giso-build-<id>` → cancelled, no
      archive, inputs kept, second cancel refused with 409).
- [x] multiple-build-inventory isolation integration -
      `test_consecutive_builds_use_only_their_own_inventory`.

Not covered: a real `gisobuild` or builder image (see the licensed-ISO
acceptance level in `docs/testing.md`).

## Browser/DOM tests

Implemented 2026-09-17 in `giso-webui/browser_tests/test_operator_flows.py`:
Playwright 1.55.0 + Chromium in `docker/browser-tests.Dockerfile` (pinned by
digest), the real Flask app in-process on synthetic placeholder files, only
Docker/gisobuild/disk space patched, assertions on the rendered page, and any
uncaught page JavaScript error fails the test. 14 tests, ~4 s. The first run
found four real UI defects - see "Operator UI defects found by the first
real-browser tests" in `07-BUG-AUDIT-TODO.md`.

- [x] automatic selection (`test_automatic_selection`)
- [x] manual CSC selection (`test_manual_csc_selection`)
- [x] upload while manual mode open
      (`test_upload_while_manual_mode_is_open_keeps_the_manual_selection`)
- [x] manual → automatic (`test_manual_to_automatic`)
- [x] inventory refresh (`test_inventory_refresh`)
- [x] no RPM state (`test_no_rpm_state`)
- [x] failed compatibility (`test_failed_compatibility`)
- [x] successful preflight (`test_successful_preflight` - stops at the
      confirmation dialog, no build is started)
- [x] Build button enable/disable (`test_build_button_enable_disable`)
- [x] unknown platform presentation (`test_unknown_platform_presentation`)
- [x] multiple ISO ambiguity blocks Build (`test_multiple_iso_ambiguity_blocks_build`)
- [x] duplicate RPM basename conflict is visible
      (`test_duplicate_rpm_basename_conflict_is_visible`)
- [x] ISO switch refreshes auto-derived release
      (`test_iso_switch_refreshes_auto_derived_release`)

Also: `test_dependency_blocker_names_the_prerequisite_smu` (Step 2 names the
README prerequisite SMU).

## Security tests

- [x] TAR traversal (`test_tar_path_traversal_is_rejected`; the protective
      code already existed, this section was just under-checked)
- [x] symlink archive member (`test_tar_symlink_member_is_rejected`,
      `test_tar_hardlink_member_is_rejected` for the upload path;
      `test_cisco_archive_extraction_rejects_symlink_members` added
      2026-09-16 to cover `extract_cisco_archive()`'s identical check
      directly — until then that function had no test coverage at all)
- [x] absolute path (`test_tar_absolute_path_member_is_rejected` — new)
- [x] oversized expansion (`test_tar_expansion_size_limit_is_enforced` — new,
      covers `MAX_EXTRACTED_BYTES` directly; the pre-existing
      `test_tar_extraction_requires_reserved_free_space` only covered the
      separate free-disk-space guard)
- [x] member-count limit — fixed 2026-09-16: `MAX_TAR_MEMBERS` existed in
      both the upload path and `extract_cisco_archive()` but neither was
      tested. Added `test_tar_member_count_limit_is_enforced` and
      `test_cisco_archive_extraction_enforces_member_count_limit`.
- [x] duplicate filename conflict
- [x] malicious job/artifact path (`test_archive_delete_rejects_path_traversal`,
      `test_path_traversal_is_rejected`; pre-existing, just under-checked)
- [x] package glob metacharacters
- [x] secret redaction (`test_cisco_config_only_exposes_availability` proves
      Cisco credentials never leave the config-check endpoint beyond a
      yes/no; `test_quoted_artifact_path_with_spaces_is_fully_redacted` and
      `test_build_output_is_redacted_and_written_to_service_log` cover
      filename/command redaction in logs)

## CI pipeline

Run (`.github/workflows/ci.yml`):

- [x] Python tests — "Run tests inside the built container" step
      (`giso-webui/tests` via `unittest discover`, matching `docs/testing.md`).
- [x] JS/DOM tests — "Run browser tests (Playwright/Chromium in Docker)"
      step in `.github/workflows/ci.yml` (added 2026-09-17; actionlint and
      hadolint pass locally in their containers). Not yet observed running
      on GitHub Actions - nothing is pushed from this environment.
- [x] lint — `ruff check` step, now running a pinned `ruff==0.16.7` from
      `docker/tooling.Dockerfile` (fixed 2026-09-16; previously an unpinned
      `pip install ruff` — see "`ruff` is installed unpinned in CI" in
      `07-BUG-AUDIT-TODO.md`), against an explicit rule selection pinned in
      the repo-root `ruff.toml` (also fixed 2026-09-16, see the same
      `07-BUG-AUDIT-TODO.md` entry) — both the ruff *version* and the rule
      *selection* it runs are now reproducible.
- [ ] formatting check — deliberately still open. `ruff format --check`
      (2026-09-17) would reformat 13 of 16 Python files, `app.py` wholesale;
      adopting a formatter is a one-off whole-repo rewrite that should land
      on its own, not inside feature work, so no gate is added yet.
- [x] static security checks — 2026-09-17: `ruff.toml` now extends the
      pinned selection with the whole flake8-bandit `S` family, so the
      existing "Lint Python" CI step is the security gate. Ignored with a
      written reason: `S603` (every subprocess call is list-form, never
      `shell=True`) and `S607` (`git`/`genisoimage` by PATH inside pinned
      images). The eight other findings were reviewed one by one: `S105`
      on `TOKEN_URL` (a URL), `S310` on Cisco API constants and on URLs
      already checked by `_validate_download_url()` (https, allowlisted
      host, global addresses only), and on `scripts/e2e_real_iso.py`'s
      validated origin - each carries a justified `noqa`; the three `S324`
      test MD5s now pass `usedforsecurity=False`. `ruff check giso-webui
      staging scripts` passes; the CI lint now also covers
      `giso-webui/browser_tests`.
- [x] Docker build — "Build production container" step
      (`docker compose build giso-webui`).
- [x] synthetic eXR integration — `tests/test_integration_build.py`, run by
      the existing "Run tests inside the built container" step (see
      "Integration test" above).
- [x] synthetic LNT integration — same file and step.
- [x] SBOM generation — 2026-09-17: "Generate SBOM for the production image"
      runs pinned `anchore/syft:v1.33.0` against `giso-webui-giso-webui` and
      uploads `giso-webui.spdx.json` as a CI artifact. Run locally the same
      way: 92 packages, including `flask`, `gunicorn`, `click`, `rpm`,
      `cdrkit` and `docker-cli`. actionlint passes; not yet observed on
      GitHub Actions (nothing is pushed from this environment).
- [x] Graphify freshness validation for code-changing PRs

Steps that exist but weren't listed here at all: `actionlint` (workflow
linting), `hadolint` (both Dockerfiles), `docker compose config -q`
(compose file validation, both `giso-webui` and `staging`), and
`bash -n` syntax-checking the shell scripts.

Optional:

- [x] Trivy image scan — 2026-09-17: pinned `aquasec/trivy:0.65.0` in CI
      fails the run on any fixable HIGH/CRITICAL vulnerability in the
      production image. Its first local run found seven fixed HIGH util-linux
      CVEs in the base image's `libuuid` 2.42.1-r0 (CVE-2026-53612, -53613,
      -53614, -76642, -78408, -78409, -78410); `giso-webui/Dockerfile` now
      pins `libuuid=2.42.3-r1` and the rescan reports 0 for the Alpine
      packages and every Python package. 285 unit tests pass in the rebuilt
      image and its `/api/health` answers. Unfixed findings are not gated
      (`--ignore-unfixed`): there is nothing to upgrade to.
- [x] dependency vulnerability scan — `pip-audit -r giso-webui/requirements.txt`
      runs on every CI invocation, not gated behind an opt-in flag.

## Graphify CI guard

- [x] Regenerate from the PR/head tracked source tree and compare the structural graph (commit metadata is intentionally ignored)
- [x] Fail the CI merge gate when tracked `graphify-out/graph.json` is stale
- [x] Verify `.graphifyignore` still excludes Cisco licensed/sensitive inputs and build outputs

## Merge policy

Package-selection or build-runner changes must not merge unless:

- [ ] unit tests pass
- [ ] integration tests pass
- [ ] Docker image builds
- [ ] regression suite passes
- [x] Graphify output is current when the change affects code/architecture
