from __future__ import annotations

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
    PLATFORMS,
    check_upgrade_matrix,
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
jobs: dict[str, dict] = {}
job_processes: dict[str, subprocess.Popen] = {}
job_persisted_at: dict[str, float] = {}
uploads: dict[str, dict] = {}
cisco_searches: dict[str, dict] = {}
cisco_download_jobs: dict[str, dict] = {}
cisco_api_client: CiscoSoftwareClient | None = None
checksum_cache: dict[tuple[str, int, int], dict[str, str]] = {}
job_lock = threading.RLock()
upload_lock = threading.Lock()
archive_lock = threading.RLock()
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
MAX_JOB_HISTORY = int(os.environ.get("MAX_JOB_HISTORY", "100"))
ARCHIVE_RETENTION_DAYS = int(os.environ.get("ARCHIVE_RETENTION_DAYS", "30"))
MAX_ARCHIVE_BYTES = int(os.environ.get("MAX_ARCHIVE_BYTES", str(50 * 1024**3)))
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


def extract_cisco_archive(path: Path) -> int:
    if not path.name.lower().endswith((".tar", ".tgz")):
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
    r"(?:[\"'][^\"'\r\n]*?\.(?:iso|rpm|zip|tar|tgz|yaml|yml|cfg|ini|sh|cms|txt|json)[\"']|"
    r"(?<!\w)[^\s\"'=]+?\.(?:iso|rpm|zip|tar|tgz|yaml|yml|cfg|ini|sh|cms|txt|json)(?!\w))",
    re.IGNORECASE,
)


def safe_log_text(text: str) -> str:
    """Remove licensed or sensitive artifact names from operator-visible logs."""
    return ARTIFACT_TOKEN.sub("[artifact]", text)


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
    return {key: value for key, value in job.items() if key not in private}


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


def inventory_id(relative_path: str, sha256: str) -> str:
    """Return an opaque, stable identity without exposing an absolute path."""
    identity = hashlib.sha256(f"{relative_path}\0{sha256}".encode()).hexdigest()
    return f"file_{identity[:24]}"


def inventory_files() -> list[dict]:
    """Build the canonical, browser-safe inventory for supported input files."""
    supported = {".iso", ".rpm", ".tar", ".tgz", ".yaml", ".yml", ".cfg",
                 ".ini", ".sh", ".cms", ".json"}
    physical: list[dict] = []
    for root, names, filenames in os.walk(DATA):
        names[:] = [name for name in names
                    if name != ".parts" and not name.startswith("output_gisobuild")]
        root_path = Path(root)
        for name in filenames:
            path = root_path / name
            suffix = path.suffix.lower()
            if suffix not in supported:
                continue
            try:
                relative_path = rel_data(path)
                stat = path.stat()
                sha256 = file_checksums(path)["sha256"]
            except OSError:
                continue
            physical.append({
                "id": inventory_id(relative_path, sha256),
                "basename": name,
                "path": relative_path,
                "relative_path": relative_path,
                "size": stat.st_size,
                "sha256": sha256,
                "source": "tar" if path.parent != DATA else "upload",
                "metadata_source": "filename",
                "metadata_confidence": "low",
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


def giso_artifact_candidates(job_dir: Path) -> list[Path]:
    """Return output images eligible for verified archival."""
    top_level = list(job_dir.glob("*.iso"))
    images = top_level or [
        path for path in job_dir.rglob("*.iso")
        if any(tag in path.name.lower() for tag in ("golden", "giso"))
    ]
    return images + [path for path in job_dir.rglob("*.zip") if "usb" in path.name.lower()]


def archive_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def archive_timestamp(path: Path) -> float:
    artifacts = [item for item in path.iterdir()
                 if item.is_file() and item.suffix.lower() in {".iso", ".zip"}]
    return max((item.stat().st_mtime for item in artifacts), default=path.stat().st_mtime)


def enforce_archive_policy(*, protected_job_id: str | None = None) -> list[str]:
    """Remove expired archive jobs, then oldest jobs until the archive fits its quota."""
    removed: list[str] = []
    cutoff = time.time() - ARCHIVE_RETENTION_DAYS * 86400
    with archive_lock:
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
    with archive_lock:
        archive_dir.mkdir(parents=True, exist_ok=False)
        try:
            for source in candidates:
                destination = archive_dir / source.name
                if destination.exists():
                    raise RuntimeError(f"Build artifacts share the filename {source.name}")
                # The archive retention clock starts when the verified build is archived,
                # not when an old source file happened to be created.
                shutil.copyfile(source, destination)
                if source.stat().st_size != destination.stat().st_size or file_sha256(source) != file_sha256(destination):
                    raise RuntimeError(f"Archive verification failed for {source.name}")
                archived.append({"path": source.name, "size": destination.stat().st_size,
                                 "url": f"/archive/{job_id}/{source.name}"})
            enforce_archive_policy(protected_job_id=job_id)
            if not archive_dir.is_dir():
                raise RuntimeError("The completed GISO archive could not be retained")
            if before_cleanup is not None:
                before_cleanup()
        except Exception:
            shutil.rmtree(archive_dir, ignore_errors=True)
            raise
    for child in cleanup_paths or []:
        resolved = child.resolve()
        if DATA not in resolved.parents or not resolved.exists():
            continue
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
    shutil.rmtree(WORK / job_id, ignore_errors=True)
    shutil.rmtree(job_dir, ignore_errors=True)
    return archived


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
    if path.name.lower().endswith((".tar", ".tgz")):
        return DATA / path.name.removesuffix(".tgz").removesuffix(".tar")
    return None


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


def active_rpm_names() -> tuple[list[str], set[str]]:
    superseded: set[str] = set()
    inspected_bytes = 0
    pattern = re.compile(r"([A-Za-z0-9_-]+-[0-9][0-9.]*\.CSC\w+)\s+Full", re.IGNORECASE)
    for readme in DATA.rglob("*.txt"):
        try:
            size = readme.stat().st_size
            if size > MAX_SUPERSEDENCE_FILE_BYTES or inspected_bytes + size > MAX_SUPERSEDENCE_TOTAL_BYTES:
                continue
            inspected_bytes += size
            superseded.update(pattern.findall(readme.read_text(errors="ignore")))
        except OSError:
            pass
    candidates = [
        rpm.name for rpm in DATA.rglob("*.rpm")
        if not any(rpm.parent.name.startswith(identifier) for identifier in superseded)
    ]
    return candidates, superseded


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
    if len(isos) == 1:
        recommendation = recommend_smu_selection(isos[0], candidates)
    elif len(isos) > 1:
        recommendation = {"ready": False, "selected": [], "excluded": [],
                          "message": "More than one base ISO was found; keep one ISO or select it in Expert settings"}
    else:
        recommendation = {"ready": False, "selected": [], "excluded": [],
                          "message": "Upload one base ISO before SMUs can be selected"}
    matrices = [item["path"] for item in files
                if item["type"] == ".json" and Path(item["path"]).name.startswith("compatibility_matrix_")]
    return {"files": sorted(files, key=lambda x: x["path"]), "dirs": sorted(dirs),
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
        if payload.get("automatic_smu_selection"):
            package_plan = recommend_smu_selection(iso, active_rpm_names()[0])
            if not package_plan["ready"]:
                raise ValueError(package_plan["message"])
            payload["pkglist"] = package_plan["selected"]
        profile = validate_platform_options(payload)
        payload["platform"] = profile["id"]
        selected_rpms = resolve_rpm_identifiers(payload.get("pkglist", []))
        selected_names = [item["basename"] for item in selected_rpms]
        payload["pkglist"] = selected_names
        smu_check = validate_smu_selection(iso, selected_names)
        if smu_check["issues"]:
            raise ValueError("SMU compatibility check failed: " + "; ".join(smu_check["issues"]))
        command += ["--iso", str(safe_data_path(iso))]
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


def glob_metacharacters(value: str) -> bool:
    return any(character in value for character in "*?[]")


def build_cleanup_paths(payload: dict) -> list[Path]:
    """Resolve only inputs explicitly owned by this build request."""
    paths: set[Path] = set()
    for key in PATH_OPTIONS:
        value = payload.get(key)
        if value:
            paths.add(safe_data_path(value))
    for key in ("repo", "bridging_fixes"):
        for value in payload.get(key) or []:
            paths.add(safe_data_path(value))
    for package in payload.get("pkglist") or []:
        if Path(package).name != package or glob_metacharacters(package):
            raise ValueError(f"RPM package must be an exact filename: {package!r}")
        matches = [path for path in DATA.rglob("*.rpm") if path.name == package]
        paths.update(matches)
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


def run_job(job_id: str, command: list[str]) -> None:
    try:
        append_log(job_id, "$ " + shlex.join(command) + "\n\n")
        log_event("build_started", job_id=job_id)
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
        try:
            pull_output, _ = pull.communicate(timeout=GISO_PULL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            pull.terminate()
            pull.wait(timeout=20)
            raise
        finally:
            with job_lock:
                job_processes.pop(job_id, None)
        if cancellation_requested(job_id):
            raise BuildCancelled("Build cancelled during image preparation")
        if pull.returncode:
            raise subprocess.CalledProcessError(pull.returncode, pull.args, output=pull_output)
        if pull_output:
            append_log(job_id, pull_output)
        log_event("image_pull_completed", job_id=job_id)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
        with job_lock:
            job_processes[job_id] = proc
            jobs[job_id]["process_phase"] = "building"
            jobs[job_id]["container_pid"] = proc.pid
        if proc.stdout is None:
            raise RuntimeError("Build container output stream is unavailable")
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
        persist_job(job_id)
        log_event("build_finished", exit_code=code, job_id=job_id,
                  status="success" if success else "failed")
    except BuildCancelled:
        with job_lock:
            job_processes.pop(job_id, None)
            jobs[job_id].update(status="cancelled", phase="Cancelled", finished=time.time(),
                                updated=time.time())
        persist_job(job_id)
        log_event("build_cancelled", job_id=job_id)
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
        log_event("build_failed", error_type=type(exc).__name__, job_id=job_id)


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
    docker_ok = False
    try:
        subprocess.run([DOCKER_BIN, "info"], timeout=5, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        docker_ok = True
    except (OSError, subprocess.SubprocessError):
        pass
    checks = {
        "docker": docker_ok,
        "tool": (TOOL / "src/gisobuild.py").is_file(),
        "storage": all(path.is_dir() for path in (DATA, OUTPUT, WORK, ARCHIVE, STATE)),
    }
    ready = all(checks.values())
    return jsonify(ok=ready, **checks), 200 if ready else 503


@app.get("/api/inputs")
def inputs():
    return jsonify(discover())


@app.get("/api/platforms")
def platforms():
    return jsonify([platform_profile(key) for key in PLATFORMS])


@app.post("/api/smu/recommendation")
def smu_recommendation():
    body = json_object()
    try:
        iso = cisco_text(body.get("iso"), "base ISO", maximum=4096)
        iso_path = safe_data_path(iso)
        if iso_path.suffix.lower() != ".iso" or not iso_path.is_file():
            raise ValueError("Select an uploaded base ISO")
        packages, _ = active_rpm_names()
        return jsonify(recommend_smu_selection(iso, packages))
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
        result = {"smu": validate_smu_selection(iso, package_names), "upgrade": None}
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
    with archive_lock:
        if ARCHIVE.exists():
            paths = [path for path in ARCHIVE.glob("*/*")
                     if path.is_file() and path.suffix.lower() in {".iso", ".zip"}]
            for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
                stat = path.stat()
                items.append({"job_id": path.parent.name, "name": path.name,
                              "size": stat.st_size, "created": stat.st_mtime,
                              "url": f"/archive/{path.parent.name}/{path.name}"})
    return jsonify(items)


@app.get("/api/archive/<job_id>/<path:name>/checksums")
def archive_checksums(job_id: str, name: str):
    archive_dir = (ARCHIVE / job_id).resolve()
    path = (archive_dir / name).resolve()
    if ARCHIVE not in archive_dir.parents or archive_dir not in path.parents:
        abort(404)
    with archive_lock:
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
    allowed = (".iso", ".rpm", ".tar", ".tgz", ".yaml", ".yml", ".cfg", ".ini", ".sh", ".cms", ".txt", ".json")
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
            target = DATA / f"{Path(item['name']).stem}-{uuid.uuid4().hex[:8]}{Path(item['name']).suffix}"
        Path(item["temp"]).replace(target)
    extracted = 0
    try:
        if target.name.lower().endswith((".tar", ".tgz")):
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
        if target.name.lower().endswith((".tar", ".tgz")):
            shutil.rmtree(destination, ignore_errors=True)
        target.unlink(missing_ok=True)
        return jsonify(error=f"Tar archive rejected: {exc}"), 400
    except (tarfile.TarError, OSError) as exc:
        if target.name.lower().endswith((".tar", ".tgz")):
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
        path.unlink()
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
        job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        with job_lock:
            if any(j["status"] in ACTIVE_JOB_STATUSES for j in jobs.values()):
                return jsonify(error="A build is already running"), 409
            jobs[job_id] = {"id": job_id, "status": "queued", "created": time.time(),
                            "updated": time.time(), "progress": 1, "phase": "Validating inputs",
                            "log": "", "artifacts": [], "payload": payload, "command": []}
        try:
            command = build_command(payload, job_id)
            cleanup_paths = build_cleanup_paths(payload)
        except ValueError as exc:
            with job_lock:
                jobs.pop(job_id, None)
            return jsonify(error=str(exc)), 400
        except Exception as exc:  # noqa: BLE001 - setup failures become a stable API error
            with job_lock:
                jobs.pop(job_id, None)
            log_event("build_setup_failed", error_type=type(exc).__name__, job_id=job_id)
            return jsonify(error="Build setup failed; inspect the service log using the request ID"), 503
        with job_lock:
            jobs[job_id].update(status="running", progress=3, phase="Preparing build container",
                                command=command,
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
    with archive_lock:
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
