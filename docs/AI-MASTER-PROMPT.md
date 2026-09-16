# AI Master Prompt — Cisco IOS-XR GISO Build Web UI

You are working on:

`https://github.com/patricklind/gisobuild-gui`

This project is a Web UI and orchestration layer for:

`https://github.com/ios-xr/gisobuild`

The project goal is not to implement a small subset of gisobuild. The goal is to make the functionality supported by upstream `ios-xr/gisobuild` available through a safe, understandable Web UI wherever technically practical.

## Non-negotiable execution boundary: Docker only

Everything related to this project must execute in Docker.

The user's local PC may only be used as:

- Docker/Compose host
- Git working-copy host
- editor/client
- browser/client

Never use the local PC as a project runtime or toolchain.

Never install or execute project dependencies or project tools directly on the host.

This includes, but is not limited to:

- Python / pip / pytest / Ruff
- Node / npm / pnpm / yarn
- Graphify
- gisobuild
- RPM inspection tools
- ISO tools
- staging/rehearsal scripts
- database migrations
- dependency audits
- security scanners
- build scripts
- frontend build tools
- project package managers

Do not modify host Python, Node, `/usr`, `/opt`, `/etc`, shell profiles, package databases, or other host state to make the project work.

If something cannot run in Docker, fix the Dockerfile, Compose setup, runtime image, or dedicated tooling container. Host execution is never an acceptable fallback.

Host-side commands should be restricted to Git/source-control operations and Docker/Compose lifecycle operations.

## Upstream is the source of truth

The pinned upstream `ios-xr/gisobuild` implementation is authoritative for:

- supported IOS-XR image types
- supported platforms
- LNT/eXR behavior
- build options
- package rules
- dependencies
- supported PID behavior
- output artifacts
- validation rules

Do not create a second independent GISO implementation.

Architecture should remain conceptually:

```text
Web UI
  ↓
API / orchestration
  ↓
validation + BuildPlan
  ↓
GisoBuildEngine adapter
  ↓
official/pinned ios-xr/gisobuild
```

## Required upstream coverage

Audit the exact pinned upstream version and expose all practical capabilities through the Web UI.

At minimum account for common options such as:

- input ISO/GISO
- repositories
- RPM/TAR/TGZ inputs where upstream supports them
- package list
- bridging fixes
- XR config
- ZTP INI
- labels / no-label
- output handling
- checksum generation
- YAML configuration
- clean mode
- key request
- container/upstream execution behavior

Account for eXR-specific behavior such as:

- boot script
- x86-only
- migration
- optimize
- full ISO

Account for LNT-specific behavior such as:

- package removal
- skip USB image
- copy directory
- clear bridging fixes
- dependency debugging
- custom isoinfo
- supported PID filtering
- key-request clearing
- ownership vouchers
- ownership certificates
- clearing ownership material
- no-buildinfo

Do not show invalid options for an image type/platform/release.

## Capability-driven UI

Do not build the GUI around a static platform list.

Inspect uploaded IOS-XR images and derive information from reliable metadata such as:

- mdata.json
- ISO metadata
- gisobuild/isols tooling
- RPM metadata
- supported PID metadata

Filename parsing should only be a fallback.

Build an internal image model containing concepts such as:

```json
{
  "platform_family": "...",
  "release": "...",
  "architecture": "...",
  "image_type": "LNT|eXR|GISO|UNKNOWN",
  "supported_pids": [],
  "supported_features": {},
  "detected_packages": [],
  "metadata_source": "..."
}
```

Do not silently guess. Unknown information must remain unknown and be explained to the user.

## Beginner and advanced modes

Provide a simple workflow for normal users and an advanced workflow for experienced IOS-XR engineers.

Standard flow should resemble:

```text
Upload/select image
  ↓
Inspect image
  ↓
Upload/select package repository
  ↓
Automatic compatibility analysis
  ↓
Choose packages/fixes
  ↓
Review
  ↓
Build
  ↓
Download artifacts
```

Advanced mode may expose the complete relevant upstream option set, exact package selection, generated YAML, generated CLI arguments, PID filtering, ownership options, migration, optimization, debug controls, etc.

## BuildPlan

Maintain a normalized internal BuildPlan instead of constructing shell commands directly in UI code.

The BuildPlan should represent:

- source image
- repositories/files
- package selections
- bridging fixes
- config/ZTP/script/key-request/ownership files
- supported PID selection
- advanced flags
- generated upstream YAML
- generated upstream CLI arguments
- effective capability set

The same BuildPlan must drive review, validation, execution, history, and reproducibility.

## Automatic package handling

The UI should help users select compatible packages without pretending to replace gisobuild dependency solving.

Analyze and explain:

- release compatibility
- architecture compatibility
- duplicate versions
- package block/group relationships
- optional packages
- SMU/CSC grouping where reliably detectable
- why a package was automatically selected
- why a package was rejected

Upstream gisobuild remains the final authority.

## Jobs and logs

Builds must be asynchronous from the HTTP request perspective and represented as jobs.

Use clear states such as:

```text
queued
validating
preparing
building
packaging
completed
failed
cancelled
interrupted
```

Persist enough state for audit/history.

Provide live or near-live logs via SSE, WebSocket, or controlled polling.

Do not expose raw Python errors as the primary UX. Show structured explanations with expandable technical output.

## Artifacts and reproducibility

Detect every artifact created by upstream instead of assuming one ISO output.

Store/show:

- filename
- type
- size
- SHA-256
- timestamps
- build logs
- build metadata

Every build should record:

- Web UI version/commit
- gisobuild version/commit
- source image checksum
- all input package checksums
- exact BuildPlan
- generated YAML/CLI
- output checksums

## Security

Treat every uploaded ISO, RPM, TAR, config, script, voucher, and certificate as untrusted input.

Protect against:

- command injection
- path traversal
- archive traversal
- malicious symlinks
- malicious filenames
- disk exhaustion
- oversized uploads
- unsafe subprocess usage
- workspace collisions
- artifact disclosure
- log leakage

Use argument arrays, not shell string composition.

Avoid `shell=True`.

Build jobs must have isolated working directories.

The final architecture should not depend on `/var/run/docker.sock` if the application can execute gisobuild directly inside its own controlled containerized runtime.

## Docker architecture

Target experience:

```bash
git clone ...
cd gisobuild-gui
docker compose up -d
```

No host installation of Python, RPM tools, ISO tools, gisobuild, Graphify, or development dependencies.

Create dedicated container services/images for runtime and development tooling when useful.

All tests, staging, Graphify, linters, audits, migrations, and build-engine operations must have Docker commands.

## Graphify

Use Graphify for non-trivial architectural/code changes, but run Graphify only inside Docker.

Use it to identify:

- callers/callees
- duplicated logic
- frontend/backend coupling
- build-engine bypasses
- package-validation relationships
- job-state paths
- dead code
- architectural impact

Refresh tracked Graphify output after relevant changes.

## UI principles

Design for network engineers, including users who do not know gisobuild CLI syntax.

Prioritize:

- simple step-by-step flow
- strong image summary
- readable package tables
- automatic safe defaults
- clear explanations
- contextual advanced options
- useful pre-flight checks
- accessible error messages
- keyboard accessibility
- consistent typography and spacing

Avoid:

- giant forms
- unexplained CLI flags
- generic SaaS dashboards
- unnecessary card grids
- purple/indigo gradient AI styling
- glowing borders
- excessive animation
- vague validation messages

## Required documentation

Keep these files current:

- `AGENTS.md`
- `AI-INSTRUCTIONS.md`
- `docs/AI-MASTER-PROMPT.md`
- `ARCHITECTURE.md`
- `SECURITY.md`
- `GISOBUILD-GUIDE.md`
- `docs/todo/00-MASTER-TODO.md`
- relevant `docs/todo/*.md`
- tracked `graphify-out/`

A code change is incomplete if relevant TODO/architecture/security/Graphify documentation is stale.

## Required first step for major tasks

Before implementing substantial changes:

1. inspect the repository
2. inspect the relevant TODO files
3. inspect current Graphify output
4. run Graphify in Docker where required
5. inspect the pinned upstream gisobuild version
6. compare upstream capabilities with current Web UI support
7. identify hardcoded assumptions
8. identify Docker/host-execution violations
9. identify security issues
10. identify missing tests
11. update the TODO roadmap where needed
12. implement incrementally

## Compatibility matrix

Maintain a living upstream compatibility matrix documenting each relevant gisobuild capability as:

- implemented
- partial
- missing
- intentionally not exposed

Every intentionally unsupported capability must include a technical reason and, where possible, an alternative.

Add automated detection so a change in upstream CLI/capabilities can be surfaced by tests/CI rather than silently ignored.

## Completion criteria

The project should converge toward all of the following:

1. A user unfamiliar with gisobuild CLI can build a normal GISO through the Web UI.
2. An expert can access essentially all relevant upstream functionality.
3. LNT and eXR differences are handled automatically.
4. New upstream-supported platforms do not usually require hardcoded frontend changes.
5. Package decisions are explainable.
6. Builds are reproducible and auditable.
7. Jobs are isolated and safe.
8. Everything project-related runs in Docker, never directly on the user's local PC.
9. Deployment is predictable with Docker Compose.
10. Upstream gisobuild changes are detected automatically.
11. The Web UI clearly reports implemented, partial, and unsupported upstream capabilities.

When in doubt, preserve the Docker-only boundary and defer GISO semantics to upstream `ios-xr/gisobuild`.