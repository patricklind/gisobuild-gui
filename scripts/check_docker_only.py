"""Flag instructions and scripts that run project tooling on the host.

AGENTS.md makes Docker the only place project tooling runs. This check makes
that enforceable: it reads every tracked Markdown file's shell code blocks and
every tracked shell script, and reports command lines that start Python, pip, pytest, Ruff, Graphify, Node
tooling, gisobuild or the IOS XR inspection tools directly instead of inside
`docker run`, `docker exec` or `docker compose run/exec`.

Recognised as containerised: the tool appears on the same logical command
(backslash continuations joined) after `docker ... run|exec` or
`docker compose ... run|exec`. Workflows and Dockerfiles are not read: their
commands already execute in CI or in an image. A line may opt out with a
trailing `# docker-only: allow <reason>`.

Run it in the tooling image, never on the host:
    docker run --rm -v "$PWD:/project:ro" -w /project gisobuild-tooling \\
        python -B scripts/check_docker_only.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TOOLS = re.compile(
    r"(?:^|[\s;&|(`])(?:sudo\s+)?"
    r"(python3?(?:\.\d+)?|pip3?|pytest|ruff|graphify|npm|npx|pnpm|yarn|node|"
    r"isoinfo|rpm|[\w./-]*gisobuild\.py|[\w./-]*rehearse\.py)(?=\s|$)"
)
CONTAINERISED = re.compile(r"\bdocker(?:\s+compose)?\b[^\n]*?\b(?:run|exec)\b")
ALLOW = re.compile(r"#\s*docker-only:\s*allow\b")
SHELL_FENCES = {"bash", "sh", "shell", "console", "zsh", "text", ""}
# Files whose subject is the rule itself or historical/audit narrative.
EXEMPT = {"scripts/check_docker_only.py"}
EXEMPT_PREFIXES = ("docs/todo/", "graphify-out/")


def tracked_files(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True
    ).stdout
    return [
        name
        for name in output.splitlines()
        if name.endswith((".md", ".sh"))
        and name not in EXEMPT
        and not name.startswith(EXEMPT_PREFIXES)
    ]


def logical_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Join backslash continuations so a multi-line docker command is one unit."""
    joined: list[tuple[int, str]] = []
    buffer, start = "", None
    for number, text in lines:
        if start is None:
            start = number
        stripped = text.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        joined.append((start, buffer + stripped))
        buffer, start = "", None
    if buffer:
        joined.append((start, buffer))
    return joined


def command_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if path.suffix == ".sh":
        return logical_lines(
            [
                (i, line)
                for i, line in enumerate(text, 1)
                if line.strip() and not line.lstrip().startswith("#")
            ]
        )
    commands: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text, 1):
        marker = re.match(r"^\s*(```+|~~~+)\s*([\w-]*)", line)
        if marker:
            fence = None if fence is not None else marker.group(2).lower()
            continue
        if fence is not None and fence in SHELL_FENCES:
            commands.append((number, re.sub(r"^\s*\$\s+", "", line)))
        # Inline code spans are not checked: prose such as "never run
        # `python -m unittest` on the host" names a command to forbid it.
    return logical_lines(commands) if commands else []


def violations(root: Path) -> list[str]:
    found = []
    for name in tracked_files(root):
        for number, command in command_lines(root / name):
            if ALLOW.search(command):
                continue
            match = TOOLS.search(command)
            if not match:
                continue
            docker = CONTAINERISED.search(command)
            if docker and docker.start() < match.start():
                continue
            found.append(
                f"{name}:{number}: `{match.group(1)}` on the host: {command.strip()[:120]}"
            )
    return found


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    found = violations(root)
    for line in found:
        print(line)
    if found:
        print(
            f"\n{len(found)} host-side tooling command(s); run them in Docker "
            "(see AGENTS.md) or mark a justified line with '# docker-only: allow <reason>'."
        )
        return 1
    print("No host-side project tooling commands found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
