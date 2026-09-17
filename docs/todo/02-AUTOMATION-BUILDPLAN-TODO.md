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
- [x] metadata source/confidence - real per file since 2026-09-17
      (`file_metadata_provenance()`: `rpm-header`, `iso-metadata` or
      `filename`; see "RPM inspection").
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

### Found 2026-09-16: `isols.py` is the real upstream tool for exactly this, for LNT

`.gisobuild-tool/src/lnt/tools/_isols.py` is a complete, existing upstream
CLI (`--dump-mdata --json`) that returns platform family, XR release, ISO
type/format version, GISO label/build metadata, the full RPM/package list
per group, optional packages, key request/ownership voucher-certificate
presence, **and `supported-pids`** (`iso.query_content(supported_pids=True)`
in `image.py`) — real, upstream-verified data, not filename regex. This is
exactly the "prefer upstream tooling" principle in
`docs/AI-MASTER-PROMPT.md` section 40/41, and would directly upgrade
platform/release/PID detection from `INFERRED` to a genuine `VERIFIED`
(see the "Confidence display" honesty accounting in
`06-UI-OPERATOR-TODO.md`) and unblock a real PID picker for
`--only-support-pids` instead of a free-text field.

Why this isn't a quick pass-through, and wasn't implemented in this pass:

- `isols.py`'s `Image` class extracts and runs `image.py` **from inside the
  uploaded ISO itself** (`gisoutils.extract_image_py_sig()` in
  `.gisobuild-tool/src/lnt/gisoutils.py`), after signature verification. That
  needs the full `lnt`/`utils` package environment
  (`gisoutils`, `lnt_gisoglobals`, whatever `wrappers` module
  `add_wrappers_to_path()` pulls in) — dependencies that live in the pinned
  `ciscogisobuild/cisco-xr-gisobuild:2.3.4` build image, not in
  `giso-webui`'s own lightweight Alpine image (which only has `isoinfo` via
  `cdrkit`, no Python `lnt` package at all).
- Running it therefore means a **second, read-only `docker run` against the
  same pinned build image** (giso-webui already runs this image for real
  builds via `build_command()`), a genuinely new invocation pattern that
  needs the same care already applied to `inspect_iso_architecture()`:
  output size caps, a timeout, no write access to anything but a scratch
  temp dir, and graceful degradation to filename inference when the image
  is eXR (this tool is LNT-only), the ISO predates this capability, or the
  container can't run for any reason — never a new way to block an
  otherwise-buildable image.
- Only applies to LNT; eXR platform/release detection would still need its
  own investigation (likely `gisobuild_exr_engine.py`/`isotools_exr.py`).

Blocked on test material (2026-09-17): the only real image available to
this work is the eXR NCS5500 25.1.2 bundle. `isols.py` needs a signed LNT
ISO - it verifies and runs `image.py` from inside the image - and eXR
platform profiles report `only_support_pids: false`, so neither the
prototype nor the picklist can be verified against real content yet. A
synthetic ISO cannot stand in, because the signature check is the point.

TODO:

- [ ] Prototype invoking `isols.py --iso <mounted-iso> --dump-mdata --json`
      inside the pinned build image from `giso-webui`, capped and
      timed-out the same way `inspect_iso_architecture()` is.
- [ ] Fold real `platform-family`/`xr-version`/`supported-pids` results into
      `confidence_report()` as `VERIFIED` (`source: "isols-metadata"`) when
      available, keeping the existing filename fallback and `UNKNOWN` states
      unchanged when it isn't.
- [ ] Replace the free-text `--only-support-pids` field with a picklist
      populated from `supported-pids`, per
      `docs/AI-MASTER-PROMPT.md` section 25's hardware-PID-filtering UX. The
      warning copy this item specifies (verbatim from upstream's own
      `--only-support-pids` help text: "Removing hardware support is
      irreversible... may fail to boot... discuss with Cisco support") is
      already in place next to the field in `giso-webui/templates/index.html`
      as of 2026-09-16 — only the free-text-to-picklist upgrade remains,
      which depends on the `isols.py` work above.

Detection order (as implemented 2026-09-17, in precedence order):

- [x] ISO metadata — for eXR, platform and release are now read from the
      image's own `iosxr_image_mdata.yml` (`iso_mdata:` → `name:`, e.g.
      `ncs5500-mini-x-25.1.2`) by `iso_identity()` in `giso-webui/app.py`,
      and reported `VERIFIED` / `source: "iso-metadata"`. Used by every
      decision point — `discover()`, `/api/smu/recommendation`,
      `create_build_plan()`, `build_command()`, `/api/compatibility` — so the
      review and the final gate can never disagree. Validated against the
      real licensed NCS5500 25.1.2 image **renamed on disk to
      `customer-golden-base.iso`** (a filename `infer_platform()` returns
      `None` for, which previously dead-ended automatic selection): platform
      `ncs5500`, release `25.1.2`, the same 24-RPM selection and 5 dependency
      blockers as the correctly-named file, with the real filename still
      shown to the operator. When the metadata identity and the filename
      disagree, the image wins (`test_metadata_identity_overrides_a_misleading_filename`).
      LNT images carry no such file and fall through to the filename; that
      half still depends on the `isols.py` work above.
- [x] upstream gisobuild inspection/isoinfo — `isoinfo` reads the metadata
      and the ISO's own RPM listing (architecture fallback). The heavier
      `isols.py` route remains open above for LNT.
- [x] image/package metadata — the shipped package list per ISO section
      (`iso_shipped_packages_from_mdata()`) and each RPM's own
      `Requires`/`Provides` header (`rpm_dependency_metadata()`), both read
      from the artifacts, not filenames.
- [ ] known platform signatures — no signature database beyond the
      metadata identity above; not needed for eXR now that the image names
      itself, and LNT would get it from `isols.py`.
- [x] hardware PID mapping — `ALIASES` + `infer_platform_pid()` (see
      `01-PLATFORM-UPSTREAM-TODO.md`).
- [x] filename inference — `infer_platform()`/`ISO_RELEASE`, now strictly
      the fallback: `iso_identity()` only prefers the metadata name when it
      resolves to a known platform *and* a release, so an odd or missing
      metadata identity can never replace a working filename match
      (`test_unusable_metadata_identity_falls_back_to_the_filename`).
- [x] manual override — Expert settings platform, including the
      `exr-generic`/`lnt-generic` fallbacks; a manual platform is reported
      `operator-selected`, never `VERIFIED`, even when metadata exists.

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

Done 2026-09-17: `rpm_dependency_metadata()` reads each RPM's header with one
read-only `rpm -qp --nosignature --qf` call (pinned `rpm=4.19.1.1-r5` in the
image, cached by path/size/mtime). `rpm_filename_mismatch()` compares the
header's `NAME-VERSION-RELEASE.ARCH.rpm` with the real filename; a mismatched
file is dropped from `active_rpm_names()` and listed in `excluded` with the
name its header gives, so every filename-based decision downstream is only
ever made about files whose name is proven to be their content. An unreadable
header (or a `.src.rpm`) is never excluded on that basis - no ground truth,
no claim.

Evidence: tests `test_rpm_header_query_parses_identity_and_exact_dependencies`,
`test_renamed_rpm_is_excluded_with_the_name_its_header_gives`,
`test_unreadable_rpm_header_and_source_rpms_are_never_excluded_by_name`.
Live, in a throwaway container against the operator's real NCS5500 25.1.2
content (extracted to `$TMPDIR`, deleted afterwards): 34 real RPMs, 0 false
mismatches, 0.62 s cold; the unchanged selection was 24 RPMs with the 5 real
dependency blockers. Renaming `ncs5500-bgp-...-r2512.CSCwu14807.x86_64.rpm`
to `...r2612...` dropped the selection to 23 and excluded that file with the
new reason.

- [x] RPM name (header `NAME`)
- [x] version (header `VERSION`)
- [x] release (header `RELEASE`)
- [x] architecture (header `ARCH`)
- [x] provides (header `PROVIDENAME/FLAGS/VERSION`, exact `=` entries)
- [x] requires (header `REQUIRENAME/FLAGS/VERSION`, exact `=` entries)
- [ ] signature metadata where available - not done (integrity is: MD5
      against the Cisco SMU README, see "CSC grouping"). The query deliberately
      passes `--nosignature`; nothing reads `RSAHEADER`/`SIGPGP` or checks
      against Cisco's key. gisobuild itself verifies signatures during the
      build, so this is a pre-build nicety, not a gap in the build's safety.
- [x] CSC ID - still parsed from the filename, but the filename is now
      proven identical to the header's `RELEASE` (which carries the
      `CSCxxxxxxx` suffix) whenever the header is readable.
- [x] component - same as CSC ID: the header `NAME` equals the filename's
      component whenever the header is readable.
- [x] metadata confidence - per file since 2026-09-17:
      `file_metadata_provenance()` sets each inventory item's
      `metadata_source`/`metadata_confidence` (previously hardcoded
      `filename`/`low` for everything): `rpm-header`/`high` when the header
      matches the filename, `rpm-header`/`mismatch` plus `metadata_name`
      when it contradicts it, `iso-metadata`/`high` when the ISO's own
      metadata names a known platform and release, else `filename`/`low`.
      The manual package list shows it per RPM and disables a mismatched
      one; `selection_integrity_blockers()` also blocks a mismatched RPM
      in manual mode in all three gates. Tests:
      `test_inventory_reports_where_each_rpm_identity_comes_from`,
      `test_manual_package_list_blocks_and_labels_header_mismatches`.
      Live, `--rm` container, real NCS5500 25.1.2 content: 34/34 RPMs
      `rpm-header`/`high`, the ISO `iso-metadata`/`high`; renaming the
      CSCwu14807 RPM to `r2612` gave `mismatch` with the true name and a
      manual blocker. `inventory_files()` 8.97 s cold (dominated by the
      existing SHA-256 of the 2.2 GB ISO), 0.00 s warm.

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

Audited 2026-09-16 against real Cisco content (a real NCS5500 IOS XR 25.1.2
base bundle plus 20 real SMU tars, uploaded through the actual `/api/uploads`
flow and checked via `/api/inputs` and `/api/compatibility` — not synthetic
fixtures). All packages/data came from real Cisco distribution; nothing from
this session was retained afterward per `SECURITY.md`.

- [x] group packages by CSC — `validate_smu_selection()`'s `RPM_COMPONENT`
      regex correctly grouped a real 3-RPM Cisco fix (`CSCwu13268`:
      `ncs5500-infra`/`ncs5500-iosxr-fwding`/`ncs5500-routing`) into one CSC
      group, and nine other real single-RPM fixes into their own groups.
- [x] select complete groups by default — the real 3-RPM `CSCwu13268` group
      was selected as a whole by automatic selection, not partially.
- [x] warn/block incomplete CSC groups - fixed 2026-09-17. This was recorded
      as "not implementable without external data"; that was wrong. Every
      real Cisco SMU tar ships a README whose `RPMS:` block lists each RPM of
      the fix with its MD5. `smu_readme_manifests()` parses it and
      `smu_manifest_problems()` flags (a) every present member of a fix with
      a README-listed RPM missing, and (b) a member whose MD5 differs from
      the README, plus its siblings. Automatic selection drops them via
      `active_rpm_names()` and `add_superseded_exclusions()` explains each;
      a manual selection gets a plan blocker (`selection_integrity_blockers()`) and
      `/api/compatibility` reports it as incompatible. The earlier
      same-inventory case (`full_candidate_packages`) is unchanged.
      Tests: `test_fix_missing_a_readme_listed_rpm_is_excluded_with_what_is_missing`,
      `test_rpm_whose_md5_differs_from_its_readme_excludes_the_whole_fix`,
      `test_complete_fix_matching_its_readme_stays_selectable`,
      `test_manual_selection_of_an_incomplete_fix_is_a_plan_blocker`.
      Live, inside a `--rm` container with the operator's real NCS5500 25.1.2
      bundle and 20 SMU tars (nothing kept on the host): 20 manifests parsed,
      34 RPMs, 24 selected, 0 manifest exclusions (same 24 as before the
      change, so no false positives); deleting
      `ncs5500-iosxr-fwding-1.0.0.4-r2512.CSCwu13268.x86_64.rpm` excluded the
      other two `CSCwu13268` RPMs naming the missing file (21 selected);
      restoring it with one flipped byte excluded all three with the MD5
      reason. 0.47 s cold including MD5s.
      Still out of scope: a loose RPM uploaded *without* its README has no
      manifest, so nothing is claimed about it. README `Pre-requisites:` are
      not a blocker on their own (see "Supersedence" for how they are used).
- [x] show components — each `package_groups` entry lists its member
      component names (confirmed live: `CSCwu13268` showed `ncs5500-infra`,
      `ncs5500-iosxr-fwding`, `ncs5500-routing`).
- [x] preserve exclusion reason — every automatically-excluded real RPM
      carried a specific reason ("Superseded by a newer fix per Cisco
      supersedence notes"), not a generic rejection.
- [x] advanced RPM-level manipulation only in Expert mode — manual package
      selection (`package_selection_mode`) lives inside the "SMU
      compatibility" Expert settings group; automatic mode is the default
      and requires no Expert settings interaction at all.

## Duplicate handling

- [x] same filename + same SHA → deduplicate with retained provenance
- [x] same filename + different SHA → hard error until the unwanted copy is removed
- [x] multiple versions same component → conflict — audited 2026-09-16 with
      real data: two real, independent single-CSC fixes
      (`CSCwv36143`/`CSCwv38342`) each touched a component
      (`ncs5500-iosxr-fwding`/`ncs5500-routing`) that a third, separate
      multi-component fix (`CSCwu13268`) also touched. `component_conflicts`
      correctly flagged both as "More than one fix changes this component;
      Cisco supersedence decides which remains" — a real version conflict
      the filename-only model surfaced correctly rather than silently
      picking one side.
- [x] overlapping CSCs → show conflict/supersedence — same evidence as
      above; both `/api/inputs`' automatic recommendation and
      `/api/compatibility`'s deterministic check agreed on the same two
      conflicts and warnings.

## Supersedence

Create an explicit supersedence model.

- [ ] bundle metadata - partly. Each SMU README's `RPMS:` manifest (members
      + MD5) is used for completeness and integrity (see "CSC grouping"),
      and since 2026-09-17 its `Pre-requisites:` (SMU level and the
      per-package `CSCxxxxx <package> pkg` lines under CONSTITUENT SMU
      DETAILS) are parsed by `smu_readme_prerequisites()`. They are used to
      *name* the SMU to download in a dependency blocker
      (`explain_with_prerequisites()`), never as a blocker by themselves:
      the same READMEs list a prerequisite they also partially supersede,
      so "prerequisite absent" alone does not prove a failure. Live on the
      real NCS5500 25.1.2 set: all 5 real dependency blockers now say
      "download Cisco SMU ncs5500-25.1.2.CSCwt13701, which the README of
      ncs5500-25.1.2.CSCwu13268 lists as its prerequisite for <package>" -
      the exact five packages that README attributes to CSCwt13701. Test:
      `test_dependency_blocker_names_the_prerequisite_smu_from_the_readme`.
      README "Partial" supersedence is still not modelled.
- [ ] RPM metadata - delegated, not reimplemented. Upstream gisobuild
      already resolves version supersedence among supplied RPMs itself
      (eXR: `rpm_db.filter_superseded_rpms()` in
      `.gisobuild-tool/src/exrmod/gisobuild_exr.py:316`; LNT: highest
      version per package in `.gisobuild-tool/src/lnt/builder/_pkgpicker.py`).
      This app does not duplicate that ordering (see the
      `_version_satisfies()` rationale); it stays open because no explicit
      model in this app records the outcome before the build.
- [x] README metadata — `active_rpm_names()` parses each uploaded SMU's own
      `README.txt`-style file for Cisco's own supersedence notation
      (`<identifier> Full`) and excludes the packages it names. Verified
      2026-09-16 with real Cisco SMU tars: 10 real, genuinely-superseded
      RPMs (older `ncs5500-infra`/`ncs5500-iosxr-fwding`/`ncs5500-isis`/
      `ncs5500-mpls-te-rsvp`/`ncs5500-ospf`/`ncs5500-routing` fixes) were all
      correctly excluded with reason "Superseded by a newer fix per Cisco
      supersedence notes", exactly matching the real supersedence
      relationships stated in their own bundled README files.
- [ ] compatibility metadata
- [ ] gisobuild dependency output

Never silently exclude without a reason.

## Unified selection engine

- [x] automatic mode and manual mode use the same backend model - both are
      a `create_build_plan()` payload; automatic mode only chooses the
      identifiers, then the same resolution, `validate_smu_selection()`,
      `selection_integrity_blockers()`, dependency, space and environment
      checks run. `create_job()` pins the plan's resolved package IDs and
      turns automatic selection off, so `build_command()` builds exactly the
      reviewed set. Test: `test_automatic_and_manual_selection_reach_the_same_plan`.
- [x] manual mode modifies BuildPlan - the manual `pkglist` becomes the
      plan's `selected_packages` and is re-derived at Start.
- [x] no separate incompatible selection path - fixed 2026-09-17: the
      manual "Check compatibility" endpoint (`/api/compatibility`) skipped
      the dependency check, so it could say "compatible" for a selection
      the plan then blocked. It now reports `unsatisfied_dependencies` and
      the identical blocker text (`dependency_blocker_text()`); the UI
      metric is renamed "Package checks" because it is no longer
      filename-only. Test:
      `test_compatibility_check_reports_the_dependency_blocker_the_plan_would`.
      Live, `--rm` container, real NCS5500 25.1.2 bundle and 20 SMUs:
      automatic plan 24 RPMs with 5 dependency blockers
      (`ncs5500-dpa = 1.0.0.5`, `ncs5500-dpa-fwding = 1.0.0.2`,
      `ncs5500-fwding = 1.0.0.3`, `ncs5500-os = 1.0.0.1`,
      `ncs5500-os-support = 1.0.0.2`); manual plan with the same IDs had
      identical blockers; `/api/compatibility` for the same names returned
      `compatible: false` with the same 5 lines.
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
- [x] configuration files - fixed 2026-09-17: the SHA-256 of every path
      option's file (`xrconfig`, `ztp_ini`, `script`, `key_request`,
      `yamlfile`, ownership files) is hashed in as `config_files` and
      returned in the plan. Before, a config with an inventory suffix was
      only covered indirectly via the inventory revision, and one with any
      other suffix (e.g. `.txt`) not at all.
      Test: `test_build_plan_fingerprint_changes_when_config_content_or_gisobuild_changes`
      (a same-size in-place `.txt` edit keeps the revision but changes the
      fingerprint).
- [x] gisobuild version/commit - `gisobuild_commit()` of the mounted
      `/tool` checkout is hashed in and returned. Verified in the
      `giso-webui` image with the real `.gisobuild-tool` mount: `0388af2`,
      identical to `git -C .gisobuild-tool rev-parse --short HEAD` on the
      host. Returns `None` (still hashed) when `/tool` is not a git
      checkout; the builder image reference was already included.
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

Nothing here is a stored snapshot: `GET /api/inputs` (`discover()`)
recomputes everything from the volume on each call, with checksums and
metadata cached by path/size/mtime.

- [x] classify - `inventory_files()` by suffix on every read.
- [x] checksum - `file_checksums()` (SHA-256 + MD5) on every read, cached.
- [x] extract if needed - `upload_complete()` for uploaded `.tar`/`.tgz`,
      `extract_cisco_archive()` for Cisco downloads (see "TAR/TGZ
      handling"). An archive copied into the volume out-of-band is listed
      but not extracted.
- [x] inspect metadata - ISO `iosxr_image_mdata.yml`, RPM headers and SMU
      README manifests (`file_metadata_provenance()`, `active_rpm_names()`).
- [x] refresh inventory - recomputed per request.
- [x] refresh recommendation - `discover()` reruns `recommend_smu_selection()`.
- [x] regenerate BuildPlan - never cached: `/api/build-plan` at Start and
      `create_job()` both recompute it, and a stale confirmed fingerprint is
      rejected (see "Inventory revision").
- [x] update UI automatically - fixed 2026-09-17. The page already reloaded
      inputs after its *own* upload or Cisco download, but a change from
      anywhere else (another browser, files copied into the volume) needed
      "Check files again". New `GET /api/inventory/revision` returns only
      the revision hash; `static/app.js` polls it every 10 s while the tab
      is visible and no upload is running, checks immediately on
      `visibilitychange`, and reloads inputs only when it moved. If the
      operator has edited the manual package selection it shows a notice
      instead, so a refresh never discards their choices. Tests:
      `test_inventory_revision_moves_only_when_files_change`,
      `test_ui_refreshes_automatically_without_discarding_a_manual_selection`.
      Browser check against a throwaway `giso-webui` container (dummy files
      only): an ISO written into `/data` with `docker exec` changed Step 2 to
      "Found and ready" with no reload; a later `build.yaml` appeared on the
      next timer tick; with `packageListEdited` set, deleting it kept the
      list and showed the notice. The in-app browser pane reports
      `visibilityState: hidden`, so visibility was overridden in the page
      for that check.

"Check files again" and "Recalculate" remain, now labelled as troubleshooting
controls (button tooltip).

## Preflight

One authoritative preflight must decide whether Build is enabled.

`create_build_plan()` is that preflight: `plan.ready` is `not blockers`, the
Start button submits only after `/api/build-plan` says ready, and
`create_job()` re-derives the same plan before building. Fixed 2026-09-17: the
build environment (gisobuild, Docker CLI, a running build/upload/Cisco
download) used to be checked only in `create_job()`, so Step 2 could call a
plan ready that Start then refused. `build_environment_blockers()` now feeds
the plan; `create_job()` keeps its own identical checks as the race-safe gate
under `operation_lock`. Live check (throwaway `giso-webui` container, dummy
ISO, no Cisco content): without `/tool` mounted the plan returned exactly
`["gisobuild is not available (/tool/src/gisobuild.py is missing)"]`; with the
repo's `.gisobuild-tool` mounted it returned no blockers.

- [x] base image valid - fixed 2026-09-17: besides existing in inventory,
      the file must carry the ISO 9660 `CD001` volume descriptor
      (`is_iso9660_image()`), else a blocker names it. Tests:
      `test_build_plan_blocks_a_base_image_that_is_not_an_iso`,
      `test_real_iso9660_image_passes_the_signature_check` (genisoimage).
      Live, inside a `--rm` container (no host copy): the operator's real
      `ncs5500-mini-x-25.1.2.iso` (2 204 729 344 bytes) returned `True`; the
      first 64 KiB of the Cisco `.tar` saved as `.iso` returned `False`.
      This proves "is an ISO filesystem", not "is a bootable IOS XR image" -
      gisobuild still validates the image contents.
- [x] engine known - `validate_platform_options()` raises for an unresolved
      platform, which becomes a blocker.
- [ ] release known - not a blocker. An unknown release only degrades
      automatic selection (which blocks with "ISO release could not be
      detected") and confidence to `UNKNOWN`; a manual build with no release
      still counts as ready.
- [x] compatible package set - `validate_smu_selection()` issues plus
      `missing_package_dependencies()` are blockers.
- [x] duplicate conflicts resolved - `resolve_rpm_identifiers()` raises
      "Conflicting RPM identities selected", which becomes a blocker
      (`test_different_duplicate_rpms_are_rejected`).
- [ ] CSC completeness checked - partial multi-component bundles are
      reported (`full_candidate_packages`), but see "warn/block incomplete
      CSC groups" above for the case that is still open.
- [x] disk space sufficient - `build_space_blockers()` for uploads, work and
      output volumes.
- [x] gisobuild available - `gisobuild_tool_available()`
      (`test_build_plan_is_blocked_when_gisobuild_or_docker_is_unavailable`,
      plus the live check above).
- [x] required tools available - Docker CLI is a blocker; `isoinfo`/`rpm` are
      warnings because only this app's metadata checks need them
      (`test_missing_metadata_tools_warn_but_do_not_block`).
- [x] no conflicting job - uploads, Cisco download, active job and running
      build container
      (`test_build_plan_is_blocked_by_the_same_conditions_start_build_refuses`).
- [ ] expected outputs supported - `expected_outputs` is computed from the
      platform capabilities but never blocks; nothing rejects an option the
      engine does not support at plan time beyond `validate_platform_options()`.
