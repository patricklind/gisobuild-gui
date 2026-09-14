# Platform support and validation

The Web UI performs an early family-level check before invoking Cisco's
`gisobuild` tool. This prevents obvious eXR/LNT option mismatches. It does not
replace the tool's ISO metadata, signature, dependency, or PID validation.

## Platform matrix

| Selection | Product family | Architecture | Automatic USB expected |
| --- | --- | --- | --- |
| `asr9k` | ASR 9000 | eXR | Yes |
| `ncs1k` | NCS 1000 | eXR | Yes |
| `ncs1001` | NCS 1001 | eXR | Yes |
| `ncs1004` | NCS 1004 | eXR | Yes |
| `ncs5k` | NCS 5000 | eXR | No |
| `ncs540` | NCS 540 eXR images | eXR | Yes |
| `ncs5500` | NCS 5500 | eXR | Yes |
| `ncs560` | NCS 560 | eXR | Yes |
| `ncs6k` | NCS 6000 | eXR | No |
| `iosxrwb` | IOS XR whitebox | eXR | No |
| `iosxrwbd` | IOS XR whitebox distributed | eXR | Yes |
| `xrv9k` | IOS XRv 9000 | eXR | No |
| `8000` | Cisco 8000/8800 | IOS XR7/LNT | Yes |
| `ncs1010` | NCS 1010/1014 | IOS XR7/LNT | Yes |
| `ncs540l` | NCS 540L XR7 images | IOS XR7/LNT | Yes |
| `ncs57` | NCS 5700 | IOS XR7/LNT | Yes |

“Automatic USB expected” reflects the upstream build path, not a guarantee that
every release, route processor, or boot mode supports that artifact. Confirm the
result in the build log and the platform recovery guide.

## Option rules

- `--migration` is accepted only for ASR 9000 eXR images.
- `--full-iso` is accepted only for IOS XRv 9000.
- `--x86-only`, `--optimize`, and boot scripts are eXR options.
- package removal, PID filtering, bridging-fix clearing, and verbose dependency
  controls are IOS XR7/LNT options.
- An unrecognized filename requires an explicit platform selection.

## SMU compatibility checks

Automatic selection includes only RPM filenames that identify the same platform
and IOS XR release as the base ISO. The validator also rejects mixed processor
architectures and multiple versions of the same component and CSC. RPMs sharing
a CSC identifier are displayed as a package group, while overlapping CSC fixes
for one component are flagged for supersedence review.

These are deterministic pre-checks. They cannot prove dependency closure,
supersedence, signature validity, or PID support. Cisco `gisobuild`, ISO metadata,
and an approved Cisco package list remain authoritative.

When using PID filtering, inspect the input ISO with upstream
`isols.py --dump-mdata`. Removing PID support is one-way and can make a system
unbootable if required route processors or line cards are omitted.

## Source of truth

The eXR identifiers follow the checked-out `ios-xr/gisobuild` source. IOS XR7
support is metadata-driven upstream, so the UI groups current public product
families for early validation. Keep this table and
`giso-webui/platform_validation.py` synchronized in the same change.
