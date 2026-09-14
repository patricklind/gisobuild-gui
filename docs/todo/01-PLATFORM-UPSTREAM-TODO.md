# TODO — Upstream Platform & Capability Support

## Scope

Support **everything that the pinned upstream `ios-xr/gisobuild` revision supports**.

The application must distinguish:

- [ ] Physical PID / SKU
- [ ] Marketing family
- [ ] Upstream gisobuild platform identifier
- [ ] Build engine (`eXR` / `LNT`)
- [ ] IOS XR release
- [ ] CPU architecture
- [ ] Feature/capability support

## Upstream-first model

- [ ] Inspect pinned `ios-xr/gisobuild`
- [ ] Read `src/utils/gisoglobals.py`
- [ ] Read eXR-specific code
- [ ] Read LNT-specific code
- [ ] Detect supported CLI options from upstream
- [ ] Build a `GisoBuildCapabilities` abstraction
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
- [ ] Ensure LNT-only options are capability driven

## Hardware aliases

Create a data-only alias layer, e.g. `hardware_aliases.yaml`.

- [ ] `NCS-57C3-MODS-SYS`
- [ ] `NCS-57C3-MOD-SYS`
- [ ] `NCS57C3`
- [ ] `NCS-57C3`
- [ ] other known PID spelling variations
- [ ] normalize dash/underscore/case safely
- [ ] avoid loose substring matching

Hardware aliases must **not** become the source of truth for software support.

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

- [ ] common options
- [ ] eXR-only options
- [ ] LNT-only options
- [ ] unsupported options hidden/disabled
- [ ] adapter rejects unsupported combinations server-side

## Required capability model

- [ ] `repo`
- [ ] `pkglist`
- [ ] `xrconfig`
- [ ] `ztp`
- [ ] `usb_image`
- [ ] `migration`
- [ ] `optimize`
- [ ] `x86_only`
- [ ] `full_iso`
- [ ] `remove_packages`
- [ ] `only_support_pids`
- [ ] `verbose_dependency_check`
- [ ] `clear_bridging_fixes`
- [ ] `key_request`
- [ ] `ownership_vouchers`
- [ ] `ownership_certificate`

## Tests

- [ ] generic eXR workflow
- [ ] generic LNT workflow
- [ ] eXR-only option rejection on LNT
- [ ] LNT-only option rejection on eXR
- [ ] unknown/future upstream-supported platform
- [ ] NCS-57C3 alias normalization
- [ ] no false-positive alias matching
