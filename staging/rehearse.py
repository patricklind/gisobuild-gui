#!/usr/bin/env python3
"""Verify upgrade and rollback state transitions against the XR simulator."""

from xr_simulator import execute, state


def run(command: str) -> None:
    result = execute(command)
    if not result["ok"]:
        raise SystemExit(f"FAILED: {command}: {result['error']}")
    print(f"PASS: {command}")


for command in (
    "show version",
    "show platform",
    "show redundancy",
    "show alarms brief system active",
    "show install request",
    "install package replace /harddisk:/staging-giso.iso",
    "install apply reload",
    "show version",
    "install commit",
    "install package rollback 1",
    "install apply rollback reload",
    "show version",
    "install commit",
):
    run(command)

if state["version"] != "7.9.2" or state["committed"] != "7.9.2":
    raise SystemExit(f"FAILED: rollback did not restore the committed release: {state}")
print("PASS: full staged upgrade and rollback rehearsal")
