# TODO — Upstream Platform & Capability Support

## Scope

Support **everything that the pinned upstream `ios-xr/gisobuild` revision supports**.

The application must distinguish:

- [ ] Physical PID / SKU
- [ ] Marketing family
- [ ] Upstream gisobuild platform identifier
- [x] Build engine (`eXR` / `LNT`)
- [ ] IOS XR release
- [ ] CPU architecture
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
| `--copy-dir` (LNT) | **no — genuine gap** | copies built artifacts to an operator-chosen directory. giso-webui's own archive step (`archive_giso_artifacts_and_cleanup()`) already serves this need for a normal workflow, so this is low priority, but it is a real missing pass-through, not an intentional omission. |
| `--clear-bridging-fixes` (LNT) | yes | `BOOL_OPTIONS["clear_bridging_fixes"]` |
| `--verbose-dep-check` (LNT) | yes | `BOOL_OPTIONS["verbose_dep_check"]` |
| `--buildinfo` (LNT) | hidden upstream | internal; correctly not exposed |
| `--debug` (LNT) | yes | `BOOL_OPTIONS["debug"]` |
| `--isoinfo` (LNT) | **no — genuine gap** | lets the operator point gisobuild at a different `isoinfo` binary. Niche (giso-webui already bundles its own pinned `isoinfo` via `cdrkit` for its *own* inspection use, a separate concern from what gisobuild uses internally), but a real missing pass-through. |
| `--image-script` (LNT) | hidden upstream | internal; correctly not exposed |
| `--only-support-pids` (LNT) | yes | `LIST_OPTIONS["only_support_pids"]`, but see PID-selection UX gap in `02-AUTOMATION-BUILDPLAN-TODO.md` — currently a free-text field, not a picklist of the ISO's actual supported PIDs |
| `--clear-key-request` (LNT) | yes | `BOOL_OPTIONS["clear_key_request"]` |
| `--ownership-vouchers` (LNT) | yes | `PATH_OPTIONS["ownership_vouchers"]` |
| `--clear-ownership-vouchers` (LNT) | yes | `BOOL_OPTIONS["clear_ownership_vouchers"]` |
| `--ownership-certificate` (LNT) | yes | `PATH_OPTIONS["ownership_certificate"]` |
| `--clear-ownership-certificate` (LNT) | yes | `BOOL_OPTIONS["clear_ownership_certificate"]` |
| `--no-buildinfo` (LNT) | yes | `BOOL_OPTIONS["no_buildinfo"]` |
| `--version` | **no — genuine gap** | prints gisobuild's own version/commit; giso-webui only ever surfaces its *own* `APP_VERSION`, never the pinned tool's. See "Upstream version detection" below. |

Result: **31 of 34 non-hidden, non-architecturally-excluded upstream options
are exposed** (`--copy-dir`, `--isoinfo`, `--version`/version-surfacing are
the real gaps; `--docker`/`--use-container` is deliberately excluded, not
missing).

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

### Upstream version detection (not implemented)

`giso-webui` exposes its own `APP_VERSION` (`giso-webui/app.py`) but never
the pinned gisobuild tool's own version or commit. `gisobuild.py --version`
prints a static `"1.0"` string today (`__version__` in the pinned checkout)
with no git commit info exposed by the script itself; the commit actually
in use would have to come from the `.gisobuild-tool` checkout's own git
metadata (not currently read by `giso-webui` at all) or from labeling on
the pinned `IMAGE` tag. See `docs/AI-MASTER-PROMPT.md` section 18/37 for the
"GISO Build Engine version" and admin/system-page asks this would feed.

## Representative eXR families

Do not hardcode these as the only supported platforms.

- [ ] ASR 9000
- [ ] NCS 1K
- [ ] NCS 1001
- [ ] NCS 1004
- [ ] NCS 5K
- [ ] NCS 540
- [ ] NCS 5500
- [ ] NCS 560
- [ ] NCS 6000
- [ ] XRv9K
- [ ] IOS XR whitebox variants

## LNT

- [ ] Detect LNT support from the pinned upstream code
- [ ] Do not assume current local mappings are complete
- [ ] Ensure Cisco 8000-class and NCS57xx-class images are handled generically when upstream supports them
- [x] Ensure LNT-only options are capability driven

## Hardware aliases

Create a data-only alias layer, e.g. `hardware_aliases.yaml`.

- [ ] `NCS-57C3-MODS-SYS`
- [ ] `NCS-57C3-MOD-SYS`
- [ ] `NCS57C3`
- [ ] `NCS-57C3`
- [ ] other known PID spelling variations
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

- [ ] If upstream accepts an ISO but local marketing metadata is unknown, do not block automatically
- [ ] Show upstream identifier
- [ ] Show engine
- [ ] Show release
- [ ] Show marketing name as unknown
- [ ] Preserve an explicit confidence/source field

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

- [ ] generic eXR workflow
- [ ] generic LNT workflow
- [x] eXR-only option rejection on LNT — added 2026-09-16
      (`test_adapter_rejects_exr_only_capability_on_lnt_platform`); until
      then only the reverse direction had a test.
- [x] LNT-only option rejection on eXR (`test_adapter_rejects_capability_not_supported_by_engine`)
- [ ] unknown/future upstream-supported platform
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
