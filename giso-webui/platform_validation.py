"""Platform-aware validation for Cisco IOS XR GISO build options."""

from __future__ import annotations

import re

# eXR identifiers are synchronized with ios-xr/gisobuild's
# src/utils/gisoglobals.py. LNT uses metadata-driven validation upstream, so
# its public product families are represented explicitly here for UI checks.
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
    "ncs57": {"label": "NCS 5700", "architecture": "lnt", "usb": True},
}

ALIASES = {
    "asr9000": "asr9k", "asr9k-x64": "asr9k", "ncs5000": "ncs5k",
    "ncs6000": "ncs6k", "ncs5700": "ncs57", "cisco8000": "8000",
    "8800": "8000", "8200": "8000",
}


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
    for alias, platform in ALIASES.items():
        if alias in name:
            return platform
    return None


def validate_platform_options(payload: dict) -> dict:
    requested = payload.get("platform", "")
    platform = normalize_platform(requested) if requested else infer_platform(payload.get("iso", ""))
    if not platform:
        raise ValueError("Select the platform family; it could not be inferred from the ISO filename")
    profile = {"id": platform, **PLATFORMS[platform]}
    architecture = profile["architecture"]
    errors = []
    if payload.get("migration") and platform != "asr9k":
        errors.append("Migration TAR is supported only for ASR 9000 eXR images")
    if payload.get("full_iso") and platform != "xrv9k":
        errors.append("Full ISO is supported only for IOS XRv 9000")
    exr_only = ("x86_only", "optimize", "script")
    if architecture != "exr" and any(payload.get(option) for option in exr_only):
        errors.append("x86-only, optimize, and boot-script are eXR-only options")
    lnt_only = ("remove_packages", "only_support_pids", "clear_bridging_fixes",
                "verbose_dep_check")
    if architecture != "lnt" and any(payload.get(option) for option in lnt_only):
        errors.append("remove packages, PID filtering, and LNT build controls require an IOS XR7/LNT image")
    if not profile["usb"] and not payload.get("skip_usb_image"):
        errors.append(f"Automatic USB output is not supported for {profile['label']}; enable Skip USB image")
    if errors:
        raise ValueError("; ".join(errors))
    return profile
