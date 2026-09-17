#!/usr/bin/env python3
"""Upload a licensed XR ISO and verify real ISO plus USB build artifacts."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

CHUNK_BYTES = 16 * 1024 * 1024
ACTIVE_STATUSES = {"queued", "running", "cancelling"}


def request(url: str, *, method: str = "GET", data: bytes | None = None) -> dict | list:
    headers = {"Content-Type": "application/json"} if data and method == "POST" else {}
    # The operator-selected origin is validated to HTTP(S) before any request.
    with urllib.request.urlopen(  # nosec B310  # noqa: S310
        urllib.request.Request(url, data=data, headers=headers, method=method), timeout=120  # noqa: S310
    ) as response:
        return json.load(response)


def validate_origin(value: str, parser: argparse.ArgumentParser) -> str:
    base = value.rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        parser.error("--url must be an HTTP(S) origin without credentials or a path")
    return base


def upload_path(base: str, path: Path) -> str:
    """Upload one file and return the server-assigned path."""
    size = path.stat().st_size
    upload = request(f"{base}/api/uploads/init", method="POST",
                     data=json.dumps({"name": path.name, "size": size}).encode())
    upload_id = upload["id"]
    encoded_id = quote(upload_id, safe="")
    offset = 0
    try:
        with path.open("rb") as source:
            while chunk := source.read(CHUNK_BYTES):
                request(f"{base}/api/uploads/{encoded_id}?offset={offset}",
                        method="PUT", data=chunk)
                offset += len(chunk)
        completed = request(f"{base}/api/uploads/{encoded_id}/complete",
                            method="POST", data=b"{}")
    except Exception:
        try:
            request(f"{base}/api/uploads/session/{encoded_id}", method="DELETE")
        except (OSError, urllib.error.HTTPError, urllib.error.URLError, ValueError):
            pass
        raise
    return completed["path"]


def parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--rpm-dir", type=Path, action="append", default=[])
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--build-timeout", type=int, default=21600,
                        help="Maximum build wait in seconds (default: 21600)")
    parser.add_argument("--poll-interval", type=float, default=5,
                        help="Status polling interval in seconds (default: 5)")
    return parser, parser.parse_args()


def main() -> None:
    parser, args = parse_args()
    if not args.iso.is_file():
        parser.error("ISO does not exist")
    if args.build_timeout <= 0 or args.poll_interval <= 0:
        parser.error("--build-timeout and --poll-interval must be positive")
    for directory in args.rpm_dir:
        if not directory.is_dir():
            parser.error(f"RPM directory does not exist: {directory}")
    base = validate_origin(args.url, parser)

    uploaded_iso = upload_path(base, args.iso)
    rpms = sorted({path for directory in args.rpm_dir for path in directory.rglob("*.rpm")})
    uploaded_rpms = [Path(upload_path(base, rpm)).name for rpm in rpms]
    job = request(f"{base}/api/jobs", method="POST", data=json.dumps({
        "iso": uploaded_iso, "platform": args.platform,
        "pkglist": uploaded_rpms,
        "create_checksum": True, "skip_usb_image": False,
    }).encode())
    deadline = time.monotonic() + args.build_timeout
    while True:
        status = request(f"{base}/api/jobs/{quote(job['id'], safe='')}")
        print(f"{status['status']}: {status.get('phase', '')}")
        if status["status"] not in ACTIVE_STATUSES:
            break
        if time.monotonic() >= deadline:
            raise SystemExit(
                f"FAIL: build did not finish within {args.build_timeout} seconds; "
                f"job {job['id']} was left running for operator inspection"
            )
        time.sleep(args.poll_interval)
    if status["status"] != "success":
        raise SystemExit(status.get("error") or status.get("log") or "build failed")
    artifacts = request(f"{base}/api/archive")
    ours = [item for item in artifacts if item["job_id"] == job["id"]]
    if not any(item["name"].lower().endswith(".iso") for item in ours):
        raise SystemExit("FAIL: no Golden ISO output")
    if not any(item["name"].lower().endswith(".zip") and "usb" in item["name"].lower()
               for item in ours):
        raise SystemExit("FAIL: no USB boot output")
    for item in ours:
        encoded_job = quote(item["job_id"], safe="")
        encoded_name = quote(item["name"], safe="")
        sums = request(f"{base}/api/archive/{encoded_job}/{encoded_name}/checksums")
        print(f"PASS: {item['name']} sha256={sums['sha256']}")


if __name__ == "__main__":
    main()
