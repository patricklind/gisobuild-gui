from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

app = Flask(__name__)
DATA = Path(os.environ.get("DATA_ROOT", "/data")).resolve()
OUTPUT = Path(os.environ.get("OUTPUT_ROOT", "/output")).resolve()
TOOL = Path(os.environ.get("TOOL_ROOT", "/tool")).resolve()
WORK = Path(os.environ.get("WORK_ROOT", "/work")).resolve()
ARCHIVE = Path(os.environ.get("ARCHIVE_ROOT", "/archive")).resolve()
IMAGE = os.environ.get("GISO_IMAGE", "ciscogisobuild/cisco-xr-gisobuild:2.3.4")
jobs: dict[str, dict] = {}
uploads: dict[str, dict] = {}
checksum_cache: dict[tuple[str, int, int], dict[str, str]] = {}
job_lock = threading.Lock()
upload_lock = threading.Lock()
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024**3)))
MAX_EXTRACTED_BYTES = int(os.environ.get("MAX_EXTRACTED_BYTES", str(16 * 1024**3)))
MAX_TAR_MEMBERS = int(os.environ.get("MAX_TAR_MEMBERS", "10000"))
MAX_CHUNK_BYTES = int(os.environ.get("MAX_CHUNK_BYTES", str(16 * 1024**2)))
MAX_LOG_BYTES = int(os.environ.get("MAX_LOG_BYTES", str(10 * 1024**2)))
ALLOWED_HOSTS = {host.strip() for host in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost,giso-webui").split(",")}
app.config["MAX_CONTENT_LENGTH"] = MAX_CHUNK_BYTES

if min(MAX_UPLOAD_BYTES, MAX_EXTRACTED_BYTES, MAX_TAR_MEMBERS, MAX_CHUNK_BYTES, MAX_LOG_BYTES) <= 0:
    raise RuntimeError("Upload, extraction, tar, chunk and log limits must be positive")

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
    for key in set(PATH_OPTIONS) | {"label"}:
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


def archive_giso_artifacts_and_cleanup(job_id: str, job_dir: Path) -> list[dict]:
    """Archive verified Golden ISO and USB boot files, then remove build inputs/output."""
    iso_candidates = list(job_dir.glob("*.iso"))
    if not iso_candidates:
        iso_candidates = [path for path in job_dir.rglob("*.iso") if any(tag in path.name.lower() for tag in ("golden", "giso"))]
    if not iso_candidates:
        raise RuntimeError("No Golden ISO was produced; source files were kept")
    usb_candidates = [path for path in job_dir.rglob("*.zip") if "usb" in path.name.lower()]
    candidates = iso_candidates + usb_candidates
    archive_dir = ARCHIVE / job_id
    archive_dir.mkdir(parents=True, exist_ok=False)
    archived = []
    try:
        for source in candidates:
            if source.is_symlink() or job_dir.resolve() not in source.resolve().parents:
                raise RuntimeError(f"Unsafe build artifact: {source.name}")
            destination = archive_dir / source.name
            shutil.copy2(source, destination)
            if source.stat().st_size != destination.stat().st_size or file_sha256(source) != file_sha256(destination):
                raise RuntimeError(f"Archive verification failed for {source.name}")
            archived.append({"path": source.name, "size": destination.stat().st_size,
                             "url": f"/archive/{job_id}/{source.name}"})
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
            ["docker", "ps", "-q", "--filter", "label=app=giso-webui"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return True


def extraction_path(path: Path) -> Path | None:
    if path.name.lower().endswith((".tar", ".tgz")):
        return DATA / path.name.removesuffix(".tgz").removesuffix(".tar")
    return None


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


def child_mount_args() -> list[str]:
    """Share only required storage with the build container, never docker.sock."""
    container = os.environ.get("HOSTNAME", "giso-webui")
    result = subprocess.run(
        ["docker", "inspect", container], check=True, capture_output=True, text=True
    )
    info = __import__("json").loads(result.stdout)[0]
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
        "docker", "run", "--platform", "linux/amd64", "--rm",
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
        command += ["--iso", str(safe_data_path(iso))]
        for key, option in PATH_OPTIONS.items():
            if key in {"iso", "yamlfile"}:
                continue
            if payload.get(key):
                command += [option, str(safe_data_path(payload[key]))]
        if payload.get("auto_repo", True) and payload.get("pkglist"):
            staged_repo = Path("/work") / job_id / "repo"
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
        subprocess.run(["docker", "pull", "--platform", "linux/amd64", IMAGE], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        with job_lock:
            jobs[job_id]["container_pid"] = proc.pid
        assert proc.stdout
        for line in proc.stdout:
            append_log(job_id, line)
        code = proc.wait()
        artifacts = []
        job_dir = OUTPUT / job_id
        if job_dir.exists():
            for path in sorted(job_dir.rglob("*")):
                if path.is_file() and (path.suffix in {".iso", ".zip", ".json", ".txt"} or "log" in path.name):
                    artifacts.append({"path": str(path.relative_to(job_dir)), "size": path.stat().st_size})
        success = code == 0 and any((job_dir / artifact["path"]).parent == job_dir and artifact["path"].lower().endswith(".iso") for artifact in artifacts)
        if success:
            artifacts = archive_giso_artifacts_and_cleanup(job_id, job_dir)
        with job_lock:
            if jobs[job_id]["status"] != "cancelled":
                jobs[job_id].update(status="success" if success else "failed",
                                    exit_code=code, artifacts=artifacts, finished=time.time(),
                                    progress=100 if code == 0 else jobs[job_id].get("progress", 0),
                                    phase="Complete" if code == 0 else "Build failed")
    except Exception as exc:  # noqa: BLE001 - background failures must update job state
        append_log(job_id, f"\nERROR: {exc}\n")
        with job_lock:
            jobs[job_id].update(status="failed", error=str(exc), finished=time.time())


@app.get("/")
def index():
    return render_template("index.html")


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(BadRequest)
def bad_request(error):
    return jsonify(error=error.description or "Invalid request"), 400


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify(error=f"Request exceeds the {MAX_CHUNK_BYTES}-byte chunk limit"), 413


@app.before_request
def validate_host():
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


@app.get("/api/health")
def health():
    docker_ok = False
    try:
        subprocess.run(["docker", "info"], timeout=5, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        docker_ok = True
    except (OSError, subprocess.SubprocessError):
        pass
    return jsonify(ok=docker_ok, docker=docker_ok, image=IMAGE)


@app.get("/api/inputs")
def inputs():
    return jsonify(discover())


@app.get("/api/archive")
def archive_list():
    items = []
    if ARCHIVE.exists():
        paths = [path for path in ARCHIVE.glob("*/*")
                 if path.is_file() and path.suffix.lower() in {".iso", ".zip"}]
        for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
            items.append({"job_id": path.parent.name, "name": path.name, "size": path.stat().st_size,
                          "created": path.stat().st_mtime,
                          "url": f"/archive/{path.parent.name}/{path.name}"})
    return jsonify(items)


@app.get("/api/archive/<job_id>/<path:name>/checksums")
def archive_checksums(job_id: str, name: str):
    archive_dir = (ARCHIVE / job_id).resolve()
    path = (archive_dir / name).resolve()
    if ARCHIVE not in archive_dir.parents or archive_dir not in path.parents:
        abort(404)
    if not path.is_file() or path.suffix.lower() not in {".iso", ".zip"}:
        abort(404)
    return jsonify(name=name, size=path.stat().st_size, **file_checksums(path))


@app.post("/api/cleanup")
def cleanup():
    with job_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            return jsonify(error="Temporary files cannot be cleaned while a build is running"), 409
    if docker_build_running():
        return jsonify(error="Temporary files cannot be cleaned while a Docker build is running"), 409
    removed_bytes = 0
    removed_items = 0
    targets = [DATA / ".parts"]
    targets.extend(path for path in WORK.iterdir() if path.is_dir()) if WORK.exists() else None
    for target in targets:
        if not target.exists():
            continue
        for path in target.rglob("*"):
            if path.is_file():
                try:
                    removed_bytes += path.stat().st_size
                except OSError:
                    pass
        if target == DATA / ".parts":
            for child in list(target.iterdir()):
                child.unlink(missing_ok=True)
                removed_items += 1
        else:
            shutil.rmtree(target)
            removed_items += 1
    return jsonify(ok=True, removed_bytes=removed_bytes, removed_items=removed_items,
                   message="Temporary files removed. Uploads and completed images were kept.")


@app.post("/api/uploads/init")
def upload_init():
    body = json_object()
    name = Path(str(body.get("name", ""))).name
    try:
        size = int(body.get("size", 0))
    except (TypeError, ValueError):
        return jsonify(error="Upload size must be an integer"), 400
    allowed = (".iso", ".rpm", ".tar", ".tgz", ".yaml", ".yml", ".cfg", ".ini", ".sh", ".cms", ".txt")
    if not name or size <= 0 or size > MAX_UPLOAD_BYTES or not name.lower().endswith(allowed):
        return jsonify(error="Unsupported file or invalid size"), 400
    with job_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            return jsonify(error="Wait for the current build to finish before uploading more files"), 409
    if docker_build_running():
        return jsonify(error="Wait for the current Docker build to finish before uploading more files"), 409
    if shutil.disk_usage(DATA).free < size + 512 * 1024**2:
        return jsonify(error="Not enough free disk space for this upload"), 507
    upload_id = uuid.uuid4().hex
    parts = DATA / ".parts"
    parts.mkdir(parents=True, exist_ok=True)
    temp = parts / f"{upload_id}.part"
    temp.touch()
    with upload_lock:
        uploads[upload_id] = {"name": name, "size": size, "received": 0, "temp": str(temp)}
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
        return jsonify(received=item["received"], size=item["size"])


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
        uploads.pop(upload_id, None)
    extracted = 0
    if target.name.lower().endswith((".tar", ".tgz")):
        destination = extraction_path(target)
        assert destination is not None
        destination.mkdir()
        try:
            with tarfile.open(target, "r:*") as archive:
                members = archive.getmembers()
                if len(members) > MAX_TAR_MEMBERS:
                    raise ValueError("Tar archive contains too many files")
                expanded_size = sum(member.size for member in members if member.isfile())
                if expanded_size > MAX_EXTRACTED_BYTES:
                    raise ValueError("Expanded tar archive is too large")
                for member in members:
                    member_target = (destination / member.name).resolve()
                    if destination.resolve() not in member_target.parents and member_target != destination.resolve():
                        raise ValueError("Unsafe path in tar archive")
                    if member.issym() or member.islnk():
                        raise ValueError("Links are not accepted in uploaded tar archives")
                archive.extractall(destination, members=members, filter="data")
                extracted = sum(1 for member in members if member.isfile())
        except (tarfile.TarError, OSError, ValueError) as exc:
            shutil.rmtree(destination, ignore_errors=True)
            target.unlink(missing_ok=True)
            return jsonify(error=f"Tar archive rejected: {exc}"), 400
    return jsonify(path=target.name, size=target.stat().st_size, extracted=extracted)


@app.delete("/api/uploads/<path:name>")
def delete_upload(name: str):
    path = safe_data_path(name)
    if not path.is_file():
        abort(404)
    path.unlink()
    return jsonify(ok=True)


@app.get("/api/jobs")
def list_jobs():
    with job_lock:
        private = {"log", "command", "payload", "container_pid"}
        summary = [{k: v for k, v in job.items() if k not in private} for job in jobs.values()]
    return jsonify(sorted(summary, key=lambda x: x["created"], reverse=True))


@app.post("/api/jobs")
def create_job():
    try:
        payload = validate_build_payload(json_object())
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    with upload_lock:
        if uploads:
            return jsonify(error="Wait for all uploads to finish before starting the build"), 409
    if docker_build_running():
        return jsonify(error="A Docker build is already running"), 409
    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    with job_lock:
        if any(j["status"] in {"queued", "running"} for j in jobs.values()):
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
    threading.Thread(target=run_job, args=(job_id, command), daemon=True).start()
    return jsonify(id=job_id), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            abort(404)
        return jsonify({key: value for key, value in job.items()
                        if key not in {"command", "payload", "container_pid"}})


@app.delete("/api/jobs/<job_id>")
def cancel_job(job_id: str):
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            abort(404)
        if job["status"] not in {"queued", "running"}:
            return jsonify(error="Build is not running"), 409
    subprocess.run(["docker", "stop", "--time", "10", f"giso-build-{job_id}"],
                   timeout=20, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    if not path.is_file() or path.suffix.lower() not in {".iso", ".zip"}:
        abort(404)
    size = path.stat().st_size
    path.unlink()
    checksum_cache.clear()
    try:
        archive_dir.rmdir()
    except OSError:
        pass
    return jsonify(ok=True, removed=name, removed_bytes=size)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=8080, threaded=True)
