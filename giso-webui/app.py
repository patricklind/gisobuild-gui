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

from flask import (
    Flask,
    abort,
    g,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from platform_validation import PLATFORMS, validate_platform_options
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
job_persisted_at: dict[str, float] = {}
uploads: dict[str, dict] = {}
checksum_cache: dict[tuple[str, int, int], dict[str, str]] = {}
job_lock = threading.RLock()
upload_lock = threading.Lock()
archive_lock = threading.RLock()
checksum_lock = threading.Lock()
operation_lock = threading.Lock()
store_lock = threading.Lock()
store_initialized = False
archive_policy_checked = 0.0
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024**3)))
MAX_EXTRACTED_BYTES = int(os.environ.get("MAX_EXTRACTED_BYTES", str(16 * 1024**3)))
MAX_TAR_MEMBERS = int(os.environ.get("MAX_TAR_MEMBERS", "10000"))
MAX_CHUNK_BYTES = int(os.environ.get("MAX_CHUNK_BYTES", str(16 * 1024**2)))
MAX_LOG_BYTES = int(os.environ.get("MAX_LOG_BYTES", str(10 * 1024**2)))
MAX_JOB_HISTORY = int(os.environ.get("MAX_JOB_HISTORY", "100"))
ARCHIVE_RETENTION_DAYS = int(os.environ.get("ARCHIVE_RETENTION_DAYS", "30"))
MAX_ARCHIVE_BYTES = int(os.environ.get("MAX_ARCHIVE_BYTES", str(50 * 1024**3)))
UPLOAD_SESSION_TTL = int(os.environ.get("UPLOAD_SESSION_TTL", str(24 * 60 * 60)))
GISO_PULL_TIMEOUT_SECONDS = int(os.environ.get("GISO_PULL_TIMEOUT_SECONDS", "600"))
ALLOWED_HOSTS = {host.strip() for host in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost,giso-webui").split(",") if host.strip()}
ACTIVE_JOB_STATUSES = {"queued", "running", "cancelling"}
MIN_FREE_BYTES = 512 * 1024**2
app.config["MAX_CONTENT_LENGTH"] = MAX_CHUNK_BYTES

if min(MAX_UPLOAD_BYTES, MAX_EXTRACTED_BYTES, MAX_TAR_MEMBERS, MAX_CHUNK_BYTES,
       MAX_LOG_BYTES, MAX_JOB_HISTORY, ARCHIVE_RETENTION_DAYS, MAX_ARCHIVE_BYTES,
       UPLOAD_SESSION_TTL, GISO_PULL_TIMEOUT_SECONDS) <= 0 or not ALLOWED_HOSTS:
    raise RuntimeError("Upload, extraction, tar, chunk and log limits must be positive")

PRIVATE_JOB_FIELDS = {"command", "payload", "container_pid"}


def log_event(event: str, **fields: object) -> None:
    """Write a compact operational event without sensitive filenames or payloads."""
    details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    app.logger.info("event=%s%s", event, f" {details}" if details else "")


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
    for key in set(BOOL_OPTIONS) | {"auto_repo"}:
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
        checksum_cache.clear()
        checksum_cache[key] = result
        return result


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


def archive_giso_artifacts_and_cleanup(job_id: str, job_dir: Path) -> list[dict]:
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
                shutil.copy2(source, destination)
                if source.stat().st_size != destination.stat().st_size or file_sha256(source) != file_sha256(destination):
                    raise RuntimeError(f"Archive verification failed for {source.name}")
                archived.append({"path": source.name, "size": destination.stat().st_size,
                                 "url": f"/archive/{job_id}/{source.name}"})
            enforce_archive_policy(protected_job_id=job_id)
            if not archive_dir.is_dir():
                raise RuntimeError("The completed GISO archive could not be retained")
        except Exception:
            shutil.rmtree(archive_dir, ignore_errors=True)
            raise
    for child in list(DATA.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
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


def discover() -> dict:
    files, dirs = [], []
    ignored = {".parts"}
    for root, names, filenames in os.walk(DATA):
        names[:] = [n for n in names if n not in ignored and not n.startswith("output_gisobuild")]
        root_path = Path(root)
        if root_path != DATA:
            dirs.append(rel_data(root_path))
        for name in filenames:
            if name.lower().endswith((".iso", ".rpm", ".tar", ".tgz", ".yaml", ".yml", ".cfg", ".ini", ".sh", ".cms")):
                path = root_path / name
                files.append({"path": rel_data(path), "size": path.stat().st_size, "type": path.suffix.lower()})
    superseded = set()
    pattern = re.compile(r"([A-Za-z0-9_-]+-[0-9][0-9.]*\.CSC\w+)\s+Full", re.IGNORECASE)
    for readme in DATA.rglob("*.txt"):
        try:
            superseded.update(pattern.findall(readme.read_text(errors="ignore")))
        except OSError:
            pass
    recommended = []
    for rpm in DATA.rglob("*.rpm"):
        if not any(rpm.parent.name.startswith(identifier) for identifier in superseded):
            recommended.append(rpm.name)
    return {"files": sorted(files, key=lambda x: x["path"]), "dirs": sorted(dirs),
            "image": IMAGE, "recommended": sorted(set(recommended)),
            "superseded": sorted(superseded)}


def append_log(job_id: str, text: str) -> None:
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
        profile = validate_platform_options(payload)
        payload["platform"] = profile["id"]
        command += ["--iso", str(safe_data_path(iso))]
        for key, option in PATH_OPTIONS.items():
            if key in {"iso", "yamlfile"}:
                continue
            if payload.get(key):
                command += [option, str(safe_data_path(payload[key]))]
        if payload.get("auto_repo", True) and payload.get("pkglist"):
            staged_repo = WORK / job_id / "repo"
            staged_repo.mkdir(parents=True, exist_ok=True)
            for package in payload["pkglist"]:
                if "/" in package:
                    raise ValueError(f"RPM package must be a filename: {package!r}")
                matches = list(DATA.rglob(package))
                if package.lower().endswith(".rpm") and not matches:
                    raise ValueError(f"RPM {package!r} was not found")
                if package.lower().endswith(".rpm") and len(matches) > 1:
                    hashes = {file_sha256(match) for match in matches}
                    if len(hashes) > 1:
                        raise ValueError(f"Different RPM files share the name {package!r}; remove the unwanted copy")
                if matches:
                    shutil.copy2(matches[0], staged_repo / matches[0].name)
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


def run_job(job_id: str, command: list[str]) -> None:
    try:
        append_log(job_id, "$ " + shlex.join(command) + "\n\n")
        log_event("build_started", job_id=job_id)
        log_event("image_pull_started", job_id=job_id)
        pull = subprocess.run(
            [DOCKER_BIN, "pull", "--platform", "linux/amd64", IMAGE],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=GISO_PULL_TIMEOUT_SECONDS,
        )
        if pull.stdout:
            append_log(job_id, pull.stdout)
        log_event("image_pull_completed", job_id=job_id)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        with job_lock:
            jobs[job_id]["container_pid"] = proc.pid
        if proc.stdout is None:
            raise RuntimeError("Build container output stream is unavailable")
        for line in proc.stdout:
            append_log(job_id, line)
        code = proc.wait()
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
            artifacts = archive_giso_artifacts_and_cleanup(job_id, job_dir)
        with job_lock:
            if jobs[job_id]["status"] not in {"cancelled", "cancelling"}:
                jobs[job_id].update(status="success" if success else "failed",
                                    exit_code=code, artifacts=artifacts, finished=time.time(),
                                    updated=time.time(),
                                    progress=100 if code == 0 else jobs[job_id].get("progress", 0),
                                    phase="Complete" if code == 0 else "Build failed")
        persist_job(job_id)
        log_event("build_finished", exit_code=code, job_id=job_id,
                  status="success" if success else "failed")
    except Exception as exc:  # noqa: BLE001 - background failures must update job state
        append_log(job_id, f"\nERROR: {exc}\n")
        with job_lock:
            jobs[job_id].update(status="failed", error=str(exc), finished=time.time(),
                                updated=time.time())
        persist_job(job_id)
        log_event("build_failed", error_type=type(exc).__name__, job_id=job_id)


@app.get("/")
def index():
    return render_template("index.html")


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
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
    return jsonify(ok=ready, **checks, image=IMAGE), 200 if ready else 503


@app.get("/api/inputs")
def inputs():
    return jsonify(discover())


@app.get("/api/platforms")
def platforms():
    return jsonify([{"id": key, **value} for key, value in PLATFORMS.items()])


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
        log_event("workspace_cleanup", removed_bytes=removed_bytes,
                  removed_items=removed_items, **removed_by_area)
    return jsonify(ok=True, removed_bytes=removed_bytes, removed_items=removed_items,
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
    allowed = (".iso", ".rpm", ".tar", ".tgz", ".yaml", ".yml", ".cfg", ".ini", ".sh", ".cms", ".txt")
    if not name or size <= 0 or size > MAX_UPLOAD_BYTES or not name.lower().endswith(allowed):
        return jsonify(error="Unsupported file or invalid size"), 400
    with operation_lock:
        with job_lock:
            if any(job["status"] in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify(error="Wait for the current build to finish before uploading more files"), 409
        if docker_build_running():
            return jsonify(error="Wait for the current Docker build to finish before uploading more files"), 409
        if shutil.disk_usage(DATA).free < size + MIN_FREE_BYTES:
            return jsonify(error="Not enough free disk space for this upload"), 507
        upload_id = uuid.uuid4().hex
        parts = DATA / ".parts"
        parts.mkdir(parents=True, exist_ok=True)
        temp = parts / f"{upload_id}.part"
        temp.touch()
        with upload_lock:
            uploads[upload_id] = {"name": name, "size": size, "received": 0,
                                  "temp": str(temp), "updated": time.time()}
    log_event("upload_started", bytes=size, upload_id=upload_id)
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
    except (tarfile.TarError, OSError, ValueError) as exc:
        if target.name.lower().endswith((".tar", ".tgz")):
            shutil.rmtree(destination, ignore_errors=True)
        target.unlink(missing_ok=True)
        return jsonify(error=f"Tar archive rejected: {exc}"), 400
    finally:
        with upload_lock:
            uploads.pop(upload_id, None)
    log_event("upload_completed", bytes=target.stat().st_size, extracted_files=extracted,
              upload_id=upload_id)
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
        except ValueError as exc:
            with job_lock:
                jobs.pop(job_id, None)
            return jsonify(error=str(exc)), 400
        except Exception as exc:  # noqa: BLE001 - setup failures become a stable API error
            with job_lock:
                jobs.pop(job_id, None)
            return jsonify(error=f"Build setup failed: {exc}"), 503
        with job_lock:
            jobs[job_id].update(status="running", progress=3, phase="Preparing build container", command=command)
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
        if job["status"] not in {"queued", "running"}:
            return jsonify(error="Build is not running"), 409
        job["status"] = "cancelling"
    persist_job(job_id)
    try:
        subprocess.run([DOCKER_BIN, "stop", "--time", "10", f"giso-build-{job_id}"],
                       timeout=20, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        with job_lock:
            jobs[job_id]["status"] = "running"
        append_log(job_id, f"\nUnable to stop the build container: {exc}\n")
        return jsonify(error="The build container could not be stopped"), 503
    with job_lock:
        jobs[job_id].update(status="cancelled", finished=time.time())
    append_log(job_id, "\nBuild cancelled by user.\n")
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
