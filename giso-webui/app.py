from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import tarfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from cisco_download import CiscoDownloadError, CiscoSoftwareClient, secret_value
from flask import (
    Flask,
    abort,
    g,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from platform_validation import (
    GENERIC_PLATFORM_IDS,
    ISO_RELEASE,
    PLATFORMS,
    RPM_ARCHITECTURE,
    check_upgrade_matrix,
    infer_platform,
    infer_platform_pid,
    normalize_architecture,
    platform_profile,
    recommend_smu_selection,
    validate_platform_options,
    validate_smu_selection,
)
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge


def validate_image_reference(value: str) -> str:
    if not value or len(value) > 512 or value.startswith("-") or any(char.isspace() for char in value):
        raise RuntimeError("GISO_IMAGE must be a valid Docker image reference")
    return value


app = Flask(__name__)
app.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
DOCKER_BIN = os.environ.get("DOCKER_BIN", "/usr/bin/docker")
if not Path(DOCKER_BIN).is_absolute():
    raise RuntimeError("DOCKER_BIN must be an absolute path")
ISOINFO_BIN = os.environ.get("ISOINFO_BIN", "/usr/bin/isoinfo")
RPM_BIN = os.environ.get("RPM_BIN", "/usr/bin/rpm")
if not Path(ISOINFO_BIN).is_absolute():
    raise RuntimeError("ISOINFO_BIN must be an absolute path")
DATA = Path(os.environ.get("DATA_ROOT", "/data")).resolve()
OUTPUT = Path(os.environ.get("OUTPUT_ROOT", "/output")).resolve()
TOOL = Path(os.environ.get("TOOL_ROOT", "/tool")).resolve()
WORK = Path(os.environ.get("WORK_ROOT", "/work")).resolve()
ARCHIVE = Path(os.environ.get("ARCHIVE_ROOT", "/archive")).resolve()
STATE = Path(os.environ.get("STATE_ROOT", "/state")).resolve()
JOB_DB = STATE / "jobs.sqlite3"
IMAGE = validate_image_reference(
    os.environ.get("GISO_IMAGE", "ciscogisobuild/cisco-xr-gisobuild:2.3.4")
)
APP_VERSION = os.environ.get("APP_VERSION", "0.0.1")
jobs: dict[str, dict] = {}
job_processes: dict[str, subprocess.Popen] = {}
job_persisted_at: dict[str, float] = {}
uploads: dict[str, dict] = {}
cisco_searches: dict[str, dict] = {}
cisco_download_jobs: dict[str, dict] = {}
cisco_api_client: CiscoSoftwareClient | None = None
checksum_cache: dict[tuple[str, int, int], dict[str, str]] = {}
iso_architecture_cache: dict[tuple[str, int, int], frozenset[str]] = {}
iso_mdata_cache: dict[tuple[str, int, int], str] = {}
rpm_metadata_cache: dict[tuple[str, int, int], dict[str, list[tuple[str, str]]]] = {}
job_lock = threading.RLock()
upload_lock = threading.Lock()
archive_lock = threading.RLock()
archive_file_lock_handle = None
archive_file_lock_path: Path | None = None
archive_file_lock_depth = 0
checksum_lock = threading.Lock()
operation_lock = threading.Lock()
store_lock = threading.Lock()
cisco_lock = threading.RLock()
store_initialized = False
archive_policy_checked = 0.0
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024**3)))
MAX_EXTRACTED_BYTES = int(os.environ.get("MAX_EXTRACTED_BYTES", str(16 * 1024**3)))
MAX_TAR_MEMBERS = int(os.environ.get("MAX_TAR_MEMBERS", "10000"))
MAX_CHUNK_BYTES = int(os.environ.get("MAX_CHUNK_BYTES", str(16 * 1024**2)))
MAX_LOG_BYTES = int(os.environ.get("MAX_LOG_BYTES", str(10 * 1024**2)))
MAX_SUPERSEDENCE_FILE_BYTES = 2 * 1024**2
MAX_SUPERSEDENCE_TOTAL_BYTES = 16 * 1024**2
MAX_ISO_INSPECTION_OUTPUT_BYTES = 8 * 1024**2
MAX_FILE_PREVIEW_BYTES = 64 * 1024
ISO_MDATA_TIMEOUT_SECONDS = 30
ISO_LISTING_TIMEOUT_SECONDS = 60
RPM_QUERY_TIMEOUT_SECONDS = 15
MAX_JOB_HISTORY = int(os.environ.get("MAX_JOB_HISTORY", "100"))


def validate_archive_retention_days(value: int) -> int:
    if value < 0:
        # enforce_archive_policy()'s cutoff is time.time() -
        # ARCHIVE_RETENTION_DAYS * 86400; a negative value pushes the cutoff
        # into the future, so every archive - including one just created -
        # looks "expired" and is deleted on the very next policy check. A
        # misconfiguration typo must not silently destroy every build
        # artifact; fail fast at startup instead.
        raise RuntimeError("ARCHIVE_RETENTION_DAYS must not be negative")
    return value


def validate_max_archive_bytes(value: int) -> int:
    if value <= 0:
        # enforce_archive_policy() evicts the oldest archive while its total
        # size exceeds this quota; zero or negative makes every archive
        # "over quota" and evicts everything, immediately, on the next
        # policy check.
        raise RuntimeError("MAX_ARCHIVE_BYTES must be a positive number of bytes")
    return value


ARCHIVE_RETENTION_DAYS = validate_archive_retention_days(
    int(os.environ.get("ARCHIVE_RETENTION_DAYS", "30"))
)
MAX_ARCHIVE_BYTES = validate_max_archive_bytes(
    int(os.environ.get("MAX_ARCHIVE_BYTES", str(50 * 1024**3)))
)
UPLOAD_SESSION_TTL = int(os.environ.get("UPLOAD_SESSION_TTL", str(24 * 60 * 60)))
GISO_PULL_TIMEOUT_SECONDS = int(os.environ.get("GISO_PULL_TIMEOUT_SECONDS", "600"))
CISCO_DOWNLOAD_TIMEOUT_SECONDS = int(os.environ.get("CISCO_DOWNLOAD_TIMEOUT_SECONDS", "60"))
ALLOWED_HOSTS = {host.strip() for host in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost,giso-webui").split(",") if host.strip()}
ACTIVE_JOB_STATUSES = {"queued", "running", "finalizing", "committing", "cancelling"}
MIN_FREE_BYTES = 512 * 1024**2
app.config["MAX_CONTENT_LENGTH"] = MAX_CHUNK_BYTES

if min(MAX_UPLOAD_BYTES, MAX_EXTRACTED_BYTES, MAX_TAR_MEMBERS, MAX_CHUNK_BYTES,
       MAX_LOG_BYTES, MAX_JOB_HISTORY, ARCHIVE_RETENTION_DAYS, MAX_ARCHIVE_BYTES,
       UPLOAD_SESSION_TTL, GISO_PULL_TIMEOUT_SECONDS) <= 0 or not ALLOWED_HOSTS:
    raise RuntimeError("Upload, extraction, tar, chunk and log limits must be positive")

PRIVATE_JOB_FIELDS = {
    "command", "payload", "container_pid", "cleanup_paths", "process_phase",
}


class BuildCancelled(RuntimeError):
    """Stop a build lifecycle without converting cancellation into failure."""


def cisco_client() -> CiscoSoftwareClient:
    global cisco_api_client
    client_id = secret_value("CISCO_CLIENT_ID")
    client_secret = secret_value("CISCO_CLIENT_SECRET")
    allowed = tuple(host.strip() for host in os.environ.get(
        "CISCO_DOWNLOAD_HOSTS", "cisco.com"
    ).split(",") if host.strip())
    with cisco_lock:
        if (cisco_api_client is None or cisco_api_client.client_id != client_id or
                cisco_api_client.client_secret != client_secret or
                cisco_api_client.allowed_hosts != allowed):
            cisco_api_client = CiscoSoftwareClient(
                client_id, client_secret, timeout=CISCO_DOWNLOAD_TIMEOUT_SECONDS,
                allowed_hosts=allowed,
            )
        return cisco_api_client


def cisco_failure(exc: Exception, status_code: int = 400):
    status = "authorization-required" if str(exc).startswith(
        "Cisco authorization failed:"
    ) else "failed"
    return jsonify(error=str(exc), status=status), status_code


def cisco_download_running() -> bool:
    with cisco_lock:
        now = time.time()
        for job in cisco_download_jobs.values():
            if now - job["created"] > 3600 and job["status"] in {
                "authenticating", "downloading", "verifying", "eula-required"
            }:
                job.update(status="failed", error="Cisco download session expired")
        return any(job["status"] in {"authenticating", "downloading", "verifying", "eula-required"}
                   for job in cisco_download_jobs.values())


def cisco_text(value: object, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"Invalid Cisco {name}")
    result = value.strip()
    if any(ord(char) < 32 for char in result):
        raise ValueError(f"Invalid Cisco {name}")
    return result


def find_cisco_images(value: object, context: dict | None = None) -> list[dict]:
    """Flatten Cisco's nested product/release response without returning secrets."""
    context = dict(context or {})
    found: list[dict] = []
    if isinstance(value, dict):
        for key in ("releaseVersion", "version", "mdfId", "pid"):
            if value.get(key) not in (None, ""):
                context[key] = value[key]
        image_name = value.get("imageName", value.get("name"))
        if value.get("imageGuid") and image_name:
            try:
                size = int(value.get("imageSize", value.get("size", 0)))
            except (TypeError, ValueError):
                size = 0
            found.append({
                "guid": str(value["imageGuid"]), "name": str(image_name),
                "size": size, "release": str(value.get(
                    "releaseVersion", context.get("releaseVersion", context.get("version", ""))
                )),
                "mdf_id": str(value.get("mdfId", context.get("mdfId", ""))),
                "md5": str(value.get("md5", value.get("Md5", ""))),
                "sha512": str(value.get("sha512", "")),
                "encrypted": str(value.get("encryptionSoftwareIndicator", "N")).upper() == "Y",
                "entitlement": str(value.get("additionalEntitlement", "N")).upper() == "Y",
            })
        for nested in value.values():
            found.extend(find_cisco_images(nested, context))
    elif isinstance(value, list):
        for nested in value:
            found.extend(find_cisco_images(nested, context))
    return found


def cisco_response_requires(value: object, field: str) -> bool:
    if isinstance(value, dict):
        return bool(value.get(field)) or any(
            cisco_response_requires(nested, field) for nested in value.values()
        )
    if isinstance(value, list):
        return any(cisco_response_requires(nested, field) for nested in value)
    return False


# Longest first: ".tar.gz" must win over a bare ".gz" split. Upstream gisobuild
# documents LNT bugfixes as <platform>-<release>-CSC<id>.tar.gz.
ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar")


def archive_suffix(name: str) -> str | None:
    """The archive suffix a filename ends with (case-insensitive), or None."""
    lowered = name.lower()
    return next((suffix for suffix in ARCHIVE_SUFFIXES if lowered.endswith(suffix)), None)


def split_upload_name(name: str) -> tuple[str, str]:
    """(stem, suffix) that keeps a multi-part archive suffix like ".tar.gz" intact."""
    suffix = archive_suffix(name)
    if suffix:
        return name[:-len(suffix)], name[-len(suffix):]
    return Path(name).stem, Path(name).suffix


def extract_cisco_archive(path: Path) -> int:
    if not archive_suffix(path.name):
        return 0
    destination = extraction_path(path)
    if destination is None:
        raise CiscoDownloadError("Unsupported Cisco archive type")
    try:
        destination.mkdir()
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            if len(members) > MAX_TAR_MEMBERS:
                raise CiscoDownloadError("Cisco archive contains too many files")
            expanded_size = sum(member.size for member in members if member.isfile())
            if expanded_size > MAX_EXTRACTED_BYTES:
                raise CiscoDownloadError("Cisco archive expands beyond the configured limit")
            if shutil.disk_usage(DATA).free < expanded_size + MIN_FREE_BYTES:
                raise CiscoDownloadError("Not enough free disk space to extract the Cisco archive")
            root = destination.resolve()
            for member in members:
                target = (destination / member.name).resolve()
                if (root not in target.parents and target != root) or member.issym() or member.islnk():
                    raise CiscoDownloadError("Cisco archive contains an unsafe path or link")
            archive.extractall(destination, members=members, filter="data")
            return sum(1 for member in members if member.isfile())
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def log_event(event: str, **fields: object) -> None:
    """Write a compact operational event without sensitive filenames or payloads."""
    details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    app.logger.info("event=%s%s", event, f" {details}" if details else "")


ARTIFACT_TOKEN = re.compile(
    r"(?:[\"'][^\"'\r\n]*?\.(?:iso|rpm|zip|tar\.gz|tar|tgz|yaml|yml|cfg|ini|sh|cms|txt|json)[\"']|"
    r"(?<!\w)[^\s\"'=]+?\.(?:iso|rpm|zip|tar\.gz|tar|tgz|yaml|yml|cfg|ini|sh|cms|txt|json)(?!\w))",
    re.IGNORECASE,
)


def safe_log_text(text: str) -> str:
    """Remove licensed or sensitive artifact names from operator-visible logs."""
    return ARTIFACT_TOKEN.sub("[artifact]", text)


# gisobuild's compatibility check runs RPM's own dependency resolution inside
# the build container and surfaces unmet requirements as
# "<requirement> is needed by <package>" lines - RPM's standard transaction-
# check output format (see .gisobuild-tool src/exrmod/gisobuild_exr_engine.py
# and src/lnt/builder/_pkgchecks.py, both of which look for this exact
# "is needed by" marker themselves). Real log lines carry a
# "YYYY-MM-DD HH:MM:SS::  \t" prefix before the actual message, so this is
# deliberately *not* anchored to the start of the line - <requirement> only
# accepts identifier/version characters, which cannot span the "::" in the
# timestamp, so re.finditer naturally skips the prefix and locks onto the
# real "<name>[ <op> <version>] is needed by <package>" text wherever it
# starts. <requirement> is a bare package name or a version-constrained one
# ("pkg = 1.2.3", "pkg >= 1.2.3"); neither form nor <package> (gisobuild
# always renders it without a ".rpm" suffix here) matches ARTIFACT_TOKEN, so
# this text is never redacted from job logs.
MISSING_DEPENDENCY_PATTERN = re.compile(
    r"(?P<requirement>[\w.+-]+(?:\s*(?:>=|<=|=|>|<)\s*[\w.+-]+)?)\s+is needed by\s+(?P<required_by>\S+)"
)


def parse_missing_dependencies(log: str) -> list[dict]:
    """Extract gisobuild's own RPM dependency-check failures from a job's log.

    This does not predict or prevent a dependency failure - only gisobuild's
    real RPM transaction check, against the actual base image's own package
    set, can determine that. It only makes an already-real, already-visible
    failure legible without an operator having to search the raw build log
    for it.
    """
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for match in MISSING_DEPENDENCY_PATTERN.finditer(log):
        requirement = match.group("requirement").strip()
        required_by = match.group("required_by").strip()
        seen.setdefault((requirement, required_by),
                        {"requirement": requirement, "required_by": required_by})
    return list(seen.values())


def append_activity(text: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {safe_log_text(text).strip()}"
    STATE.mkdir(parents=True, exist_ok=True)
    with store_lock, sqlite3.connect(JOB_DB) as database:
        database.execute(
            "CREATE TABLE IF NOT EXISTS activity "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, text TEXT NOT NULL)"
        )
        database.execute(
            "INSERT INTO activity (created, text) VALUES (?, ?)", (time.time(), entry)
        )
        database.execute(
            "DELETE FROM activity WHERE id NOT IN "
            "(SELECT id FROM activity ORDER BY id DESC LIMIT 500)"
        )


def public_job(job: dict, *, include_log: bool = True) -> dict:
    private = PRIVATE_JOB_FIELDS | (set() if include_log else {"log"})
    result = {key: value for key, value in job.items() if key not in private}
    if job.get("status") == "failed":
        result["missing_dependencies"] = parse_missing_dependencies(job.get("log", ""))
    return result


def initialize_job_store() -> None:
    """Create the job store and restore safe job history once per process."""
    global store_initialized
    with store_lock:
        if store_initialized:
            return
        STATE.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(JOB_DB) as database:
            database.execute(
                "CREATE TABLE IF NOT EXISTS jobs "
                "(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL NOT NULL)"
            )
            database.execute(
                "CREATE TABLE IF NOT EXISTS activity "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, text TEXT NOT NULL)"
            )
            rows = database.execute(
                "SELECT id, data FROM jobs ORDER BY updated DESC LIMIT ?", (MAX_JOB_HISTORY,)
            )
            for job_id, raw_data in rows:
                try:
                    restored = json.loads(raw_data)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(restored, dict):
                    continue
                restored["id"] = job_id
                raw_log = restored.get("log", "")
                redacted_log = safe_log_text(raw_log) if isinstance(raw_log, str) else ""
                log_was_redacted = redacted_log != raw_log
                restored["log"] = redacted_log
                if restored.get("status") in ACTIVE_JOB_STATUSES:
                    restored.update(
                        status="interrupted",
                        phase="Interrupted by service restart",
                        error="The web service restarted before this job completed",
                        finished=time.time(),
                    )
                    database.execute(
                        "UPDATE jobs SET data = ?, updated = ? WHERE id = ?",
                        (json.dumps(restored), restored["finished"], job_id),
                    )
                elif log_was_redacted:
                    database.execute(
                        "UPDATE jobs SET data = ? WHERE id = ?",
                        (json.dumps(restored), job_id),
                    )
                with job_lock:
                    jobs.setdefault(job_id, restored)
            database.execute(
                "DELETE FROM jobs WHERE id NOT IN "
                "(SELECT id FROM jobs ORDER BY updated DESC LIMIT ?)",
                (MAX_JOB_HISTORY,),
            )
        store_initialized = True


def persist_job(job_id: str, *, min_interval: float = 0.0) -> None:
    initialize_job_store()
    now = time.monotonic()
    with job_lock:
        job = jobs.get(job_id)
        if job is None:
            return
        if min_interval and now - job_persisted_at.get(job_id, 0.0) < min_interval:
            return
        snapshot = public_job(job)
        job_persisted_at[job_id] = now
    updated = float(snapshot.get("updated", time.time()))
    with store_lock, sqlite3.connect(JOB_DB) as database:
        database.execute(
            "INSERT INTO jobs (id, data, updated) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated = excluded.updated",
            (job_id, json.dumps(snapshot), updated),
        )
        database.execute(
            "DELETE FROM jobs WHERE id NOT IN "
            "(SELECT id FROM jobs ORDER BY updated DESC LIMIT ?)",
            (MAX_JOB_HISTORY,),
        )
    with job_lock:
        removable = sorted(
            (job for job in jobs.values() if job.get("status") not in ACTIVE_JOB_STATUSES),
            key=lambda item: item.get("updated", 0),
        )
        while len(jobs) > MAX_JOB_HISTORY and removable:
            oldest = removable.pop(0)
            removed_id = oldest.get("id")
            if removed_id:
                jobs.pop(removed_id, None)
                job_persisted_at.pop(removed_id, None)

LIST_OPTIONS = {
    "repo": "--repo", "bridging_fixes": "--bridging-fixes",
    "pkglist": "--pkglist", "remove_packages": "--remove-packages",
    "only_support_pids": "--only-support-pids",
}
PATH_OPTIONS = {
    "iso": "--iso", "xrconfig": "--xrconfig", "ztp_ini": "--ztp-ini",
    "script": "--script", "key_request": "--key-request",
    "yamlfile": "--yamlfile", "ownership_vouchers": "--ownership-vouchers",
    "ownership_certificate": "--ownership-certificate",
}
BOOL_OPTIONS = {
    "no_label": "--no-label", "create_checksum": "--create-checksum",
    "x86_only": "--x86-only", "migration": "--migration",
    "optimize": "--optimize", "full_iso": "--full-iso",
    "skip_usb_image": "--skip-usb-image",
    "clear_bridging_fixes": "--clear-bridging-fixes",
    "verbose_dep_check": "--verbose-dep-check", "debug": "--debug",
    "clear_key_request": "--clear-key-request",
    "clear_ownership_vouchers": "--clear-ownership-vouchers",
    "clear_ownership_certificate": "--clear-ownership-certificate",
    "no_buildinfo": "--no-buildinfo",
}


def safe_data_path(value: str) -> Path:
    value = value.strip().lstrip("/")
    path = (DATA / value).resolve()
    if path != DATA and DATA not in path.parents:
        raise ValueError("Path escapes the mounted input directory")
    if not path.exists():
        raise ValueError(f"Input does not exist: {value}")
    return path


def json_object() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadRequest("Request body must be a JSON object")
    return body


def validate_build_payload(body: dict) -> dict:
    payload = dict(body)
    for key in set(PATH_OPTIONS) | {"label", "platform"}:
        value = payload.get(key, "")
        if not isinstance(value, str):
            raise TypeError(f"{key} must be a string")
        if len(value) > 4096:
            raise ValueError(f"{key} is too long")
    for key in LIST_OPTIONS:
        values = payload.get(key, [])
        if (not isinstance(values, list) or len(values) > 10000
                or not all(isinstance(value, str) and len(value) <= 4096 for value in values)):
            raise ValueError(f"{key} must be a list of strings")
    for key in set(BOOL_OPTIONS) | {"auto_repo", "automatic_smu_selection"}:
        if key in payload and not isinstance(payload[key], bool):
            raise ValueError(f"{key} must be true or false")
    if "confirmed_plan_fingerprint" in payload:
        value = payload["confirmed_plan_fingerprint"]
        if not isinstance(value, str) or len(value) > 128:
            raise ValueError("confirmed_plan_fingerprint must be a string")
    return payload


def rel_data(path: Path) -> str:
    return str(path.relative_to(DATA))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_checksums(path: Path) -> dict[str, str]:
    with checksum_lock:
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
        if key in checksum_cache:
            return checksum_cache[key]
        md5 = hashlib.md5(usedforsecurity=False)
        sha256 = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                md5.update(chunk)
                sha256.update(chunk)
        result = {"md5": md5.hexdigest(), "sha256": sha256.hexdigest()}
        if len(checksum_cache) >= 4096:
            checksum_cache.pop(next(iter(checksum_cache)))
        checksum_cache[key] = result
        return result


ISO_MDATA_X86_64_LIST = re.compile(
    r"^x86_64 supported arch list:\s*(?P<value>\S.*)$", re.IGNORECASE | re.MULTILINE
)
ISO_MDATA_ARM_LIST = re.compile(
    r"^arm supported arch list:\s*(?P<value>\S.*)$", re.IGNORECASE | re.MULTILINE
)


def iso_architectures_from_mdata(text: str) -> frozenset[str]:
    """Read the canonical arch families straight from an eXR ``iosxr_image_mdata.yml``.

    Upstream (src/exrmod/gisobuild_exr_engine.py) reads this file's "x86_64
    supported arch list" / "arm supported arch list" keys as the authoritative
    processor-family membership for the ISO. A narrow key match, not a full
    YAML parse, is used deliberately: this text comes from inside an uploaded
    ISO and a full parse of untrusted, unbounded content is unnecessary risk
    when only two known keys are needed.
    """
    architectures: set[str] = set()
    if ISO_MDATA_X86_64_LIST.search(text):
        architectures.add("x86_64")
    if ISO_MDATA_ARM_LIST.search(text):
        architectures.add("aarch64")
    return frozenset(architectures)


# Each "rpms in <type> ISO:" key lists the packages that ISO section ships, as
# space-separated "<name>-<version>-r<release>" tokens which YAML may wrap onto
# following indented lines. Validated 2026-09-17 against a real licensed
# NCS5500 25.1.2 image - see 07-BUG-AUDIT-TODO.md, "The base ISO already tells
# us which packages/versions it ships".
ISO_MDATA_SHIPPED_RPMS = re.compile(
    r"^\s*rpms in \S+ ISO:\s*(?P<value>\S.*(?:\n\s{2,}\S.*)*)$", re.IGNORECASE | re.MULTILINE
)
SHIPPED_RPM_TOKEN = re.compile(
    r"^(?P<name>[A-Za-z][\w.+-]*?)-(?P<version>\d[\w.]*)-r(?P<release>\d{3,6})(?P<suffix>\.\w+)?$"
)


def iso_shipped_packages_from_mdata(text: str) -> dict[str, str]:
    """Map package name -> version for everything the base ISO itself ships.

    Read from the same ``iosxr_image_mdata.yml`` the architecture keys come
    from, so this is VERIFIED data out of the image, not a filename guess.
    A later, unequal entry never overwrites an earlier one silently: the
    first version seen for a name wins and any conflict is simply ignored,
    because this is an informational inventory of the image, not a decision
    input on its own.

    Same narrow-key approach as iso_architectures_from_mdata(): no full YAML
    parse of untrusted ISO content.
    """
    shipped: dict[str, str] = {}
    for block in ISO_MDATA_SHIPPED_RPMS.finditer(text):
        for token in block.group("value").split():
            match = SHIPPED_RPM_TOKEN.match(token.strip())
            if match:
                shipped.setdefault(match.group("name"), match.group("version"))
    return shipped


RPM_QUERY_FORMAT = (
    "NVRA %{NAME}|%{VERSION}|%{RELEASE}|%{ARCH}\n"
    "[REQ %{REQUIRENAME}|%{REQUIREFLAGS:depflags}|%{REQUIREVERSION}\n]"
    "[PRV %{PROVIDENAME}|%{PROVIDEFLAGS:depflags}|%{PROVIDEVERSION}\n]"
)


def rpm_dependency_metadata(rpm_path: Path) -> dict:
    """Read one RPM's own identity and Requires/Provides from its header.

    One `rpm -qp --nosignature --qf ...` call per file, which only *reads* the
    file - it never installs anything and never touches an RPM database.
    Returns {"identity": {name, version, release, arch} | None,
    "requires": [(name, version)], "provides": [(name, version)]}, keeping
    only exact-version ("=") dependency entries, because those are the only
    ones this app acts on (see missing_package_dependencies()).

    On any failure identity is None and both lists are empty - a package whose
    header cannot be read must never be treated as "has no dependencies" *or*
    as broken; callers simply have no ground truth for it and leave it alone.
    """
    empty: dict = {"identity": None, "requires": [], "provides": []}
    with checksum_lock:
        try:
            stat = rpm_path.stat()
        except OSError:
            return empty
        key = (str(rpm_path), stat.st_size, stat.st_mtime_ns)
        if key in rpm_metadata_cache:
            return rpm_metadata_cache[key]
    try:
        completed = subprocess.run(
            [RPM_BIN, "-qp", "--nosignature", "--qf", RPM_QUERY_FORMAT, str(rpm_path)],
            capture_output=True, text=True, timeout=RPM_QUERY_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return empty
    if completed.returncode != 0:
        return empty
    result: dict = {"identity": None, "requires": [], "provides": []}
    for line in completed.stdout[:MAX_ISO_INSPECTION_OUTPUT_BYTES].splitlines():
        tag, _, body = line.partition(" ")
        fields = body.split("|")
        if tag == "NVRA" and len(fields) == 4 and all(fields):
            result["identity"] = dict(zip(("name", "version", "release", "arch"), fields))
        elif tag in {"REQ", "PRV"} and len(fields) == 3:
            name, operator, version = (field.strip() for field in fields)
            # Only "=" constraints: a bare name, ">=" or "<" cannot be proven
            # unsatisfiable from the facts available here. Epoch-qualified
            # versions are skipped rather than compared imprecisely.
            if operator == "=" and version and ":" not in version:
                result["requires" if tag == "REQ" else "provides"].append((name, version))
    with checksum_lock:
        if len(rpm_metadata_cache) >= 4096:
            rpm_metadata_cache.pop(next(iter(rpm_metadata_cache)))
        rpm_metadata_cache[key] = result
    return result


def rpm_filename_mismatch(rpm_path: Path) -> str | None:
    """The canonical filename an RPM's own header implies, if its real name differs.

    Every automatic decision here - platform, release, architecture, CSC group -
    is read from the filename, following RPM's standard
    ``NAME-VERSION-RELEASE.ARCH.rpm`` naming. If a file was renamed (or is a
    different package than its name claims), all of those decisions are made
    about a package that is not actually inside it. Returns ``None`` when the
    name matches, and also when the header cannot be read at all: no ground
    truth means no claim, never an exclusion.
    """
    if rpm_path.name.lower().endswith(".src.rpm"):
        return None
    identity = rpm_dependency_metadata(rpm_path).get("identity")
    if not identity:
        return None
    canonical = (f"{identity['name']}-{identity['version']}-"
                 f"{identity['release']}.{identity['arch']}.rpm")
    return None if canonical == rpm_path.name else canonical


def _version_satisfies(provided: str, required: str) -> bool:
    """True when a Provides version answers an exact "= required" requirement.

    RPM compares only as far as the requirement specifies, so a requirement
    of "1.0.0.2" is satisfied by a provide of "1.0.0.2-r2512.CSCxxxxx" - the
    release suffix is not part of the comparison when the requirement omits
    it. Deliberately string-based rather than a reimplementation of RPM's
    version ordering: this only ever answers "equal (ignoring release)",
    never "newer than", so there is no ordering to get wrong.
    """
    return provided == required or provided.startswith(f"{required}-")


def missing_package_dependencies(
    selected: list[dict], iso_shipped: dict[str, str]
) -> list[dict[str, str]]:
    """Find requirements that provably cannot be satisfied, before the build runs.

    This is the pre-build counterpart to parse_missing_dependencies(), which
    only explains the same failure *after* gisobuild reports it. It is
    deliberately narrow, because a false "this will fail" is worse than a
    missed prediction - it would block a build that actually works. A
    requirement is only reported when all of these hold:

      1. It carries an exact "=" version constraint (a bare name or a ">="
         range cannot be disproven from this data).
      2. Its name is one the base ISO's own metadata says the image ships,
         so there is VERIFIED ground truth about it. Anything else - file
         paths, shared libraries, optional packages the image never mentions
         - is out of scope and ignored.
      3. The version the base image ships is not the version required.
      4. No selected RPM Provides that name at that version.

    Under those four conditions the conclusion is not a guess: the image has
    the package at one version, something needs a different one, and nothing
    in the selection supplies it - exactly what RPM's own transaction check
    reports as "<requirement> is needed by <package>".

    One known imprecision, in "required_by" only, never in whether to block:
    RPM resolves a transaction to the newest candidate per package name, so a
    superseded sibling in the same selection (e.g. routing 1.0.0.2 alongside
    routing 1.0.0.3) never reaches its own dependency evaluation upstream.
    This lists every selected package that *declares* the requirement, which
    can therefore name more packages than gisobuild's log does. Modelling
    RPM's newest-wins selection here would mean reimplementing RPM version
    ordering - the thing _version_satisfies() deliberately avoids - for a
    cosmetic gain, so the attribution is deliberately over-inclusive rather
    than approximated.
    """
    if not iso_shipped:
        return []
    provided: dict[str, set[str]] = {
        name: {version} for name, version in iso_shipped.items()
    }
    requirements: list[tuple[str, str, str]] = []
    for item in selected:
        try:
            metadata = rpm_dependency_metadata(safe_data_path(item["relative_path"]))
        except (OSError, ValueError):
            continue
        for name, version in metadata["provides"]:
            provided.setdefault(name, set()).add(version)
        for name, version in metadata["requires"]:
            requirements.append((name, version, item["basename"]))

    missing: dict[tuple[str, str], dict] = {}
    for name, version, required_by in requirements:
        if name not in iso_shipped:
            continue
        if any(_version_satisfies(candidate, version)
               for candidate in provided.get(name, set())):
            continue
        entry = missing.setdefault((name, version), {
            "requirement": f"{name} = {version}",
            "required_by": [],
            "base_image_has": iso_shipped[name],
        })
        # Every package that needs it, not just the first one found: the
        # operator has to decide what to remove or fetch, and "three of your
        # SMUs need this" is a different decision from "one does".
        if required_by not in entry["required_by"]:
            entry["required_by"].append(required_by)
    for entry in missing.values():
        entry["required_by"].sort()
    return explain_with_prerequisites(
        sorted(missing.values(), key=lambda entry: entry["requirement"])
    )


def iso_architectures_from_listing(text: str) -> frozenset[str]:
    """Fall back to the ISO's own RPM repository when no eXR metadata file exists.

    LNT images carry their RPM repository directly on the ISO with the plain
    x86_64/aarch64/arm64 filename suffix, so the same RPM_ARCHITECTURE
    resolver used for operator-selected RPMs applies here.
    """
    architectures: set[str] = set()
    for line in text.splitlines():
        name = line.strip().split(";")[0].strip()
        if not name.lower().endswith(".rpm"):
            continue
        match = RPM_ARCHITECTURE.search(name)
        if match:
            canonical = normalize_architecture(match.group("architecture"))
            if canonical:
                architectures.add(canonical)
    return frozenset(architectures)


def inspect_iso_architecture(iso_path: Path) -> frozenset[str]:
    """Best-effort processor-architecture detection straight from the ISO contents.

    Returns an empty frozenset when detection is inconclusive (missing
    isoinfo, an ISO format isoinfo cannot read, or no recognizable RPM
    architecture suffixes). Callers must treat an empty result as "unknown",
    never as "no architecture", so an upstream-valid image is never blocked
    solely because local inspection failed.
    """
    with checksum_lock:
        stat = iso_path.stat()
        key = (str(iso_path), stat.st_size, stat.st_mtime_ns)
        if key in iso_architecture_cache:
            return iso_architecture_cache[key]
    architectures = frozenset()
    try:
        mdata = subprocess.run(
            [ISOINFO_BIN, "-R", "-i", str(iso_path), "-x", "/iosxr_image_mdata.yml"],
            capture_output=True, text=True, timeout=ISO_MDATA_TIMEOUT_SECONDS, check=False,
        )
        if mdata.returncode == 0 and mdata.stdout.strip():
            architectures = iso_architectures_from_mdata(mdata.stdout[:MAX_ISO_INSPECTION_OUTPUT_BYTES])
        if not architectures:
            listing = subprocess.run(
                [ISOINFO_BIN, "-R", "-l", "-i", str(iso_path)],
                capture_output=True, text=True, timeout=ISO_LISTING_TIMEOUT_SECONDS, check=False,
            )
            if listing.returncode == 0:
                architectures = iso_architectures_from_listing(
                    listing.stdout[:MAX_ISO_INSPECTION_OUTPUT_BYTES]
                )
    except (OSError, subprocess.SubprocessError):
        architectures = frozenset()
    with checksum_lock:
        if len(iso_architecture_cache) >= 256:
            iso_architecture_cache.pop(next(iter(iso_architecture_cache)))
        iso_architecture_cache[key] = architectures
    return architectures


def read_iso_mdata(iso_path: Path) -> str:
    """The base ISO's own ``iosxr_image_mdata.yml`` text, capped, or "" if unavailable.

    One cached read shared by every fact derived from that file (shipped
    packages, image identity), so a page load does not spawn isoinfo once per
    fact. "" means "no metadata here" - an LNT image, a non-ISO, or a read
    failure - and every consumer must treat it as absence of ground truth.
    """
    with checksum_lock:
        stat = iso_path.stat()
        key = (str(iso_path), stat.st_size, stat.st_mtime_ns)
        if key in iso_mdata_cache:
            return iso_mdata_cache[key]
    text = ""
    try:
        mdata = subprocess.run(
            [ISOINFO_BIN, "-R", "-i", str(iso_path), "-x", "/iosxr_image_mdata.yml"],
            capture_output=True, text=True, timeout=ISO_MDATA_TIMEOUT_SECONDS, check=False,
        )
        if mdata.returncode == 0 and mdata.stdout.strip():
            text = mdata.stdout[:MAX_ISO_INSPECTION_OUTPUT_BYTES]
    except (OSError, subprocess.SubprocessError):
        text = ""
    with checksum_lock:
        if len(iso_mdata_cache) >= 256:
            iso_mdata_cache.pop(next(iter(iso_mdata_cache)))
        iso_mdata_cache[key] = text
    return text


def inspect_iso_shipped_packages(iso_path: Path) -> dict[str, str]:
    """Package name -> version for what the base ISO itself ships, or {} if unknown.

    {} must be read as "no ground truth", never as "ships nothing".
    """
    return iso_shipped_packages_from_mdata(read_iso_mdata(iso_path))


ISO_MDATA_IDENTITY_NAME = re.compile(r"^\s+name:\s*(?P<name>[\w.+-]+)\s*$")


def iso_identity_from_mdata(text: str) -> str | None:
    """The image's own name from the top-level ``iso_mdata:`` block, if present.

    Real eXR images carry an ``iso_mdata:`` block whose indented ``name:``
    is e.g. ``ncs5500-mini-x-25.1.2`` (validated 2026-09-17 against a
    licensed NCS5500 image). Only the ``iso_mdata`` block is read: the later ``iso_rpms`` list
    also has ``name:`` lines (``host-25.1.2``) that must not be mistaken for
    the image identity.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.rstrip() != "iso_mdata:":
            continue
        for following in lines[index + 1:]:
            if not following.startswith((" ", "\t")):
                return None
            match = ISO_MDATA_IDENTITY_NAME.match(following)
            if match:
                return match.group("name")
        return None
    return None


def iso_identity(iso_path: Path) -> tuple[str, bool]:
    """Name to infer platform/release from, and whether it came from the image itself.

    Prefers the ISO's own metadata over its filename: an operator can rename
    a file on disk, but the image's embedded identity cannot drift that way.
    Only used when the metadata name actually resolves to a known platform
    *and* a release - otherwise the filename is kept, so this can only ever
    add information, never replace a working filename match with a worse one.
    """
    try:
        name = iso_identity_from_mdata(read_iso_mdata(iso_path))
    except OSError:
        name = None
    if name and infer_platform(name) and ISO_RELEASE.search(name):
        return f"{name}.iso", True
    return iso_path.name, False


def dependency_blocker_text(entry: dict) -> str:
    """One operator-facing line per unsatisfiable requirement, shared by every gate."""
    action = (
        f"download Cisco SMU {entry['prerequisite_smu']}, which the README of "
        f"{entry['listed_by']} lists as its prerequisite for "
        f"{entry['requirement'].split(' = ')[0]}"
        if entry.get("prerequisite_smu")
        else f"download the Cisco SMU that provides {entry['requirement']}"
    )
    return (
        f"{entry['requirement']} is required by {', '.join(entry['required_by'])}, "
        f"but the base image ships {entry['requirement'].split(' = ')[0]} "
        f"{entry['base_image_has']} and no selected package provides it — {action}"
    )


def unsatisfied_dependencies_for_recommendation(iso_relative_path: str, selected_names: list[str]) -> list[dict]:
    """Run the pre-build dependency check for a Step 2 preview selection.

    create_build_plan() has resolved inventory records to work with; the live
    review only has basenames, so resolve them here. Any name that cannot be
    resolved is skipped rather than guessed at - the authoritative gate in
    create_build_plan() re-runs this against the real resolved selection
    before a build can start either way.
    """
    if not selected_names:
        return []
    try:
        iso_path = safe_data_path(iso_relative_path)
        if not iso_path.is_file():
            return []
        shipped = inspect_iso_shipped_packages(iso_path)
    except (OSError, ValueError):
        return []
    by_name = {item["basename"]: item for item in inventory_files() if item["type"] == ".rpm"}
    selected = [by_name[name] for name in selected_names if name in by_name]
    return missing_package_dependencies(selected, shipped)


def inventory_id(relative_path: str, sha256: str) -> str:
    """Return an opaque, stable identity without exposing an absolute path."""
    identity = hashlib.sha256(f"{relative_path}\0{sha256}".encode()).hexdigest()
    return f"file_{identity[:24]}"


def file_metadata_provenance(path: Path) -> tuple[str, str, str | None]:
    """Where this file's platform/release identity comes from: (source, confidence, name).

    "high" only when the artifact's own embedded metadata confirmed it - an
    RPM header whose NAME-VERSION-RELEASE.ARCH equals the filename, or an ISO
    whose iosxr_image_mdata.yml names a known platform and release.
    "mismatch" when the header contradicts the filename (name is what the
    header says). Everything else is "low": identity is the filename alone.
    Both readers are cached by path, size and mtime.
    """
    suffix = path.suffix.lower()
    if suffix == ".rpm" and not path.name.lower().endswith(".src.rpm"):
        identity = rpm_dependency_metadata(path).get("identity")
        if identity:
            canonical = rpm_filename_mismatch(path)
            if canonical:
                return "rpm-header", "mismatch", canonical
            return "rpm-header", "high", None
    elif suffix == ".iso":
        try:
            name, from_metadata = iso_identity(path)
        except OSError:
            from_metadata = False
        if from_metadata:
            return "iso-metadata", "high", name
    return "filename", "low", None


def inventory_files() -> list[dict]:
    """Build the canonical, browser-safe inventory for supported input files."""
    supported = {".iso", ".rpm", *ARCHIVE_SUFFIXES, ".yaml", ".yml", ".cfg",
                 ".ini", ".sh", ".cms", ".json"}
    physical: list[dict] = []
    for root, names, filenames in os.walk(DATA):
        names[:] = [name for name in names
                    if name != ".parts" and not name.startswith("output_gisobuild")]
        root_path = Path(root)
        for name in filenames:
            path = root_path / name
            suffix = archive_suffix(name) or path.suffix.lower()
            if suffix not in supported:
                continue
            try:
                relative_path = rel_data(path)
                stat = path.stat()
                sha256 = file_checksums(path)["sha256"]
            except OSError:
                continue
            extraction_dir = top_level_extraction_dir(path)
            source_archive = archive_source_for_extraction(extraction_dir) if extraction_dir else None
            metadata_source, metadata_confidence, metadata_name = file_metadata_provenance(path)
            physical.append({
                "id": inventory_id(relative_path, sha256),
                "basename": name,
                "path": relative_path,
                "relative_path": relative_path,
                "size": stat.st_size,
                "sha256": sha256,
                "source": "tar" if path.parent != DATA else "upload",
                "extracted_from": source_archive.name if source_archive else None,
                "metadata_source": metadata_source,
                "metadata_confidence": metadata_confidence,
                "metadata_name": metadata_name,
                "lifecycle": "READY",
                "type": suffix,
            })

    by_basename: dict[str, list[dict]] = {}
    for item in physical:
        by_basename.setdefault(item["basename"], []).append(item)
    for group in by_basename.values():
        hashes = {item["sha256"] for item in group}
        paths = sorted(item["relative_path"] for item in group)
        for item in group:
            item["duplicate"] = len(group) > 1
            item["duplicate_kind"] = (
                "conflict" if len(hashes) > 1 else "identical" if len(group) > 1 else None
            )
            item["provenance"] = paths
    return sorted(physical, key=lambda item: item["relative_path"])


def resolve_rpm_identifiers(identifiers: list[str]) -> list[dict]:
    """Resolve opaque inventory IDs, retaining legacy exact basenames temporarily."""
    rpms = [item for item in inventory_files() if item["type"] == ".rpm"]
    by_id = {item["id"]: item for item in rpms}
    by_name: dict[str, list[dict]] = {}
    for item in rpms:
        by_name.setdefault(item["basename"], []).append(item)
    resolved: list[dict] = []
    for identifier in identifiers:
        if identifier in by_id:
            resolved.append(by_id[identifier])
            continue
        if Path(identifier).name != identifier or glob_metacharacters(identifier):
            raise ValueError(f"RPM package must be an inventory ID or exact filename: {identifier!r}")
        matches = by_name.get(identifier, [])
        if not matches:
            raise ValueError(f"RPM {identifier!r} was not found")
        if len({item["sha256"] for item in matches}) > 1:
            raise ValueError(
                f"Different RPM files share the name {identifier!r}; select a specific inventory item"
            )
        resolved.append(matches[0])
    selected_by_name: dict[str, set[str]] = {}
    for item in resolved:
        selected_by_name.setdefault(item["basename"], set()).add(item["sha256"])
    conflicts = [name for name, hashes in selected_by_name.items() if len(hashes) > 1]
    if conflicts:
        raise ValueError("Conflicting RPM identities selected: " + ", ".join(sorted(conflicts)))
    return resolved


def package_names_for_validation(identifiers: list[str]) -> list[str]:
    """Translate known inventory IDs while allowing filename-only preflight input."""
    by_id = {item["id"]: item["basename"] for item in inventory_files()
             if item["type"] == ".rpm"}
    return [by_id.get(identifier, identifier) for identifier in identifiers]


def current_inventory_revision(items: list[dict] | None = None) -> str:
    """Fingerprint the exact ready inventory snapshot used for preflight."""
    inventory = items if items is not None else inventory_files()
    state = [{"id": item["id"], "lifecycle": item["lifecycle"]} for item in inventory]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:24]


def confidence_report(*, resolved_platform: str | None, platform_manual: bool,
                      release: str | None, iso_architectures: frozenset[str],
                      package_groups: list, has_rpm_selection: bool,
                      matched_pid: str | None = None,
                      identity_from_metadata: bool = False) -> dict:
    """Report how each detected fact was derived, never presenting a guess as verified.

    Only iso_architecture is read from the artifact's own contents (see
    inspect_iso_architecture) and can honestly be called VERIFIED. Platform,
    release, RPM architecture and CSC grouping are all read from filenames,
    so they stay INFERRED even when the operator picked the platform
    manually; dependency closure is never computed here at all.

    A platform of exr-generic/lnt-generic is a third case, distinct from
    both: it is not a filename guess (INFERRED) and not a real, named
    platform the operator confirmed (which would still show INFERRED,
    since even a manual pick of a *known* platform isn't independently
    verified against the ISO's own metadata) - it is the operator
    explicitly declaring "I know this is eXR/LNT, I cannot name the exact
    platform," which is a fundamentally different kind of uncertainty and
    must not be shown identically to a filename match that merely happens
    to be correct.
    """
    platform_is_generic = resolved_platform in GENERIC_PLATFORM_IDS
    # identity_from_metadata: platform and release were read from the image's
    # own iosxr_image_mdata.yml (see iso_identity()), not its filename, so they
    # earn VERIFIED - unless the operator overrode the platform, in which case
    # the platform shown is theirs, not the image's.
    platform_verified = identity_from_metadata and not platform_manual and bool(resolved_platform)
    if platform_is_generic:
        platform_value = "MANUAL"
    elif platform_verified:
        platform_value = "VERIFIED"
    else:
        platform_value = "INFERRED" if resolved_platform else "UNKNOWN"
    if platform_is_generic:
        platform_detail = ("The operator declared a generic engine profile; the real platform "
                           "identity is unverified and no platform-specific capabilities apply.")
    elif platform_verified:
        platform_detail = "Read from the ISO's own embedded image metadata, not its filename."
    else:
        platform_detail = ("Not cross-checked against ISO metadata; select it manually in Expert "
                           "settings if the filename guess is wrong.")
    if matched_pid and not platform_is_generic:
        platform_detail += f" Matched hardware PID/SKU spelling: {matched_pid.upper()}."
    release_verified = identity_from_metadata and bool(release)
    return {
        "platform": {
            "value": platform_value,
            "source": ("operator-selected" if platform_manual
                       else "iso-metadata" if platform_verified
                       else "iso-filename-pattern" if resolved_platform else "none"),
            "pid": matched_pid,
            "detail": platform_detail,
        },
        "release": {
            "value": "VERIFIED" if release_verified else "INFERRED" if release else "UNKNOWN",
            "source": "iso-metadata" if release_verified else "iso-filename-pattern",
            "detail": ("Read from the ISO's own embedded image metadata, not its filename."
                       if release_verified else
                       "Read from the ISO filename's release tag; not parsed from ISO metadata."),
        },
        "iso_architecture": {
            "value": "VERIFIED" if iso_architectures else "UNKNOWN",
            "source": "iso-contents" if iso_architectures else "none",
            "detail": "Read directly from the ISO's own metadata/RPM listing."
                      if iso_architectures else
                      "Could not be determined from the ISO's contents (isoinfo unavailable, "
                      "unreadable image, or no recognizable architecture markers).",
        },
        "package_architecture": {
            "value": "INFERRED" if has_rpm_selection else "UNKNOWN",
            "source": "rpm-filename-suffix",
            "detail": "Read from each RPM filename's architecture suffix; not parsed from the "
                      "RPM header.",
        },
        "csc_groups": {
            "value": "INFERRED" if package_groups else "UNKNOWN",
            "source": "rpm-filename-pattern",
            "detail": "CSC identifiers and component grouping are read from RPM filenames.",
        },
        "dependency_closure": {
            "value": "UNKNOWN",
            "source": "none",
            "detail": "Filename checks cannot prove RPM dependencies; Cisco gisobuild performs "
                      "the authoritative dependency check during the build.",
        },
    }


ISO9660_SIGNATURE_OFFSET = 16 * 2048 + 1  # first volume descriptor's "CD001" identifier


def is_iso9660_image(path: Path) -> bool:
    """Whether a file carries the ISO 9660 primary volume descriptor signature.

    Every IOS XR base image - eXR and LNT, plain or hybrid-bootable - is an
    ISO 9660 filesystem, which always has "CD001" at byte 32769. Checking
    five bytes costs nothing and turns "renamed a tarball to .iso" from a
    build that fails minutes into gisobuild into a blocker before it starts.
    Unreadable counts as not valid: the build could not read it either.
    """
    try:
        with path.open("rb") as handle:
            handle.seek(ISO9660_SIGNATURE_OFFSET)
            return handle.read(5) == b"CD001"
    except OSError:
        return False


def gisobuild_tool_available() -> bool:
    """The pinned gisobuild checkout build_command() mounts into the builder."""
    return (TOOL / "src/gisobuild.py").is_file()


def build_environment_blockers() -> tuple[list[str], list[str]]:
    """Everything outside the inventory that decides whether a build can start now.

    create_job() has always refused a build while an upload, a Cisco download
    or another build was active, and build_command() needs gisobuild and the
    Docker CLI - but none of that was part of the BuildPlan, so Step 2 could
    report "ready" for a build Start would then refuse. Folding these checks
    in here makes create_build_plan() the one preflight that decides; the
    identical checks in create_job() remain as the race-safe gate under
    operation_lock.

    isoinfo and rpm are warnings, not blockers: without them this app cannot
    read ISO/RPM metadata and falls back to filenames, but gisobuild itself
    does not need them and still validates the real transaction.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    if not gisobuild_tool_available():
        blockers.append(f"gisobuild is not available ({TOOL / 'src/gisobuild.py'} is missing)")
    if not os.access(DOCKER_BIN, os.X_OK):
        blockers.append(f"The Docker CLI is not available at {DOCKER_BIN}")
    elif docker_build_running():
        blockers.append("A build container is already running, or Docker cannot be reached "
                        "to confirm that none is")
    if cisco_download_running():
        blockers.append("Wait for the Cisco download to finish before starting a build")
    with upload_lock:
        if uploads:
            blockers.append("Wait for all uploads to finish before starting the build")
    with job_lock:
        if any(j["status"] in ACTIVE_JOB_STATUSES for j in jobs.values()):
            blockers.append("A build is already running")
    for label, binary in (("isoinfo", ISOINFO_BIN), ("rpm", RPM_BIN)):
        if not os.access(binary, os.X_OK):
            warnings.append(f"{label} is not available at {binary}; ISO/RPM metadata checks "
                            f"fall back to filenames")
    return blockers, warnings


def create_build_plan(payload: dict) -> dict:
    """Create one immutable, backend-owned build decision from current inventory."""
    inventory = inventory_files()
    revision = current_inventory_revision(inventory)
    blockers, warnings = build_environment_blockers()
    if bool(payload.get("ownership_vouchers")) != bool(payload.get("ownership_certificate")):
        # Mirrors _validate_ovs_and_oc() in .gisobuild-tool/src/lnt/builder/_coordinate.py:
        # gisobuild requires both an ownership certificate and ownership
        # vouchers to be present in the final image, or neither. This is a
        # warning, not a blocker, because the base ISO may already carry the
        # other one from an earlier build - giso-webui cannot see the ISO's
        # existing package groups without real ISO content inspection (see
        # the isols.py investigation in 02-AUTOMATION-BUILDPLAN-TODO.md), so
        # flatly rejecting one-without-the-other here would produce false
        # positives gisobuild itself would have accepted.
        warnings.append(
            "Ownership vouchers and an ownership certificate are normally supplied "
            "together; gisobuild rejects one without the other unless the base ISO "
            "already carries the missing one from an earlier build."
        )
    iso_name = payload.get("iso", "")
    iso = next((item for item in inventory
                if item["type"] == ".iso" and item["relative_path"] == iso_name), None)
    if not iso:
        blockers.append("Select one ISO that exists in the current inventory")

    recommendation = {"selected": [], "excluded": [], "package_groups": [],
                      "component_conflicts": []}
    selected: list[dict] = []
    profile = None
    iso_architectures: frozenset[str] = frozenset()
    identity_name, identity_from_metadata = iso_name, False
    if iso:
        identifiers = payload.get("pkglist", [])
        # Same check discover(), /api/smu-recommendation, /api/compatibility, and
        # build_command() already apply - the preview and the actual build must
        # agree on whether a build is ready, not just build_command() as a
        # second, later gate.
        iso_path = safe_data_path(iso["relative_path"])
        if not is_iso9660_image(iso_path):
            blockers.append(
                f"{iso['relative_path']} is not an ISO 9660 image (no CD001 volume descriptor); "
                "upload the Cisco base ISO itself, not an archive or a renamed file"
            )
        iso_architectures = inspect_iso_architecture(iso_path)
        identity_name, identity_from_metadata = iso_identity(iso_path)
        candidates, superseded = active_rpm_names()
        if payload.get("automatic_smu_selection"):
            recommendation = recommend_smu_selection(
                identity_name, candidates, iso_architectures=iso_architectures
            )
            recommendation = add_superseded_exclusions(recommendation, superseded)
            if recommendation.get("ready"):
                identifiers = recommendation["selected"]
            else:
                blockers.append(recommendation["message"])
        try:
            selected = resolve_rpm_identifiers(identifiers)
            profile = validate_platform_options({**payload, "iso": identity_name})
            compatibility = validate_smu_selection(
                identity_name, [item["basename"] for item in selected],
                iso_architectures=iso_architectures,
                full_candidate_packages=candidates,
            )
            blockers.extend(compatibility["issues"])
            warnings.extend(compatibility["warnings"])
            blockers.extend(selection_integrity_blockers([item["basename"] for item in selected]))
            if not recommendation["package_groups"]:
                recommendation["package_groups"] = compatibility["package_groups"]
                recommendation["component_conflicts"] = compatibility["component_conflicts"]
        except ValueError as exc:
            blockers.append(str(exc))

    # Dependency pre-check. Only fires on requirements that are provably
    # unsatisfiable against the base image's own metadata (see
    # missing_package_dependencies()); anything it cannot prove, gisobuild's
    # real RPM transaction still checks during the build, and
    # parse_missing_dependencies() explains the outcome.
    unsatisfied = []
    if iso and selected:
        unsatisfied = missing_package_dependencies(
            selected, inspect_iso_shipped_packages(safe_data_path(iso["relative_path"]))
        )
        blockers.extend(dependency_blocker_text(entry) for entry in unsatisfied)

    # The estimate the Step 2 UI already showed (base ISO + selected RPMs) is
    # the best lower bound available for what this build has to write, so use
    # the same figure for the real gate rather than inventing a second one.
    estimated_output_bytes = (iso["size"] if iso else 0) + sum(
        item.get("size", 0) for item in selected
    )
    blockers.extend(build_space_blockers(estimated_output_bytes))

    release = recommendation.get("release") or (
        validate_smu_selection(identity_name, [])["iso_release"] if iso else None
    )
    resolved_platform = (profile["id"] if profile else None) or recommendation.get("platform")
    confidence = confidence_report(
        resolved_platform=resolved_platform,
        platform_manual=bool(payload.get("platform")),
        release=release,
        iso_architectures=iso_architectures,
        package_groups=recommendation["package_groups"],
        has_rpm_selection=any(item.get("basename", "").lower().endswith(".rpm")
                              for item in selected),
        matched_pid=infer_platform_pid(iso_name) if iso_name else None,
        identity_from_metadata=identity_from_metadata,
    )

    option_keys = sorted(set(BOOL_OPTIONS) | set(PATH_OPTIONS) | set(LIST_OPTIONS) |
                         {"label", "platform", "auto_repo", "automatic_smu_selection"})
    options = {key: payload[key] for key in option_keys if key in payload}
    # Content, not just the path: an xrconfig edited in place (or one whose
    # suffix keeps it out of the inventory, and so out of the revision) must
    # still invalidate a plan the operator already reviewed.
    config_files: dict[str, str | None] = {}
    for key in sorted(PATH_OPTIONS.keys() - {"iso"}):
        value = payload.get(key)
        if not value:
            continue
        try:
            config_path = safe_data_path(value)
            config_files[key] = file_checksums(config_path)["sha256"] if config_path.is_file() else None
        except (OSError, ValueError):
            config_files[key] = None
    tool_commit = gisobuild_commit()
    fingerprint_input = {
        "application_version": APP_VERSION,
        "builder_image": IMAGE,
        "gisobuild_commit": tool_commit,
        "config_files": config_files,
        "inventory_revision": revision,
        "iso": {"id": iso["id"], "sha256": iso["sha256"]} if iso else None,
        "packages": [{"id": item["id"], "sha256": item["sha256"]} for item in selected],
        "options": options,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "fingerprint": fingerprint,
        "inventory_revision": revision,
        "ready": not blockers,
        "iso": iso,
        "engine": profile["engine"] if profile else None,
        "platform": profile["id"] if profile else None,
        "release": release,
        "capabilities": profile["capabilities"] if profile else {},
        "selected_packages": selected,
        "selected_csc_groups": recommendation["package_groups"],
        "excluded_packages": recommendation["excluded"],
        "component_conflicts": recommendation["component_conflicts"],
        "options": options,
        "config_files": config_files,
        "gisobuild_commit": tool_commit,
        "confidence": confidence,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "expected_outputs": {
            "iso": True,
            "usb": bool(profile and profile["capabilities"].get("usb_image")
                        and not payload.get("skip_usb_image")),
        },
        "estimated_output_bytes": estimated_output_bytes,
        "volume_free_bytes": build_volume_free_bytes(),
        "unsatisfied_dependencies": unsatisfied,
    }


def giso_artifact_candidates(job_dir: Path) -> list[Path]:
    """Return output images eligible for verified archival."""
    top_level = list(job_dir.glob("*.iso"))
    images = top_level or [
        path for path in job_dir.rglob("*.iso")
        if any(tag in path.name.lower() for tag in ("golden", "giso"))
    ]
    return images + [path for path in job_dir.rglob("*.zip") if "usb" in path.name.lower()]


def build_volume_free_bytes() -> dict[str, int]:
    """Free space on every volume a build actually touches, not just uploads.

    Every MIN_FREE_BYTES guard before this measured DATA (the uploads
    volume) exclusively, but giso-webui/compose.yaml defines giso-uploads,
    giso-work and giso-output as three separate named volumes: gisobuild
    extracts and builds in WORK and writes the finished image to OUTPUT.
    A deployment that sizes those independently could start a build with
    plenty of "free" upload space and no room to write its own output,
    failing partway through with no advance warning - see
    07-BUG-AUDIT-TODO.md.

    Volumes that resolve to the same filesystem (the common single-disk
    deployment) simply report the same number; this does not try to
    de-duplicate them, because which mount is which is exactly what an
    operator needs to see when they are *not* the same.
    """
    volumes = {"uploads": DATA, "work": WORK, "output": OUTPUT}
    free: dict[str, int] = {}
    for name, path in volumes.items():
        try:
            free[name] = shutil.disk_usage(path).free
        except OSError:
            # A volume that cannot be measured must not take the whole page
            # (or a build) down; report it as unknown and let the caller
            # decide. build_space_blockers() treats a missing key as "not
            # provably short", never as "definitely full".
            continue
    return free


def build_space_blockers(required_bytes: int = 0) -> list[str]:
    """Name every build volume that cannot fit this build, for the pre-build gate.

    Returns operator-facing strings (empty when fine) rather than raising,
    so create_build_plan() can fold them into the same blockers list every
    other pre-build problem already uses.
    """
    needed = required_bytes + MIN_FREE_BYTES
    labels = {"uploads": "uploads", "work": "build working", "output": "build output"}
    return [
        f"Not enough free space on the {labels[name]} volume: "
        f"{free // 1024**2} MiB free, {needed // 1024**2} MiB needed"
        for name, free in sorted(build_volume_free_bytes().items())
        if free < needed
    ]


def archive_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def archive_timestamp(path: Path) -> float:
    artifacts = [item for item in path.iterdir()
                 if item.is_file() and item.suffix.lower() in {".iso", ".zip"}]
    return max((item.stat().st_mtime for item in artifacts), default=path.stat().st_mtime)


@contextlib.contextmanager
def cross_process_archive_lock():
    """Serialize ARCHIVE access across processes, not just threads.

    archive_lock (a threading.RLock) only ever protected this process's own
    threads. The separate archive-maintenance container imports and calls
    enforce_archive_policy() too, on the same ARCHIVE volume, from a
    different OS process that has its own independent archive_lock object -
    which gives it zero coordination with this one. An flock() on a file
    inside ARCHIVE is the only lock primitive both processes actually share.

    flock() is not reentrant across independently opened file descriptors
    (man 2 flock), unlike archive_lock, so this keeps a single persistent
    file handle per process and only actually flocks/unflocks at the
    outermost nesting level (depth 0->1 and back), tracked under archive_lock
    exactly the way archive_lock's own reentrancy already works - every
    caller below still holds archive_lock for the full duration, so only one
    thread in this process can be inside this block at a time regardless of
    nesting.
    """
    global archive_file_lock_handle, archive_file_lock_path, archive_file_lock_depth
    with archive_lock:
        if archive_file_lock_depth == 0:
            ARCHIVE.mkdir(parents=True, exist_ok=True)
            lock_path = ARCHIVE / ".lock"
            if archive_file_lock_handle is None or archive_file_lock_path != lock_path:
                if archive_file_lock_handle is not None:
                    archive_file_lock_handle.close()
                archive_file_lock_handle = open(lock_path, "w")  # noqa: SIM115 - kept open for process lifetime
                archive_file_lock_path = lock_path
            fcntl.flock(archive_file_lock_handle, fcntl.LOCK_EX)
        archive_file_lock_depth += 1
        try:
            yield
        finally:
            archive_file_lock_depth -= 1
            if archive_file_lock_depth == 0:
                fcntl.flock(archive_file_lock_handle, fcntl.LOCK_UN)


def enforce_archive_policy(*, protected_job_id: str | None = None) -> list[str]:
    """Remove expired archive jobs, then oldest jobs until the archive fits its quota."""
    removed: list[str] = []
    cutoff = time.time() - ARCHIVE_RETENTION_DAYS * 86400
    with cross_process_archive_lock():
        if not ARCHIVE.exists():
            return removed
        job_dirs = [path for path in ARCHIVE.iterdir() if path.is_dir()]
        for job_dir in job_dirs:
            if job_dir.name == protected_job_id:
                continue
            if archive_timestamp(job_dir) < cutoff:
                shutil.rmtree(job_dir)
                removed.append(job_dir.name)
        remaining = sorted(
            (path for path in ARCHIVE.iterdir() if path.is_dir()),
            key=archive_timestamp,
        )
        total = sum(archive_size(path) for path in remaining)
        while total > MAX_ARCHIVE_BYTES and remaining:
            oldest = next((path for path in remaining if path.name != protected_job_id), None)
            if oldest is None:
                break
            remaining.remove(oldest)
            total -= archive_size(oldest)
            shutil.rmtree(oldest)
            removed.append(oldest.name)
        if removed:
            with checksum_lock:
                checksum_cache.clear()
            log_event("archive_policy_cleanup", removed_jobs=len(removed))
    return removed


def archive_giso_artifacts_and_cleanup(
    job_id: str,
    job_dir: Path,
    cleanup_paths: list[Path] | None = None,
    before_cleanup=None,
) -> list[dict]:
    """Archive verified Golden ISO and USB boot files, then remove build inputs/output."""
    candidates = giso_artifact_candidates(job_dir)
    iso_candidates = [path for path in candidates if path.suffix.lower() == ".iso"]
    if not iso_candidates:
        raise RuntimeError("No Golden ISO was produced; source files were kept")
    for source in candidates:
        if source.is_symlink() or job_dir.resolve() not in source.resolve().parents:
            raise RuntimeError(f"Unsafe build artifact: {source.name}")
    candidate_size = sum(path.stat().st_size for path in candidates)
    if candidate_size > MAX_ARCHIVE_BYTES:
        raise RuntimeError("The completed GISO artifacts exceed the archive's total size limit; source files were kept")
    archive_dir = ARCHIVE / job_id
    archived = []
    with cross_process_archive_lock():
        archive_dir.mkdir(parents=True, exist_ok=False)
        try:
            for source in candidates:
                destination = archive_dir / source.name
                if destination.exists():
                    raise RuntimeError(f"Build artifacts share the filename {source.name}")
                # The archive retention clock starts when the verified build is archived,
                # not when an old source file happened to be created.
                shutil.copyfile(source, destination)
                digest = file_sha256(destination)
                if source.stat().st_size != destination.stat().st_size or file_sha256(source) != digest:
                    raise RuntimeError(f"Archive verification failed for {source.name}")
                archived.append({"path": source.name, "size": destination.stat().st_size,
                                 "sha256": digest, "url": f"/archive/{job_id}/{source.name}"})
            enforce_archive_policy(protected_job_id=job_id)
            if not archive_dir.is_dir():
                raise RuntimeError("The completed GISO archive could not be retained")
            if before_cleanup is not None:
                before_cleanup()
        except Exception:
            shutil.rmtree(archive_dir, ignore_errors=True)
            raise
    touched_extraction_dirs: set[Path] = set()
    for child in cleanup_paths or []:
        resolved = child.resolve()
        if DATA not in resolved.parents or not resolved.exists():
            continue
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            extraction_dir = top_level_extraction_dir(resolved)
            resolved.unlink()
            if extraction_dir is not None:
                touched_extraction_dirs.add(extraction_dir)
    for extraction_dir in touched_extraction_dirs:
        if not extraction_dir.is_dir() or any(item.is_file() for item in extraction_dir.rglob("*")):
            continue
        source = archive_source_for_extraction(extraction_dir)
        shutil.rmtree(extraction_dir, ignore_errors=True)
        if source is not None:
            source.unlink(missing_ok=True)
    shutil.rmtree(WORK / job_id, ignore_errors=True)
    shutil.rmtree(job_dir, ignore_errors=True)
    return archived


def build_report(job: dict, artifacts: list[dict]) -> dict:
    """Structured, offline-readable record of one successful build.

    AI-MASTER-PROMPT.md "Artifacts and reproducibility" asks every build to
    record the web UI/gisobuild version, every input/output checksum, the
    exact BuildPlan and the generated CLI. The "Show build report" UI already
    renders this same data for a running job from live job state; this
    persists it as a plain JSON file next to the archived artifacts so it
    survives after the job record itself ages out of job history.
    """
    return {
        "job_id": job["id"],
        "label": (job.get("payload") or {}).get("label") or None,
        "created": job.get("created"),
        "finished": job.get("finished"),
        "web_ui_version": APP_VERSION,
        "gisobuild_image": IMAGE,
        "gisobuild_commit": gisobuild_commit(),
        "generated_command": job.get("command_preview", ""),
        "build_plan": job.get("build_plan"),
        "output_artifacts": artifacts,
    }


def write_build_report(job_id: str, job: dict, artifacts: list[dict]) -> None:
    try:
        report_path = ARCHIVE / job_id / "build-report.json"
        report_path.write_text(json.dumps(build_report(job, artifacts), indent=2, sort_keys=True))
    except OSError:
        pass  # The report is a convenience artifact; a write failure must not fail the build.


# Backwards-compatible name for callers outside the web application.
archive_golden_iso_and_cleanup = archive_giso_artifacts_and_cleanup


def docker_build_running() -> bool:
    try:
        result = subprocess.run(
            [DOCKER_BIN, "ps", "-q", "--filter", "label=app=giso-webui"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return True


def extraction_path(path: Path) -> Path | None:
    suffix = archive_suffix(path.name)
    return DATA / path.name[:-len(suffix)] if suffix else None


def archive_source_for_extraction(directory: Path) -> Path | None:
    """Return the archive file that produced this extraction directory, if any.

    extraction_path() deterministically derives the extraction directory name
    from the archive filename by stripping .tar/.tgz, so the relationship can
    be recovered without persisting extra provenance state: a direct child of
    DATA named "foo" was produced by extracting "foo.tar" or "foo.tgz" if
    that archive file still exists alongside it.
    """
    if directory.parent != DATA:
        return None
    for suffix in ARCHIVE_SUFFIXES:
        candidate = DATA / f"{directory.name}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def top_level_extraction_dir(path: Path) -> Path | None:
    """Return the direct-child-of-DATA ancestor directory that contains `path`."""
    try:
        relative = path.relative_to(DATA)
    except ValueError:
        return None
    if len(relative.parts) < 2:
        return None
    return DATA / relative.parts[0]


def upload_name(value: object) -> str:
    """Validate a client filename without silently rewriting path components."""
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValueError("Upload filename must be between 1 and 255 characters")
    if value != Path(value).name or any(ord(char) < 32 for char in value):
        raise ValueError("Upload filename must not contain a path or control characters")
    return value


def expire_upload_sessions() -> None:
    cutoff = time.time() - UPLOAD_SESSION_TTL
    expired: list[dict] = []
    with upload_lock:
        for upload_id, item in list(uploads.items()):
            if (not item.get("completing")
                    and item.get("updated", time.time()) < cutoff
                    and item.get("temp")):
                expired.append(uploads.pop(upload_id))
    for item in expired:
        Path(item["temp"]).unlink(missing_ok=True)
    parts = DATA / ".parts"
    tracked = {Path(item["temp"]).resolve() for item in uploads.values() if item.get("temp")}
    if parts.is_dir():
        for partial in parts.glob("*.part"):
            try:
                if partial.resolve() not in tracked and partial.stat().st_mtime < cutoff:
                    partial.unlink()
            except OSError:
                pass


def rpm_is_superseded(rpm: Path, superseded: set[str]) -> bool:
    """A package's containing directory names the Cisco supersedence identifier it belongs to."""
    return any(rpm.parent.name.startswith(identifier) for identifier in superseded)


def add_superseded_exclusions(recommendation: dict, superseded: set[str]) -> dict:
    """Explain, rather than silently drop, RPMs active_rpm_names() already filtered out.

    active_rpm_names() removes superseded packages from the candidate list
    before automatic selection ever sees them, so without this they never
    appear in "excluded" and the operator has no way to know they exist.
    """
    explained: dict[str, str] = {}
    for rpm in DATA.rglob("*.rpm"):
        if rpm_is_superseded(rpm, superseded):
            explained.setdefault(rpm.name, "Superseded by a newer fix per Cisco supersedence notes")
            continue
        canonical = rpm_filename_mismatch(rpm)
        if canonical:
            # active_rpm_names() also drops these; say why instead of letting
            # them vanish.
            explained.setdefault(
                rpm.name,
                f"Filename does not match the package inside it (its own metadata says "
                f"{canonical}); platform, release and CSC checks cannot be trusted for it",
            )
    for name, reason in _screened_rpms()[2].items():
        explained.setdefault(name, reason)
    if explained:
        recommendation["excluded"] = sorted(
            recommendation.get("excluded", []) + [
                {"name": name, "reason": reason} for name, reason in sorted(explained.items())
            ],
            key=lambda item: item["name"],
        )
    return recommendation


SUPERSEDENCE_FULL = re.compile(r"([A-Za-z0-9_-]+-[0-9][0-9.]*\.CSC\w+)\s+Full", re.IGNORECASE)
SMU_README_NAME = re.compile(r"^Name:[ \t]+(?P<name>\S+)[ \t]*$", re.MULTILINE)
SMU_README_RPMS = re.compile(
    r"^RPMS:[ \t]*\n(?P<body>(?:[ \t]+\S+\.rpm[ \t]+[0-9A-Fa-f]{32}[ \t]*\n)+)", re.MULTILINE
)
SMU_README_RPM_LINE = re.compile(r"(?P<rpm>\S+\.rpm)[ \t]+(?P<md5>[0-9A-Fa-f]{32})")


def smu_readme_texts() -> list[str]:
    """Every bounded-size .txt in the workspace - Cisco ships one README per SMU."""
    texts: list[str] = []
    inspected_bytes = 0
    for readme in DATA.rglob("*.txt"):
        try:
            size = readme.stat().st_size
            if size > MAX_SUPERSEDENCE_FILE_BYTES or inspected_bytes + size > MAX_SUPERSEDENCE_TOTAL_BYTES:
                continue
            inspected_bytes += size
            texts.append(readme.read_text(errors="ignore"))
        except OSError:
            pass
    return texts


def smu_readme_manifests(texts: list[str]) -> dict[str, dict[str, str]]:
    """{SMU name: {rpm basename: md5}} from each Cisco SMU README's "RPMS:" block.

    Cisco's README is the only authority in the workspace on how many RPMs a
    fix consists of: a filename's CSC ID only says which RPMs *present* share
    it, never that a companion was never uploaded. READMEs without an RPMS
    block (the base bundle's, or an unknown format) yield nothing - no
    manifest means no claim.
    """
    manifests: dict[str, dict[str, str]] = {}
    for text in texts:
        name = SMU_README_NAME.search(text)
        block = SMU_README_RPMS.search(text)
        if not name or not block:
            continue
        rpms = {match.group("rpm"): match.group("md5").lower()
                for match in SMU_README_RPM_LINE.finditer(block.group("body"))}
        if rpms:
            manifests.setdefault(name.group("name"), {}).update(rpms)
    return manifests


SMU_README_PREREQ_BLOCK = re.compile(
    r"^Pre-requisites:[ \t]*\n(?P<body>(?:[ \t]+\S.*\n)+)", re.MULTILINE
)
SMU_README_PREREQ_SMU = re.compile(r"^[ \t]+(?P<smu>\S+\.(?P<csc>CSC[A-Za-z0-9]+))[ \t]*$")
SMU_README_PREREQ_PACKAGE = re.compile(
    r"^[ \t]+(?P<csc>CSC[A-Za-z0-9]+)[ \t]+(?P<package>\S+)[ \t]+pkg[ \t]*$"
)


def smu_readme_prerequisites(texts: list[str]) -> dict[str, dict[str, str]]:
    """{SMU name: {package name: prerequisite SMU name}} from each README.

    A Cisco SMU README names its prerequisite SMUs, and under "CONSTITUENT
    SMU DETAILS" which package each prerequisite supplies
    (``CSCwt13701 ncs5500-dpa pkg``). Only packages whose CSC also appears in
    the SMU-level list are kept, so the full SMU name is Cisco's, not built
    here.
    """
    prerequisites: dict[str, dict[str, str]] = {}
    for text in texts:
        name = SMU_README_NAME.search(text)
        if not name:
            continue
        smu_by_csc: dict[str, str] = {}
        packages: dict[str, str] = {}
        for block in SMU_README_PREREQ_BLOCK.finditer(text):
            for line in block.group("body").splitlines():
                smu = SMU_README_PREREQ_SMU.match(line)
                if smu:
                    smu_by_csc[smu.group("csc")] = smu.group("smu")
                package = SMU_README_PREREQ_PACKAGE.match(line)
                if package:
                    packages[package.group("package")] = package.group("csc")
        resolved = {package: smu_by_csc[csc] for package, csc in packages.items() if csc in smu_by_csc}
        if resolved:
            prerequisites.setdefault(name.group("name"), {}).update(resolved)
    return prerequisites


def explain_with_prerequisites(entries: list[dict]) -> list[dict]:
    """Name the Cisco SMU that supplies each unsatisfiable requirement, when a README says.

    Adds ``prerequisite_smu`` (and ``listed_by``) to an entry only when an
    SMU that requires the package lists, in its own README, a prerequisite
    SMU for exactly that package. The block itself never depends on this -
    it only turns "download the SMU that provides X" into its actual name.
    """
    if not entries:
        return entries
    texts = smu_readme_texts()
    manifests = smu_readme_manifests(texts)
    prerequisites = smu_readme_prerequisites(texts)
    smu_by_rpm = {rpm: smu for smu, rpms in manifests.items() for rpm in rpms}
    for entry in entries:
        package = entry["requirement"].split(" = ")[0]
        for rpm in entry["required_by"]:
            smu = smu_by_rpm.get(rpm)
            prerequisite = prerequisites.get(smu or "", {}).get(package)
            if prerequisite:
                entry["prerequisite_smu"] = prerequisite
                entry["listed_by"] = smu
                break
    return entries


def smu_manifest_problems(available: list[str], texts: list[str] | None = None) -> dict[str, str]:
    """RPMs that must not be built because their own Cisco README says so.

    For every SMU with at least one RPM in `available`: if a README-listed
    RPM is not available, every present member is incomplete; if a present
    member's MD5 differs from the README, that file is not the Cisco
    original and the whole fix is unusable. Returns {basename: reason}.
    """
    present = set(available)
    paths_by_name: dict[str, list[Path]] = {}
    for rpm in DATA.rglob("*.rpm"):
        if rpm.name in present:
            paths_by_name.setdefault(rpm.name, []).append(rpm)
    problems: dict[str, str] = {}
    manifests = smu_readme_manifests(smu_readme_texts() if texts is None else texts)
    for smu, members in sorted(manifests.items()):
        here = sorted(name for name in members if name in present)
        if not here:
            continue
        missing = sorted(name for name in members if name not in present)
        corrupt = []
        for name in here:
            for path in paths_by_name.get(name, []):
                try:
                    if file_checksums(path)["md5"] != members[name]:
                        corrupt.append(name)
                        break
                except OSError:
                    corrupt.append(name)
                    break
        for name in here:
            if name in corrupt:
                problems.setdefault(name, f"MD5 does not match the Cisco README for {smu}; "
                                          "the file is damaged or not the Cisco original")
            elif corrupt:
                problems.setdefault(name, f"Part of {smu}, but {', '.join(corrupt)} from the same "
                                          "fix failed its README checksum")
            elif missing:
                problems.setdefault(name, f"Incomplete fix: the Cisco README for {smu} lists "
                                          f"{len(members)} RPMs; missing {', '.join(missing)}")
    return problems


def _screened_rpms() -> tuple[list[str], set[str], dict[str, str]]:
    texts = smu_readme_texts()
    superseded: set[str] = set()
    for text in texts:
        superseded.update(SUPERSEDENCE_FULL.findall(text))
    readable = [
        rpm.name for rpm in DATA.rglob("*.rpm")
        if not rpm_is_superseded(rpm, superseded) and rpm_filename_mismatch(rpm) is None
    ]
    return readable, superseded, smu_manifest_problems(readable, texts)


def selection_integrity_blockers(selected_names: list[str]) -> list[str]:
    """Selected RPMs the workspace itself proves unusable - for manual selection.

    Two proofs: the RPM's own header names a different package than its
    filename (rpm_filename_mismatch()), or its Cisco SMU README shows the fix
    incomplete or the file altered (smu_manifest_problems()). Automatic
    selection never picks these (active_rpm_names() drops them), so this only
    fires when an operator chose one by hand; manual mode may override
    inference, never a failure the workspace already proves.
    """
    wanted = set(selected_names)
    blockers = []
    for rpm in sorted(DATA.rglob("*.rpm")):
        if rpm.name in wanted:
            canonical = rpm_filename_mismatch(rpm)
            if canonical:
                blockers.append(f"{rpm.name}: its own RPM header says it is {canonical}")
    problems = _screened_rpms()[2]
    blockers.extend(f"{name}: {problems[name]}" for name in sorted(wanted) if name in problems)
    return blockers


def active_rpm_names() -> tuple[list[str], set[str]]:
    readable, superseded, problems = _screened_rpms()
    return [name for name in readable if name not in problems], superseded


def discover() -> dict:
    files, dirs = inventory_files(), []
    ignored = {".parts"}
    for root, names, filenames in os.walk(DATA):
        names[:] = [n for n in names if n not in ignored and not n.startswith("output_gisobuild")]
        root_path = Path(root)
        if root_path != DATA:
            dirs.append(rel_data(root_path))
    candidates, superseded = active_rpm_names()
    isos = [item["path"] for item in files if item["type"] == ".iso"]
    iso_architectures: frozenset[str] = frozenset()
    identity_name, identity_from_metadata = (isos[0] if isos else ""), False
    if len(isos) == 1:
        try:
            iso_path = safe_data_path(isos[0])
            iso_architectures = inspect_iso_architecture(iso_path)
            identity_name, identity_from_metadata = iso_identity(iso_path)
        except (OSError, ValueError):
            iso_architectures = frozenset()
        recommendation = recommend_smu_selection(identity_name, candidates, iso_architectures=iso_architectures)
        # Platform/release may come from the image's embedded identity, but the
        # operator-facing "iso" is always the real file they uploaded.
        recommendation["iso"] = Path(isos[0]).name
    elif len(isos) > 1:
        recommendation = {"ready": False, "selected": [], "excluded": [],
                          "message": "More than one base ISO was found; keep one ISO or select it in Expert settings"}
    else:
        recommendation = {"ready": False, "selected": [], "excluded": [],
                          "message": "Upload one base ISO before SMUs can be selected"}
    recommendation = add_superseded_exclusions(recommendation, superseded)
    recommendation["unsatisfied_dependencies"] = (
        unsatisfied_dependencies_for_recommendation(isos[0], recommendation.get("selected", []))
        if len(isos) == 1 else []
    )
    recommendation["confidence"] = confidence_report(
        resolved_platform=recommendation.get("platform"),
        platform_manual=False,
        release=recommendation.get("release"),
        iso_architectures=iso_architectures,
        package_groups=recommendation.get("package_groups", []),
        has_rpm_selection=bool(recommendation.get("selected")),
        matched_pid=infer_platform_pid(isos[0]) if len(isos) == 1 else None,
        identity_from_metadata=identity_from_metadata,
    )
    matrices = [item["path"] for item in files
                if item["type"] == ".json" and Path(item["path"]).name.startswith("compatibility_matrix_")]
    return {"files": sorted(files, key=lambda x: x["path"]), "dirs": sorted(dirs),
            "inventory_revision": current_inventory_revision(files),
            "recommended": recommendation["selected"], "recommendation": recommendation,
            "superseded": sorted(superseded), "matrices": matrices}


def append_log(job_id: str, text: str) -> None:
    text = safe_log_text(text)
    phase_change = None
    with job_lock:
        jobs[job_id]["log"] += text
        encoded = jobs[job_id]["log"].encode("utf-8")
        if len(encoded) > MAX_LOG_BYTES:
            tail = encoded[-MAX_LOG_BYTES:].decode("utf-8", errors="ignore")
            jobs[job_id]["log"] = "[Earlier build output was truncated]\n" + tail
        jobs[job_id]["updated"] = time.time()
        lower = text.lower()
        milestones = [
            ("found bundle iso", 15, "Reading base image"),
            ("scanning repository", 28, "Scanning update packages"),
            ("building rpm database", 42, "Checking package information"),
            ("following xr x86_64 rpm", 58, "Resolving package dependencies"),
            ("building golden iso", 72, "Building Golden ISO"),
            ("golden iso image location", 88, "Golden ISO created"),
            ("creating usb boot zip", 92, "Creating USB package"),
            ("usb boot zip", 97, "Finalizing output"),
        ]
        for marker, progress, phase in milestones:
            if marker in lower and progress > jobs[job_id].get("progress", 0):
                jobs[job_id].update(progress=progress, phase=phase)
                phase_change = (progress, phase)
    if phase_change:
        log_event("build_progress", job_id=job_id, progress=phase_change[0],
                  phase=json.dumps(phase_change[1]))
    for line in text.splitlines():
        if line.strip():
            app.logger.info("event=build_output job_id=%s message=%s", job_id, line)
    persist_job(job_id, min_interval=1.0)


def child_mount_args() -> list[str]:
    """Share only required storage with the build container, never docker.sock."""
    container = os.environ.get("HOSTNAME", "giso-webui")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container):
        raise RuntimeError("Container hostname is invalid")
    result = subprocess.run(
        [DOCKER_BIN, "inspect", container], check=True, capture_output=True, text=True,
        timeout=5,
    )
    info = json.loads(result.stdout)[0]
    wanted = {"/uploads": "ro", "/output": "rw", "/tool": "ro", "/work": "rw"}
    args: list[str] = []
    found = set()
    for mount in info.get("Mounts", []):
        destination = mount.get("Destination")
        if destination not in wanted:
            continue
        source = mount.get("Name") if mount.get("Type") == "volume" else mount.get("Source")
        if not source:
            raise RuntimeError(f"Cannot resolve container mount {destination}")
        args += ["-v", f"{source}:{destination}:{wanted[destination]}"]
        found.add(destination)
    missing = set(wanted) - found
    if missing:
        raise RuntimeError("Missing required mounts: " + ", ".join(sorted(missing)))
    return args


def build_command(payload: dict, job_id: str) -> list[str]:
    command = [
        DOCKER_BIN, "run", "--platform", "linux/amd64", "--rm",
        "--name", f"giso-build-{job_id}", "--label", "app=giso-webui",
        *child_mount_args(), IMAGE,
        "/tool/src/gisobuild.py",
    ]
    if payload.get("yamlfile"):
        command += ["--yamlfile", str(safe_data_path(payload["yamlfile"]))]
    else:
        iso = payload.get("iso", "")
        if not iso:
            raise ValueError("Select an ISO, or provide a YAML file")
        iso_path = safe_data_path(iso)
        iso_architectures = inspect_iso_architecture(iso_path)
        # Must infer from the same identity create_build_plan() used, or the
        # final gate could reject a plan the review step just approved.
        identity_name, _ = iso_identity(iso_path)
        candidates = active_rpm_names()[0]
        if payload.get("automatic_smu_selection"):
            package_plan = recommend_smu_selection(
                identity_name, candidates, iso_architectures=iso_architectures
            )
            if not package_plan["ready"]:
                raise ValueError(package_plan["message"])
            payload["pkglist"] = package_plan["selected"]
        profile = validate_platform_options({**payload, "iso": identity_name})
        payload["platform"] = profile["id"]
        selected_rpms = resolve_rpm_identifiers(payload.get("pkglist", []))
        selected_names = [item["basename"] for item in selected_rpms]
        payload["pkglist"] = selected_names
        smu_check = validate_smu_selection(
            identity_name, selected_names, iso_architectures=iso_architectures,
            full_candidate_packages=candidates,
        )
        issues = smu_check["issues"] + selection_integrity_blockers(selected_names)
        if issues:
            raise ValueError("SMU compatibility check failed: " + "; ".join(issues))
        command += ["--iso", str(iso_path)]
        for key, option in PATH_OPTIONS.items():
            if key in {"iso", "yamlfile"}:
                continue
            if payload.get(key):
                command += [option, str(safe_data_path(payload[key]))]
        if payload.get("auto_repo", True) and selected_rpms:
            staged_repo = WORK / job_id / "repo"
            staged_repo.mkdir(parents=True, exist_ok=True)
            for package in selected_rpms:
                source = safe_data_path(package["relative_path"])
                shutil.copy2(source, staged_repo / package["basename"])
            command += ["--repo", str(staged_repo)]
        for key, option in LIST_OPTIONS.items():
            if key == "repo" and payload.get("auto_repo", True):
                continue
            values = payload.get(key) or []
            if values:
                command.append(option)
                if key in {"repo", "bridging_fixes"}:
                    command += [str(safe_data_path(v)) for v in values]
                else:
                    command += values
        if payload.get("label") and not payload.get("no_label"):
            if not re.fullmatch(r"[A-Za-z0-9_]+", payload["label"]):
                raise ValueError("Label may contain only letters, numbers and underscore")
            command += ["--label", payload["label"]]
        for key, option in BOOL_OPTIONS.items():
            if payload.get(key):
                command.append(option)
    command += ["--out-directory", f"/output/{job_id}", "--clean"]
    return command


def command_preview(command: list[str]) -> str:
    """Redacted, script-only view of the real build command for operator display.

    docs/AI-MASTER-PROMPT.md section 10 asks operators be able to inspect
    "the effective command" for troubleshooting/reproducing builds/TAC
    cases, with "secrets or sensitive filesystem paths... masked where
    appropriate". The real `command` list is never sent to the browser
    (it's in PRIVATE_JOB_FIELDS) because its `docker run ... -v <source> ...`
    prefix can contain the real host filesystem path or Docker volume name
    behind a bind mount (see child_mount_args()) - genuinely sensitive
    deployment detail, not something a build operator needs. This strips
    that prefix entirely and keeps only the actual gisobuild.py invocation,
    showing each absolute container path (e.g. "/uploads/foo.rpm") as just
    its basename for readability - the same shape as a typical documented
    gisobuild command line, and accurate, since these are the real
    arguments, not a reconstruction.
    """
    try:
        script_index = next(i for i, arg in enumerate(command) if arg.endswith("gisobuild.py"))
    except StopIteration:
        return ""
    tail = ["gisobuild.py", *command[script_index + 1:]]
    cleaned = [Path(arg).name if arg.startswith("/") else arg for arg in tail]
    return shlex.join(cleaned)


def glob_metacharacters(value: str) -> bool:
    return any(character in value for character in "*?[]")


def build_cleanup_paths(payload: dict, selected_rpms: list[dict]) -> list[Path]:
    """Resolve only inputs explicitly owned by this build request.

    RPMs must come from selected_rpms (resolve_rpm_identifiers()'s output),
    not by globbing payload["pkglist"] for a basename match: two uploads can
    share a basename with different content (see the duplicate-inventory
    handling in resolve_rpm_identifiers()), and by the time this runs
    build_command() has already overwritten payload["pkglist"] with
    basenames, so a glob-by-basename here would schedule every file sharing
    that name for deletion, not just the one actually used in this build.
    """
    paths: set[Path] = set()
    for key in PATH_OPTIONS:
        value = payload.get(key)
        if value:
            paths.add(safe_data_path(value))
    for key in ("repo", "bridging_fixes"):
        for value in payload.get(key) or []:
            paths.add(safe_data_path(value))
    for package in selected_rpms:
        paths.add(safe_data_path(package["relative_path"]))
    return sorted(paths, key=str)


def cancellation_requested(job_id: str) -> bool:
    with job_lock:
        return jobs[job_id]["status"] in {"cancelling", "cancelled"}


def prepare_destructive_finalization(job_id: str) -> None:
    """Commit the final state transition before any owned input is removed."""
    with job_lock:
        if jobs[job_id]["status"] in {"cancelling", "cancelled"}:
            raise BuildCancelled("Build cancelled before finalization")
        jobs[job_id]["status"] = "committing"


def local_builder_image_id() -> str | None:
    """Docker's ID for the builder image if this host already has it, else None."""
    try:
        result = subprocess.run(
            [DOCKER_BIN, "image", "inspect", "--format", "{{.Id}}", IMAGE],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    image_id = result.stdout.strip()
    return image_id if result.returncode == 0 and image_id.startswith("sha256:") else None


def run_job(job_id: str, command: list[str]) -> None:
    with job_lock:
        job_started = jobs[job_id]["created"]
        build_log_context = {"inventory_revision": jobs[job_id].get("inventory_revision"),
                             "plan_fingerprint": jobs[job_id].get("plan_fingerprint")}
    try:
        append_log(job_id, "$ " + shlex.join(command) + "\n\n")
        log_event("build_started", job_id=job_id, **build_log_context)
        log_event("image_pull_started", job_id=job_id)
        pull = subprocess.Popen(
            [DOCKER_BIN, "pull", "--platform", "linux/amd64", IMAGE],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        with job_lock:
            job_processes[job_id] = pull
            jobs[job_id]["process_phase"] = "pulling"
        pull_failure = None
        try:
            pull_output, _ = pull.communicate(timeout=GISO_PULL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            pull.terminate()
            pull.wait(timeout=20)
            pull_output, pull_failure = "", f"timed out after {GISO_PULL_TIMEOUT_SECONDS} seconds"
        finally:
            with job_lock:
                job_processes.pop(job_id, None)
        if cancellation_requested(job_id):
            raise BuildCancelled("Build cancelled during image preparation")
        if pull_output:
            append_log(job_id, pull_output)
        if pull_failure is None and pull.returncode:
            pull_failure = f"exited with status {pull.returncode}"
        # Registry access is not a build input: when the pull fails, a builder
        # image this host already holds is used instead of failing every build
        # during a registry or network outage. A digest-pinned reference is
        # content-addressed, so the cached copy is exactly what would have been
        # pulled; a tag-only one may lag the registry, which the log says.
        image_id = local_builder_image_id()
        if pull_failure:
            if image_id is None:
                raise RuntimeError(
                    f"The builder image could not be pulled ({pull_failure}) and is not cached "
                    f"on this host: {IMAGE}"
                )
            pinned = "@sha256:" in IMAGE
            append_log(job_id, (
                f"\nWARNING: pulling the builder image {pull_failure}; using the copy already "
                f"on this host ({image_id[:19]}). "
                + ("The reference is digest-pinned, so it is identical.\n" if pinned else
                   "The reference is a tag, so this copy may be older than the registry's.\n")
            ))
            log_event("image_pull_fallback_to_cache", job_id=job_id, pinned=pinned)
        else:
            log_event("image_pull_completed", job_id=job_id)
        with job_lock:
            jobs[job_id]["builder_image"] = {
                "reference": IMAGE, "id": image_id,
                "source": "cache" if pull_failure else "registry",
            }
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
        with job_lock:
            job_processes[job_id] = proc
            jobs[job_id]["process_phase"] = "building"
            jobs[job_id]["container_pid"] = proc.pid
        if proc.stdout is None:
            raise RuntimeError("Build container output stream is unavailable")
        # Close the pipe explicitly: iterating it to EOF does not, so every
        # build otherwise left a descriptor for the garbage collector.
        with proc.stdout:
            for line in proc.stdout:
                append_log(job_id, line)
        code = proc.wait()
        with job_lock:
            job_processes.pop(job_id, None)
        if cancellation_requested(job_id):
            raise BuildCancelled("Build cancelled")
        artifacts = []
        job_dir = OUTPUT / job_id
        if job_dir.exists():
            for path in sorted(job_dir.rglob("*")):
                if path.is_file() and (path.suffix in {".iso", ".zip", ".json", ".txt"} or "log" in path.name):
                    artifacts.append({"path": str(path.relative_to(job_dir)), "size": path.stat().st_size})
        success = code == 0 and any(
            path.suffix.lower() == ".iso" for path in giso_artifact_candidates(job_dir)
        )
        if success:
            with job_lock:
                jobs[job_id]["status"] = "finalizing"
                cleanup_paths = [Path(path) for path in jobs[job_id].get("cleanup_paths", [])]
            artifacts = archive_giso_artifacts_and_cleanup(
                job_id, job_dir, cleanup_paths, lambda: prepare_destructive_finalization(job_id)
            )
        with job_lock:
            if jobs[job_id]["status"] not in {"cancelled", "cancelling"}:
                jobs[job_id].update(status="success" if success else "failed",
                                    exit_code=code, artifacts=artifacts, finished=time.time(),
                                    updated=time.time(),
                                    progress=100 if success else jobs[job_id].get("progress", 0),
                                    phase="Complete" if success else "Build failed")
            job_snapshot = dict(jobs[job_id])
        persist_job(job_id)
        if success:
            write_build_report(job_id, job_snapshot, artifacts)
        log_event("build_finished", exit_code=code, job_id=job_id,
                  status="success" if success else "failed",
                  duration_ms=round((time.time() - job_started) * 1000), **build_log_context)
    except BuildCancelled:
        with job_lock:
            job_processes.pop(job_id, None)
            jobs[job_id].update(status="cancelled", phase="Cancelled", finished=time.time(),
                                updated=time.time())
        persist_job(job_id)
        log_event("build_cancelled", job_id=job_id,
                  duration_ms=round((time.time() - job_started) * 1000), **build_log_context)
    except Exception as exc:  # noqa: BLE001 - background failures must update job state
        append_log(job_id, f"\nERROR: {exc}\n")
        with job_lock:
            job_processes.pop(job_id, None)
            if jobs[job_id]["status"] in {"cancelling", "cancelled"}:
                jobs[job_id].update(status="cancelled", phase="Cancelled", finished=time.time(),
                                    updated=time.time())
            else:
                jobs[job_id].update(
                    status="failed",
                    error="Build failed; review the redacted technical details",
                    phase="Build failed",
                    finished=time.time(),
                    updated=time.time(),
                )
        persist_job(job_id)
        log_event("build_failed", error_type=type(exc).__name__, job_id=job_id,
                  duration_ms=round((time.time() - job_started) * 1000), **build_log_context)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/activity")
def activity():
    with store_lock, sqlite3.connect(JOB_DB) as database:
        rows = database.execute(
            "SELECT text FROM activity ORDER BY id ASC LIMIT 500"
        ).fetchall()
    return jsonify(log="\n".join(row[0] for row in rows))


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; form-action 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; worker-src 'none'; manifest-src 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    request_id = getattr(g, "request_id", uuid.uuid4().hex[:12])
    response.headers["X-Request-ID"] = request_id
    if request.endpoint not in {"health", "upload_chunk"} or response.status_code >= 400:
        elapsed_ms = round((time.monotonic() - getattr(g, "request_started", time.monotonic())) * 1000)
        log_event("http_request", elapsed_ms=elapsed_ms, endpoint=request.endpoint or "unknown",
                  method=request.method, request_id=request_id, status=response.status_code)
    return response


@app.errorhandler(BadRequest)
def bad_request(error):
    return jsonify(error=error.description or "Invalid request"), 400


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify(error=f"Request exceeds the {MAX_CHUNK_BYTES}-byte chunk limit"), 413


@app.before_request
def validate_host():
    global archive_policy_checked
    supplied_request_id = request.headers.get("X-Request-ID", "")
    g.request_id = (supplied_request_id if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", supplied_request_id)
                    else uuid.uuid4().hex[:12])
    g.request_started = time.monotonic()
    initialize_job_store()
    expire_upload_sessions()
    host = request.host.split(":", 1)[0].strip("[]")
    if host not in ALLOWED_HOSTS:
        abort(400)
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            abort(403)
        origin = request.headers.get("Origin")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != request.host:
                abort(403)
    now = time.monotonic()
    if now - archive_policy_checked >= 3600:
        enforce_archive_policy()
        archive_policy_checked = now


@app.get("/api/health")
def health():
    """Liveness only: has the process itself started and can it respond.

    Dependency/storage/disk checks live in /api/ready. A container
    orchestrator should restart on health failure but only stop routing
    traffic (without restarting) on readiness failure - conflating the two
    here made every dependency hiccup look like a crashed process.
    """
    return jsonify(ok=True), 200


@app.get("/api/ready")
def ready():
    docker_ok = False
    try:
        subprocess.run([DOCKER_BIN, "info"], timeout=5, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        docker_ok = True
    except (OSError, subprocess.SubprocessError):
        pass
    db_ok = False
    try:
        with sqlite3.connect(JOB_DB, timeout=5) as database:
            database.execute("SELECT 1")
        db_ok = True
    except sqlite3.Error:
        pass
    disk_ok = False
    try:
        disk_ok = shutil.disk_usage(DATA).free >= MIN_FREE_BYTES
    except OSError:
        pass
    checks = {
        "docker": docker_ok,
        "tool": (TOOL / "src/gisobuild.py").is_file(),
        "storage": all(path.is_dir() for path in (DATA, OUTPUT, WORK, ARCHIVE, STATE)),
        "database": db_ok,
        "disk": disk_ok,
    }
    is_ready = all(checks.values())
    return jsonify(ok=is_ready, **checks), 200 if is_ready else 503


@app.get("/api/storage")
def storage():
    """Operator-facing storage visibility (AI-MASTER-PROMPT.md section 37/45).

    A read, not a mutation, so - like archive_download() - this does not
    take cross_process_archive_lock(): a transiently stale number during a
    concurrent archive write is harmless for a usage display and self
    corrects on the next poll.
    """
    archive_used = archive_size(ARCHIVE) if ARCHIVE.is_dir() else 0
    return jsonify(
        disk_free_bytes=shutil.disk_usage(DATA).free,
        volume_free_bytes=build_volume_free_bytes(),
        archive_used_bytes=archive_used,
        archive_quota_bytes=MAX_ARCHIVE_BYTES,
        archive_retention_days=ARCHIVE_RETENTION_DAYS,
    )


def gisobuild_commit() -> str | None:
    """Best-effort short git commit of the mounted .gisobuild-tool checkout.

    Returns None (never raises) when TOOL isn't a git checkout or git isn't
    available - version info is diagnostic, never load-bearing.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(TOOL), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


@app.get("/api/version")
def version():
    """Surface which pinned gisobuild build engine this deployment actually runs.

    APP_VERSION is this web UI's own version; gisobuild_image/gisobuild_commit
    identify the separate, upstream build engine - see AI-MASTER-PROMPT.md
    section 18 ("Upstream version detection").
    """
    return jsonify(
        app_version=APP_VERSION,
        source_revision=os.environ.get("SOURCE_REVISION") or None,
        build_date=os.environ.get("BUILD_DATE") or None,
        gisobuild_image=IMAGE,
        gisobuild_commit=gisobuild_commit(),
    )


@app.get("/api/inputs")
def inputs():
    return jsonify(discover())


@app.get("/api/inventory/revision")
def inventory_revision():
    """Cheap change signal for the UI's automatic refresh.

    Hashes the same ready-inventory snapshot /api/inputs reports, without
    re-running recommendation, ISO inspection or dependency checks. Checksums
    are cached by path/size/mtime, so an unchanged workspace costs a
    directory walk; the page calls /api/inputs only when this value moves.
    """
    return jsonify(inventory_revision=current_inventory_revision())


@app.get("/api/platforms")
def platforms():
    return jsonify([platform_profile(key) for key in PLATFORMS])


@app.get("/api/file-preview")
def file_preview():
    """Best-effort text preview of an expert-mode config path (xrconfig, ztp_ini,
    boot script, key request, ...) so an operator can see what they are about to
    hand gisobuild without opening it outside the browser - AI-MASTER-PROMPT.md
    section 27 ("offer preview" for text configuration files).
    """
    try:
        path = safe_data_path(request.args.get("path", ""))
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    if not path.is_file():
        raise BadRequest("Path is not a file")
    size = path.stat().st_size
    if size > MAX_FILE_PREVIEW_BYTES:
        return jsonify(previewable=False, reason="File is too large to preview here", size=size)
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return jsonify(previewable=False, reason="File is not plain text", size=size)
    return jsonify(previewable=True, text=text, size=size)


@app.post("/api/smu/recommendation")
def smu_recommendation():
    body = json_object()
    try:
        iso = cisco_text(body.get("iso"), "base ISO", maximum=4096)
        iso_path = safe_data_path(iso)
        if iso_path.suffix.lower() != ".iso" or not iso_path.is_file():
            raise ValueError("Select an uploaded base ISO")
        packages, superseded = active_rpm_names()
        iso_architectures = inspect_iso_architecture(iso_path)
        identity_name, identity_from_metadata = iso_identity(iso_path)
        recommendation = recommend_smu_selection(identity_name, packages, iso_architectures=iso_architectures)
        recommendation["iso"] = iso_path.name
        recommendation = add_superseded_exclusions(recommendation, superseded)
        recommendation["unsatisfied_dependencies"] = (
            unsatisfied_dependencies_for_recommendation(iso, recommendation.get("selected", []))
        )
        recommendation["confidence"] = confidence_report(
            resolved_platform=recommendation.get("platform"),
            platform_manual=False,
            release=recommendation.get("release"),
            iso_architectures=iso_architectures,
            package_groups=recommendation.get("package_groups", []),
            has_rpm_selection=bool(recommendation.get("selected")),
            matched_pid=infer_platform_pid(iso),
            identity_from_metadata=identity_from_metadata,
        )
        return jsonify(recommendation)
    except (OSError, TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400


@app.post("/api/compatibility")
def compatibility():
    body = json_object()
    try:
        iso = cisco_text(body.get("iso"), "base ISO", maximum=4096)
        packages = body.get("packages", [])
        if (not isinstance(packages, list) or len(packages) > 10000 or
                not all(isinstance(item, str) and len(item) <= 4096 for item in packages)):
            raise ValueError("Packages must be a list")
        package_names = package_names_for_validation(packages)
        iso_architectures = frozenset()
        identity_name = iso
        try:
            iso_candidate = safe_data_path(iso)
            if iso_candidate.suffix.lower() == ".iso" and iso_candidate.is_file():
                iso_architectures = inspect_iso_architecture(iso_candidate)
                identity_name, _ = iso_identity(iso_candidate)
        except ValueError:
            iso_architectures = frozenset()
        smu = validate_smu_selection(
            identity_name, package_names, iso_architectures=iso_architectures,
            full_candidate_packages=active_rpm_names()[0],
        )
        # The same package-level proofs create_build_plan() blocks on, so this
        # manual check can never call a selection compatible that Start would
        # then refuse.
        extra_issues = selection_integrity_blockers(package_names)
        smu["unsatisfied_dependencies"] = unsatisfied_dependencies_for_recommendation(iso, package_names)
        extra_issues += [dependency_blocker_text(entry) for entry in smu["unsatisfied_dependencies"]]
        if extra_issues:
            smu["issues"] = sorted(set(smu["issues"]) | set(extra_issues))
            smu["compatible"] = False
        result = {"smu": smu, "upgrade": None}
        matrix_name = body.get("matrix", "")
        if matrix_name:
            matrix_path = safe_data_path(cisco_text(matrix_name, "compatibility matrix", maximum=4096))
            if matrix_path.suffix.lower() != ".json" or matrix_path.stat().st_size > 1024 * 1024:
                raise ValueError("Compatibility matrix must be a JSON file smaller than 1 MiB")
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            result["upgrade"] = check_upgrade_matrix(
                matrix, cisco_text(body.get("source_release"), "source release"),
                cisco_text(body.get("target_release"), "target release"),
                cisco_text(body.get("platform"), "platform"),
                package_names,
            )
        return jsonify(result)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400


@app.post("/api/build-plan")
def build_plan():
    try:
        payload = validate_build_payload(json_object())
        return jsonify(create_build_plan(payload))
    except (OSError, TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400


@app.get("/api/cisco/config")
def cisco_config():
    try:
        enabled = bool(secret_value("CISCO_CLIENT_ID") and
                       secret_value("CISCO_CLIENT_SECRET"))
    except CiscoDownloadError:
        enabled = False
    return jsonify(enabled=enabled)


@app.post("/api/cisco/search")
def cisco_search():
    body = json_object()
    try:
        pid = cisco_text(body.get("pid"), "PID")
        current = cisco_text(body.get("current_release"), "current release")
        target = cisco_text(body.get("target_release"), "target release")
        response = cisco_client().search(pid, current, target)
        images = find_cisco_images(response)
        transaction_id = cisco_text(response.get("metadataTransId"), "transaction ID", maximum=40)
    except (ValueError, CiscoDownloadError) as exc:
        log_event("cisco_search_failed", error_type=type(exc).__name__)
        return cisco_failure(exc)
    search_id = uuid.uuid4().hex
    with cisco_lock:
        cisco_searches.clear()
        cisco_searches[search_id] = {"created": time.time(), "pid": pid,
                                     "transaction_id": transaction_id,
                                     "images": {item["guid"]: item for item in images}}
    log_event("cisco_search_completed", images=len(images), search_id=search_id)
    append_activity(f"Cisco search completed: {len(images)} software files available.")
    return jsonify(id=search_id, images=images)


def run_cisco_download(job_id: str, search: dict, selected: list[dict], downloads: list[dict]) -> None:
    with cisco_lock:
        job = cisco_download_jobs[job_id]
    created_files: list[Path] = []
    try:
        for number, item in enumerate(selected, 1):
            remote = next((entry for entry in downloads if entry.get("imageGuid") == item["guid"]), None)
            if not remote or not remote.get("url"):
                raise CiscoDownloadError("Cisco did not return a download URL")
            name = upload_name(item["name"])
            target = DATA / name
            if target.exists():
                target = DATA / f"{target.stem}-{uuid.uuid4().hex[:8]}{target.suffix}"
            def update_progress(written: int, total: int, file_number: int = number) -> None:
                file_fraction = written / total if total else 0
                progress = int(((file_number - 1 + file_fraction) / len(selected)) * 100)
                with cisco_lock:
                    job.update(status="downloading", progress=min(progress, 99))

            with cisco_lock:
                job.update(status="downloading", progress=(number - 1) * 100 // len(selected))
            append_activity(f"Cisco download {number} of {len(selected)} started.")
            result = cisco_client().download(
                str(remote["url"]), target, expected_size=item["size"],
                max_bytes=MAX_UPLOAD_BYTES, cloud_token=str(remote.get("token", "")),
                expected_md5=item["md5"], expected_sha512=item["sha512"],
                progress=update_progress,
            )
            created_files.append(result.path)
            extracted = extract_cisco_archive(result.path)
            with cisco_lock:
                job["files"].append({"name": result.path.name, "size": result.size,
                                     "sha256": result.sha256, "extracted": extracted})
                job.update(status="verifying", progress=number * 100 // len(selected))
        with cisco_lock:
            job.update(status="ready", progress=100)
        append_activity(f"Cisco download completed: {len(selected)} files verified and ready.")
        log_event("cisco_download_completed", files=len(selected), job_id=job_id)
    except (CiscoDownloadError, OSError, ValueError) as exc:
        for path in created_files:
            path.unlink(missing_ok=True)
            extracted_path = extraction_path(path)
            if extracted_path:
                shutil.rmtree(extracted_path, ignore_errors=True)
        with cisco_lock:
            job.update(status="failed", error=str(exc), files=[])
        log_event("cisco_download_failed", error_type=type(exc).__name__, job_id=job_id)
        append_activity("Cisco download failed. Check the Cisco access status and technical details.")


@app.post("/api/cisco/downloads")
def cisco_download_start():
    body = json_object()
    with cisco_lock:
        search = cisco_searches.get(str(body.get("search_id", "")))
    guids = body.get("image_guids")
    if not search or time.time() - search["created"] > 3300:
        return jsonify(error="Cisco search has expired; search again"), 410
    if (not isinstance(guids, list) or not 1 <= len(guids) <= 5 or
            any(not isinstance(x, str) for x in guids) or len(set(guids)) != len(guids)):
        return jsonify(error="Select between one and five unique Cisco files"), 400
    job_id = uuid.uuid4().hex
    with operation_lock:
        with upload_lock:
            if uploads:
                return jsonify(error="Wait for the current upload to finish"), 409
        with job_lock:
            if any(job["status"] in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify(error="Wait for the current build to finish"), 409
        if docker_build_running():
            return jsonify(error="Wait for the current Docker build to finish"), 409
        with cisco_lock:
            if cisco_download_running():
                return jsonify(error="Wait for the current Cisco download to finish"), 409
            cisco_download_jobs.clear()
            cisco_download_jobs[job_id] = {
                "id": job_id, "status": "authenticating", "progress": 0,
                "files": [], "error": "", "created": time.time(),
            }
    try:
        selected = [search["images"][guid] for guid in guids]
        if any(item["size"] <= 0 or item["size"] > MAX_UPLOAD_BYTES for item in selected):
            raise CiscoDownloadError("A selected Cisco file has an invalid size")
        if shutil.disk_usage(DATA).free < sum(item["size"] for item in selected) + MIN_FREE_BYTES:
            raise CiscoDownloadError("Not enough free disk space for the Cisco download")
        mdf_ids = {item["mdf_id"] for item in selected}
        if len(mdf_ids) != 1 or not next(iter(mdf_ids)):
            raise CiscoDownloadError("Selected Cisco files do not share valid product metadata")
        response = cisco_client().request_download(search["pid"], next(iter(mdf_ids)),
                                                   search["transaction_id"], guids)
    except (KeyError, CiscoDownloadError) as exc:
        with cisco_lock:
            cisco_download_jobs.pop(job_id, None)
        return cisco_failure(exc)
    eula_required = cisco_response_requires(response, "eulaContent")
    k9_required = cisco_response_requires(response, "k9Content")
    acceptance_required = eula_required or k9_required
    downloads = response.get("downloads") or []
    job = {"id": job_id, "status": "eula-required" if acceptance_required else "downloading",
           "progress": 0, "files": [], "error": "", "created": time.time()}
    with cisco_lock:
        cisco_download_jobs[job_id] = job
    if acceptance_required:
        job["pending"] = {"search": search, "selected": selected, "downloads": downloads,
                          "eula_required": eula_required, "k9_required": k9_required}
        return jsonify({key: value for key, value in job.items() if key != "pending"} |
                       {"agreement": {"eula": eula_required, "k9": k9_required}}), 202
    threading.Thread(target=run_cisco_download, args=(job_id, search, selected, downloads),
                     daemon=True).start()
    return jsonify(job), 202


@app.post("/api/cisco/downloads/<job_id>/accept")
def cisco_accept(job_id: str):
    job = cisco_download_jobs.get(job_id)
    if not job or job.get("status") != "eula-required" or "pending" not in job:
        abort(404)
    body = json_object()
    pending = job["pending"]
    if pending["eula_required"] and body.get("accept_eula") is not True:
        return jsonify(error="The Cisco EULA must be accepted"), 400
    names = [item["name"] for item in pending["selected"]]
    try:
        client = cisco_client()
        if pending["eula_required"]:
            client.accept_eula(names)
        if pending["k9_required"]:
            for name in names:
                client.accept_k9(name, commercial_or_civil=body.get("commercial_or_civil") is True,
                                  not_government_or_military=body.get("not_government_or_military") is True)
        response = client.request_download(pending["search"]["pid"], pending["selected"][0]["mdf_id"],
                                           pending["search"]["transaction_id"],
                                           [item["guid"] for item in pending["selected"]])
    except CiscoDownloadError as exc:
        return cisco_failure(exc)
    if cisco_response_requires(response, "eulaContent") or cisco_response_requires(response, "k9Content"):
        return jsonify(error="Cisco still requires agreement confirmation"), 409
    downloads = response.get("downloads") or []
    job.pop("pending", None)
    job["status"] = "downloading"
    threading.Thread(target=run_cisco_download,
                     args=(job_id, pending["search"], pending["selected"], downloads),
                     daemon=True).start()
    return jsonify(job), 202


@app.get("/api/cisco/downloads/<job_id>")
def cisco_download_status(job_id: str):
    job = cisco_download_jobs.get(job_id)
    if not job:
        abort(404)
    return jsonify({key: value for key, value in job.items() if key != "pending"})


@app.get("/api/archive")
def archive_list():
    enforce_archive_policy()
    items = []
    with cross_process_archive_lock():
        if ARCHIVE.exists():
            paths = [path for path in ARCHIVE.glob("*/*")
                     if path.is_file() and path.suffix.lower() in {".iso", ".zip"}]
            for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
                stat = path.stat()
                items.append({"job_id": path.parent.name, "name": path.name,
                              "size": stat.st_size, "created": stat.st_mtime,
                              "url": f"/archive/{path.parent.name}/{path.name}",
                              "has_report": (path.parent / "build-report.json").is_file()})
    return jsonify(items)


@app.get("/api/archive/<job_id>/<path:name>/checksums")
def archive_checksums(job_id: str, name: str):
    archive_dir = (ARCHIVE / job_id).resolve()
    path = (archive_dir / name).resolve()
    if ARCHIVE not in archive_dir.parents or archive_dir not in path.parents:
        abort(404)
    with cross_process_archive_lock():
        if not path.is_file() or path.suffix.lower() not in {".iso", ".zip"}:
            abort(404)
        return jsonify(name=name, size=path.stat().st_size, **file_checksums(path))


@app.post("/api/cleanup")
def cleanup():
    with operation_lock:
        if cisco_download_running():
            return jsonify(error="Temporary files cannot be cleaned during a Cisco download"), 409
        with job_lock:
            if any(job["status"] in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify(error="Temporary files cannot be cleaned while a build is running"), 409
        with upload_lock:
            if uploads:
                return jsonify(error="Temporary files cannot be cleaned while an upload is active"), 409
        if docker_build_running():
            return jsonify(error="Temporary files cannot be cleaned while a Docker build is running"), 409
        removed_bytes = 0
        removed_items = 0
        removed_by_area: dict[str, int] = {}
        for area, root in (("uploads", DATA), ("work", WORK), ("output", OUTPUT)):
            area_items = 0
            if not root.exists():
                continue
            for child in list(root.iterdir()):
                paths = [child]
                if child.is_dir() and not child.is_symlink():
                    paths.extend(child.rglob("*"))
                for path in paths:
                    if path.is_file() or path.is_symlink():
                        try:
                            removed_bytes += path.lstat().st_size
                        except OSError:
                            pass
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    try:
                        child.unlink()
                    except FileNotFoundError:
                        continue
                removed_items += 1
                area_items += 1
            removed_by_area[area] = area_items
        cleared_artifacts = 0
        changed_jobs: list[str] = []
        with job_lock:
            for job_id, job in jobs.items():
                artifacts = job.get("artifacts", [])
                retained = [
                    artifact for artifact in artifacts
                    if str(artifact.get("url", "")).startswith("/archive/")
                ]
                if len(retained) != len(artifacts):
                    cleared_artifacts += len(artifacts) - len(retained)
                    job["artifacts"] = retained
                    job["updated"] = time.time()
                    changed_jobs.append(job_id)
        for job_id in changed_jobs:
            persist_job(job_id)
        log_event("workspace_cleanup", cleared_artifacts=cleared_artifacts,
                  removed_bytes=removed_bytes, removed_items=removed_items, **removed_by_area)
        append_activity(
            f"Workspace cleanup completed: {removed_items} top-level items and "
            f"{removed_bytes} bytes removed; completed archives were kept."
        )
    return jsonify(ok=True, removed_bytes=removed_bytes, removed_items=removed_items,
                   cleared_artifacts=cleared_artifacts,
                   removed=removed_by_area,
                   message="Uploads, partial files, build work, and raw output were removed. Archived images were kept.")


@app.post("/api/uploads/init")
def upload_init():
    body = json_object()
    try:
        name = upload_name(body.get("name"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    size = body.get("size")
    if isinstance(size, bool) or not isinstance(size, int):
        return jsonify(error="Upload size must be an integer"), 400
    allowed = (".iso", ".rpm", *ARCHIVE_SUFFIXES, ".yaml", ".yml", ".cfg", ".ini", ".sh", ".cms", ".txt", ".json")
    if not name or size <= 0 or size > MAX_UPLOAD_BYTES or not name.lower().endswith(allowed):
        return jsonify(error="Unsupported file or invalid size"), 400
    with operation_lock:
        if cisco_download_running():
            return jsonify(error="Wait for the Cisco download to finish before uploading"), 409
        with job_lock:
            if any(job["status"] in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify(error="Wait for the current build to finish before uploading more files"), 409
        if docker_build_running():
            return jsonify(error="Wait for the current Docker build to finish before uploading more files"), 409
        with upload_lock:
            reserved = sum(
                max(0, int(item["size"]) - int(item["received"]))
                for item in uploads.values()
            )
            if shutil.disk_usage(DATA).free < reserved + size + MIN_FREE_BYTES:
                return jsonify(error="Not enough free disk space for this upload"), 507
            upload_id = uuid.uuid4().hex
            parts = DATA / ".parts"
            parts.mkdir(parents=True, exist_ok=True)
            temp = parts / f"{upload_id}.part"
            temp.touch()
            uploads[upload_id] = {"name": name, "size": size, "received": 0,
                                  "temp": str(temp), "updated": time.time()}
    log_event("upload_started", bytes=size, upload_id=upload_id)
    append_activity(f"Upload started: {size} bytes expected.")
    return jsonify(id=upload_id)


@app.put("/api/uploads/<upload_id>")
def upload_chunk(upload_id: str):
    chunk = request.get_data(cache=False)
    if not chunk:
        return jsonify(error="Upload chunk is empty"), 400
    with upload_lock:
        item = uploads.get(upload_id)
        if not item:
            abort(404)
        try:
            offset = int(request.args.get("offset", -1))
        except ValueError:
            return jsonify(error="Invalid chunk offset"), 400
        if offset != item["received"]:
            return jsonify(error="Unexpected chunk offset", expected=item["received"]), 409
        if item["received"] + len(chunk) > item["size"]:
            return jsonify(error="Upload exceeds declared size"), 400
        with open(item["temp"], "ab") as handle:
            handle.write(chunk)
        item["received"] += len(chunk)
        item["updated"] = time.time()
        percent = item["received"] * 100 // item["size"]
        previous = item.get("reported_percent", -10)
        if percent >= previous + 10 or item["received"] == item["size"]:
            item["reported_percent"] = percent
            log_event("upload_progress", percent=percent, received_bytes=item["received"],
                      total_bytes=item["size"], upload_id=upload_id)
            append_activity(
                f"Upload progress: {percent}% ({item['received']} of {item['size']} bytes)."
            )
        return jsonify(received=item["received"], size=item["size"])


@app.delete("/api/uploads/session/<upload_id>")
def cancel_upload(upload_id: str):
    with upload_lock:
        item = uploads.get(upload_id)
        if not item:
            abort(404)
        if item.get("completing"):
            return jsonify(error="Upload is already being completed"), 409
        uploads.pop(upload_id)
    Path(item["temp"]).unlink(missing_ok=True)
    log_event("upload_cancelled", received_bytes=item["received"], upload_id=upload_id)
    append_activity(f"Upload cancelled after {item['received']} bytes.")
    return jsonify(ok=True)


@app.post("/api/uploads/<upload_id>/complete")
def upload_complete(upload_id: str):
    with upload_lock:
        item = uploads.get(upload_id)
        if not item:
            abort(404)
        if item.get("completing"):
            return jsonify(error="Upload is already being completed"), 409
        if item["received"] != item["size"]:
            return jsonify(error="Upload is incomplete"), 409
        item["completing"] = True
    with upload_lock:
        target = DATA / item["name"]
        while target.exists() or (extraction_path(target) and extraction_path(target).exists()):
            stem, suffix = split_upload_name(item["name"])
            target = DATA / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
        Path(item["temp"]).replace(target)
    extracted = 0
    try:
        if archive_suffix(target.name):
            destination = extraction_path(target)
            if destination is None:
                raise ValueError("Unsupported archive type")
            destination.mkdir()
            with tarfile.open(target, "r:*") as archive:
                members = archive.getmembers()
                if len(members) > MAX_TAR_MEMBERS:
                    raise ValueError("Tar archive contains too many files")
                expanded_size = sum(member.size for member in members if member.isfile())
                if expanded_size > MAX_EXTRACTED_BYTES:
                    raise ValueError("Expanded tar archive is too large")
                if shutil.disk_usage(DATA).free < expanded_size + MIN_FREE_BYTES:
                    raise ValueError("Not enough free disk space to extract tar archive")
                for member in members:
                    member_target = (destination / member.name).resolve()
                    if destination.resolve() not in member_target.parents and member_target != destination.resolve():
                        raise ValueError("Unsafe path in tar archive")
                    if member.issym() or member.islnk():
                        raise ValueError("Links are not accepted in uploaded tar archives")
                archive.extractall(destination, members=members, filter="data")
                extracted = sum(1 for member in members if member.isfile())
    except ValueError as exc:
        if archive_suffix(target.name):
            shutil.rmtree(destination, ignore_errors=True)
        target.unlink(missing_ok=True)
        return jsonify(error=f"Tar archive rejected: {exc}"), 400
    except (tarfile.TarError, OSError) as exc:
        if archive_suffix(target.name):
            shutil.rmtree(destination, ignore_errors=True)
        target.unlink(missing_ok=True)
        log_event("upload_archive_failed", error_type=type(exc).__name__, upload_id=upload_id)
        return jsonify(error="Tar archive could not be read safely"), 400
    finally:
        with upload_lock:
            uploads.pop(upload_id, None)
    log_event("upload_completed", bytes=target.stat().st_size, extracted_files=extracted,
              upload_id=upload_id)
    if extracted:
        append_activity(f"Upload completed and archive extracted: {extracted} files ready.")
    else:
        append_activity("Upload completed and file is ready.")
    return jsonify(path=target.name, size=target.stat().st_size, extracted=extracted)


@app.delete("/api/uploads/<path:name>")
def delete_upload(name: str):
    with operation_lock:
        try:
            path = safe_data_path(name)
        except ValueError:
            abort(404)
        if not path.is_file():
            abort(404)
        with job_lock:
            if any(job["status"] in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify(error="Inputs cannot be deleted while a build is running"), 409
        if docker_build_running():
            return jsonify(error="Inputs cannot be deleted while a Docker build is running"), 409
        destination = extraction_path(path)
        path.unlink()
        if destination is not None and destination.is_dir():
            shutil.rmtree(destination, ignore_errors=True)
    return jsonify(ok=True)


@app.get("/api/jobs")
def list_jobs():
    with job_lock:
        summary = [public_job(job, include_log=False) for job in jobs.values()]
    return jsonify(sorted(summary, key=lambda x: x["created"], reverse=True))


@app.post("/api/jobs")
def create_job():
    try:
        payload = validate_build_payload(json_object())
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    with operation_lock:
        if cisco_download_running():
            return jsonify(error="Wait for the Cisco download to finish before starting a build"), 409
        with upload_lock:
            if uploads:
                return jsonify(error="Wait for all uploads to finish before starting the build"), 409
        if docker_build_running():
            return jsonify(error="A Docker build is already running"), 409
        with job_lock:
            if any(j["status"] in ACTIVE_JOB_STATUSES for j in jobs.values()):
                return jsonify(error="A build is already running"), 409
        plan = create_build_plan(payload)
        if not plan["ready"]:
            return jsonify(error="BuildPlan is blocked: " + "; ".join(plan["blockers"]),
                           plan=plan), 400
        confirmed_fingerprint = payload.get("confirmed_plan_fingerprint")
        if confirmed_fingerprint and confirmed_fingerprint != plan["fingerprint"]:
            return jsonify(error="Inventory changed since this BuildPlan was reviewed; "
                                 "refresh and confirm the new plan before building",
                           plan=plan), 409
        payload["pkglist"] = [item["id"] for item in plan["selected_packages"]]
        payload["automatic_smu_selection"] = False
        job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        with job_lock:
            if any(j["status"] in ACTIVE_JOB_STATUSES for j in jobs.values()):
                return jsonify(error="A build is already running"), 409
            jobs[job_id] = {"id": job_id, "status": "queued", "created": time.time(),
                            "updated": time.time(), "progress": 1, "phase": "Validating inputs",
                            "log": "", "artifacts": [], "payload": payload, "command": [],
                            "inventory_revision": plan["inventory_revision"],
                            "plan_fingerprint": plan["fingerprint"], "build_plan": plan}
        try:
            command = build_command(payload, job_id)
            cleanup_paths = build_cleanup_paths(payload, plan["selected_packages"])
        except ValueError as exc:
            with job_lock:
                jobs.pop(job_id, None)
            return jsonify(error=str(exc)), 400
        except Exception as exc:  # noqa: BLE001 - setup failures become a stable API error
            with job_lock:
                jobs.pop(job_id, None)
            log_event("build_setup_failed", error_type=type(exc).__name__, job_id=job_id,
                      inventory_revision=plan["inventory_revision"], plan_fingerprint=plan["fingerprint"])
            return jsonify(error="Build setup failed; inspect the service log using the request ID"), 503
        with job_lock:
            jobs[job_id].update(status="running", progress=3, phase="Preparing build container",
                                command=command, command_preview=command_preview(command),
                                cleanup_paths=[str(path) for path in cleanup_paths])
        with store_lock, sqlite3.connect(JOB_DB) as database:
            rows = database.execute(
                "SELECT text FROM activity ORDER BY id DESC LIMIT 50"
            ).fetchall()
        recent_activity = "\n".join(row[0] for row in reversed(rows))
        if recent_activity:
            append_log(job_id, "Upload and workspace activity:\n" + recent_activity + "\n\n")
        persist_job(job_id)
    threading.Thread(target=run_job, args=(job_id, command), daemon=True).start()
    return jsonify(id=job_id), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            abort(404)
        return jsonify(public_job(job))


@app.delete("/api/jobs/<job_id>")
def cancel_job(job_id: str):
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            abort(404)
        if job["status"] not in {"queued", "running", "finalizing"}:
            return jsonify(error="Build is not running"), 409
        previous_status = job["status"]
        job["status"] = "cancelling"
        process = job_processes.get(job_id)
        process_phase = job.get("process_phase")
    persist_job(job_id)
    process_was_running = process is not None and process.poll() is None
    if process_was_running:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if previous_status == "finalizing":
        return jsonify(ok=True)
    if process_phase == "pulling" or not process_was_running:
        with job_lock:
            jobs[job_id].update(status="cancelled", phase="Cancelled", finished=time.time(),
                                updated=time.time())
        append_log(job_id, "\nBuild cancelled by user.\n")
        persist_job(job_id)
        return jsonify(ok=True)
    try:
        subprocess.run([DOCKER_BIN, "stop", "--time", "10", f"giso-build-{job_id}"],
                       timeout=20, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        with job_lock:
            jobs[job_id]["status"] = "running"
        append_log(job_id, f"\nUnable to stop the build container: {exc}\n")
        return jsonify(error="The build container could not be stopped"), 503
    with job_lock:
        jobs[job_id].update(status="cancelled", finished=time.time(), updated=time.time())
    append_log(job_id, "\nBuild cancelled by user.\n")
    persist_job(job_id)
    return jsonify(ok=True)


@app.get("/download/<job_id>/<path:name>")
def download(job_id: str, name: str):
    job_dir = (OUTPUT / job_id).resolve()
    if OUTPUT not in job_dir.parents:
        abort(404)
    return send_from_directory(job_dir, name, as_attachment=True)


@app.get("/archive/<job_id>/<path:name>")
def archive_download(job_id: str, name: str):
    archive_dir = (ARCHIVE / job_id).resolve()
    if ARCHIVE not in archive_dir.parents:
        abort(404)
    return send_from_directory(archive_dir, name, as_attachment=True)


@app.delete("/api/archive/<job_id>/<path:name>")
def archive_delete(job_id: str, name: str):
    archive_dir = (ARCHIVE / job_id).resolve()
    path = (archive_dir / name).resolve()
    if ARCHIVE not in archive_dir.parents or archive_dir not in path.parents:
        abort(404)
    with cross_process_archive_lock():
        if not path.is_file() or path.suffix.lower() not in {".iso", ".zip"}:
            abort(404)
        size = path.stat().st_size
        path.unlink()
        with checksum_lock:
            checksum_cache.clear()
        try:
            archive_dir.rmdir()
        except OSError:
            pass
    return jsonify(ok=True, removed=name, removed_bytes=size)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app.run(host="127.0.0.1", port=8080, threaded=True)
