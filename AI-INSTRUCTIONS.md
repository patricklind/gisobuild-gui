# AI-INSTRUCTIONS.md

These instructions apply to every AI coding agent working in this repository, including Codex, Claude Code, GitHub Copilot, Gemini, Cursor, and similar tools.

## Non-negotiable Docker-only execution policy

All project execution must happen inside Docker containers.

The user's local computer may host Docker, Git, the working tree, editor, and browser, but it must not be used as a project runtime or project toolchain.

AI agents must never install or execute project dependencies, build tools, test frameworks, analyzers, package managers, Cisco tooling, Python scripts, Node tooling, database tooling, Graphify, or gisobuild directly on the local host.

Examples that are forbidden on the host include:

- `python`, `python3`, `pip`, `pipx`, `pytest`, `ruff`;
- `npm`, `pnpm`, `yarn` or frontend build/test tools;
- `apt`, `dnf`, `yum`, `apk`, `brew` for project dependencies;
- `gisobuild.py` and IOS-XR ISO/RPM inspection/build tooling;
- Graphify;
- staging/rehearsal Python scripts;
- database migrations and project maintenance commands;
- linters, security scanners, dependency auditors, or release scripts.

Do not modify the host OS, host Python installation, host Node installation, shell profile, `/usr`, `/opt`, `/etc`, or other host state to make the project work.

If a command cannot run in Docker, that is a project/containerization defect. Fix or extend the relevant Dockerfile, Compose service, or dedicated tooling container. Never fall back to host execution.

Host commands should be limited to Git/source-control operations and Docker/Compose lifecycle operations. Git/worktree coordination helpers may run on the host only if they strictly perform Git/filesystem coordination and execute no project runtime/tooling code.

This rule overrides any older documentation or examples that suggest running project Python, test, staging, Graphify, package-management, or build commands directly on the host. Correct those examples when encountered.

## Mandatory startup workflow

Before planning, editing code, reviewing a change, or proposing architecture changes:

1. Read `AGENTS.md`.
2. Read `docs/todo/00-MASTER-TODO.md`.
3. Read every `docs/todo/*.md` file relevant to the task.
4. Use Graphify inside Docker to inspect the affected code paths, dependencies, callers/callees, and architectural relationships before making non-trivial changes.
5. Check whether the requested work already exists as a TODO, is partially complete, or conflicts with another TODO.

The files under `docs/todo/` are the shared implementation roadmap and project memory for AI-assisted development. Graphify is the required codebase-understanding layer for non-trivial changes.

## Mandatory Graphify workflow

Graphify must be used when the task changes application logic, architecture, dependencies, data flow, build orchestration, platform handling, API behavior, security boundaries, or other non-trivial code paths.

Graphify itself must run inside Docker. It must never be installed or executed directly on the user's host.

Before editing:

- Inspect the current Graphify output under `graphify-out/`.
- Use containerized Graphify to identify the affected modules, important dependencies, callers, callees, and shared files.
- Use that information to reduce accidental regressions and avoid duplicating existing abstractions.
- If Graphify output appears stale relative to the code, refresh it in Docker before relying on it.

After relevant code changes:

- Refresh the tracked Graphify output from Docker.
- Review the Graphify diff for unexpected dependency or architecture changes.
- Include required `graphify-out/` updates in the same branch/PR.
- Never include licensed or sensitive Cisco IOS XR artifacts in Graphify input or output.
- Respect `.graphifyignore` and the repository's artifact-safety rules.

If Graphify cannot run in the existing Docker environment, state that clearly, add/fix the required tooling container, and leave the relevant work incomplete until it can be verified. Do not install Graphify on the host as a workaround.

## Mandatory TODO workflow

During implementation:

- Keep the relevant TODO file open as the task checklist.
- If new defects, architectural constraints, security risks, test gaps, or follow-up work are discovered, add them to the appropriate TODO file before finishing the task.
- If the implementation changes the architecture or intended design, update the relevant TODO text so it describes the new agreed direction.
- Never silently abandon or supersede a TODO. Rewrite it or mark it with a clear explanation.
- Add TODO work whenever an existing workflow still requires project execution on the host.

Before finishing any code change:

1. Update the relevant `docs/todo/*.md` files in the same branch/PR.
2. Mark completed checklist items with `[x]` only when the implementation and appropriate verification are actually complete.
3. Leave incomplete or partially verified work as `[ ]` and add a short note explaining what remains when useful.
4. Add newly discovered follow-up work to the correct TODO file.
5. Check whether `00-MASTER-TODO.md` also needs progress or scope updates.
6. Refresh Graphify output for relevant code changes using Docker and review its diff.
7. Include TODO and Graphify changes in the same commit/PR whenever practical.
8. Verify that all tests/tools/build steps used for the task were containerized.

A task that changes implementation but leaves `docs/todo/`, relevant Graphify state, or required Docker execution support stale is not complete.

## TODO ownership by topic

- `docs/todo/00-MASTER-TODO.md` — global roadmap, phases, and acceptance criteria.
- `docs/todo/01-PLATFORM-UPSTREAM-TODO.md` — upstream `ios-xr/gisobuild` support, eXR/LNT capabilities, platform/PID aliases.
- `docs/todo/02-AUTOMATION-BUILDPLAN-TODO.md` — inventory, ISO/RPM inspection, CSC grouping, automatic selection, BuildPlan.
- `docs/todo/03-DOCKER-SELF-CONTAINED-TODO.md` — strict Docker-only execution, self-contained container, bundled/pinned gisobuild, tooling containers, and removal of Docker socket dependency.
- `docs/todo/04-STATE-SECURITY-OBSERVABILITY-TODO.md` — persistence, job state, security, health/readiness, logging.
- `docs/todo/05-TESTING-CI-TODO.md` — unit/integration/UI/security tests, CI and release verification.
- `docs/todo/06-UI-OPERATOR-TODO.md` — operator workflow, automatic defaults, expert settings, decision explanations.

If a change spans several areas, update every affected TODO file.

## Source-of-truth rule

For IOS XR platform/build support, the pinned upstream `ios-xr/gisobuild` revision is authoritative. Local hardware/PID mappings improve detection and presentation; they must not become an independent support matrix that artificially blocks upstream-supported images.

All gisobuild interaction must be performed through the containerized application/build-engine environment. Do not require a host-side gisobuild checkout or host-side IOS-XR build dependencies.

## Do not fake completion

Do not mark a TODO complete because code was drafted. Completion requires the implementation to exist and the relevant tests/verification to pass, subject to the repository's licensed-Cisco-artifact restrictions and Docker-only execution policy.
