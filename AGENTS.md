# AGENTS.md

Every Codex session reads this file automatically. Follow this protocol before
changing code. Multiple agents may work in this repository at the same time;
these rules keep their branches and ownership boundaries explicit.

## CRITICAL: Docker-only execution boundary

This repository has a strict **Docker-only execution policy**.

AI agents, developers, helper scripts, tests, build tools, Graphify, gisobuild,
Python tooling, linters, package managers, dependency installers, database tools,
and project automation MUST NOT execute directly on the user's local host OS.

The local computer is only allowed to act as:

- a Docker/Compose host;
- a Git working-copy host;
- an editor/client;
- a browser/client for the Web UI.

Everything that executes project code or project tooling must run inside a
container.

### Forbidden on the local host

Never run or instruct the user to run project operations such as:

- `python`, `python3`, `pip`, `pipx`, `pytest`, `ruff`, or Python scripts;
- `npm`, `pnpm`, `yarn`, Node-based project tooling, or frontend build tools;
- `rpm`, `dnf`, `yum`, `apt`, `apk`, `brew`, or other package installation for
  project dependencies;
- `gisobuild.py`, Cisco build tooling, ISO tools, RPM inspection tools, or GISO
  generation;
- Graphify or other code-analysis tooling;
- project database migrations or maintenance commands;
- project shell scripts whose implementation executes project logic on the host;
- test suites, staging rehearsals, build validation, or release tooling.

Do not modify host Python, Node, Ruby, Java, system packages, `/usr`, `/opt`,
`/etc`, shell profiles, environment configuration, or other host state in order
to make this project work.

Do not use the user's workstation as a temporary substitute when a container is
missing a dependency. Fix the Docker image instead.

### Allowed host commands

Host-side commands should be limited to container and source-control lifecycle
operations such as:

```bash
docker compose build
docker compose up -d
docker compose down
docker compose ps
docker compose logs
docker compose run --rm <service> <command>
docker compose exec <service> <command>
docker build ...
docker run ...
git status
git diff
git branch
git worktree ...
```

Git/worktree/coordination helpers may run on the host only when they strictly
perform Git/filesystem coordination and do not execute project runtime code,
install dependencies, or invoke project tooling. If that separation is unclear,
run them from a dedicated tooling container instead.

### No host fallback

If a required command cannot currently run in Docker:

1. stop;
2. treat the missing container capability as a project defect;
3. update the relevant Dockerfile/Compose/tooling container;
4. run the command inside Docker;
5. add regression coverage/documentation so host execution is never required.

Never solve the problem by installing the missing tool on the local machine.

### Docker boundary applies to all environments

The rule applies equally to:

- local development;
- Codex and Claude Code sessions;
- tests;
- Graphify;
- staging/rehearsal workflows;
- gisobuild execution;
- RPM/ISO inspection;
- frontend builds;
- migrations;
- debugging;
- release preparation.

CI may use its own runner infrastructure, but project build/test commands should
still execute in the same containerized environment used by the application
where practical.

## Mandatory project roadmap and Graphify — read before doing anything

Read `AI-INSTRUCTIONS.md` first, then read `docs/todo/00-MASTER-TODO.md` and every
relevant file under `docs/todo/` before planning, editing, reviewing, or proposing
architecture changes.

For non-trivial code changes, inspect and use Graphify before editing to understand
affected modules, callers/callees, dependencies, and architectural relationships.
Graphify itself must run in Docker. Refresh tracked `graphify-out/` after relevant
code changes and review the graph diff for unexpected impact. If Graphify cannot
be run in the containerized tooling environment, say so explicitly and add/fix
the missing Docker capability instead of installing Graphify on the host.

The TODO files are living project state. Codex must update the relevant TODO
files in the same branch/PR whenever implementation status, architecture,
security findings, tests, defects, or follow-up work changes. Mark `[x]` only
when implementation and appropriate verification are complete. A code change
that leaves `docs/todo/` or relevant Graphify state stale is not complete.

## Parallel work — do this first

Before editing anything:

1. Check the coordination board. Prefer a containerized coordination command.
   A host helper is allowed only if it is proven to perform Git/filesystem
   coordination only and executes no project runtime/tooling code.
2. Never develop on `main` in the primary checkout. Create a task worktree on a
   `codex/<name>` branch. Git worktree lifecycle commands may run on the host.
3. Claim the module before editing it.
4. Stay inside the claimed module. Do not edit files owned by another claim.
5. When implementation and verification are complete, mark the module done,
   push the branch, and open a pull request.
6. After merge, release the module and remove the task worktree.

See [parallel work](docs/parallel-work.md) and
[coordination](docs/coordination.md) for the complete workflow. If those documents
contain host-execution examples that violate the Docker-only rule, the Docker-only
rule in this file wins and the examples must be corrected.

## Hard rules

- Cisco IOS XR ISO, RPM, SMU, TAR, USB, key-request, certificate, configuration,
  and ownership-voucher inputs are licensed or sensitive artifacts. Never add
  them to Git, test fixtures, container images, logs, releases, or Graphify.
- Never claim that a synthetic fixture or the staging simulator is a real GISO
  or hardware validation. Real acceptance evidence must come from an actual
  licensed ISO processed by Cisco's `gisobuild` tool; router validation requires
  matching lab hardware.
- Do not connect to, upgrade, reload, roll back, or configure a Cisco router
  unless the user explicitly authorizes the exact device and operation.
- All application/runtime/build execution must stay inside Docker. Never install
  project dependencies or invoke project code directly on the user's host.
- The default deployment (`giso-webui/compose.yaml`) bundles gisobuild, has no
  Docker socket and runs read-only with only `SYS_CHROOT`; keep it that way.
  The alternative `giso-webui/compose.socket.yaml` controls Docker through
  `/var/run/docker.sock`. Keep both bound to localhost, preserve host/origin
  checks, and do not weaken container isolation without an explicit security
  review.
- The bundled gisobuild in the default image is pinned by commit and by
  a SHA-256 manifest (`GISOBUILD_COMMIT`, `GISOBUILD_SOURCE_SHA256` in
  `docker/selfcontained.Dockerfile`). Bumping gisobuild means updating both and
  running the platform drift tests against the new image.
- Preserve the single-build lock, SQLite job history, 30-day archive retention,
  and 50 GiB combined ISO/USB quota unless the task explicitly changes them.
- Shared files are conflict magnets: `README.md`, `ARCHITECTURE.md`,
  `GISOBUILD-GUIDE.md`, `.github/workflows/`, `graphify-out/`, `AI-INSTRUCTIONS.md`,
  and `docs/todo/`. Claim the relevant shared module and update them only when
  necessary.
- One module has one owner at a time. Never edit the same file from two
  worktrees.
- Do not manually create a version tag or GitHub Release until CI is green - a
  patch release now happens automatically once CI passes on `main`
  (`.github/workflows/auto-release.yml`; see `docs/releasing.md`), and a
  deliberate minor/major bump or pre-release still goes through the manual
  Release workflow. Never publish Cisco artifacts; the release contains this
  application's container image and
  documentation only.

## Project overview

This repository provides a Docker-hosted Web UI and orchestration layer around
Cisco's `ios-xr/gisobuild` project.

- Web application: `giso-webui/`
- Container images: `docker/selfcontained.Dockerfile` (the default deployment:
  web app plus pinned gisobuild), `giso-webui/Dockerfile` (socket deployment and
  unit tests), `docker/tooling.Dockerfile`, `docker/browser-tests.Dockerfile`
- Platform validation: `giso-webui/platform_validation.py`
- CLI helper: `build-giso.sh`
- Safe workflow simulator: `staging/`
- Real licensed-ISO acceptance runner: `scripts/e2e_real_iso.py`
- CI and release automation: `.github/workflows/`
- Architecture: `ARCHITECTURE.md`
- Build, upgrade, and rollback guidance: `GISOBUILD-GUIDE.md`
- Security boundary: `SECURITY.md`
- AI workflow rules: `AI-INSTRUCTIONS.md`
- Shared implementation roadmap: `docs/todo/`
- Tracked code graph: `graphify-out/`

## Required verification

Run checks proportionate to the changed module. **Every project command below
must execute inside Docker.** Host-side Python/test/tool invocations are forbidden.

At minimum, before a pull request that touches application or release behavior,
use containerized equivalents of:

```bash
docker compose -f giso-webui/compose.yaml config -q
docker compose -f giso-webui/compose.socket.yaml config -q
docker compose -f staging/compose.yaml config -q
docker compose -f giso-webui/compose.socket.yaml build giso-webui
docker run --rm -v "$(pwd):/project:ro" -w /project/giso-webui \
  giso-webui-giso-webui python -B -m unittest discover -s tests -v
```

The staging rehearsal, Graphify refresh, Ruff, dependency auditing, Actionlint,
Hadolint, security checks, frontend tooling, and any other project validation
must also run inside an appropriate container. If no container exists for a
required check, create or extend a tooling/test container; do not run it on the
host as a fallback.

Changes to the operator UI also need the Playwright browser tests, and changes to
platform handling the upstream drift tests in the default image; both
commands are in `docs/testing.md`.

Run the `giso-webui` unit test suite only inside the built `giso-webui-giso-webui`
container image. Never run `python -m unittest`, `pytest`, staging Python scripts,
or similar commands directly against the host Python interpreter.

Refresh tracked Graphify outputs after code changes from a containerized Graphify
environment, review the Graphify diff for unexpected dependency changes, and
never allow Cisco input or generated GISO artifacts into the graph.

Before finishing, update every affected file under `docs/todo/` and mark only
fully implemented and appropriately verified work as complete.

## Gotchas

- The public CI environment has no licensed Cisco ISO, so it cannot replace the
  real acceptance runner.
- eXR and IOS XR7/LNT options are not interchangeable. Keep the platform matrix
  synchronized with the pinned upstream tool (`test_platform_compatibility.py`
  fails on drift; CI runs it in the default image) and defer exact PID
  support to ISO metadata.
- Automatic USB output is not supported for every eXR family. Do not promise a
  USB artifact where upstream `gisobuild` does not create one.
- Builds run in a `linux/amd64` Cisco-compatible environment. Apple Silicon
  relies on Docker emulation and may be significantly slower.
- Successful builds remove uploaded source and temporary build files only after
  archive copies pass SHA-256 verification.
- An active build cannot be reattached after a Web UI restart; its persisted job
  is marked `interrupted` (with the local runner its work files are removed).
- eXR builds with the local runner need `CAP_SYS_CHROOT` and therefore root;
  without it gisobuild exits 0 having built nothing, so the plan blocks it.
- Host execution is never an acceptable workaround for missing container
  dependencies or broken container tooling.
