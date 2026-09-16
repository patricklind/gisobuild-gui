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

- [ ] drag/drop ISO
- [ ] drag/drop TAR/RPM/SMU
- [ ] Cisco download integration
- [ ] automatic analysis starts immediately

### Step 2 — Review BuildPlan

Show:

- [ ] ISO
- [ ] release
- [ ] engine
- [ ] platform
- [ ] confidence/source
- [ ] CSC groups
- [ ] excluded packages
- [ ] warnings
- [ ] blockers
- [ ] expected output
- [ ] free disk estimate

### Step 3 — Build

- [ ] clear progress
- [ ] current phase
- [ ] cancellation
- [ ] friendly error
- [ ] technical details collapsed by default
- [ ] artifact download
- [ ] checksums
- [ ] build report

## Automatic by default

Do not ask for these unless ambiguous:

- [ ] platform
- [ ] architecture
- [ ] target release
- [ ] repo path
- [ ] package list
- [ ] build engine

## Expert settings

Keep advanced controls, but:

- [x] capability-driven
- [x] hide unsupported settings
- [x] server validates everything
- [ ] warn before unsafe/manual overrides

## Explain decisions

Every exclusion must explain why:

- [ ] wrong release
- [ ] wrong platform
- [ ] wrong architecture
- [ ] superseded
- [x] duplicate
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
