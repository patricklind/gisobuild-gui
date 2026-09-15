#!/usr/bin/env python3
"""Regenerate the tracked code graph from tracked files and compare it structurally."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REQUIRED_IGNORES = {
    ".gisobuild-tool/",
    "output_gisobuild*/",
    "giso-webui/uploads/",
    "giso-webui/output/",
    "*.iso",
    "*.rpm",
    "*.tar",
    "*.tgz",
    "*usb_boot*.zip",
    ".env",
    ".env.*",
}


def normalized_graph(path: Path) -> dict:
    graph = json.loads(path.read_text(encoding="utf-8"))
    graph.pop("built_at_commit", None)
    return graph


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [Path(value.decode()) for value in result.stdout.split(b"\0") if value]


def verify_ignore_policy(root: Path) -> None:
    rules = {
        line.strip()
        for line in (root / ".graphifyignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = sorted(REQUIRED_IGNORES - rules)
    if missing:
        raise RuntimeError(
            ".graphifyignore is missing required safety rules: " + ", ".join(missing)
        )


def check(root: Path, graphify: str) -> None:
    verify_ignore_policy(root)
    expected_path = root / "graphify-out/graph.json"
    if not expected_path.is_file():
        raise RuntimeError("Tracked graphify-out/graph.json is missing")

    with tempfile.TemporaryDirectory(prefix="giso-graphify-check-") as temporary:
        checkout = Path(temporary) / "repo"
        checkout.mkdir()
        for relative in tracked_files(root):
            source = root / relative
            if not source.is_file():
                continue
            destination = checkout / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        subprocess.run([graphify, "update", str(checkout)], cwd=checkout, check=True)
        actual_path = checkout / "graphify-out/graph.json"
        if normalized_graph(expected_path) != normalized_graph(actual_path):
            raise RuntimeError(
                "Tracked Graphify output is stale. Run `graphify update .`, review the diff, "
                "and commit graphify-out/."
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphify", default="graphify")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    check(args.root.resolve(), args.graphify)
    print("Graphify graph matches the tracked source tree and artifact ignore policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
