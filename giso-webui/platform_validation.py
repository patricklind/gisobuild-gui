"""Platform-aware validation for Cisco IOS XR GISO build options."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# eXR identifiers are synchronized with ios-xr/gisobuild's
# src/utils/gisoglobals.py. LNT uses metadata-driven validation upstream, so
# its public product families are represented explicitly here for UI checks.
COMMON_CAPABILITIES = {
    "repo", "pkglist", "xrconfig", "ztp", "create_checksum", "skip_usb_image",
    "label", "no_label", "debug",
}
EXR_CAPABILITIES = COMMON_CAPABILITIES | {
    "script", "optimize", "x86_only", "bridging_fixes",
}
LNT_CAPABILITIES = COMMON_CAPABILITIES | {
    "remove_packages", "only_support_pids", "verbose_dependency_check",
    "bridging_fixes", "clear_bridging_fixes", "ownership_vouchers",
    "ownership_certificate", "clear_ownership_vouchers",
    "clear_ownership_certificate", "key_request", "clear_key_request", "no_buildinfo",
}

# The eXR identifiers and engine option sets come from the pinned upstream
# src/utils/gisoglobals.py maps. Marketing aliases below aid presentation only;
# upstream ISO inspection remains authoritative for actual build support.
PLATFORMS = {
    "asr9k": {"label": "ASR 9000", "architecture": "exr", "usb": True},
    "ncs1k": {"label": "NCS 1000", "architecture": "exr", "usb": True},
    "ncs1001": {"label": "NCS 1001", "architecture": "exr", "usb": True},
    "ncs1004": {"label": "NCS 1004", "architecture": "exr", "usb": True},
    "ncs5k": {"label": "NCS 5000", "architecture": "exr", "usb": False},
    "ncs540": {"label": "NCS 540 (eXR)", "architecture": "exr", "usb": True},
    "ncs5500": {"label": "NCS 5500", "architecture": "exr", "usb": True},
    "ncs560": {"label": "NCS 560", "architecture": "exr", "usb": True},
    "ncs6k": {"label": "NCS 6000", "architecture": "exr", "usb": False},
    "iosxrwb": {"label": "IOS XR Whitebox", "architecture": "exr", "usb": False},
    "iosxrwbd": {"label": "IOS XR Whitebox Distributed", "architecture": "exr", "usb": True},
    "xrv9k": {"label": "IOS XRv 9000", "architecture": "exr", "usb": False},
    "8000": {"label": "Cisco 8000 / 8800", "architecture": "lnt", "usb": True},
    "ncs1010": {"label": "NCS 1010/1014", "architecture": "lnt", "usb": True},
    "ncs540l": {"label": "NCS 540L (XR7)", "architecture": "lnt", "usb": True},
    "ncs57": {"label": "NCS 5700 / NCS 57C3", "architecture": "lnt", "usb": True},
}

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
    "asr9000": "asr9k", "asr9k-x64": "asr9k", "ncs5000": "ncs5k",
    "ncs6000": "ncs6k", "ncs5700": "ncs57", "cisco8000": "8000",
    "8800": "8000", "8200": "8000",
    # NCS 57C3 hardware SKU spellings seen in Cisco inventory and image metadata.
    # Keep both MODS-SYS and MOD-SYS variants so manual selection and filename
    # inference normalize to the NCS 5700/LNT family rather than failing closed.
    "ncs-57c3-mods-sys": "ncs57", "ncs57c3modssys": "ncs57",
    "ncs-57c3-mod-sys": "ncs57", "ncs57c3modsys": "ncs57",
    "ncs-57c3": "ncs57", "ncs57c3": "ncs57",
}

RPM_RELEASE = re.compile(r"-r(?P<release>\d{3,6})(?:\.|-)", re.IGNORECASE)
ISO_RELEASE = re.compile(r"-(?P<release>\d+\.\d+\.\d+)(?:[-.]|$)", re.IGNORECASE)
RPM_COMPONENT = re.compile(
    r"^(?P<component>[a-z0-9_-]+?)-(?P<version>\d[^/]*?)-r\d{3,6}\.CSC(?P<bug>[a-z0-9]+)",
    re.IGNORECASE,
)
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
    "x86_64": "x86_64", "amd64": "x86_64", "corei7_64": "x86_64",
    "aarch64": "aarch64", "arm64": "aarch64", "arm": "aarch64",
}


def normalize_architecture(token: str) -> str | None:
    """Return the canonical processor family for a filename/metadata token."""
    return ARCH_ALIASES.get(token.strip().lower()) if token else None


def capabilities_for_platform(platform: str) -> dict[str, bool]:
    """Return the UI/adapter capabilities for one normalized platform."""
    normalized = normalize_platform(platform)
    profile = PLATFORMS[normalized]
    supported = set(LNT_CAPABILITIES if profile["architecture"] == "lnt" else EXR_CAPABILITIES)
    supported.update(PLATFORM_CAPABILITY_OVERRIDES.get(normalized, set()))
    if profile["usb"]:
        supported.add("usb_image")
    known = COMMON_CAPABILITIES | EXR_CAPABILITIES | LNT_CAPABILITIES | {
        "usb_image", "migration", "full_iso",
    }
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
    candidates = sorted(PLATFORMS, key=len, reverse=True)
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


def validate_smu_selection(
    iso: str, packages: list[str], iso_architectures: frozenset[str] | None = None
) -> dict:
    """Check deterministic filename compatibility before upstream dependency resolution.

    ``iso_architectures`` is the set of canonical processor families detected
    directly from the base ISO's own contents (see ``inspect_iso_architecture``
    in app.py); pass None or an empty set when detection was not run or was
    inconclusive so an upstream-valid image is never blocked on that basis
    alone.
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
        if rpm_release:
            tag = rpm_release.group("release")
            releases.add(tag)
            if expected_tag and tag != expected_tag:
                issues.append(f"{name}: release r{tag} does not match IOS XR {iso_release}")
        else:
            warnings.append(f"{name}: release could not be determined from the filename")
        component = RPM_COMPONENT.search(name)
        if component:
            component_name = component.group("component").lower()
            bug = f"CSC{component.group('bug')}".upper()
            components.setdefault(component_name, set()).add(bug)
            variants.setdefault((component_name, bug), set()).add(component.group("version").lower())
            bundle = bundles.setdefault(bug, {"components": set(), "files": set()})
            bundle["components"].add(component_name)
            bundle["files"].add(name)
        architecture = RPM_ARCHITECTURE.search(name)
        if architecture:
            canonical_architecture = normalize_architecture(architecture.group("architecture"))
            if canonical_architecture:
                architectures.add(canonical_architecture)
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
            issues.append(f"Multiple versions of {component} for {bug} are selected; keep one RPM")
    for component, bugs in components.items():
        if len(bugs) > 1:
            warnings.append(
                f"{component} is changed by {', '.join(sorted(bugs))}; Cisco supersedence data is required to choose between them"
            )
    if checked:
        warnings.append(
            "Filename checks cannot prove RPM dependencies; Cisco gisobuild performs the authoritative dependency check"
        )
    package_groups = []
    for bug, bundle in sorted(bundles.items()):
        names = sorted(bundle["components"])
        package_groups.append({
            "csc": bug,
            "components": names,
            "files": sorted(bundle["files"]),
            "count": len(names),
            "relationship": "Multi-component fix; keep these RPMs together" if len(names) > 1
            else "Single-component fix",
        })
    component_conflicts = [
        {"component": component, "cscs": sorted(bugs),
         "reason": "More than one fix changes this component; Cisco supersedence decides which remains"}
        for component, bugs in sorted(components.items()) if len(bugs) > 1
    ]
    return {"compatible": not issues, "iso_release": iso_release, "checked": checked,
            "issues": sorted(set(issues)), "warnings": sorted(set(warnings)),
            "package_groups": package_groups, "component_conflicts": component_conflicts,
            "architectures": sorted(architectures),
            "iso_architectures": sorted(iso_architectures) if iso_architectures else []}


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
        return {"ready": False, "selected": [], "excluded": [], "package_groups": [],
                "component_conflicts": [], "architectures": [], "iso_architectures": [],
                "warnings": [], "blockers": [], "iso": iso_name,
                "message": f"The ISO {missing} could not be detected; select it in Expert settings"}

    for package in sorted(set(packages)):
        name = Path(package).name
        package_platform = infer_platform(name)
        rpm_release = RPM_RELEASE.search(name)
        rpm_architecture = RPM_ARCHITECTURE.search(name)
        package_architecture = (
            normalize_architecture(rpm_architecture.group("architecture"))
            if rpm_architecture else None
        )
        if not package_platform:
            excluded.append({"name": name, "reason": "Platform is missing from filename"})
        elif package_platform != iso_platform:
            excluded.append({"name": name, "reason": "Different platform"})
        elif rpm_release and rpm_release.group("release") != expected_tag:
            excluded.append({"name": name, "reason": "Different IOS XR release"})
        elif not rpm_release:
            excluded.append({"name": name, "reason": "Release is missing from filename"})
        elif (iso_architectures and package_architecture
              and package_architecture not in iso_architectures):
            excluded.append({"name": name, "reason": "Processor architecture does not match the base ISO"})
        else:
            selected.append(name)

    analysis = validate_smu_selection(iso_name, selected, iso_architectures=iso_architectures)
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


def check_upgrade_matrix(matrix: dict, source: str, target: str, platform: str,
                         selected_packages: list[str] | None = None) -> dict:
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

    match = next((item for item in candidates if matrix_platform(item) == normalized), None)
    if not match:
        return {"permitted": False, "bridge_smus": [], "missing_bridge_smus": [], "caveats": [],
                "message": f"The matrix does not permit {source} to {target} on {PLATFORMS[normalized]['label']}"}
    bridge_smus = match.get("bridge_smus") or []
    caveats = match.get("caveats") or []
    if (not isinstance(bridge_smus, list) or len(bridge_smus) > 100 or
            not all(isinstance(item, str) and len(item) <= 512 for item in bridge_smus)):
        raise ValueError("The compatibility matrix contains invalid bridge SMUs")
    if (not isinstance(caveats, list) or len(caveats) > 100 or
            not all(isinstance(item, str) and len(item) <= 4096 for item in caveats)):
        raise ValueError("The compatibility matrix contains invalid caveats")
    selected_names = {Path(item).name.lower() for item in (selected_packages or [])}
    selected_cscs = {
        token.upper()
        for item in selected_names
        for token in re.findall(r"CSC[a-z0-9]+", item, re.IGNORECASE)
    }
    missing_bridge_smus = [
        item for item in bridge_smus
        if Path(item).name.lower() not in selected_names
        and not any(token.upper() in selected_cscs
                    for token in re.findall(r"CSC[a-z0-9]+", item, re.IGNORECASE))
    ]
    return {"permitted": True, "bridge_smus": bridge_smus,
            "missing_bridge_smus": missing_bridge_smus, "caveats": caveats,
            "message": f"The matrix permits {source} to {target} on {PLATFORMS[normalized]['label']}"}


def validate_platform_options(payload: dict) -> dict:
    requested = payload.get("platform", "")
    platform = normalize_platform(requested) if requested else infer_platform(payload.get("iso", ""))
    if not platform:
        raise ValueError("Select the platform family; it could not be inferred from the ISO filename")
    profile = platform_profile(platform)
    architecture = profile["architecture"]
    errors = []
    if payload.get("migration") and platform != "asr9k":
        errors.append("Migration TAR is supported only for ASR 9000 eXR images")
    if payload.get("full_iso") and platform != "xrv9k":
        errors.append("Full ISO is supported only for IOS XRv 9000")
    option_capabilities = {
        "x86_only": "x86_only", "optimize": "optimize", "script": "script",
        "remove_packages": "remove_packages", "only_support_pids": "only_support_pids",
        "clear_bridging_fixes": "clear_bridging_fixes",
        "verbose_dep_check": "verbose_dependency_check",
        "ownership_vouchers": "ownership_vouchers",
        "ownership_certificate": "ownership_certificate",
        "clear_ownership_vouchers": "clear_ownership_vouchers",
        "clear_ownership_certificate": "clear_ownership_certificate",
        "key_request": "key_request", "clear_key_request": "clear_key_request",
        "no_buildinfo": "no_buildinfo",
    }
    unsupported = [option for option, capability in option_capabilities.items()
                   if payload.get(option) and not profile["capabilities"].get(capability, False)]
    if unsupported:
        errors.append(
            f"{', '.join(unsupported)} not supported by the {profile['label']} {architecture.upper()} build engine"
        )
    if not profile["usb"] and not payload.get("skip_usb_image"):
        errors.append(f"Automatic USB output is not supported for {profile['label']}; enable Skip USB image")
    if errors:
        raise ValueError("; ".join(errors))
    return profile
