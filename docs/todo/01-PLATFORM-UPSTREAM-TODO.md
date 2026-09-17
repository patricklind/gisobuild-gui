# TODO — Upstream Platform & Capability Support

## Scope

Support **everything that the pinned upstream `ios-xr/gisobuild` revision supports**.

The application must distinguish:

- [x] Physical PID / SKU — fixed 2026-09-16: `ALIASES` already routed an
      exact PID spelling (`ncs-57c3-mod-sys`, …) to its marketing family
      (`ncs57`), but discarded the spelling itself, so an operator could not
      tell "we matched your exact NCS-57C3-MOD-SYS" from "we guessed the NCS
      5700 family". Added `infer_platform_pid()` in
      `giso-webui/platform_validation.py`, which returns the literal alias
      token matched (or `None` when the filename matched a canonical
      platform ID directly — then the family name *is* what was in the
      filename, and there is no separate SKU to report). Surfaced as a new
      `pid` field on `confidence_report()`'s platform entry, and appended to
      that entry's `detail` text ("Matched hardware PID/SKU spelling: …"),
      which the existing confidence badge already renders as its tooltip —
      no new UI element needed. Wired into all three `confidence_report()`
      call sites (`create_build_plan()`, `discover()`,
      `/api/smu/recommendation`). Honest limitation, documented in the
      function's own docstring: `ALIASES` also holds alternate marketing
      digit-spellings that are not distinct physical SKUs (`asr9k-x64`,
      `8800`), and this reports those too — separating "true PID" from
      "family nickname" would need a distinction upstream does not track
      either. Verified by
      `test_hardware_pid_is_reported_separately_from_the_marketing_family`
      in `giso-webui/tests/test_platform_compatibility.py`.
- [x] Marketing family — `platform_profile()["label"]` (e.g. "NCS 5700 /
      NCS 57C3"), shown in the platform dropdown, the Step 2 flow row, and
      the build report.
- [x] Upstream gisobuild platform identifier — `platform_profile()["id"]`
      (e.g. `ncs57`, `ncs5500`, `exr-generic`), the exact string
      `normalize_platform()` resolves to and `validate_platform_options()`
      passes through as `payload["platform"]`; shown directly (uppercased)
      in the same flow row as "Platform".
- [x] Build engine (`eXR` / `LNT`)
- [x] IOS XR release — `release` field throughout (confidence report,
      BuildPlan, build report), extracted from the ISO filename independent
      of platform detection — confirmed live it is populated correctly even
      for an unrecognized/generic platform (see "Unknown-but-valid
      platforms" below).
- [x] CPU architecture — `iso_architecture`/`package_architecture` are
      separate fields in `confidence_report()`, and `iso_architectures`
      (read from the ISO's own contents via `inspect_iso_architecture()`)
      gates RPM architecture matching independently of platform/release.
- [x] Feature/capability support

## Upstream-first model

- [x] Inspect pinned `ios-xr/gisobuild` — full CLI-argument audit against
      `.gisobuild-tool/src/gisobuild.py:parsecli()` done 2026-09-16, see the
      "CLI option compatibility matrix" below. This is a one-time manual
      audit of the pinned checkout, not automatic per-version detection —
      see "Stop using a locally maintained list" below for what remains.
- [x] Read `src/utils/gisoglobals.py`
- [x] Read eXR-specific code
- [x] Read LNT-specific code
- [x] Detect supported CLI options from upstream
- [x] Build a `GisoBuildCapabilities` abstraction
- [ ] Stop using a locally maintained list as the authoritative support list
      — still open: `platform_validation.PLATFORMS`'s eXR entries remain a
      hand-maintained Python literal, not something read from the mounted
      `.gisobuild-tool` checkout at runtime. What changed 2026-09-16: added
      `test_exr_platform_list_matches_the_pinned_upstream_engine` in
      `giso-webui/tests/test_platform_compatibility.py`, which reads
      `Giso.SUPPORTED_PLATFORMS` directly out of the pinned
      `.gisobuild-tool/src/exrmod/gisobuild_exr_engine.py` (via
      `ast.literal_eval` on the regex-extracted list literal, not a
      hand-copied assumption) and asserts `PLATFORMS`'s eXR entries are
      exactly that set. Confirmed the two lists are identical today (12
      platforms each), and this closes the *silent-drift* risk — a future
      pinned-commit bump that changes upstream's list now fails this test
      loudly instead of the local copy quietly going stale. It does not
      close the item itself: the list is still hardcoded, only verified;
      true dynamic discovery would mean parsing `SUPPORTED_PLATFORMS` out of
      the mounted checkout at application startup (or build time) instead of
      maintaining a parallel Python literal at all. That is real remaining
      work — the test above is a safety net for the interim, not a
      replacement for it.

      **Considered and deliberately deferred (2026-09-16): full runtime
      discovery.** Designed this out before writing code: `PLATFORMS` also
      carries marketing label and `usb` capability per platform, neither of
      which exists in gisobuild's own source (there is no per-platform USB
      flag anywhere in `.gisobuild-tool` — confirmed by direct source
      inspection while investigating a since-disproven `--skip-usb-image`
      concern, see `07-BUG-AUDIT-TODO.md`), so a discovered ID with no local
      entry can only ever get a synthetic, unnamed, conservative profile —
      exactly `exr-generic`'s shape, just keyed by a real ID instead of a
      placeholder. Building that means either mutating the module-level
      `PLATFORMS` dict once at startup (test-isolation risk: any test
      importing it fresh after that mutation sees extra synthetic keys) or
      threading an optional `platforms` parameter through `normalize_platform()`,
      `infer_platform()`, `capabilities_for_platform()`, `platform_profile()`
      and `validate_platform_options()` and every one of their ~15 call
      sites — real, invasive surface area for a change that is a **complete
      no-op today**, since the sync test above already proves upstream and
      local are identical. The chosen alternative achieves the same
      practical outcome with far less risk: the sync test makes drift
      impossible to miss silently, and the fix when it *does* fire is a
      one-line `PLATFORMS` addition (the same shape as `exr-generic`) — not
      a redesign. That satisfies "handle a new upstream platform without
      major code changes" without the standing complexity and blast radius
      of a live filesystem-parsing merge running on every request. Revisit
      if the sync test ever actually fires in practice and a one-line fix
      turns out to be too slow to ship for a given deployment's needs.

## CLI option compatibility matrix (2026-09-16)

Audited directly against `.gisobuild-tool/src/gisobuild.py`'s `parsecli()` —
every `add_argument()` call in the pinned checkout — cross-referenced with
`PATH_OPTIONS`/`BOOL_OPTIONS`/`LIST_OPTIONS` in `giso-webui/app.py`. This is
the evidence-based audit `docs/AI-MASTER-PROMPT.md` section 58 asks for,
against the actual upstream source rather than assumption.

| Upstream option | Exposed in Web UI? | Notes |
| --- | --- | --- |
| `--iso` | yes | `PATH_OPTIONS["iso"]` |
| `--repo` | yes | `LIST_OPTIONS["repo"]`; auto-managed by `auto_repo` staging, not manually typed |
| `--bridging-fixes` | yes | `LIST_OPTIONS["bridging_fixes"]` |
| `--xrconfig` | yes | `PATH_OPTIONS["xrconfig"]` |
| `--ztp-ini` | yes | `PATH_OPTIONS["ztp_ini"]` |
| `--label` / `-l` | yes | special-cased in `build_command()`, validated against `[A-Za-z0-9_]+` |
| `--no-label` | yes | `BOOL_OPTIONS["no_label"]` |
| `--out-directory` | **by design, not user-facing** | always set internally to `/output/<job_id>` — exposing this would let one job's output path collide with another's |
| `--create-checksum` | yes | `BOOL_OPTIONS["create_checksum"]` |
| `--yamlfile` | yes | `PATH_OPTIONS["yamlfile"]` |
| `--clean` | **by design, not user-facing** | always appended — the job's output directory is always fresh, never reused |
| `--exriso` | hidden upstream (`argparse.SUPPRESS`) | internal; correctly not exposed |
| `--pkglist` | yes | `LIST_OPTIONS["pkglist"]`, resolved from opaque inventory IDs, never raw paths |
| `--key-request` | yes | `PATH_OPTIONS["key_request"]` |
| `--docker` / `--use-container` | **no — architecturally incompatible** | this tells gisobuild to pull/run its *own* nested container for the eXR build step. giso-webui already runs the whole `gisobuild.py` invocation inside one container itself (`build_command()`), and that container has no `docker.sock` mount (`child_mount_args()` only shares `/uploads`, `/output`, `/tool`, `/work`) — passing `--docker` would just fail. Not a gap; documented here so it isn't mistaken for one. |
| `--bes-logging` | hidden upstream | internal; correctly not exposed |
| `--script` (eXR) | yes | `PATH_OPTIONS["script"]` |
| `--in_docker` (eXR) | hidden upstream | internal; correctly not exposed |
| `--x86-only` (eXR) | yes | `BOOL_OPTIONS["x86_only"]` |
| `--migration` (eXR) | yes | `BOOL_OPTIONS["migration"]`, restricted to ASR9k in `validate_platform_options()` |
| `--optimize` (eXR) | yes, but see gap below | `BOOL_OPTIONS["optimize"]` |
| `--full-iso` (eXR) | yes, but see gap below | `BOOL_OPTIONS["full_iso"]`, restricted to xrv9k |
| `--remove-packages` (LNT) | yes | `LIST_OPTIONS["remove_packages"]` |
| `--skip-usb-image` (LNT) | yes | `BOOL_OPTIONS["skip_usb_image"]` |
| `--skip-dep-check` (LNT) | hidden upstream | internal; correctly not exposed |
| `--copy-dir` (LNT) | **no — deliberately not exposed** | copies built artifacts to an operator-chosen directory. Revisited 2026-09-16: `child_mount_args()` only shares `/uploads`, `/output`, `/tool`, `/work` into the build container — there is no mechanism today to write into an arbitrary operator-supplied host path safely, and building one (validating/scoping an arbitrary destination path) is real design work, not a quick pass-through. `archive_giso_artifacts_and_cleanup()` already serves the normal "get my artifacts" need. Documented here rather than implemented unsafely. |
| `--clear-bridging-fixes` (LNT) | yes | `BOOL_OPTIONS["clear_bridging_fixes"]` |
| `--verbose-dep-check` (LNT) | yes | `BOOL_OPTIONS["verbose_dep_check"]`; the checkbox now defaults to checked (2026-09-16) — this flag only controls the *verbosity of the dependency check's own output* (per gisobuild's own `--help`: "Verbose output for the dependency check"), not whether the check itself runs, which is unconditional. There is no reason to make an operator opt in to more diagnostic detail for a check that always happens anyway. |
| `--buildinfo` (LNT) | hidden upstream | internal; correctly not exposed |
| `--debug` (LNT) | yes | `BOOL_OPTIONS["debug"]` |
| `--isoinfo` (LNT) | **no — deliberately not exposed, security** | lets gisobuild use a caller-specified `isoinfo` *executable* instead of its bundled one. Revisited 2026-09-16: this is meant for a trusted deployer to point at a specific vetted binary already present in the build environment, not a per-build choice for a web operator — accepting an operator-supplied executable path here (or, worse, an uploaded binary) would mean the privileged build process executes something the operator chose, which is a code-execution risk, not a missing convenience. Not implemented, and should not be, in this trust model. |
| `--image-script` (LNT) | hidden upstream | internal; correctly not exposed |
| `--only-support-pids` (LNT) | yes | `LIST_OPTIONS["only_support_pids"]`, but see PID-selection UX gap in `02-AUTOMATION-BUILDPLAN-TODO.md` — currently a free-text field, not a picklist of the ISO's actual supported PIDs |
| `--clear-key-request` (LNT) | yes | `BOOL_OPTIONS["clear_key_request"]` |
| `--ownership-vouchers` (LNT) | yes | `PATH_OPTIONS["ownership_vouchers"]`; warns when supplied without `--ownership-certificate` (2026-09-16, see below) |
| `--clear-ownership-vouchers` (LNT) | yes | `BOOL_OPTIONS["clear_ownership_vouchers"]` |
| `--ownership-certificate` (LNT) | yes | `PATH_OPTIONS["ownership_certificate"]`; warns when supplied without `--ownership-vouchers` |
| `--clear-ownership-certificate` (LNT) | yes | `BOOL_OPTIONS["clear_ownership_certificate"]` |
| `--no-buildinfo` (LNT) | yes | `BOOL_OPTIONS["no_buildinfo"]` |
| `--version` | **fixed 2026-09-16** | `giso-webui` now surfaces the pinned engine's own version/commit via `GET /api/version`, shown in the page header ("Web UI 0.0.1 · Build engine ciscogisobuild/cisco-xr-gisobuild:2.3.4 @ 0388af2"). See "Upstream version detection" below. |

Result: **32 of 34 non-hidden, non-architecturally-excluded upstream options
are exposed.** `--copy-dir` and `--isoinfo` are deliberately not exposed
(no safe arbitrary-write mechanism / operator-supplied-executable
code-execution risk, respectively — see their rows above), not missing by
oversight; `--docker`/`--use-container` is separately excluded as
architecturally incompatible.

### A capability giso-webui cannot currently verify: `--optimize`/`--full-iso` gating

`OPTIMIZE_CAPABLE` in `gisobuild.py` (`pathlib.Path(__file__).resolve().parents[2] / "exr"`)
only registers the `--optimize`/`--full-iso` arguments at all when an `exr/`
directory is present relative to where `gisobuild.py` actually runs. Inside
the real build container, `gisobuild.py` runs from `/tool/src/gisobuild.py`
(the mounted `.gisobuild-tool` checkout), so this resolves to `/exr` at the
*container image's* filesystem root — something that would need to come
from the pinned `ciscogisobuild/cisco-xr-gisobuild:2.3.4` image itself, not
from `.gisobuild-tool`. `giso-webui` has no way to know today whether that
directory exists in the image it is about to run, yet unconditionally
offers `--optimize`/`--full-iso` in the UI whenever the platform capability
map says an eXR platform (or xrv9k) supports them. If the pinned image
lacks `/exr`, the generated command would fail at gisobuild's own
argument-parsing stage with an unrecognized-argument error — not a
security issue, but exactly the "capability the UI shows as available but
isn't" gap `docs/AI-MASTER-PROMPT.md` section 19 warns about. Not fixed
here: verifying this needs either running `gisobuild.py --help` once
against the pinned image and caching which flags it actually registers, or
Cisco documentation confirming `/exr` is always present in the published
`cisco-xr-gisobuild` image — neither was available in this pass.

### Upstream version detection (fixed 2026-09-16)

`giso-webui` used to expose only its own `APP_VERSION`, never the pinned
gisobuild tool's own version or commit. `gisobuild.py --version` prints a
static `"1.0"` string (`__version__` in the pinned checkout, not
per-release), so the meaningful signal is which *commit* of
`.gisobuild-tool` is actually mounted, not that string.

Added `gisobuild_commit()` and `GET /api/version` in `giso-webui/app.py`:
reads `git -C <TOOL> rev-parse --short HEAD` against the mounted
`.gisobuild-tool` checkout, degrading to `null` (never raising) when `TOOL`
isn't a git checkout — version info is diagnostic, never load-bearing.
Required adding a pinned `git` package to `giso-webui/Dockerfile`
(`git=2.54.0-r0`, matching the pinned Alpine base image). Surfaced in the
page header via `loadVersion()` in `giso-webui/static/app.js`.

Verified: `test_version_reports_none_commit_when_tool_is_not_a_git_checkout`
and `test_version_reports_the_real_commit_of_a_git_checkout` (the latter
points `TOOL` at this repository's own mounted checkout and asserts a real
commit hash comes back, proving the happy path, not just graceful failure)
in `giso-webui/tests/test_app.py`; confirmed live against the real
container — `/api/version` returned the actual pinned
`.gisobuild-tool` commit, and the header showed "Web UI 0.0.1 · Build
engine ciscogisobuild/cisco-xr-gisobuild:2.3.4 @ 0388af2" in a browser.

This answers `docs/AI-MASTER-PROMPT.md` section 18's "GISO Build Engine
version" ask directly. Storage usage (section 37/45) is also now answered:
`GET /api/storage` returns free disk space and archive quota usage, shown
as "Archive: X of 50 GiB used · Y GiB free on the upload volume" in the
GISO Archive panel (`loadStorage()` in `giso-webui/static/app.js`),
refreshed on load, after a build completes, after workspace cleanup, and
on manual archive refresh. Verified by
`test_storage_reports_real_disk_and_archive_usage` and
`test_storage_reports_zero_archive_usage_before_any_archive_exists` in
`giso-webui/tests/test_app.py`, and live against the real container.
The fuller section 37 admin/system page (build worker status,
required-binary checks) remains open.

## Representative eXR families

Do not hardcode these as the only supported platforms — see
`test_exr_platform_list_matches_the_pinned_upstream_engine`, which proves
this exact list is not just "present" but *identical* to what the pinned
`.gisobuild-tool`'s own engine actually enforces (`Giso.SUPPORTED_PLATFORMS`).

- [x] ASR 9000 (`asr9k`)
- [x] NCS 1K (`ncs1k`)
- [x] NCS 1001 (`ncs1001`)
- [x] NCS 1004 (`ncs1004`)
- [x] NCS 5K (`ncs5k`)
- [x] NCS 540 (`ncs540`)
- [x] NCS 5500 (`ncs5500`)
- [x] NCS 560 (`ncs560`)
- [x] NCS 6000 (`ncs6k`)
- [x] XRv9K (`xrv9k`)
- [x] IOS XR whitebox variants (`iosxrwb`, `iosxrwbd`)

## LNT

- [x] Detect LNT support from the pinned upstream code — confirmed by direct
      source inspection: LNT has no fixed platform whitelist upstream at
      all (unlike eXR's `SUPPORTED_PLATFORMS`) — `find_platform_object()` in
      `.gisobuild-tool/src/lnt/image.py` determines platform from the ISO's
      own metadata, not a hardcoded list. This app's LNT entries in
      `PLATFORMS` are marketing/capability presentation only, matching that
      upstream reality — there was nothing to "detect" as a list because
      upstream itself does not gate LNT by one.
- [x] Do not assume current local mappings are complete — the `lnt-generic`
      fallback (see "Unknown-but-valid platforms" below) is exactly this:
      an LNT image whose marketing name this app does not recognize can
      still be built, in Manual package list mode, via an explicit generic
      override rather than being blocked because the local LNT map is
      incomplete.
- [x] Ensure Cisco 8000-class and NCS57xx-class images are handled
      generically when upstream supports them — both are named `PLATFORMS`
      entries (`8000`, `ncs57`) with the same generic capability-driven
      model every other platform uses (no `8000`- or `ncs57`-specific
      branching anywhere — confirmed by grep: the only per-platform
      conditionals in the whole codebase are `PLATFORM_CAPABILITY_OVERRIDES`
      for `asr9k`/`xrv9k`'s genuine eXR-only quirks), and an
      NCS57-class image whose exact PID the local `ALIASES` map does not
      yet know (e.g. a future variant) falls through to `lnt-generic`
      rather than being rejected.
- [x] Ensure LNT-only options are capability driven
- [x] Select LNT SMU packages automatically - fixed 2026-09-17. Automatic
      selection assumed eXR filenames (`<platform>-<component>-…-rNNN.CSC….rpm`)
      for every engine, so every real LNT package - upstream's own README
      names them `xr-cdp-24.3.1v1.0.0-1.x86_64.rpm`, with no platform family
      and no CSC ID - was excluded as "Platform is missing from filename",
      leaving an LNT Golden ISO with none of its fixes unless the operator
      went to manual mode. `LNT_RPM`/`lnt_rpm_release()` in
      `platform_validation.py` now parse that naming: for an LNT base image
      a package is selected when its XR release prefix (build suffixes like
      `24.3.1.22I` normalized) equals the ISO's and its processor family
      fits; a platform is only compared when the name actually carries one,
      matching upstream's "include all RPMs, the router installs what suits
      its PIDs". `validate_smu_selection()` blocks an LNT package built for
      another release ("built for IOS XR 24.2.1, not 24.3.1"). eXR behaviour
      is unchanged. Verified with synthetic fixtures only
      (`tests/test_platform_fixtures.py`); no real LNT content was available
      to this work. Not modelled: LNT block grouping (a package's
      PID-specific RPMs) - gisobuild adds whole blocks itself.

## Hardware aliases

Create a data-only alias layer, e.g. `hardware_aliases.yaml` — not literally
built as a separate YAML file, but `ALIASES` in
`giso-webui/platform_validation.py` already *is* exactly this: a flat,
data-only `dict[str, str]` with no branching logic attached to any entry,
which is the substantive requirement ("must not become the source of truth
for software support" — aliases only ever resolve to a `PLATFORMS` key,
never independently grant or deny build support). Splitting it into a
separate file is a packaging preference, not a functional gap, so not done
purely for that reason.

- [x] `NCS-57C3-MODS-SYS` (`ncs-57c3-mods-sys`/`ncs57c3modssys`)
- [x] `NCS-57C3-MOD-SYS` (`ncs-57c3-mod-sys`/`ncs57c3modsys`)
- [x] `NCS57C3` (`ncs57c3`)
- [x] `NCS-57C3` (`ncs-57c3`)
- [ ] other known PID spelling variations — open-ended by nature (this can
      never be "complete", only "extensible"); the alias mechanism itself
      is proven correct (word-boundary matched, not loose substring —
      `test_alias_matching_does_not_produce_false_positives_on_substrings`)
      and adding a new spelling is a one-line dict entry, not a design gap.
- [x] normalize dash/underscore/case safely (verified:
      `normalize_platform()` strips non-`[a-z0-9-]` characters before alias
      lookup, so underscore/dash/case variants of the same SKU already
      collapse to one key)
- [x] avoid loose substring matching (see fix above)

Hardware aliases must **not** become the source of truth for software support.

Fixed: `infer_platform()` in `giso-webui/platform_validation.py` matched
`ALIASES` with a bare substring check (`if alias in name`) while its primary
platform-ID loop just above it used word-boundary matching — an alias such as
`"8800"` could match inside an unrelated numeric run (e.g.
`router-188005-image.iso`). The alias loop now uses the same word-boundary
regex as the primary loop. Verified by
`test_alias_matching_does_not_produce_false_positives_on_substrings` in
`giso-webui/tests/test_platform_compatibility.py`, run inside the built
container image (146/146 tests pass).

## Unknown-but-valid platforms

- [x] If upstream accepts an ISO but local marketing metadata is unknown, do
      not block automatically — fixed 2026-09-16: before this, an ISO/RPM
      set for a real platform gisobuild supports but whose filename
      `infer_platform()` cannot recognize (a genuinely new upstream platform,
      or just an unusually named file) had **no path forward at all** — not
      even a manual override, since `normalize_platform()` rejected any
      value that was not already a literal key in `PLATFORMS`. Added two
      manual-only fallback entries, `exr-generic` and `lnt-generic`
      (`GENERIC_PLATFORM_IDS` in `giso-webui/platform_validation.py`),
      explicitly excluded from `infer_platform()`'s candidate loop (a
      *guessed* generic platform is worthless — the whole point is the
      operator affirmatively saying "I know this is eXR/LNT, I just can't
      name it"), so they only ever come from an explicit Expert-settings
      override. They expose only the common capability set for the chosen
      engine (no `migration`/`full_iso`, which are genuine ASR9k/XRv9K-only
      quirks this profile cannot know apply) and default `usb: False`
      (unknown real support, conservative default, operator can still
      uncheck "Skip USB image" if they know better). This does **not**
      extend to automatic package selection, which still correctly requires
      a recognizable platform to cross-check RPM filenames against — an
      unknown platform must use Manual package list mode; deciding this was
      the right line to hold rather than inventing an unsafe automatic-match
      heuristic for a fundamentally underdetermined case.
      Verified by `test_unknown_upstream_platform_can_still_be_built_via_manual_override`
      and `test_generic_platform_fallbacks_are_never_inferred_from_a_filename`
      in `giso-webui/tests/test_platform_compatibility.py`, and confirmed
      live end-to-end against an isolated throwaway container: uploaded a
      real ISO+RPM named `mystery-platform-*` (a filename `infer_platform()`
      correctly returns `None` for) through the actual upload API, selected
      `exr-generic` with manual package selection, and got
      `POST /api/build-plan` → `"ready": true` — a build that was previously
      impossible to start at all.
- [x] Show upstream identifier — confirmed live for the generic-platform
      case: `POST /api/build-plan` with `platform: "exr-generic"` returns
      `"platform": "exr-generic"` directly (the real `normalize_platform()`
      result, not a translated label), rendered uppercased in the Step 2/
      build-report flow row exactly as any named platform's `id` is.
- [x] Show engine — same response, `"engine": "exr"`; rendered in the same
      flow row.
- [x] Show release — same response, `"release": "30.1.1"` (from a synthetic
      `mystery-30.1.1.iso` test upload) — release detection reads the ISO
      filename independently of platform recognition, so it is unaffected
      by the platform being unknown/generic.
- [x] Show marketing name as unknown — the generic fallback's own label
      ("Other eXR platform (manual override)") already communicates this;
      no separate marketing-name field needed for the fallback case itself.
- [x] Preserve an explicit confidence/source field — fixed 2026-09-16:
      `confidence_report()`'s platform entry previously reported
      `value: "INFERRED"` even when the operator picked
      `exr-generic`/`lnt-generic`, reading as a filename guess rather than
      "operator declared this is a generic engine profile, real platform
      unverified." Added a genuine third tier, `MANUAL`, returned only when
      `resolved_platform in GENERIC_PLATFORM_IDS`; `source: "operator-selected"`
      was already correct and unchanged. Added the matching
      `.confidence-badge.manual` CSS rule (blue, distinct from
      verified/inferred/unknown's green/amber/gray) and extended the
      confidence-note explanation text. Separately found and fixed while
      verifying this: `renderBuildReport()` (the permanent Step 3 record of
      a completed build) never rendered `plan.confidence` at all, even
      though `create_build_plan()` has always computed it and Step 2's live
      review already shows the same data via the same `confidenceGrid()`
      helper — the one place an operator could look back at *how sure* the
      system was about a build's platform/release/architecture (including
      this new MANUAL case) after the fact showed nothing. Now rendered
      there too. Verified by
      `test_build_plan_confidence_marks_generic_platform_fallback_as_manual`
      in `giso-webui/tests/test_app.py` and
      `test_build_report_shows_the_confidence_grid` in
      `giso-webui/tests/test_build_script.py`; confirmed live by invoking
      the real `renderBuildReport()` in a browser with a build plan carrying
      a MANUAL platform confidence entry and reading back the rendered
      badge's class (`confidence-badge manual`), text and tooltip.

## Capability-driven UI

Replace logic like:

```python
if platform == "ncs5500":
    ...
```

with:

```python
if capabilities.optimize:
    ...
```

- [x] common options
- [x] eXR-only options
- [x] LNT-only options
- [x] unsupported options hidden/disabled
- [x] adapter rejects unsupported combinations server-side

## Required capability model

- [x] `repo`
- [x] `pkglist`
- [x] `xrconfig`
- [x] `ztp`
- [x] `usb_image`
- [x] `migration`
- [x] `optimize`
- [x] `x86_only`
- [x] `full_iso`
- [x] `remove_packages`
- [x] `only_support_pids`
- [x] `verbose_dependency_check`
- [x] `clear_bridging_fixes`
- [x] `key_request`
- [x] `ownership_vouchers`
- [x] `ownership_certificate`

## Tests

- [x] generic eXR workflow — `test_build_recalculates_automatic_smu_selection_server_side`
      in `giso-webui/tests/test_app.py` exercises the full
      discover-through-`build_command()` pipeline (automatic selection,
      wrong-release exclusion, real generated command) for an eXR platform
      (`ncs5500`).
- [x] generic LNT workflow — added 2026-09-16:
      `test_build_recalculates_automatic_smu_selection_server_side_for_lnt_platforms`,
      the same pipeline for an LNT platform (`ncs57`/`ncs5700`-named files) —
      previously LNT's only `build_command()` coverage was narrower
      option-passthrough checks (`--verbose-dep-check`, ownership fields),
      not automatic-selection recalculation through the real command.
- [x] eXR-only option rejection on LNT — added 2026-09-16
      (`test_adapter_rejects_exr_only_capability_on_lnt_platform`); until
      then only the reverse direction had a test.
- [x] LNT-only option rejection on eXR (`test_adapter_rejects_capability_not_supported_by_engine`)
- [x] unknown/future upstream-supported platform — see "Unknown-but-valid
      platforms" above (`test_unknown_upstream_platform_can_still_be_built_via_manual_override`).
      Covers "the operator manually declares an unrecognized platform and
      still gets a valid, buildable profile"; does not cover "a future
      pinned-commit bump adds a genuinely new upstream eXR platform to
      `SUPPORTED_PLATFORMS`" being picked up automatically — that is the
      still-open "Stop using a locally maintained list" item above, which
      `test_exr_platform_list_matches_the_pinned_upstream_engine` now at
      least fails loudly on instead of silently drifting.
- [x] NCS-57C3 alias normalization (`test_ncs57c3_filename_is_inferred_as_ncs57`,
      `test_ncs57c3_inventory_sku_normalizes_to_ncs57`, both pre-existing and
      passing)
- [x] no false-positive alias matching
      (`test_alias_matching_does_not_produce_false_positives_on_substrings`)

## Implemented capability slice

The API now returns an engine and explicit capability map for every known UI
profile. The map mirrors the upstream eXR/LNT CLI maps and adds only narrow
per-platform exceptions for ASR 9000 migration and XRv9K full ISO. It drives
both browser visibility and server-side rejection. Runtime pinning and dynamic
discovery from the bundled upstream checkout remain open because the current
deployment still supplies gisobuild through an external mount.
