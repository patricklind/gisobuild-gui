# TODO roadmap for AI-assisted development

These files are the living implementation roadmap for the project.

All coding agents must read repository-root `AI-INSTRUCTIONS.md`, then
`00-MASTER-TODO.md`, then the task-relevant TODO files before making changes.
For non-trivial changes they must also inspect/use Graphify and the tracked
`graphify-out/` state before editing.

## Update policy

- Keep TODO changes in the same branch/PR as the implementation whenever possible.
- Mark `[x]` only after implementation and appropriate verification are complete.
- Leave partial work unchecked.
- Add newly discovered defects, security risks, test gaps, architectural follow-up,
  and migration work to the relevant file before finishing.
- If a design changes, update the TODO wording instead of leaving stale guidance.
- If a task spans several areas, update all affected TODO files.
- Review `00-MASTER-TODO.md` after significant changes to keep the global roadmap accurate.
- Refresh tracked Graphify output after relevant code changes and review the graph diff.
- Never allow licensed Cisco IOS XR inputs or generated GISO artifacts into Graphify.

## Files

- `00-MASTER-TODO.md` — roadmap, phases, final acceptance criteria
- `01-PLATFORM-UPSTREAM-TODO.md` — upstream gisobuild, eXR/LNT, capabilities, PID aliases
- `02-AUTOMATION-BUILDPLAN-TODO.md` — inventory, metadata, CSC, automation, BuildPlan
- `03-DOCKER-SELF-CONTAINED-TODO.md` — self-contained runtime and Docker architecture
- `04-STATE-SECURITY-OBSERVABILITY-TODO.md` — persistence, jobs, security, health, logging
- `05-TESTING-CI-TODO.md` — unit/integration/UI/security testing and CI
- `06-UI-OPERATOR-TODO.md` — operator workflow and UX

The pinned upstream `ios-xr/gisobuild` revision remains authoritative for actual
IOS XR build/platform capability support.
