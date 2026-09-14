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

## Validation status

Static checks, Docker unit tests, Compose validation, and the isolated staging
upgrade/rollback rehearsal run in CI. Licensed-ISO and matching-router tests are
separate acceptance levels because Cisco software and hardware are unavailable
to public CI. Do not describe simulated or synthetic results as real GISO or
hardware validation.

## Release safety

Releases contain only this application's source, documentation, and container
image. Cisco ISO, RPM, SMU, USB, configuration, certificate, key-request, and
ownership-voucher artifacts must never be committed, logged, graphed, or
attached to a release.
