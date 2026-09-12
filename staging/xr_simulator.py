#!/usr/bin/env python3
"""Non-networked IOS XR transaction simulator for rehearsal only."""

from __future__ import annotations

import json
import sys

state = {"version": "7.9.2", "committed": "7.9.2", "pending": None,
         "rollback": None, "healthy": True}


def execute(command: str) -> dict:
    command = command.strip()
    if command in {"show version", "show platform", "show redundancy",
                   "show alarms brief system active"}:
        return {"ok": True, "command": command, "healthy": state["healthy"],
                "version": state["version"]}
    if command == "show install request":
        return {"ok": True, "pending": state["pending"]}
    if command.startswith("install package replace "):
        if state["pending"]:
            return {"ok": False, "error": "install transaction already pending"}
        state["pending"] = "upgrade"
        return {"ok": True, "pending": "upgrade"}
    if command == "install apply reload":
        if state["pending"] != "upgrade":
            return {"ok": False, "error": "no staged upgrade"}
        state["rollback"] = state["version"]
        state["version"] = "staged-target"
        state["pending"] = None
        return {"ok": True, "reloaded": True, "version": state["version"]}
    if command.startswith("install package rollback "):
        if not state["rollback"]:
            return {"ok": False, "error": "no rollback point"}
        state["pending"] = "rollback"
        return {"ok": True, "pending": "rollback"}
    if command == "install apply rollback reload":
        if state["pending"] != "rollback":
            return {"ok": False, "error": "no staged rollback"}
        state["version"], state["pending"] = state["rollback"], None
        return {"ok": True, "reloaded": True, "version": state["version"]}
    if command == "install commit":
        if not state["healthy"]:
            return {"ok": False, "error": "health gate failed"}
        state["committed"] = state["version"]
        return {"ok": True, "committed": state["committed"]}
    return {"ok": False, "error": "unsupported rehearsal command"}


def main() -> None:
    for line in sys.stdin:
        print(json.dumps(execute(line)), flush=True)


if __name__ == "__main__":
    main()
