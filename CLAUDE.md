# CLAUDE.md

Before changing anything in this repository, read `AI-INSTRUCTIONS.md` and follow
`AGENTS.md`.

Then read:

1. `docs/todo/00-MASTER-TODO.md`
2. every relevant `docs/todo/*.md` file for the task
3. the current Graphify output under `graphify-out/`

For non-trivial code changes, use Graphify before editing to understand impacted
modules, dependencies, callers/callees, and architecture. Refresh `graphify-out/`
after relevant code changes and review the graph diff.

The TODO files are living project state and must be updated as part of the same
work whenever implementation status, architecture, discovered defects, security
risks, tests, or follow-up work changes.

Do not mark a TODO `[x]` until the implementation exists and appropriate
verification has passed. If work is partial, leave it unchecked and document
what remains.

If Graphify cannot be run in the current environment, state that clearly rather
than claiming it was refreshed.
