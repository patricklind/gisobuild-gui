# GitHub Copilot repository instructions

Before proposing or modifying code, read `AI-INSTRUCTIONS.md`, then read
`docs/todo/00-MASTER-TODO.md` and the relevant files under `docs/todo/`.

Inspect `graphify-out/` before non-trivial changes. Use Graphify to understand
impacted modules, dependencies, callers/callees, and architecture, then refresh
tracked Graphify output after relevant code changes and review the graph diff for
unexpected impact.

Treat `docs/todo/` as living project state. When a change completes, changes, or
discovers work represented there, update the appropriate TODO files in the same
branch/PR. Mark `[x]` only after implementation and appropriate verification are
complete. Add newly discovered defects, security risks, test gaps, and follow-up
work to the appropriate TODO file.

Do not create an independent platform-support model. The pinned upstream
`ios-xr/gisobuild` revision is authoritative for IOS XR build support; local
hardware/PID mappings are for detection and presentation only.

Never include licensed Cisco artifacts in Graphify input/output. Follow
`.graphifyignore` and all coordination, security, artifact, and verification
rules in `AGENTS.md`.
