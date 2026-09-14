# GEMINI.md

Read `AI-INSTRUCTIONS.md` and `AGENTS.md` before making changes.

Then read `docs/todo/00-MASTER-TODO.md`, all task-relevant files under
`docs/todo/`, and the current tracked Graphify output under `graphify-out/`.

For non-trivial code changes, use Graphify before editing to understand impacted
modules, dependencies, callers/callees, and architecture. Refresh tracked
Graphify output after relevant changes and review the resulting graph diff.

The TODO files are living project state. Update them in the same change whenever
implementation status, architecture, defects, security findings, tests, or
follow-up work changes. Mark `[x]` only when implementation and appropriate
verification are complete.

Never allow licensed Cisco IOS XR inputs or generated GISO artifacts into
Graphify. Respect `.graphifyignore` and the safety requirements in `AGENTS.md`.
