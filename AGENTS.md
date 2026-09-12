# AGENTS.md

Every Codex session reads this file automatically. Follow this protocol before
changing code. Multiple agents may work in this repository at the same time;
these rules keep their branches and ownership boundaries explicit.

## Parallel work — do this first

Before editing anything:

1. Check the coordination board with `./scripts/coord.sh status`
   (PowerShell: `.\scripts\coord.ps1 status`).
2. Never develop on `main` in the primary checkout. Create a task worktree with
   `./scripts/worktree.sh new <name>`. It creates `../gisobuild-<name>` on the
   `codex/<name>` branch. Start Codex in that directory and work only there.
3. Claim the module before editing it:
   `./scripts/coord.sh claim <module> "short note"`.
   If the claim fails, coordinate with its owner or choose another module.
4. Stay inside the claimed module. Do not edit files owned by another claim.
5. When implementation and verification are complete, run
   `./scripts/coord.sh done <module>`, push the branch, and open a pull request.
6. After merge, run `./scripts/coord.sh release <module>` from the primary
   checkout and remove the task worktree with
   `./scripts/worktree.sh remove <name>`.

See [parallel work](docs/parallel-work.md) and
[coordination](docs/coordination.md) for the complete workflow.

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
- The Web UI controls Docker through `/var/run/docker.sock`. Keep it bound to
  localhost, preserve host/origin checks, and do not weaken container isolation
  without an explicit security review.
- Preserve the single-build lock, SQLite job history, 30-day archive retention,
  and 50 GiB combined ISO/USB quota unless the task explicitly changes them.
- Shared files are conflict magnets: `README.md`, `ARCHITECTURE.md`,
  `GISOBUILD-GUIDE.md`, `.github/workflows/`, and `graphify-out/`. Claim the
  relevant shared module and update them only when necessary.
- One module has one owner at a time. Never edit the same file from two
  worktrees.
- Do not create a version tag or GitHub Release until CI is green. Never publish
  Cisco artifacts; the release contains this application's container image and
  documentation only.

## Project overview

This repository provides a local Flask Web UI and shell helper around Cisco's
`ios-xr/gisobuild` project.

- Web application: `giso-webui/`
- Platform validation: `giso-webui/platform_validation.py`
- CLI helper: `build-giso.sh`
- Safe workflow simulator: `staging/`
- Real licensed-ISO acceptance runner: `scripts/e2e_real_iso.py`
- CI and release automation: `.github/workflows/`
- Architecture: `ARCHITECTURE.md`
- Build, upgrade, and rollback guidance: `GISOBUILD-GUIDE.md`
- Security boundary: `SECURITY.md`

## Required verification

Run checks proportionate to the changed module. Before a pull request that
touches application or release behavior, run at least:

```bash
docker compose -f giso-webui/compose.yaml config -q
docker compose -f staging/compose.yaml config -q
docker compose -f giso-webui/compose.yaml build giso-webui
docker run --rm -v "$(pwd):/project:ro" -w /project/giso-webui \
  giso-webui-giso-webui python -B -m unittest discover -s tests -v
python3 staging/rehearse.py
git diff --check
```

Run Ruff, dependency auditing, Actionlint, Hadolint, and the security checks
defined in CI when their inputs change. Refresh tracked Graphify outputs after
code changes, but never allow Cisco input or generated GISO artifacts into the
graph.

## Gotchas

- The public CI environment has no licensed Cisco ISO, so it cannot replace the
  real acceptance runner.
- eXR and IOS XR7/LNT options are not interchangeable. Keep the platform matrix
  synchronized with the checked-out upstream tool and defer exact PID support
  to ISO metadata.
- Automatic USB output is not supported for every eXR family. Do not promise a
  USB artifact where upstream `gisobuild` does not create one.
- Builds run in an `linux/amd64` Cisco container. Apple Silicon relies on Docker
  emulation and may be significantly slower.
- Successful builds remove uploaded source and temporary build files only after
  archive copies pass SHA-256 verification.
- An active build cannot be reattached after a Web UI restart; its persisted job
  is marked `interrupted`.
