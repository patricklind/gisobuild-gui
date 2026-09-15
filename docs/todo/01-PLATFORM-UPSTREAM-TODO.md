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

- [ ] Inspect pinned `ios-xr/gisobuild`
- [x] Read `src/utils/gisoglobals.py`
- [x] Read eXR-specific code
- [x] Read LNT-specific code
- [x] Detect supported CLI options from upstream
- [x] Build a `GisoBuildCapabilities` abstraction
- [ ] Stop using a locally maintained list as the authoritative support list

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
- [ ] eXR-only option rejection on LNT
- [ ] LNT-only option rejection on eXR
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
