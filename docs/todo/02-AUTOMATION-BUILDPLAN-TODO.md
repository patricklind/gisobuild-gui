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
- [x] source (`upload`, `tar`, `cisco-download`) — completed 2026-09-17.
      Cisco downloads landed next to manual uploads with nothing recording
      their origin. `run_cisco_download()` now records each verified file in
      a `file_provenance` table (job store schema version 2, added through
      the new migrations); `inventory_files()` reports `cisco-download` for
      it and for everything extracted from it, but only while the SHA-256
      still matches, so a file replaced by hand reverts to `upload`. The
      same change fixed the Cisco download's rename-on-collision, which split
      `.tar.gz` like uploads once did and ignored an existing extraction
      directory. Test: `test_cisco_downloads_are_recorded_as_such_in_the_inventory`.
- [x] metadata source/confidence - real per file since 2026-09-17
      (`file_metadata_provenance()`: `rpm-header`, `iso-metadata` or
      `filename`; see "RPM inspection").
- [x] lifecycle state — 2026-09-17: `assign_lifecycle()` in `inventory_files()`,
      with `problems` listing why. Test:
      `test_inventory_lifecycle_reflects_what_the_workspace_proves`. Real
      NCS5500 content (`--rm` container): ISO and all 34 RPMs `VALID`,
      nothing `INVALID`; warm inventory 0.01 s (cold 8.2 s is the existing
      ISO SHA-256).

Suggested lifecycle:

- [ ] `UPLOADING` - not an inventory state: an in-progress upload is not in
      the workspace yet (it lives in `.parts`); the page shows its progress
      from the upload itself.
- [x] `READY` - inputs with no deeper checks (YAML, configs, archives)
- [ ] `ANALYZING` - not modelled: analysis is synchronous within the request
      that reads the inventory, so no request can observe it.
- [x] `VALID` - ISO/RPM that passed the checks below
- [x] `INVALID` - ISO without an ISO 9660 filesystem; RPM whose header
      contradicts its name, same-name file with different content, or a fix
      its Cisco README shows incomplete or altered
- [x] `IN_USE` - ISO or RPM in the plan of an active job
- [ ] `ARCHIVED` - not an inventory state: archived artifacts are a separate
      listing (`/api/archive`) and never re-enter the workspace.
- [ ] `DELETING` - not modelled: deletion is synchronous under the
      operation lock.

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
  `.gisobuild-tool/src/lnt/gisoutils.py`), after signature verification.
- Only applies to LNT; eXR platform/release detection would still need its
  own investigation (likely `gisobuild_exr_engine.py`/`isotools_exr.py`).

**Revised 2026-09-19: the "second docker run against a separate pinned
image" obstacle no longer applies to the default deployment.** This was
written when the socket deployment (mounting Cisco's own external
`ciscogisobuild/cisco-xr-gisobuild:2.3.4` image) was the only target: the
`lnt`/`utils` package environment `isols.py` needs lived only in that
external image, not in `giso-webui`'s own lightweight Alpine app image.
Since 2026-09-17 the *default* deployment is the self-contained image
(`docker/selfcontained.Dockerfile`), which already copies the complete
`ios-xr/gisobuild` source tree to `/opt/gisobuild` (the same tree
`gisobuild.py` itself runs from as a child process via `GISOBUILD_PYTHON`)
and installs the same AlmaLinux/`python3-rpm` runtime upstream's own
`prep_dependency.sh` calls for. Confirmed directly: the real entry point,
`.gisobuild-tool/src/lntmod/isols.py` (not `lnt/tools/_isols.py`, which is a
package-internal module that errors on a bare relative import when invoked
directly — the wrapper script fixes `sys.path` first), runs with
`/opt/gisobuild/src/lntmod/isols.py --help` in the real
`giso-webui-selfcontained` image with **no additional dependency missing**
and prints its full option list (`--dump-mdata`, `--rpms`,
`--optional-packages`, `--fixes`, etc.) exactly as upstream documents it. So
in the default deployment this would be an ordinary local subprocess call
next to the existing `gisobuild.py` invocation, not a second container - the
output-cap/timeout/scratch-dir care below is still real, but the "needs its
own container plumbing" complexity this item was blocked on is gone. The
socket deployment's own copy of this question is unaffected (its external
image is still uninspected here).

Still genuinely blocked on test material (2026-09-17, unchanged): the only
real image available to this work is the eXR NCS5500 25.1.2 bundle.
`isols.py` needs a signed LNT ISO - it verifies and runs `image.py` from
inside the image, and that signature check is the entire point of using it
over filename parsing - so neither the prototype's actual JSON output shape
nor a real PID picklist can be verified against genuine content yet. A
synthetic ISO cannot stand in for the same reason a synthetic signature
couldn't stand in anywhere else in this codebase: the check being verified
*is* the signature. Do not write the integration against assumed/guessed
output shape - the `--help` run above only proves the environment is
sufficient, not what `--dump-mdata --json` actually returns.

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
- [x] signature metadata where available - 2026-09-17: the same single
      `rpm -qp` query now reads `RSAHEADER` (algorithm and key ID; nothing is
      verified - that remains gisobuild's signature check). Inventory items
      carry `signature`; the plan warns when a selected RPM is unsigned or
      when selected RPMs use different keys. Tests:
      `test_rpm_header_query_parses_identity_and_exact_dependencies`,
      `test_unsigned_or_mixed_key_rpms_are_warned_about`. Real NCS5500 bundle
      + 20 SMUs: all 34 RPMs `RSA/SHA256`, key `7476b0605746bd08`, no
      warnings.
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
operator-uploaded archive) and `extract_cisco_archive()` (a Cisco-downloaded
archive). Both are now covered. Since 2026-09-17 both accept `.tar.gz` as
well as `.tar`/`.tgz` (`ARCHIVE_SUFFIXES`, `archive_suffix()`): upstream
gisobuild documents LNT bugfixes as `<platform>-<release>-CSC<id>.tar.gz`,
and that suffix was rejected at upload. The collision rename keeps the whole
suffix, the inventory type is `.tar.gz`, provenance (`extracted_from`) and
log redaction cover it; a plain `.gz` is still rejected. Tests:
`test_lnt_bugfix_tar_gz_is_uploaded_extracted_and_traced_to_its_archive`,
`test_plain_gzip_upload_is_still_rejected`, `test_tar_gz_paths_are_redacted_whole`.

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
      model in this app records the outcome before the build - see the
      "SMUs that are incompatible with the rest of the selection" item below
      for the 2026-09-18 correction and the verified comparison approach.
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

- [x] **SMUs that are incompatible with the rest of the selection must be
      deselected, not just reported** (raised by the maintainer 2026-09-17:
      "hvis de SMU pakker ikke er kompatible med resten skal de fravælges").
      Today automatic selection removes what cannot install *against the base
      image* (wrong platform/release/architecture, renamed or unreadable RPMs,
      incomplete or altered fixes, unmet exact-version dependencies, superseded
      fixes). What it does not do is resolve a conflict *between two selected
      SMUs*: when two different CSC fixes change the same component
      (`component_conflicts`, "More than one fix changes this component"), both
      stay selected - it becomes a warning, or a blocker from
      `validate_smu_selection()` when they carry different versions of one
      component. The operator then has to work out which fix to drop.

      Corrected 2026-09-18 (maintainer research): this is not a scenario
      gisobuild itself fails on - both engines already resolve "two fixes
      touch the same component" themselves, silently and unconditionally. But
      a first pass at this research (also 2026-09-18, superseded within the
      same day - kept below as a record of what turned out to be wrong) assumed
      both engines pick the winner the same way, via real `rpmvercmp`. They do
      not, and the difference changes what "mirror gisobuild" requires:

      - **LNT genuinely uses `rpm.labelCompare()`** (true rpmvercmp: epoch,
        tilde pre-release, caret post-release) - `_highest_pkg_version.py`
        (`.gisobuild-tool/src/lnt/builder/_highest_pkg_version.py`) is a small
        standalone script taking `epoch,version,release` tuples as argv,
        called via subprocess from `_pkgpicker.py`'s `_run_highest_pkg_version()`
        using `sys.executable` (gisobuild's own platform Python, which has the
        `rpm` module). But LNT filenames carry no CSC ID at all (see
        `LNT_RPM`'s docstring above) - this app's own `component_conflicts` is
        built entirely from the `.CSC<bug>` filename token
        (`RPM_COMPONENT`), so it can never fire for an LNT selection today.
        LNT conflict detection would need a different signal than filename
        parsing (upstream itself groups by dependency "blocks" resolved from
        RPM Provides/Requires, not filenames - see `_pkgpicker.py`'s
        `GroupedPackages`/`_add_blocks`) and is out of scope until that exists.
      - **eXR does not use `rpm.labelCompare()` at all.** `filter_superseded_rpms()`
        (`.gisobuild-tool/src/exrmod/gisobuild_exr_engine.py`, called from
        `gisobuild_exr.py:316`, confirmed at the pinned commit
        `0388af2989bb7022d780a8732dbfbfeb77a70ee7`) groups candidates by
        `f"{name}.{package_type}.{arch}.{vm_type}"` (all four from the RPM's
        own header - `package_type`/`vm_type` come from Cisco's custom
        `PACKAGETYPE`/`VMTYPE` tags, which this app does not currently read at
        all) and picks the winner with a **hand-rolled comparator** local to
        that file (`_compare_rpm_labels` → `_compare_rpm_field` →
        `_iter_rpm_subfields`): it splits `version`/`release` into alternating
        text/number runs and compares them subfield-by-subfield (fewer
        subfields is lower; a differing subfield decides by string test for
        two text runs, integer test for two number runs). This is *not* full
        rpmvercmp - no tilde-as-prerelease or caret-as-postrelease weighting,
        so `1.0~rc1` is just the text run `"~rc"` compared lexically, not
        recognized as "older than 1.0". And critically, eXR's own `%{RELEASE}`
        header value *is* what this app already reads as `identity["release"]`
        in `rpm_dependency_metadata()` - confirmed against this app's own test
        fixture (`test_rpm_header_query_parses_identity_and_exact_dependencies`,
        `giso-webui/tests/test_app.py`): a real value looks like
        `"r2512.CSCtest00001"`, i.e. Cisco bakes the CSC ID into the RELEASE
        tag itself. Comparing two different fixes' `release` strings therefore
        partly compares their CSC-ID text as an incidental tiebreaker, not a
        clean "which fix supersedes which" signal.

      Practical effect: mirroring gisobuild for real needs *two different*
      comparators (one per engine), and eXR's - the only one `component_conflicts`
      can currently see - is a small, dependency-free, pure-Python algorithm,
      not something `rpm`/`rpmvercmp` reproduces. The earlier plan below (Lua
      `rpm --eval vercmp`) is verified to work as a *generic* rpmvercmp, but
      is the wrong comparator to mirror eXR's actual decision, so it must not
      be wired into automatic selection as originally planned.

      Done 2026-09-18: ported eXR's exact `_compare_rpm_field()`/
      `_iter_rpm_subfields()`/`_compare_rpm_labels()` (BSD-3-Clause, Cisco
      Systems - attributed in the docstring) as
      `platform_validation.compare_exr_rpm_labels()`, needing no `rpm`
      binary/module and thus no Dockerfile change. Tests added in
      `ExrRpmLabelCompareTests` (`giso-webui/tests/test_platform_compatibility.py`):
      plain unit cases (the `1.0~rc1` vs `1.0` quirk above, equal labels,
      release-only tie-break) plus a drift test that executes the real
      pinned-commit source itself (same technique as
      `test_exr_platform_list_matches_the_pinned_upstream_engine` above) rather
      than trusting the local port statically. Verified 2026-09-18 inside
      `giso-webui-giso-webui` (built from `giso-webui/Dockerfile`) per
      `AGENTS.md`'s required verification: full suite green - 332 passed, 3
      skipped (missing `.gisobuild-tool`/`TOOL_ROOT`, expected in a plain
      checkout) - and the drift test forced to actually run (not skip) by
      mounting a throwaway clone of the pinned upstream commit as `TOOL_ROOT`,
      confirming `compare_exr_rpm_labels()` agrees with the real source.
      `ruff check` on the changed files: clean (the only finding, `EXE002`,
      is pre-existing and identical on untouched `app.py` - a Windows-mount
      artifact, not a real issue).

      Done 2026-09-18: `PACKAGETYPE`/`VMTYPE` are Cisco custom RPM tags, not
      real rpm tags a stock `rpm` binary knows - confirmed with `docker run`
      against both pinned rpm builds that querying them directly with `rpm -qp
      --qf '%{PACKAGETYPE}'` errors the *entire* `--qf` call ("unknown tag"),
      which would have silently broken every other field read in the same
      combined `RPM_QUERY_FORMAT` string (name/version/release/arch too).
      Reading upstream's own `populate_mdata()`
      (`.gisobuild-tool/src/exrmod/gisobuild_exr_engine.py`) showed how it
      actually gets them: Cisco packs both into the standard, always-safe
      `%{GROUP}` tag as `"<display name>,SUPPCARDS:...;VMTYPE:host;
      PACKAGETYPE:smu;..."` - confirmed `%{GROUP}` is always queryable
      (`rpm -q --qf '%{GROUP}'` on an unrelated real package: `EXIT=0`).
      Ported that same parsing as `exr_package_type_and_vm_type()`
      (`giso-webui/app.py`): added `%{GROUP}` as a 5th field to
      `RPM_QUERY_FORMAT`, and `rpm_dependency_metadata()`'s identity now
      carries `package_type`/`vm_type` (`None` for anything without Cisco's
      "SUPPCARDS"/"XRRELEASE" marker in `%{GROUP}` - e.g. a plain RPM's
      "Unspecified" - never guessed).

      Wired `compare_exr_rpm_labels()` into `resolve_component_conflicts()`
      (`giso-webui/app.py`), called after `exclude_unsatisfiable_packages()`
      in all three places automatic selection is computed
      (`discover()`, `create_build_plan()`, `/api/smu/recommendation`).
      Scope, deliberately narrow: resolves a conflict only when every
      contending CSC is a single-component fix (group `count == 1`) for
      *this* component, all candidates share the real four-part key
      (`name`+`package_type`+`arch`+`vm_type`, with `package_type`/`vm_type`
      both present on every side), and the version comparison is
      unambiguous. Otherwise it leaves `component_conflicts` untouched -
      still today's warning/blocker, never a guess. The dropped file gets a
      `SUPERSEDED`-classified reason naming the fix that kept the component
      (`classify_exclusion()` on the message returns `SUPERSEDED`, verified
      by test). Manual selection is unaffected (only the automatic-selection
      recommendation is resolved; `validate_smu_selection()`'s own pure
      filename-based warning/blocker behavior is untouched, so
      `test_multiple_fixes_for_same_component_require_supersedence_data` and
      `test_multiple_versions_of_same_component_and_fix_are_rejected` still
      pass unchanged).

      Revised same day, before this was ever released: the first cut above
      required every contending CSC to be a *single-component* fix
      (`group["count"] == 1`), leaving a conflict inside a multi-component
      fix as today's warning. On reflection that was overcautious - traced
      through `validate_smu_selection()`'s own bundle-completeness check
      (the `full_candidate_packages` branch) and confirmed it only ever
      fires when 2+ of a CSC's components are *partially* selected; once a
      losing component's single file is dropped, exactly one component of
      that CSC remains selected, which the check treats as "nothing to
      verify", not as "verified complete" - so dropping just that one file
      cannot spuriously trip it. `resolve_component_conflicts()` now
      resolves per RPM, not per CSC group: for each side of a conflict it
      finds (via `platform_validation.RPM_COMPONENT`) only the specific
      selected file that carries the *contested* component and compares
      those; any other file the same CSC contributes for one of its other
      components is untouched. This matches gisobuild's own granularity -
      `filter_superseded_rpms()` supersedes individual packages with no
      notion of "the SMU tar they arrived in" - so a multi-component fix
      losing one shared component to a newer fix elsewhere, while remaining
      the only fix for its other component(s), is now resolved exactly like
      a single-component conflict: the losing file is dropped and excluded
      with reason, the rest of that CSC's files stay selected. Test renamed
      accordingly:
      `test_component_conflict_inside_a_multi_component_fix_drops_only_that_file`
      asserts the contested file is dropped and excluded while a sibling
      file for a different, uncontested component of the same CSC stays in
      `selected`.

      Verified 2026-09-18 in the containerized `giso-webui-giso-webui` image
      per `AGENTS.md`: full suite green - 338 passed, 3 skipped (same
      pre-existing `.gisobuild-tool`/`TOOL_ROOT`-dependent skips). Six
      `resolve_component_conflicts()` cases plus
      `test_rpm_header_group_without_cisco_metadata_yields_no_package_or_vm_type`
      in `giso-webui/tests/test_app.py`: resolves a real conflict, resolves
      inside a multi-component fix without touching the sibling file, does
      *not* resolve across different `vm_type`, does *not* resolve without
      package_type/vm_type metadata, and does *not* resolve a version tie.
      `ruff check` on the changed files: clean (only the same pre-existing,
      unrelated `EXE002` Windows-mount artifact noted above). Graphify
      refreshed (1270 nodes, 2170 edges, 82 communities); diff reviewed, no
      unexpected architecture changes.

      **Real-content verification, 2026-09-18** (throwaway container and
      Docker volumes; all 10 real NCS5500 25.1.2 SMU tars extracted
      unmodified, licensed content removed afterwards): loaded all 20 real,
      signed RPMs and got a genuine, previously-untested conflict shape -
      `CSCwt13701` (7 components: dpa, dpa-fwding, fwding, infra,
      iosxr-fwding, os, os-support) has two of its components (`infra`,
      `iosxr-fwding`) also touched by later, unrelated fixes
      (`CSCwu13268`/`CSCwv36143`/`CSCwv38342`), and none of these three CSCs
      supersede each other via README `Full` notation, so the conflict
      reaches `resolve_component_conflicts()` genuinely unresolved by the
      earlier README-based path. `resolve_component_conflicts()` itself
      correctly picked the highest real version each time (`ncs5500-infra`
      1.0.0.8 over 1.0.0.3, `ncs5500-iosxr-fwding` 1.0.0.5 over 1.0.0.4 and
      1.0.0.1, `ncs5500-routing` 1.0.0.3 over 1.0.0.2) - the port of
      `compare_exr_rpm_labels()` is proven correct against real Cisco
      version/release strings, not just the unit tests' constructed ones.

      That same real run then surfaced three further, real defects this
      exact conflict shape exposes (a CSC losing *more than one* of its
      components to *different* other CSCs - the unit tests above only
      covered losing exactly one):

      1. **The bundle-completeness check re-blocked a plan
         `resolve_component_conflicts()` had already resolved.**
         `create_build_plan()`'s own `validate_smu_selection(...,
         full_candidate_packages=candidates)` call passed the *raw* uploaded
         RPM list, still containing the two files `resolve_component_conflicts()`
         had just (correctly) dropped, so it re-derived "CSCwt13701 is a
         multi-component fix; 5 of 7 required RPMs are selected" as a
         blocker - contradicting the resolution that had just explained the
         very same gap. Fixed: `full_candidate_packages` now excludes
         whatever `recommendation["excluded"]` already explains, in
         `create_build_plan()` and in `build_command()` (via a new
         `already_excluded` parameter, populated from
         `plan["excluded_packages"]`) - so a file this automatic pipeline has
         already proven unnecessary is not "silently missing" to either
         check. Manual selection is unaffected: `recommendation["excluded"]`
         is only ever populated by the automatic pipeline.
      2. **The build preview (`generated_command`) showed both the dropped
         and the kept version of every contested component.** It re-derived
         selection through `build_command()`'s own bare
         `recommend_smu_selection()` call (no `add_superseded_exclusions()`/
         `exclude_unsatisfiable_packages()`/`resolve_component_conflicts()`),
         instead of previewing the plan's own already-resolved selection -
         so the "gisobuild command this plan will run" named 17 packages
         where the plan itself said 14. Fixed: `create_build_plan()` now
         previews `{**payload, "pkglist": identifiers, "automatic_smu_selection":
         False}` (the plan's own resolved identifiers), matching exactly what
         `create_job()` already does for the real build.
      3. **`POST /api/jobs` rejected the exact plan `POST /api/build-plan`
         had just called `ready: true`** - the same stale-`full_candidate_packages`
         defect as (1), reached through `build_command()`'s own copy of the
         same check when `create_job()` calls it with the plan's resolved
         pkglist. This is the same "review says ready, Start rejects it"
         class of bug `build_command()`'s own docstring already warns
         against for a different case. Fixed by the same `already_excluded`
         threading as (1).

         All three verified against the real RPMs before and after the fix:
         before, `/api/build-plan` returned `ready: false` with the stale
         blocker and a 17-package preview; `/api/jobs` returned 400
         `"SMU compatibility check failed: CSCWT13701 is a multi-component
         fix; 5 of 7 required RPMs are selected..."`. After, `/api/build-plan`
         returns `ready: true`, a 14-package preview matching
         `selected_packages` exactly, and `/api/jobs` accepts the identical
         plan (202, job created) with exactly those 14 RPMs; the real
         gisobuild run itself was left to complete separately (see below) so
         this fix's own verification did not block on its full duration.
         Regression test (synthetic, reproducing the real shape - one
         CSC losing two different components to two different other CSCs):
         `test_component_conflict_resolution_does_not_desync_plan_from_job_or_preview`
         in `giso-webui/tests/test_app.py`, asserting all three of the above
         together (plan readiness, preview-vs-selection agreement, and job
         acceptance) so they cannot silently drift apart again. Full suite
         green after the fix (339 unit/integration tests, 22 browser tests,
         `ruff check` and `ruff format --check` clean).

      Not yet exercised: an LNT-side equivalent (out of scope today per the
      LNT section above - LNT filenames carry no CSC ID, so
      `component_conflicts` cannot fire for an LNT selection).

      **Latent copy of the same bug, closed same day.** `build_command()`
      has its own `automatic_smu_selection` branch (defensive re-derivation
      if ever called directly with a possibly-stale pkglist - see its own
      test `test_build_recalculates_automatic_smu_selection_server_side`).
      It called bare `recommend_smu_selection()` with none of
      `add_superseded_exclusions()`/`exclude_unsatisfiable_packages()`/
      `resolve_component_conflicts()`, so a caller reaching this branch with
      a real component conflict would reproduce the exact bug above on this
      path. Not reachable today - `create_job()` and the build preview
      always pass a pre-resolved pkglist with `automatic_smu_selection:
      False` - but it was a landmine for any future caller. Now runs the
      same three steps and folds the result into `already_excluded` before
      its own `validate_smu_selection()` call. Test (confirmed to fail
      without the fix - both the dropped and kept version present with no
      resolution at all - and pass with it):
      `test_build_commands_own_automatic_selection_also_resolves_component_conflicts`.
      Full suite green (340 unit/integration tests, 22 browser tests, `ruff
      check` and `ruff format --check` clean).

      **A second real gap in the build preview, same day.** The preview
      panel added earlier the same session (`renderBuildPreview()` in
      `giso-webui/static/app.js`) showed `plan.blockers` but never
      `plan.warnings` or `plan.component_conflicts` - so a plan
      `resolve_component_conflicts()` could not decide (a version tie,
      mixed `vm_type`, or missing `package_type`/`vm_type` metadata) still
      showed plainly "READY TO BUILD" with no sign that two conflicting
      fixes remained selected side by side for gisobuild's own
      supersedence to decide - visible only in Step 2's separate live
      review, not in the preview meant to show everything before starting.
      Now renders both under "Review before building" (reusing the same
      `.smu-relationship-warning` style Step 2 uses). Browser test
      (confirmed to fail without the fix - the warning panel did not
      exist - and pass with it):
      `test_build_preview_shows_an_unresolved_conflict_before_building`.
      Its first fixture attempt (both files given an identical, hand-picked
      `version`/`release`) reconstructed neither file's real name via
      `rpm_filename_mismatch()`, so both were silently excluded as
      `INVALID` before `resolve_component_conflicts()` ever ran - the test
      still passed, for the wrong reason (masked by two files sharing a
      class-level "Review before building" heading with the unrelated
      warnings panel it also renders). Corrected to reconstruct each file's
      real name and omit `package_type`/`vm_type`, the genuinely-unresolved
      case above - which also surfaced that Step 2's own equivalent test
      (added alongside, see `06-UI-OPERATOR-TODO.md`) needed the same fix,
      and needed to scope its locator past the *other*,
      also-"Review before building" `plan.warnings` panel Step 2 renders
      separately. Full suite green (340 unit/integration tests, 24 browser
      tests, ruff clean, Graphify refreshed).

      **Root-cause DRY fix, same day.** The four bugs above all trace back
      to one thing: `recommend_smu_selection()` →
      `add_superseded_exclusions()` → `exclude_unsatisfiable_packages()` →
      `resolve_component_conflicts()`, in that exact order, was written out
      separately at four call sites (`create_build_plan()`, `discover()`,
      `build_command()`'s automatic branch, `POST /api/smu/recommendation`)
      instead of once - exactly the shape that let two of them drift out of
      sync unnoticed. Extracted the sequence into one function,
      `resolve_automatic_recommendation()`, and rewrote all four call sites
      to use it; a caller with no ISO (`discover()`'s zero/multiple-ISO
      branches) still gets `add_superseded_exclusions()` alone, matching
      the original behavior (it only explains files already screened out,
      independent of any ISO). No future call site can add the steps out
      of order or with one missing, because there is only one place they
      are written. Full suite unchanged (340 unit/integration tests, 24
      browser tests, ruff and `ruff format --check` clean, Graphify
      refreshed) - the refactor changed no observable behavior, only where
      the logic lives.

      **Full gisobuild run: attempted, not completed, 2026-09-18.** Two
      attempts against the real, complete NCS5500 25.1.2 workspace (base ISO
      + all 12 base `optional-rpms/*` + all 10 SMU tars, 25 selected RPMs)
      each ran for well over an hour under this Mac's amd64/Rosetta
      emulation without reaching a terminal state - the first attempt's
      earlier, *incomplete* workspace (missing the 12 base packages; a test
      setup mistake, not a code defect) did complete in ~31 minutes and
      failed gisobuild's own compatibility check exactly as expected for a
      workspace missing base dependencies, which is what surfaced the
      missing-files mistake. Both full-workspace attempts were cancelled
      cleanly through `DELETE /api/jobs/<id>` (`build_cancelled`, no orphan
      processes) rather than left to run indefinitely; this is a real
      limitation of today's verification, not a simulated result, and this
      TODO item is deliberately left unchecked until a full run actually
      completes. It does not weaken the fix itself: the defect and its fix
      were in this application's own plan/preview/job-creation code path
      (proven directly via `create_build_plan()`/`POST /api/jobs` against
      the real RPMs, before and after), not in whether the separate,
      third-party `gisobuild` binary itself can finish on this machine
      today. Retry when time and environment performance allow; the
      correctly-complete throwaway workspace recipe is above (extract the
      base tar's `optional-rpms/` directory in addition to the SMU tars,
      not just the SMU tars alone).

      **Full gisobuild run: completed, 2026-09-19.** Retried in a fresh
      isolated throwaway container (`giso-ccheck2`, its own named volumes
      and network, port 8098 - never touching the separately-running live
      `giso-webui` deployment) against the exact same real, complete
      NCS5500 25.1.2 workspace as before (base ISO + all 12 base
      `optional-rpms/*` + all 10 real SMU tars uploaded through the real
      chunked-upload API so extraction ran normally, not copied in raw).
      Automatic selection correctly picked 25 RPMs (resolving the same real
      `infra`/`iosxr-fwding`/`routing` component conflicts documented
      above) and excluded 5 with reasons, including one genuinely new,
      real-world case: Cisco's own tar ships the `k9sec` (crypto) RPM with
      restrictive owner/group permissions (`-rwxr-x---`, owner `swtools`,
      group `crypto`) unlike every other package in the same tar - a
      deliberate Cisco packaging choice for export-controlled content. With
      `CAP_DAC_OVERRIDE` correctly dropped (matching the real production
      security posture), the container's root process cannot bypass that
      permission bit, and `service_can_read()` correctly detected and
      excluded it with a clear, actionable reason instead of crashing or
      silently mis-selecting it - the first real-content confirmation of
      that specific exclusion path, previously proven only against
      synthetic fixtures.

      `POST /api/jobs` accepted the plan; the real `gisobuild` engine ran
      for ~32 minutes (`docker top` confirmed genuine, ongoing
      `rpm -qp --provides` subprocess activity throughout the slow
      "Scanning update packages" phase under this Mac's amd64/Rosetta
      emulation - not stalled, just slow) and completed with **exit code 0,
      `status: success`**. Both real artifacts were archived and verified:
      `ncs5500-golden-x-25.1.2-CCHECK2.iso` (2 668 240 896 bytes, SHA-256
      `7e92b398d2ad4e5f2c1a36685338a8ba7bd7d72250c7ef2a1ed8fb5718adeff4`) and
      `ncs5500-usb_boot-25.1.2-CCHECK2.zip` (2 645 392 512 bytes, SHA-256
      `4ab53e775240df89ac8cfc646000e9f52f1a3ba141edcbfd9dd30f8ec629dee4`),
      builder recorded as `gisobuild 0388af2989bb (bundled)` - the pinned
      commit. The throwaway container, its five named volumes and its
      network were all deleted immediately afterward; nothing from this run
      was committed or left on disk. This is the first confirmed full
      completion of this exact real-content build in this project's
      history - the item below is now genuinely, not provisionally, closed.

      <details><summary>Superseded same-day: the rpmvercmp/Lua-eval plan (kept as a record, not a task list)</summary>

      So the task is not "invent a rule for which fix wins" - it is **make our
      own automatic-selection output agree with what gisobuild will actually
      build**: drop the lower version with a reason derived from the same
      comparison gisobuild uses, instead of leaving both "selected" behind a
      warning/blocker.

      Version comparison must be a real `rpmvercmp`-equivalent (handles epoch,
      tilde pre-release, caret post-release), not a naive string/tuple compare
      - and must not be a hand-rolled reimplementation that then needs its own
      correctness verification. Checked 2026-09-18: neither runtime image can
      `import rpm` from the process that runs this app. `giso-webui/Dockerfile`
      installs only the `rpm` CLI (no `py3-rpm`); confirmed with `docker run
      python:3.12-alpine sh -c "apk add py3-rpm"` that Alpine's `py3-rpm`
      package pulls in its own separate `python3` (3.14.7), not the base
      image's pinned `python:3.12-alpine` interpreter, so `import rpm` still
      fails there even if the package were added. In
      `docker/selfcontained.Dockerfile`, `python3-rpm` is bound only to the
      platform `python3` that gisobuild itself runs on (`GISOBUILD_PYTHON`);
      the web app runs under a separately pip-installed `python3.12`, which
      does not have it either.

      Verified working (as a generic rpmvercmp, not as eXR's actual algorithm -
      see above): shell out to `rpm` for the comparison itself, via its own Lua
      macro evaluator, e.g. `rpm --eval '%{lua: print(rpm.vercmp("1:1.0-1",
      "2.0-1"))}'`. Confirmed 2026-09-18 with `docker run` against the exact
      pinned versions of both images: Alpine `rpm=4.19.1.1-r5`
      (`giso-webui/Dockerfile`) and AlmaLinux 8.10's `rpm-4.14.3`
      (`docker/selfcontained.Dockerfile`'s runtime stage) both support
      `%{lua: ...}` and both return correct results for a plain compare,
      an epoch tie-break (`1:1.0-1` > `2.0-1`), a tilde pre-release
      (`1.0~rc1-1` < `1.0-1`), and a caret post-release (`1.0^git1-1` >
      `1.0-1`). This remains useful context (it is genuinely rpm's own
      comparator) but is not what decides eXR's real winner, so it is not
      being wired in.

      </details>


- [x] one status vocabulary for every decision (2026-09-17). Each excluded
      package now carries a status code from
      `platform_validation.PACKAGE_STATUSES` - WRONG_PLATFORM, WRONG_RELEASE,
      WRONG_ARCHITECTURE, CONFLICT, SUPERSEDED, MISSING_DEPENDENCY, DUPLICATE,
      INVALID, UNKNOWN, with MANUAL_REVIEW_REQUIRED as the only fallback -
      together with the identity its filename carries (platform, release,
      architecture, CSC) and which check decided it (`source`). One
      `finalize_recommendation()` adds them, so the inventory response, the
      recommendation endpoint and the BuildPlan cannot describe the same
      package differently, and every response also carries a `summary`
      (`discovered`, `included`, `excluded`, `by_status`) for the build
      preview. The page shows the counts in the exclusion heading and a status
      chip per row, all from the backend. Tests:
      `test_every_reason_the_selection_engine_writes_maps_to_a_status`,
      `test_describe_package_reads_identity_from_both_naming_schemes`,
      browser `test_automatic_selection`.

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
- [x] CSC completeness checked - partial selection of present members
      (`full_candidate_packages`) and, since 2026-09-17, fixes whose Cisco SMU
      README lists RPMs that were never uploaded or whose MD5 differs
      (`selection_integrity_blockers()`); see "CSC grouping".
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
- [x] expected outputs supported - 2026-09-17: `expected_outputs` now follows
      upstream per engine (eXR: USB zip exactly for platforms in
      `usb_zip/platform_scripts.yaml`, pinned by
      `test_exr_usb_support_matches_the_pinned_upstream_usb_scripts`; LNT:
      USB unless `--skip-usb-image`), `validate_platform_options()` blocks
      options the engine does not support (`OPTION_UNSUPPORTED`), and the
      real self-contained NCS5500 build produced ISO + USB zip, which the
      plan predicted wrongly then (it honoured `--skip-usb-image`) and the
      corrected logic now predicts.
