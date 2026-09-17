# Platform support and validation

The Web UI performs an early family-level check before invoking Cisco's
`gisobuild` tool. This prevents obvious eXR/LNT option mismatches. It does not
replace the tool's ISO metadata, signature, dependency, or PID validation.

## Platform matrix

| Selection | Product family | Architecture | Automatic USB expected |
| --- | --- | --- | --- |
| `asr9k` | ASR 9000 | eXR | Yes |
| `ncs1k` | NCS 1000 | eXR | Yes |
| `ncs1001` | NCS 1001 | eXR | No |
| `ncs1004` | NCS 1004 | eXR | Yes |
| `ncs5k` | NCS 5000 | eXR | No |
| `ncs540` | NCS 540 eXR images | eXR | Yes |
| `ncs5500` | NCS 5500 | eXR | Yes |
| `ncs560` | NCS 560 | eXR | Yes |
| `ncs6k` | NCS 6000 | eXR | No |
| `iosxrwb` | IOS XR whitebox | eXR | No |
| `iosxrwbd` | IOS XR whitebox distributed | eXR | Yes |
| `xrv9k` | IOS XRv 9000 | eXR | No |
| `exr-generic` | Other eXR platform (manual override) | eXR | Not assumed |
| `lnt-generic` | Other LNT platform (manual override) | IOS XR7/LNT | Not assumed |
| `8000` | Cisco 8000/8800 | IOS XR7/LNT | Yes |
| `ncs1010` | NCS 1010/1014 | IOS XR7/LNT | Yes |
| `ncs540l` | NCS 540L XR7 images | IOS XR7/LNT | Yes |
| `ncs57` | NCS 5700 | IOS XR7/LNT | Yes |

For eXR, “Automatic USB expected” follows upstream's
`src/exrmod/usb_zip/platform_scripts.yaml`; for LNT it follows upstream's LNT
engine. It reflects the upstream build path, not a guarantee that
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

Automatic selection includes RPMs for the same platform and IOS XR release as
the base ISO. For eXR the platform and release come from the image's own
`iosxr_image_mdata.yml`; LNT images are still identified by filename, and LNT
packages are matched by upstream's naming (`xr-cdp-24.3.1v1.0.0-1.x86_64.rpm`).
Each RPM's own header (name, version, release, architecture, requires,
provides, signature key ID) is read, and each Cisco SMU README's package list,
MD5s and prerequisites are used when present.

Automatic selection leaves out, with a reason, anything proven unable to
install: a different platform, release or processor architecture, a renamed or
unreadable RPM, a fix whose README shows it incomplete or altered, and a
package whose exact-version dependency nothing in the base image or selection
provides. The rest of that fix is left out with it, and the reason names the
Cisco SMU to download. Manual selection is never edited: the same problems
block the build instead. Multiple versions of one component and CSC are
rejected; RPMs sharing a CSC identifier are displayed as one package group, and
overlapping CSC fixes for one component are flagged for supersedence review.

Every package left out is reported with a status code (`WRONG_PLATFORM`,
`WRONG_RELEASE`, `WRONG_ARCHITECTURE`, `CONFLICT`, `SUPERSEDED`,
`MISSING_DEPENDENCY`, `DUPLICATE`, `INVALID`, `UNKNOWN`, or
`MANUAL_REVIEW_REQUIRED`), the reason in plain words, the platform, release,
architecture and CSC its filename carries, and which check decided it. The API
also returns the counts behind those statuses, and the page shows them.

These are pre-checks. Dependency closure is checked only for exact-version
requirements, signatures are read but not verified, and supersedence order and
PID support are not decided here. Cisco `gisobuild` performs the full
dependency, supersedence and signature validation and remains authoritative,
together with the ISO metadata and an approved Cisco package list.

When using PID filtering, inspect the input ISO with upstream
`isols.py --dump-mdata`. Removing PID support is one-way and can make a system
unbootable if required route processors or line cards are omitted.

## Source of truth

The eXR identifiers and USB flags follow the pinned `ios-xr/gisobuild` source;
`giso-webui/tests/test_platform_compatibility.py` fails if they drift, and CI runs
it against the gisobuild bundled in the self-contained image. IOS XR7
support is metadata-driven upstream, so the UI groups current public product
families for early validation. Keep this table and
`giso-webui/platform_validation.py` synchronized in the same change.
