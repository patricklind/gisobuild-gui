#!/usr/bin/env python3
"""Upload a licensed XR ISO and verify real ISO plus USB build artifacts."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def request(url: str, *, method: str = "GET", data: bytes | None = None) -> dict | list:
    headers = {"Content-Type": "application/json"} if data and method == "POST" else {}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers,
                                                      method=method), timeout=120) as response:
        return json.load(response)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("iso", type=Path)
parser.add_argument("--platform", required=True)
parser.add_argument("--rpm-dir", type=Path, action="append", default=[])
parser.add_argument("--url", default="http://127.0.0.1:8080")
args = parser.parse_args()
if not args.iso.is_file():
    parser.error("ISO does not exist")
base = args.url.rstrip("/")


def upload_path(path: Path) -> None:
    size = path.stat().st_size
    upload = request(f"{base}/api/uploads/init", method="POST",
                     data=json.dumps({"name": path.name, "size": size}).encode())
    upload_id = upload["id"]
    offset = 0
    with path.open("rb") as source:
        while chunk := source.read(16 * 1024 * 1024):
            request(f"{base}/api/uploads/{upload_id}?offset={offset}", method="PUT", data=chunk)
            offset += len(chunk)
    request(f"{base}/api/uploads/{upload_id}/complete", method="POST", data=b"{}")


upload_path(args.iso)
rpms = sorted({path for directory in args.rpm_dir for path in directory.rglob("*.rpm")})
for rpm in rpms:
    upload_path(rpm)
job = request(f"{base}/api/jobs", method="POST", data=json.dumps({
    "iso": args.iso.name, "platform": args.platform,
    "pkglist": [rpm.name for rpm in rpms],
    "create_checksum": True, "skip_usb_image": False,
}).encode())
while True:
    status = request(f"{base}/api/jobs/{job['id']}")
    print(f"{status['status']}: {status.get('phase', '')}")
    if status["status"] not in {"queued", "running", "cancelling"}:
        break
    time.sleep(5)
if status["status"] != "success":
    raise SystemExit(status.get("error") or status.get("log") or "build failed")
artifacts = request(f"{base}/api/archive")
ours = [item for item in artifacts if item["job_id"] == job["id"]]
if not any(item["name"].lower().endswith(".iso") for item in ours):
    raise SystemExit("FAIL: no Golden ISO output")
if not any(item["name"].lower().endswith(".zip") and "usb" in item["name"].lower() for item in ours):
    raise SystemExit("FAIL: no USB boot output")
for item in ours:
    sums = request(f"{base}/api/archive/{item['job_id']}/{item['name']}/checksums")
    print(f"PASS: {item['name']} sha256={sums['sha256']}")
