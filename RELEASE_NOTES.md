# Release notes

Published releases and generated change logs are available on the
[GitHub Releases page](https://github.com/patricklind/gisobuild-gui/releases).
The latest published version is
[v0.0.5](https://github.com/patricklind/gisobuild-gui/releases/tag/v0.0.5).

## Unreleased

- Clears raw failed-build output and its stale download links from memory,
  SQLite job history, and the build-result panel.
- Groups matching SMU RPMs by CSC identifier and explains platform, release,
  architecture, duplicate-version, overlap, and upgrade-matrix findings.
- Adds guided Expert settings with automatic package selection as the default.
- Preserves ISO and supported USB boot artifacts only after verified archival.
- Hardens interrupted uploads, multi-file Cisco downloads, archive timestamps,
  log redaction, CLI staging, and the licensed-ISO acceptance runner.
- Automatic selection leaves out packages proven unable to install (unmet
  exact dependencies, incomplete or altered Cisco fixes per their SMU README,
  renamed or unreadable RPMs) and names the SMU to download; manual selections
  are blocked instead. Checks read RPM headers, signature key IDs, Cisco SMU
  READMEs and ISO 9660 signatures, not only filenames.
- Selects LNT packages named the upstream way (`xr-cdp-24.3.1v1.0.0-1.x86_64.rpm`)
  and accepts `.tar.gz` bugfix bundles; eXR USB output follows upstream's
  per-platform scripts.
- Adds a self-contained image (`docker/selfcontained.Dockerfile`,
  `giso-webui/compose.selfcontained.yaml`) that runs pinned gisobuild without a
  Docker socket, read-only and with only `SYS_CHROOT`.
- Structured error codes with suggested actions, per-step build timings,
  builder provenance, evidence-based confidence, automatic inventory refresh,
  resumable uploads across dropped connections and restarts, a startup
  self-test in `/api/ready`, a versioned job store, and cached-builder
  fallback when the registry is unreachable.
- Fixes manual CSC group checkboxes, lost manual selections on upload, and the
  upgrade check reading the Cisco search form's target release.
- CI adds real-browser tests, synthetic build integration tests, platform
  fixtures, flake8-bandit rules, Trivy scans, an SBOM and a Docker-only guard.

## Validation status

Static checks, Docker unit/integration/browser tests, image scans, Compose
validation, and the isolated staging upgrade/rollback rehearsal run in CI.
Real Golden ISO builds from a licensed NCS5500 25.1.2 bundle (base only, and 19
RPMs including 7 SMUs) were completed in the self-contained image outside CI;
no LNT image has been built yet. Licensed-ISO and matching-router tests are
separate acceptance levels because Cisco software and hardware are unavailable
to public CI. Do not describe simulated or synthetic results as real GISO or
hardware validation.

## Release safety

Releases contain only this application's source, documentation, and container
image. Cisco ISO, RPM, SMU, USB, configuration, certificate, key-request, and
ownership-voucher artifacts must never be committed, logged, graphed, or
attached to a release.
