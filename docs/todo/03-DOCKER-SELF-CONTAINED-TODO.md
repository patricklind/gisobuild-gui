# TODO — Self-contained Docker Image

## Goal

Production deployment and local development must require only Docker/Compose plus Git/editor/browser on the host.

Target production startup:

```bash
docker compose up -d
```

The user's local computer must never become part of the application runtime or project toolchain.

No host-side project execution:

- [x] no host Python/pip/pytest/Ruff — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host Node/npm/pnpm/yarn project tooling — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host Graphify — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host gisobuild execution — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host IOS-XR ISO/RPM inspection tools — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host staging/rehearsal scripts — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host database migration/maintenance commands — schema migrations run inside the app on start (`apply_schema_migrations()`); archive maintenance is its own container
- [x] no host package installation for project dependencies — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers
- [x] no host release/build/security tooling — 2026-09-17: documented commands contain none (`scripts/check_docker_only.py`, CI-enforced), and this whole session's work ran tests, lint, audits, scans, Graphify, staging and builds only in containers

No external runtime dependencies:

Status 2026-09-17: available as `docker/selfcontained.Dockerfile` +
`giso-webui/compose.selfcontained.yaml` (runner `GISO_RUNNER=local`). The
original `compose.yaml` (socket + child builder) still exists and is still
the documented default; switching the default is left to the maintainer.

**Real-build evidence** (throwaway container and Docker volumes on this Mac,
amd64 emulation; licensed content only inside those volumes, all removed
afterwards): the self-contained image, run `--read-only`, `--cap-drop ALL
--cap-add SYS_CHROOT`, `no-new-privileges`, no socket and no host checkout,
built a real Golden ISO from the NCS5500 IOS XR 25.1.2 bundle through
`POST /api/jobs`: automatic selection of its 12 optional RPMs, gisobuild
"signature check [PASS]", "compatibility check [PASS]", "Golden ISO creation
SUCCESS", archived `ncs5500-goldenk9-x-25.1.2-SELFCONTAINED.iso`
(2 479 153 152 bytes) and `ncs5500-usb_boot-25.1.2-SELFCONTAINED.zip`, job
`builder_image.source = bundled`, `/api/version` runner `local` at gisobuild
`0388af2989bb`. The first attempt, with *no* capabilities, produced no image:
gisobuild's eXR engine `chroot`s for every RPM, logged "Operation not
permitted", found "0 RPM(s)" and exited 0 ("Nothing to do"); the app
correctly reported it as failed (no ISO), and the plan now blocks that case
up front (see "Security").

- [x] separate `ios-xr/gisobuild` checkout - source cloned in the image build
      at a pinned commit, verified, `.git` removed.
- [x] `.gisobuild-tool` bind mount - not in `compose.selfcontained.yaml`
      (guarded by `test_compose_never_mounts_the_docker_socket_or_a_host_gisobuild_checkout`).
- [x] `/var/run/docker.sock` in the final target architecture - absent in the
      self-contained deployment (same guard; confirmed missing in the running
      container).
- [x] child Docker builder container in the final target architecture -
      gisobuild runs as a child process (`build_command()` local branch).
- [x] manual pull of a Cisco builder image - no pull in local mode.

## Docker-only enforcement

Make the Docker-only rule enforceable rather than documentation-only.

- [x] inventory every README, script, Makefile/task file, CI command, developer guide, and agent instruction for host-side project commands - 2026-09-17: `scripts/check_docker_only.py` scans every tracked Markdown shell block and shell script (no Makefile/task files exist; workflows run in CI). First run: 9 hits; 4 were prose forbidding a command (inline spans are no longer scanned), 1 was a bash-array `docker run` element (`build-giso.sh`, allow-marked with a reason), and 2 real host instructions were rewritten (see next item).
- [x] replace host `python`, `pytest`, staging, Graphify, lint, audit, frontend, and build examples with `docker compose run`, `docker compose exec`, or dedicated tooling-container commands - `GISOBUILD-GUIDE.md`'s direct `./src/gisobuild.py` build now runs in `giso-webui-selfcontained`; `staging/README.md`'s rehearsal runs in `gisobuild-tooling`.
- [x] add a documented developer command set for common operations — "Developer command reference" in `docs/testing.md`
- [x] add a dedicated tooling/test service or image where the application image is not appropriate — `docker/tooling.Dockerfile` (ruff, pip-audit, Graphify, staging) and `docker/browser-tests.Dockerfile` (Playwright)
- [x] ensure Graphify runs in Docker — `gisobuild-tooling graphify update .`, used after every code change this session
- [x] ensure staging/rehearsal runs in Docker — `gisobuild-tooling python -B rehearse.py`: "PASS: full staged upgrade and rollback rehearsal" (2026-09-17)
- [x] ensure integration and unit tests run in Docker — unit, synthetic integration, platform fixture and browser suites all run only in images
- [x] ensure linters/security scanners/dependency audits run in Docker or dedicated CI containers — ruff (+bandit rules), pip-audit, Trivy, Syft, hadolint, actionlint all containerised
- [x] ensure database migrations run in Docker — inside the application container
- [x] ensure all IOS-XR/gisobuild inspection and build commands run in Docker — isoinfo/rpm in the app image; gisobuild in the builder or self-contained image; guide rewritten
- [x] add CI/static checks that flag new documentation/scripts which invoke known project tooling directly on the host where practical - "Check docs and scripts for host-side project tooling" step in `ci.yml`; tests `test_host_commands_are_flagged_and_containerised_ones_are_not`, `test_this_repository_passes`.
- [x] document that missing container dependencies must be fixed in Dockerfiles rather than installed on the workstation — `docs/testing.md` command reference

Host-side operations may be limited to Docker/Compose lifecycle, Git/source-control operations, editor/browser usage, and Git/worktree coordination helpers that are proven not to execute project runtime/tooling code.

## Build the image around upstream gisobuild requirements

Study:

- [x] upstream `Dockerfile` - `almalinux:8.10` + `setup/prep_dependency.sh`;
      the self-contained image uses the same base (amd64 manifest digest).
      Trivy (same CI gate as the socket image) first found seven fixed HIGH
      CVEs, all in the base image's unused `vim-minimal`; it is removed and
      the rescan passes with `--exit-code 1`. CI now builds this image,
      checks `gisobuild.py --help` in it and scans it (actionlint-clean; not
      yet observed on GitHub Actions).
- [x] `setup/prep_dependency.sh` - its Red Hat package list is installed
      as-is; its `pip install --user` is replaced by a system-wide install at
      the versions `ciscogisobuild/cisco-xr-gisobuild:2.3.4` ships
      (dataclasses 0.8, defusedxml 0.7.1, packaging 21.3, PyYAML 6.0.1),
      because the sanitized build environment moves `HOME`.
- [x] `src/gisobuild.py` - runs under the platform Python 3.6.8, exactly as
      in Cisco's image; `--help` and a real build work.
- [x] eXR dependencies - proven by the real NCS5500 build above; the eXR
      engine additionally needs `CAP_SYS_CHROOT`.
- [ ] LNT dependencies - installed from the same upstream list but not
      exercised: no LNT image is available to this work.

Use a compatible Linux base.

## Multi-stage image

Suggested stages:

### Stage 1 — source

- [x] pin upstream gisobuild commit (`ARG GISOBUILD_COMMIT`, 40-hex, checked
      by `test_image_pins_one_exact_gisobuild_commit_and_uses_the_local_runner`)
- [x] record repository URL (label + `GISOBUILD_REPOSITORY` env +
      `/api/version.gisobuild_repository`)
- [x] record commit SHA (label, env, `/api/version.gisobuild_commit`; the
      build fails unless `git rev-parse HEAD` equals the pin)
- [x] verify expected source hash - 2026-09-17: `ARG GISOBUILD_SOURCE_SHA256`
      pins the SHA-256 of a `sha256sum` manifest of every file (C-sorted; the
      build also refuses symlinks/special files). The image build fails on a
      mismatch (proven with an all-zero pin: `sha256sum: WARNING: 1 of 1
      computed checksums did NOT match`, exit 1). The manifest ships as
      `/opt/gisobuild.sha256sums`; `gisobuild_source_integrity()` re-checks
      every file and rejects additions at startup (required self-test check
      `gisobuild_source`, and a build blocker classified `ENVIRONMENT_ERROR`).
      `/api/version.gisobuild_source_sha256` and an image label report the pin.
      Live: the rebuilt image reported "67 files match the pinned SHA-256
      manifest"; the same image with `src/gisobuild.py` bind-mounted over
      reported "1 changed or missing (src/gisobuild.py)" and logged
      `startup_self_test_failed check=gisobuild_source`. Tests:
      `test_self_contained_gisobuild_source_is_checked_against_its_pinned_sha256`,
      `test_unpinned_gisobuild_checkout_skips_the_source_check_and_version_reports_the_pin`,
      `test_image_verifies_and_records_one_sha256_of_the_gisobuild_source`.

### Stage 2 — dependencies

- [x] install gisobuild system dependencies
- [x] ISO utilities (`genisoimage` incl. `isoinfo`, `libcdio`, `squashfs-tools`)
- [x] RPM utilities (`rpm`, `python3-rpm`, `createrepo_c`)
- [x] archive utilities (`cpio`, `gzip`, `p7zip-plugins`, `zip`, `unzip`)
- [x] Python/runtime dependencies (Python 3.6 for gisobuild, Python 3.12 +
      pinned `requirements.txt` for the app)
- [ ] include all test/runtime utilities needed so the host never needs them -
      tests still run in the separate `giso-webui` / browser-test images.

### Stage 3 — application

- [x] copy web app
- [x] copy pinned gisobuild source (`/opt/gisobuild`)
- [x] install web Python dependencies
- [x] add version metadata (OCI labels, `SOURCE_REVISION`, `BUILD_DATE`)
- [x] add health/readiness checks (`HEALTHCHECK` on `/api/health`;
      `/api/ready` checks gisobuild's interpreter in local mode)

### Optional Stage / Service — tooling

Provide a dedicated container where appropriate for development-only tooling that should not bloat production runtime.

- [x] Graphify — `docker/tooling.Dockerfile`
- [x] Ruff/linting — `docker/tooling.Dockerfile`
- [x] dependency/security auditing — `docker/tooling.Dockerfile`
- [x] staging/rehearsal — `docker/tooling.Dockerfile`
- [x] developer utilities — `gisobuild-tooling` + `scripts/check_docker_only.py`
- [x] frontend tooling if applicable — `docker/browser-tests.Dockerfile` (no JS build step exists)

The tooling container must use the repository through a controlled bind mount and must not install dependencies on the host.

## Runtime layout

Suggested:

```text
/opt/app
/opt/gisobuild
/data/uploads
/data/work
/data/archive
/data/state
```

Actual layout: `/opt/app`, `/opt/gisobuild`, volumes `/uploads`, `/work`,
`/output`, `/archive`, `/state`.

- [x] application files read-only (`read_only: true` root filesystem)
- [x] persistent archive/state volumes
- [x] temporary work separated (`/work`, with gisobuild's `TMPDIR` under the
      job's work directory instead of the 64 MiB `/tmp` tmpfs)
- [x] uploads separated

## Replace nested Docker

Current architecture must be replaced with a local runner **inside the application/build container**, not on the host.

Implement `GisoBuildRunner`.

Implemented as a runner mode inside the existing functions rather than a
new `GisoBuildRunner` class (`GISO_RUNNER`, `build_command()`, `run_job()`,
`builder_process_environment()`, `terminate_process_group()`):

- [x] version detection (`gisobuild_commit()` falls back to the recorded
      `GISOBUILD_COMMIT`)
- [x] ISO inspection (unchanged: `isoinfo`/`rpm` read-only, now in-image)
- [x] capability detection (platform profiles, plus the `CAP_SYS_CHROOT`
      preflight for eXR in local mode)
- [x] command generation (`python3 /opt/gisobuild/src/gisobuild.py …`,
      `--out-directory` on the output volume)
- [x] execution
- [x] stdout/stderr capture (merged stream, redacted log)
- [x] cancellation (see "Cancellation")
- [x] exit classification (success needs exit 0 *and* an ISO: the real
      "Nothing to do" exit 0 above was reported as failed)
- [x] artifact discovery (unchanged; the real build archived ISO + USB zip)

Invocation concept inside the container:

```bash
python /opt/gisobuild/src/gisobuild.py ...
```

This command must never be required on the user's host.

## Security

- [x] no Docker socket in the final architecture (self-contained deployment)
- [x] no `shell=True` in the app (list-form subprocesses; ruff `S` gate).
      Upstream gisobuild itself uses `shell=True` internally, e.g.
      `create_usb_zip()`, which this app does not control.
- [x] sanitized environment - `builder_process_environment()`: PATH, HOME,
      TMPDIR, locale only; Cisco API credentials never reach gisobuild
      (`test_local_build_runs_gisobuild_directly_with_a_sanitized_environment`).
- [x] explicit allowed paths (`safe_data_path()` for every input; outputs
      only under `/output/<job>`, work under `/work/<job>`)
- [x] process group isolation (`start_new_session=True`, group signals)
- [x] non-root where possible - evaluated 2026-09-17: **not possible for eXR
      builds**. In the self-contained image with `--cap-drop ALL --cap-add
      SYS_CHROOT --security-opt no-new-privileges:true`, uid 0 has
      `CapEff 0000000000040000` and `os.chroot()` succeeds; uid 1000 has
      `CapEff 0000000000000000` and gets "Operation not permitted", because
      Docker does not raise added capabilities for a non-root user, and file
      capabilities on a helper are exactly what `no-new-privileges` blocks.
      gisobuild's eXR engine needs that chroot for every RPM. So the process
      stays root, contained by the other controls below; the local-runner
      preflight would block an eXR plan if it were ever run non-root. An
      LNT-only non-root deployment was not tested.
- [x] document root requirements if unavoidable - here and in the README:
      root in the container with every capability dropped except
      `SYS_CHROOT`.
- [x] `no-new-privileges`
- [x] drop unnecessary capabilities - `cap_drop: ALL`, `cap_add:
      [SYS_CHROOT]`, the minimum the real build needed. Without it a local
      eXR plan is now blocked before starting
      (`test_local_exr_plan_requires_sys_chroot_before_starting`; live: the
      cap-drop-ALL container returned exactly that blocker).
- [x] read-only root filesystem where practical (`read_only: true`, verified
      in the real build)
- [x] controlled writable mounts only (five named volumes + `/tmp` tmpfs)
- [x] no installation or modification of host system packages
- [x] no dependency on host `/usr`, `/opt`, `/etc`, Python site-packages, Node modules, or shell configuration

## Cancellation

- [x] graceful process-group termination (SIGTERM to the group)
- [x] timeout (20 s grace)
- [x] forced termination if needed (SIGKILL to the group)
- [x] no orphan processes (`test_cancelling_a_local_build_leaves_no_orphan_processes`
      kills a child that gisobuild itself spawned)
- [x] cleanup work directory - 2026-09-17: `discard_job_work_directory()`
      removes `/work/<job>` (staged RPM copies, gisobuild temp files) when a
      build fails, errors or is cancelled; success already removed it while
      archiving. Inputs stay in `/uploads`, gisobuild logs in `/output/<job>`.
      Asserted in the dependency-failure and cancellation integration tests.
      Real-engine check (self-contained image, NCS5500 bundle, cancelled 75 s
      into the build): during the build gisobuild (pid 26) and its
      `zcat | cpio` shell child were running and `/output/<job>` held 7.1 GiB
      of `tmp*` extraction directories and an inner `system_image.iso`, which
      a killed gisobuild never removes. After cancel: status and stage
      `cancelled`, no gisobuild process left, `/work` empty, and
      `/output/<job>` down to 32 KiB (`logs/gisobuild.log-…` only), because
      the cleanup now also removes `tmp*` directories and ISO files of an
      unsuccessful job and runs inside `cancel_job()` once the process group
      is gone (no race with the "cancelled" status).
- [x] persist `cancelled`

## Version endpoint

Implement `/api/version`.

Return:

- [x] app version
- [x] app git SHA (`source_revision`)
- [x] gisobuild repository (`gisobuild_repository`, self-contained image)
- [x] gisobuild commit
- [ ] gisobuild version - upstream has no version string beyond the commit
- [x] image version (`app_version` = image version label; `runner`)
- [x] schema version - `/api/version.schema_version` (job store schema,
      see "schema migrations" in `04-STATE-SECURITY-OBSERVABILITY-TODO.md`)

## Reproducibility

Progress 2026-09-17 on today's `giso-webui` image (the self-contained
image this file targets does not exist yet; these apply to it too):

- [x] pin base-image digest - `FROM python:3.12-alpine@sha256:b64631e0…`;
      system packages pinned by version (`apk add … =`), hadolint-clean.
- [x] pin Python dependencies - `requirements.txt` now pins all nine
      installed distributions, including Flask's and gunicorn's transitive
      ones (`blinker`, `itsdangerous`, `Jinja2`, `MarkupSafe`, `packaging`,
      `Werkzeug`), which were previously resolved freshly on every build.
      `pip freeze` in the rebuilt image lists exactly those nine; pip-audit
      reports no known vulnerabilities.
- [x] pin gisobuild commit - in the self-contained image (see "Stage 1");
      the socket deployment still bind-mounts `.gisobuild-tool`.
- [x] image labels - OCI `org.opencontainers.image.{title,description,source,
      revision,created,version}` in `giso-webui/Dockerfile`.
- [x] SBOM - SPDX JSON from pinned Syft in CI, uploaded as an artifact (see
      `05-TESTING-CI-TODO.md`).
- [x] build timestamp - `BUILD_DATE` build arg → label, env and
      `/api/version.build_date`; CI passes UTC now.
- [x] source revision - `SOURCE_REVISION` build arg → label, env,
      `/api/version.source_revision` and the page's version line; CI passes
      `$GITHUB_SHA`. Verified by building with the local HEAD: label and
      API both returned `c6158c668c16f4f8cd17e8b652df8a676ff3e68c`.

## Compose

- [x] one primary runtime service where practical — `compose.selfcontained.yaml`: `giso-webui` plus the small `archive-maintenance`
- [x] dedicated tooling/test service if needed — tooling and browser-test images rather than compose services
- [x] persistent volumes — uploads, work, output, archive, state
- [x] secrets mounted as files — `/run/secrets` read-only with `CISCO_CLIENT_*_FILE`
- [x] healthcheck — image `HEALTHCHECK`
- [x] readiness check — `/api/ready` incl. the startup self-test
- [x] no Docker socket in the final architecture — self-contained compose
- [x] no external tool checkout — self-contained compose
- [x] commands for test/lint/Graphify/staging that execute entirely inside containers — `docs/testing.md` command reference
- [x] no requirement for host Python, Node, RPM tools, ISO tools, or gisobuild dependencies — self-contained image carries them

## Developer experience acceptance criteria

A new developer or AI coding agent with only Git and Docker available should be able to perform all supported project work without installing language runtimes or project tools on the host.

Expected patterns:

```bash
docker compose build
docker compose up -d
docker compose run --rm <tooling-service> <test-command>
docker compose run --rm <tooling-service> <graphify-command>
docker compose exec <service> <maintenance-command>
```

- [x] document all common commands — `docs/testing.md` command reference, README deployment sections
- [ ] verify clean-machine workflow with no host Python/Node/project packages
- [x] verify local test suite entirely in containers — 304 unit/integration and 17 browser tests run only in containers (2026-09-17)
- [x] verify Graphify entirely in containers — see above
- [x] verify staging/rehearsal entirely in containers — rehearsal PASS in `gisobuild-tooling`
- [x] verify real gisobuild workflow requires no host tooling other than Docker — the real NCS5500 self-contained build used only Docker plus `curl` against the API

## Optional publishing

Prepare for:

- [x] `ghcr.io/patricklind/gisobuild-gui:<version>` — configured in `release.yml` (now with source revision and version build args); publishing not observed from this environment
- [x] `ghcr.io/patricklind/gisobuild-gui:latest` — same
- [x] self-contained image published alongside as `:<version>-selfcontained` and `:latest-selfcontained` (linux/amd64) — configured in `release.yml` 2026-09-17; not observed from this environment
