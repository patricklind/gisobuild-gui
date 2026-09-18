"""Platform-aware validation for Cisco IOS XR GISO build options."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

# eXR identifiers are synchronized with ios-xr/gisobuild's
# src/utils/gisoglobals.py. LNT uses metadata-driven validation upstream, so
# its public product families are represented explicitly here for UI checks.
COMMON_CAPABILITIES = {
    "repo",
    "pkglist",
    "xrconfig",
    "ztp",
    "create_checksum",
    "label",
    "no_label",
    "debug",
}
EXR_CAPABILITIES = COMMON_CAPABILITIES | {
    "script",
    "optimize",
    "x86_only",
    "bridging_fixes",
}
# skip_usb_image is LNT-only: upstream's EXR_CLI_DICT_MAP maps it to None and
# the eXR engine builds a USB zip on its own whenever the platform has a USB
# script (src/exrmod/usb_zip/platform_scripts.yaml), skipping it otherwise.
LNT_CAPABILITIES = COMMON_CAPABILITIES | {
    "skip_usb_image",
    "remove_packages",
    "only_support_pids",
    "verbose_dependency_check",
    "bridging_fixes",
    "clear_bridging_fixes",
    "ownership_vouchers",
    "ownership_certificate",
    "clear_ownership_vouchers",
    "clear_ownership_certificate",
    "key_request",
    "clear_key_request",
    "no_buildinfo",
}

# The eXR identifiers and engine option sets come from the pinned upstream
# src/utils/gisoglobals.py maps. Marketing aliases below aid presentation only;
# upstream ISO inspection remains authoritative for actual build support.
PLATFORMS = {
    "asr9k": {"label": "ASR 9000", "architecture": "exr", "usb": True},
    "ncs1k": {"label": "NCS 1000", "architecture": "exr", "usb": True},
    # No USB script upstream for ncs1001 (src/exrmod/usb_zip/platform_scripts.yaml).
    "ncs1001": {"label": "NCS 1001", "architecture": "exr", "usb": False},
    "ncs1004": {"label": "NCS 1004", "architecture": "exr", "usb": True},
    "ncs5k": {"label": "NCS 5000", "architecture": "exr", "usb": False},
    "ncs540": {"label": "NCS 540 (eXR)", "architecture": "exr", "usb": True},
    "ncs5500": {"label": "NCS 5500", "architecture": "exr", "usb": True},
    "ncs560": {"label": "NCS 560", "architecture": "exr", "usb": True},
    "ncs6k": {"label": "NCS 6000", "architecture": "exr", "usb": False},
    "iosxrwb": {"label": "IOS XR Whitebox", "architecture": "exr", "usb": False},
    "iosxrwbd": {
        "label": "IOS XR Whitebox Distributed",
        "architecture": "exr",
        "usb": True,
    },
    "xrv9k": {"label": "IOS XRv 9000", "architecture": "exr", "usb": False},
    "8000": {"label": "Cisco 8000 / 8800", "architecture": "lnt", "usb": True},
    "ncs1010": {"label": "NCS 1010/1014", "architecture": "lnt", "usb": True},
    "ncs540l": {"label": "NCS 540L (XR7)", "architecture": "lnt", "usb": True},
    "ncs57": {"label": "NCS 5700 / NCS 57C3", "architecture": "lnt", "usb": True},
    # Manual-only fallbacks so an upstream-supported platform this local
    # marketing map does not yet know by name never dead-ends the operator -
    # see 01-PLATFORM-UPSTREAM-TODO.md "Unknown-but-valid platforms". Only
    # selectable by explicit operator override in Expert settings, never
    # inferred from a filename (GENERIC_PLATFORM_IDS below excludes them from
    # infer_platform()'s candidate loop). USB defaults to unsupported (the
    # conservative default) since the real platform's capabilities are
    # unknown here; the operator can still uncheck "Skip USB image" if they
    # know the real platform supports it. Exposes only the common capability
    # set for the chosen engine - no migration/full_iso/other named-platform
    # quirks, which are genuine Cisco/GISO-specific differences this profile
    # cannot know apply.
    "exr-generic": {
        "label": "Other eXR platform (manual override)",
        "architecture": "exr",
        "usb": False,
    },
    "lnt-generic": {
        "label": "Other LNT platform (manual override)",
        "architecture": "lnt",
        "usb": False,
    },
}

GENERIC_PLATFORM_IDS = frozenset({"exr-generic", "lnt-generic"})

PLATFORM_CAPABILITY_OVERRIDES = {
    "asr9k": {"migration"},
    "xrv9k": {"full_iso"},
}


@dataclass(frozen=True)
class GisoBuildCapabilities:
    """Immutable option set shared by the API, UI and build adapter."""

    supported: frozenset[str]

    def supports(self, capability: str) -> bool:
        return capability in self.supported

    def as_dict(self, known: set[str]) -> dict[str, bool]:
        return {name: self.supports(name) for name in sorted(known)}


ALIASES = {
    "asr9000": "asr9k",
    "asr9k-x64": "asr9k",
    "ncs5000": "ncs5k",
    "ncs6000": "ncs6k",
    "ncs5700": "ncs57",
    "cisco8000": "8000",
    "8800": "8000",
    "8200": "8000",
    # NCS 57C3 hardware SKU spellings seen in Cisco inventory and image metadata.
    # Keep both MODS-SYS and MOD-SYS variants so manual selection and filename
    # inference normalize to the NCS 5700/LNT family rather than failing closed.
    "ncs-57c3-mods-sys": "ncs57",
    "ncs57c3modssys": "ncs57",
    "ncs-57c3-mod-sys": "ncs57",
    "ncs57c3modsys": "ncs57",
    "ncs-57c3": "ncs57",
    "ncs57c3": "ncs57",
}

RPM_RELEASE = re.compile(r"-r(?P<release>\d{3,6})(?:\.|-)", re.IGNORECASE)
ISO_RELEASE = re.compile(r"-(?P<release>\d+\.\d+\.\d+)(?:[-.]|$)", re.IGNORECASE)
RPM_COMPONENT = re.compile(
    r"^(?P<component>[a-z0-9_-]+?)-(?P<version>\d[^/]*?)-r\d{3,6}\.CSC(?P<bug>[a-z0-9]+)",
    re.IGNORECASE,
)
# LNT (IOS XR7) package naming, as documented by upstream gisobuild's README
# ("Specifying LNT bugfixes and packages"): <package>-<XR release>v<package
# version>-<rpm release>.<arch>.rpm, e.g. xr-cdp-24.3.1v1.0.0-1.x86_64.rpm or
# the PID-specific xr-cdp-8101-32h-24.3.1v1.0.0-1.x86_64.rpm. The XR release
# may carry an engineering suffix (xr-telnet-24.3.1.22Iv1.0.0-1). Unlike eXR,
# the name carries neither the platform family nor a CSC ID.
LNT_RPM = re.compile(
    r"^(?P<package>[a-z0-9][a-z0-9_.+-]*?)-(?P<xr>\d+\.\d+\.\d+(?:\.[0-9A-Za-z]+)?)"
    r"v(?P<version>\d[0-9A-Za-z.]*)-(?P<release>[0-9A-Za-z.]+)"
    r"\.(?P<architecture>x86_64|aarch64|arm64|noarch)\.rpm$",
    re.IGNORECASE,
)


def lnt_rpm_release(filename: str) -> str | None:
    """The IOS XR release an LNT RPM filename was built for, without any build suffix."""
    match = LNT_RPM.match(Path(filename).name)
    if not match:
        return None
    return ".".join(match.group("xr").split(".")[:3])


def is_lnt_platform(platform: str | None) -> bool:
    return bool(platform) and PLATFORMS.get(platform, {}).get("architecture") == "lnt"


RPM_ARCHITECTURE = re.compile(
    r"\.(?P<architecture>x86_64|aarch64|arm64|corei7_64)\.rpm$", re.IGNORECASE
)

# eXR RPMs identify the processor family the same way upstream does in
# src/exrmod/gisobuild_exr_engine.py (x86_64 vs "arm", the latter also seen as
# "corei7_64" in the x86_64 family and various variant tokens in the arm
# family). LNT RPMs use the plain x86_64/aarch64/arm64 rpm suffix. Normalize
# both through one resolver so a mismatch is detected regardless of which
# naming scheme produced the token, mirroring how normalize_platform() is the
# single resolver for platform aliases.
ARCH_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "corei7_64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
    "arm": "aarch64",
}


def normalize_architecture(token: str) -> str | None:
    """Return the canonical processor family for a filename/metadata token."""
    return ARCH_ALIASES.get(token.strip().lower()) if token else None


def capabilities_for_platform(platform: str) -> dict[str, bool]:
    """Return the UI/adapter capabilities for one normalized platform."""
    normalized = normalize_platform(platform)
    profile = PLATFORMS[normalized]
    supported = set(
        LNT_CAPABILITIES if profile["architecture"] == "lnt" else EXR_CAPABILITIES
    )
    supported.update(PLATFORM_CAPABILITY_OVERRIDES.get(normalized, set()))
    if profile["usb"]:
        supported.add("usb_image")
    known = (
        COMMON_CAPABILITIES
        | EXR_CAPABILITIES
        | LNT_CAPABILITIES
        | {
            "usb_image",
            "migration",
            "full_iso",
        }
    )
    return GisoBuildCapabilities(frozenset(supported)).as_dict(known)


def platform_profile(platform: str) -> dict:
    normalized = normalize_platform(platform)
    profile = {"id": normalized, **PLATFORMS[normalized]}
    profile["engine"] = profile["architecture"]
    profile["capabilities"] = capabilities_for_platform(normalized)
    profile["source"] = "upstream-cli-map-and-local-aliases"
    profile["confidence"] = "INFERRED"
    return profile


def normalize_platform(value: str) -> str:
    key = re.sub(r"[^a-z0-9-]", "", value.lower())
    key = ALIASES.get(key, key)
    if key not in PLATFORMS:
        raise ValueError(f"Unsupported platform family: {value}")
    return key


def infer_platform(filename: str) -> str | None:
    name = filename.lower()
    candidates = sorted(PLATFORMS.keys() - GENERIC_PLATFORM_IDS, key=len, reverse=True)
    for platform in candidates:
        if re.search(rf"(^|[^a-z0-9]){re.escape(platform)}([^a-z0-9]|$)", name):
            return platform
    # Word-boundary matched, same as the loop above: a bare substring check
    # here would let an alias like "8800" match inside an unrelated numeric
    # run (for example "router-188005-image.iso").
    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(rf"(^|[^a-z0-9]){re.escape(alias)}([^a-z0-9]|$)", name):
            return ALIASES[alias]
    return None


def infer_platform_pid(filename: str) -> str | None:
    """Return the exact hardware PID/SKU spelling matched from ALIASES, if any.

    Distinct from infer_platform(): that resolves straight to the marketing
    family (e.g. "ncs57"); this preserves which literal alias token was
    actually recognized in the filename, so "we matched your exact
    NCS-57C3-MOD-SYS" can be shown separately from "we guessed NCS 5700
    family". Honest limitation: ALIASES also holds alternate marketing
    digit-spellings that are not distinct physical SKUs at all (e.g.
    "asr9000"/"8800" are just other ways of writing the same family, not a
    different piece of hardware) - this returns whatever token matched,
    without trying to separate "genuine PID" from "family nickname" within
    ALIASES, since that distinction is not tracked anywhere upstream either.
    """
    name = filename.lower()
    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(rf"(^|[^a-z0-9]){re.escape(alias)}([^a-z0-9]|$)", name):
            return alias
    return None


def _bundle_files_by_csc(
    packages: list[str], iso_platform: str | None, expected_tag: str
) -> dict[str, set[str]]:
    """Map each CSC bug ID to every candidate filename belonging to it.

    Mirrors validate_smu_selection()'s own per-package platform/release
    matching so "full bundle size" and "selected bundle size" are computed
    the same way - a candidate whose platform or release does not match the
    base ISO was never part of this bundle to begin with.
    """
    bundles: dict[str, set[str]] = {}
    for package in packages:
        name = Path(package).name
        package_platform = infer_platform(name)
        if iso_platform and package_platform and package_platform != iso_platform:
            continue
        rpm_release = RPM_RELEASE.search(name)
        if expected_tag and (
            not rpm_release or rpm_release.group("release") != expected_tag
        ):
            continue
        component = RPM_COMPONENT.search(name)
        if component:
            bug = f"CSC{component.group('bug')}".upper()
            bundles.setdefault(bug, set()).add(name)
    return bundles


# Ported, not reimplemented, from upstream gisobuild's own eXR supersedence
# decision, so a decision this app makes agrees with what the eXR engine
# actually builds (see docs/todo/02-AUTOMATION-BUILDPLAN-TODO.md "SMUs that
# are incompatible with the rest of the selection"). Source: `_subfield_pattern`
# / `_iter_rpm_subfields()` / `_compare_rpm_field()` / `_compare_rpm_labels()`
# in `src/exrmod/gisobuild_exr_engine.py` (BSD-3-Clause, Copyright (c)
# 2021-2025 Cisco Systems, Inc. and its affiliates), pinned commit
# 0388af2989bb7022d780a8732dbfbfeb77a70ee7. Deliberately NOT full rpmvercmp -
# no tilde/caret pre/post-release weighting, and more subfields always beats
# fewer regardless of what they are (so e.g. "1.0~rc1" sorts *above* "1.0",
# the opposite of real rpmvercmp) - matching upstream exactly means matching
# its quirks too. See ExrRpmLabelCompareTests in test_platform_compatibility.py
# for a test that runs the pinned upstream source itself and fails loudly if
# a future commit bump changes this algorithm.
_EXR_SUBFIELD = re.compile(r"[^a-zA-Z0-9]*(?:(?P<text>[a-zA-Z]+)|(?P<num>[0-9]+))")


def _exr_rpm_subfields(field: str) -> list[tuple[int, object]]:
    subfields: list[tuple[int, object]] = []
    for match in _EXR_SUBFIELD.finditer(field):
        text = match.group("text")
        subfields.append(
            (0, text) if text is not None else (1, int(match.group("num")))
        )
    return subfields


def _compare_exr_rpm_field(lhs: str, rhs: str) -> int:
    if lhs == rhs:
        return 0
    lhs_subfields = _exr_rpm_subfields(lhs)
    rhs_subfields = _exr_rpm_subfields(rhs)
    for lhs_sf, rhs_sf in zip_longest(lhs_subfields, rhs_subfields):
        if lhs_sf == rhs_sf:
            continue
        if lhs_sf is None:
            return -1
        if rhs_sf is None:
            return 1
        return -1 if lhs_sf < rhs_sf else 1
    return 0


def compare_exr_rpm_labels(lhs: tuple[str, str], rhs: tuple[str, str]) -> int:
    """Compare two eXR RPMs' (version, release), the way gisobuild's own
    filter_superseded_rpms() does, to predict which one it would keep.

    Epoch is left out: upstream's own call site always passes literal 0 for
    both sides, which short-circuits _compare_rpm_field's exact-match branch
    before it would ever really compare an epoch - so epoch plays no role in
    the real decision either.

    Returns 1 if lhs > rhs (lhs is what gisobuild would keep), -1 if
    lhs < rhs, 0 if equal.
    """
    lhs_version, lhs_release = lhs
    rhs_version, rhs_release = rhs
    result = _compare_exr_rpm_field(lhs_version, rhs_version)
    if result:
        return result
    return _compare_exr_rpm_field(lhs_release, rhs_release)


def validate_smu_selection(
    iso: str,
    packages: list[str],
    iso_architectures: frozenset[str] | None = None,
    full_candidate_packages: list[str] | None = None,
) -> dict:
    """Check deterministic filename compatibility before upstream dependency resolution.

    ``iso_architectures`` is the set of canonical processor families detected
    directly from the base ISO's own contents (see ``inspect_iso_architecture``
    in app.py); pass None or an empty set when detection was not run or was
    inconclusive so an upstream-valid image is never blocked on that basis
    alone.

    ``full_candidate_packages`` is the complete uploaded RPM inventory (not
    just what is selected) - pass it (from active_rpm_names(), matching what
    automatic selection itself considers) whenever the operator can select
    RPMs individually, e.g. Manual package list mode. Automatic selection
    can never produce a partial multi-component bundle on its own (it
    includes every matching file for a bug or none), but a manual pick can,
    e.g. two of a three-RPM "keep these together" fix - a real, silent
    "will fail" case (or at best get a materially different, unintended
    Golden ISO) this cannot detect without knowing what the full bundle was
    supposed to contain. Without this argument, that case is invisible.
    """
    iso_name = Path(iso).name
    release_match = ISO_RELEASE.search(iso_name)
    iso_release = release_match.group("release") if release_match else ""
    expected_tag = iso_release.replace(".", "") if iso_release else ""
    iso_platform = infer_platform(iso_name)
    issues: list[str] = []
    warnings: list[str] = []
    releases: set[str] = set()
    components: dict[str, set[str]] = {}
    variants: dict[tuple[str, str], set[str]] = {}
    bundles: dict[str, dict[str, set[str]]] = {}
    architectures: set[str] = set()
    checked = 0
    for package in packages:
        name = Path(package).name
        if not name.lower().endswith(".rpm"):
            continue
        checked += 1
        package_platform = infer_platform(name)
        if iso_platform and package_platform and package_platform != iso_platform:
            issues.append(
                f"{name}: platform {PLATFORMS[package_platform]['label']} does not match "
                f"{PLATFORMS[iso_platform]['label']}"
            )
        rpm_release = RPM_RELEASE.search(name)
        lnt_release = lnt_rpm_release(name) if not rpm_release else None
        if rpm_release:
            tag = rpm_release.group("release")
            releases.add(tag)
            if expected_tag and tag != expected_tag:
                issues.append(
                    f"{name}: release r{tag} does not match IOS XR {iso_release}"
                )
        elif lnt_release:
            releases.add(lnt_release.replace(".", ""))
            if iso_release and lnt_release != iso_release:
                issues.append(
                    f"{name}: built for IOS XR {lnt_release}, not {iso_release}"
                )
        else:
            warnings.append(
                f"{name}: release could not be determined from the filename"
            )
        component = RPM_COMPONENT.search(name)
        if component:
            component_name = component.group("component").lower()
            bug = f"CSC{component.group('bug')}".upper()
            components.setdefault(component_name, set()).add(bug)
            variants.setdefault((component_name, bug), set()).add(
                component.group("version").lower()
            )
            bundle = bundles.setdefault(bug, {"components": set(), "files": set()})
            bundle["components"].add(component_name)
            bundle["files"].add(name)
        architecture = RPM_ARCHITECTURE.search(name)
        if architecture:
            canonical_architecture = normalize_architecture(
                architecture.group("architecture")
            )
            if canonical_architecture:
                architectures.add(canonical_architecture)
        elif lnt_release:
            lnt_architecture = normalize_architecture(
                LNT_RPM.match(name).group("architecture")
            )
            if lnt_architecture:  # noarch has no processor family to compare
                architectures.add(lnt_architecture)
    if len(releases) > 1:
        issues.append("Selected RPMs contain more than one IOS XR release tag")
    if len(architectures) > 1:
        issues.append("Selected RPMs contain more than one processor architecture")
    if iso_architectures and architectures and not architectures & iso_architectures:
        issues.append(
            f"Selected RPMs use processor architecture {', '.join(sorted(architectures))}, "
            f"but the base ISO supports {', '.join(sorted(iso_architectures))}"
        )
    for (component, bug), versions in variants.items():
        if len(versions) > 1:
            issues.append(
                f"Multiple versions of {component} for {bug} are selected; keep one RPM"
            )
    for component, bugs in components.items():
        if len(bugs) > 1:
            warnings.append(
                f"{component} is changed by {', '.join(sorted(bugs))}; Cisco supersedence data is required to choose between them"
            )
    if full_candidate_packages is not None:
        full_bundles = _bundle_files_by_csc(
            full_candidate_packages, iso_platform, expected_tag
        )
        for bug, bundle in sorted(bundles.items()):
            if len(bundle["components"]) <= 1:
                continue
            full_files = full_bundles.get(bug, bundle["files"])
            missing = sorted(full_files - bundle["files"])
            if missing:
                issues.append(
                    f"{bug} is a multi-component fix; {len(bundle['files'])} of "
                    f"{len(full_files)} required RPMs are selected (missing "
                    f"{', '.join(missing)}) - include the rest or exclude "
                    f"{', '.join(sorted(bundle['files']))} too"
                )
    if checked:
        warnings.append(
            "Filename checks cannot prove RPM dependencies; Cisco gisobuild performs the authoritative dependency check"
        )
    package_groups = []
    for bug, bundle in sorted(bundles.items()):
        names = sorted(bundle["components"])
        package_groups.append(
            {
                "csc": bug,
                "components": names,
                "files": sorted(bundle["files"]),
                "count": len(names),
                "relationship": "Multi-component fix; keep these RPMs together"
                if len(names) > 1
                else "Single-component fix",
            }
        )
    component_conflicts = [
        {
            "component": component,
            "cscs": sorted(bugs),
            "reason": "More than one fix changes this component; Cisco supersedence decides which remains",
        }
        for component, bugs in sorted(components.items())
        if len(bugs) > 1
    ]
    return {
        "compatible": not issues,
        "iso_release": iso_release,
        "checked": checked,
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "package_groups": package_groups,
        "component_conflicts": component_conflicts,
        "architectures": sorted(architectures),
        "iso_architectures": sorted(iso_architectures) if iso_architectures else [],
    }


def recommend_smu_selection(
    iso: str, packages: list[str], iso_architectures: frozenset[str] | None = None
) -> dict:
    """Select every deterministic platform/release match for upstream dependency resolution."""
    iso_name = Path(iso).name
    iso_platform = infer_platform(iso_name)
    release_match = ISO_RELEASE.search(iso_name)
    iso_release = release_match.group("release") if release_match else ""
    expected_tag = iso_release.replace(".", "") if iso_release else ""
    selected: list[str] = []
    excluded: list[dict[str, str]] = []

    if not iso_platform or not expected_tag:
        missing = "platform" if not iso_platform else "release"
        return {
            "ready": False,
            "selected": [],
            "excluded": [],
            "package_groups": [],
            "component_conflicts": [],
            "architectures": [],
            "iso_architectures": [],
            "warnings": [],
            "blockers": [],
            "iso": iso_name,
            "message": f"The ISO {missing} could not be detected; select it in Expert settings",
        }

    for package in sorted(set(packages)):
        name = Path(package).name
        package_platform = infer_platform(name)
        rpm_release = RPM_RELEASE.search(name)
        rpm_architecture = RPM_ARCHITECTURE.search(name)
        package_architecture = (
            normalize_architecture(rpm_architecture.group("architecture"))
            if rpm_architecture
            else None
        )
        lnt_release = lnt_rpm_release(name) if is_lnt_platform(iso_platform) else None
        if lnt_release:
            # Upstream LNT builds take every RPM of a package and install only
            # what suits the router's PIDs, and the filename names no platform
            # family - so only a platform the name *does* carry, the XR release
            # and the processor family can rule a package out here.
            lnt_architecture = normalize_architecture(
                LNT_RPM.match(name).group("architecture")
            )
            if package_platform and package_platform != iso_platform:
                excluded.append({"name": name, "reason": "Different platform"})
            elif lnt_release != iso_release:
                excluded.append({"name": name, "reason": "Different IOS XR release"})
            elif (
                iso_architectures
                and lnt_architecture
                and lnt_architecture not in iso_architectures
            ):
                excluded.append(
                    {
                        "name": name,
                        "reason": "Processor architecture does not match the base ISO",
                    }
                )
            else:
                selected.append(name)
        elif not package_platform:
            excluded.append(
                {"name": name, "reason": "Platform is missing from filename"}
            )
        elif package_platform != iso_platform:
            excluded.append({"name": name, "reason": "Different platform"})
        elif rpm_release and rpm_release.group("release") != expected_tag:
            excluded.append({"name": name, "reason": "Different IOS XR release"})
        elif not rpm_release:
            excluded.append(
                {"name": name, "reason": "Release is missing from filename"}
            )
        elif (
            iso_architectures
            and package_architecture
            and package_architecture not in iso_architectures
        ):
            excluded.append(
                {
                    "name": name,
                    "reason": "Processor architecture does not match the base ISO",
                }
            )
        else:
            selected.append(name)

    analysis = validate_smu_selection(
        iso_name, selected, iso_architectures=iso_architectures
    )
    return {
        "ready": True,
        "selected": selected,
        "excluded": excluded,
        "iso": iso_name,
        "platform": iso_platform,
        "release": iso_release,
        "package_groups": analysis["package_groups"],
        "component_conflicts": analysis["component_conflicts"],
        "architectures": analysis["architectures"],
        "iso_architectures": analysis["iso_architectures"],
        "warnings": analysis["warnings"],
        # validate_smu_selection() runs against the automatically-selected set
        # too - it can still fail here (e.g. two different fixes changing the
        # same component to different versions both pass the platform/release
        # filename filters above), so this is a real, itemized blocker list,
        # not a duplicate of "warnings". Without this, an operator only ever
        # saw the underlying issue as a generic error thrown from the final
        # "Start build" click (create_build_plan()'s own blockers, computed
        # the same way from the same identifiers), never during ongoing
        # Step 2 review - see 06-UI-OPERATOR-TODO.md "blockers".
        "blockers": analysis["issues"],
        "message": (
            f"Selected {len(selected)} matching RPMs; Cisco gisobuild will resolve dependencies "
            "and supersedence from the complete matching repository"
        ),
    }


def check_upgrade_matrix(
    matrix: dict,
    source: str,
    target: str,
    platform: str,
    selected_packages: list[str] | None = None,
) -> dict:
    if not isinstance(matrix, dict) or not isinstance(matrix.get("permitted"), dict):
        raise TypeError("The compatibility matrix has an invalid format")
    targets = matrix["permitted"].get(source, {})
    if not isinstance(targets, dict):
        raise TypeError("The compatibility matrix has an invalid source-release entry")
    candidates = targets.get(target, [])
    if not isinstance(candidates, list):
        raise TypeError("The compatibility matrix has an invalid upgrade entry")
    normalized = normalize_platform(platform)

    def matrix_platform(item: object) -> str | None:
        if not isinstance(item, dict):
            return None
        try:
            return normalize_platform(str(item.get("platform", "")))
        except ValueError:
            return None

    match = next(
        (item for item in candidates if matrix_platform(item) == normalized), None
    )
    if not match:
        return {
            "permitted": False,
            "bridge_smus": [],
            "missing_bridge_smus": [],
            "caveats": [],
            "message": f"The matrix does not permit {source} to {target} on {PLATFORMS[normalized]['label']}",
        }
    bridge_smus = match.get("bridge_smus") or []
    caveats = match.get("caveats") or []
    if (
        not isinstance(bridge_smus, list)
        or len(bridge_smus) > 100
        or not all(isinstance(item, str) and len(item) <= 512 for item in bridge_smus)
    ):
        raise ValueError("The compatibility matrix contains invalid bridge SMUs")
    if (
        not isinstance(caveats, list)
        or len(caveats) > 100
        or not all(isinstance(item, str) and len(item) <= 4096 for item in caveats)
    ):
        raise ValueError("The compatibility matrix contains invalid caveats")
    selected_names = {Path(item).name.lower() for item in (selected_packages or [])}
    selected_cscs = {
        token.upper()
        for item in selected_names
        for token in re.findall(r"CSC[a-z0-9]+", item, re.IGNORECASE)
    }
    missing_bridge_smus = [
        item
        for item in bridge_smus
        if Path(item).name.lower() not in selected_names
        and not any(
            token.upper() in selected_cscs
            for token in re.findall(r"CSC[a-z0-9]+", item, re.IGNORECASE)
        )
    ]
    return {
        "permitted": True,
        "bridge_smus": bridge_smus,
        "missing_bridge_smus": missing_bridge_smus,
        "caveats": caveats,
        "message": f"The matrix permits {source} to {target} on {PLATFORMS[normalized]['label']}",
    }


# Every build option that a platform's capabilities decide, and the human name
# the operator sees. Which platforms have which capability is data
# (PLATFORMS/PLATFORM_CAPABILITY_OVERRIDES, derived from upstream's own CLI
# maps), never a platform name written into a condition: a new upstream
# platform needs a profile entry, not a code change.
OPTION_CAPABILITIES = {
    "migration": "migration",
    "full_iso": "full_iso",
    "x86_only": "x86_only",
    "optimize": "optimize",
    "script": "script",
    "remove_packages": "remove_packages",
    "only_support_pids": "only_support_pids",
    "clear_bridging_fixes": "clear_bridging_fixes",
    "verbose_dep_check": "verbose_dependency_check",
    "ownership_vouchers": "ownership_vouchers",
    "ownership_certificate": "ownership_certificate",
    "clear_ownership_vouchers": "clear_ownership_vouchers",
    "clear_ownership_certificate": "clear_ownership_certificate",
    "key_request": "key_request",
    "clear_key_request": "clear_key_request",
    "no_buildinfo": "no_buildinfo",
}
OPTION_LABELS = {
    "migration": "Migration TAR",
    "full_iso": "Full ISO",
    "x86_only": "x86-only packages",
    "optimize": "Optimized ISO",
    "script": "Boot script",
    "remove_packages": "Remove packages",
    "only_support_pids": "PID filtering",
    "clear_bridging_fixes": "Clear bridging fixes",
    "verbose_dep_check": "Verbose dependency check",
    "ownership_vouchers": "Ownership vouchers",
    "ownership_certificate": "Ownership certificate",
    "clear_ownership_vouchers": "Clear ownership vouchers",
    "clear_ownership_certificate": "Clear ownership certificate",
    "key_request": "Key request",
    "clear_key_request": "Clear key request",
    "no_buildinfo": "No build information",
}


def platforms_supporting(capability: str) -> list[str]:
    """Labels of the real platforms whose capabilities include `capability`.

    Used to turn "this option is not available here" into "upstream offers it
    on <platforms>". The manual-override profiles are left out: they claim no
    platform-specific capability, so naming them would mislead.
    """
    return sorted(
        PLATFORMS[name]["label"]
        for name in PLATFORMS
        if name not in GENERIC_PLATFORM_IDS
        and capabilities_for_platform(name).get(capability, False)
    )


def validate_platform_options(payload: dict) -> dict:
    requested = payload.get("platform", "")
    platform = (
        normalize_platform(requested)
        if requested
        else infer_platform(payload.get("iso", ""))
    )
    if not platform:
        raise ValueError(
            "Select the platform family; it could not be inferred from the ISO filename"
        )
    profile = platform_profile(platform)
    architecture = profile["architecture"]
    errors = []
    for option, capability in OPTION_CAPABILITIES.items():
        if not payload.get(option) or profile["capabilities"].get(capability, False):
            continue
        elsewhere = platforms_supporting(capability)
        named, extra = elsewhere[:3], len(elsewhere) - 3
        where = ", ".join(named) + (f" and {extra} more" if extra > 0 else "")
        errors.append(
            f"{OPTION_LABELS.get(option, option)} is not supported on {profile['label']} "
            f"({architecture.upper()} build engine)"
            + (f"; upstream gisobuild offers it on {where}" if elsewhere else "")
        )
    # Only LNT can be told to skip USB, and only LNT would try and fail; the
    # eXR engine simply produces no USB zip for a platform without a script.
    if (
        architecture == "lnt"
        and not profile["usb"]
        and not payload.get("skip_usb_image")
    ):
        errors.append(
            f"Automatic USB output is not supported for {profile['label']}; enable Skip USB image"
        )
    if errors:
        raise ValueError("; ".join(errors))
    return profile


# One vocabulary for why a package is not in the build, so the API, the page
# and the build report agree. The first pattern that matches a reason decides;
# ordering matters where reasons overlap (a superseded fix also mentions a
# component). UNKNOWN is deliberately last: it means the file could not be
# identified well enough to judge, which is never an automatic inclusion.
PACKAGE_STATUSES = (
    (
        "WRONG_PLATFORM",
        re.compile(r"different platform|belongs to .* platform", re.IGNORECASE),
    ),
    (
        "WRONG_RELEASE",
        re.compile(r"different ios xr release|belongs to ios xr", re.IGNORECASE),
    ),
    ("WRONG_ARCHITECTURE", re.compile(r"processor architecture", re.IGNORECASE)),
    ("CONFLICT", re.compile(r"more than one fix|conflict", re.IGNORECASE)),
    ("SUPERSEDED", re.compile(r"supersed", re.IGNORECASE)),
    (
        "MISSING_DEPENDENCY",
        re.compile(
            r"depend|requires|needs |nothing provides|prerequisite|"
            r"cannot be installed|part of csc",
            re.IGNORECASE,
        ),
    ),
    ("DUPLICATE", re.compile(r"duplicate|another copy|same version", re.IGNORECASE)),
    (
        "INVALID",
        re.compile(
            r"md5|incomplete fix|cannot read|does not match the package inside|"
            r"from the same fix",
            re.IGNORECASE,
        ),
    ),
    ("UNKNOWN", re.compile(r"missing from filename|could not be", re.IGNORECASE)),
)


def classify_exclusion(reason: str) -> str:
    """The status code for one exclusion reason (see PACKAGE_STATUSES)."""
    for status, pattern in PACKAGE_STATUSES:
        if pattern.search(reason or ""):
            return status
    return "MANUAL_REVIEW_REQUIRED"


def describe_package(name: str) -> dict:
    """Everything a filename alone says about a package, for the status table."""
    csc = re.search(r"\.(CSC[A-Za-z0-9]+)\.", name, re.IGNORECASE)
    architecture = RPM_ARCHITECTURE.search(name)
    release = lnt_rpm_release(name)
    if not release:
        # eXR names carry the release as a compact tag (r2512 for 25.1.2); keep
        # the tag verbatim so the table never implies a release Cisco did not
        # write, and let the reason text explain the comparison.
        tag = RPM_RELEASE.search(name)
        release = f"r{tag.group('release')}" if tag else None
    return {
        "name": name,
        "platform": infer_platform(name),
        "release": release,
        "architecture": (
            normalize_architecture(architecture.group("architecture"))
            if architecture
            else None
        ),
        # Cisco writes CSCxx12345; keep the filename's own spelling.
        "csc": csc.group(1) if csc else None,
    }
