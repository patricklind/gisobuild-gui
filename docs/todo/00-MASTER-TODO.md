# GISOBuild GUI — Master TODO

Repository: `patricklind/gisobuild-gui`

Goal: Turn the project into a secure, automated frontend and orchestration layer for **everything supported by the pinned upstream `ios-xr/gisobuild` version**.

Core principle:

> Do not build a GUI for a handful of router models. Build a generic frontend for Cisco `ios-xr/gisobuild`.

## Final operator workflow

- [ ] Start the application with `docker compose up -d`
- [ ] Upload/select one IOS XR ISO
- [ ] Upload/select RPM/SMU/TAR files or use Cisco download integration
- [ ] Automatically inspect ISO metadata
- [ ] Automatically determine eXR vs LNT
- [ ] Automatically determine release/platform/capabilities
- [ ] Automatically extract TAR/TGZ safely
- [ ] Automatically inspect RPM metadata
- [ ] Automatically group RPMs by CSC
- [ ] Automatically exclude incompatible packages with reasons
- [ ] Automatically generate one authoritative BuildPlan
- [ ] Show warnings/blockers before build
- [ ] Build using bundled/pinned upstream gisobuild
- [ ] Verify output artifacts
- [ ] Produce checksums and `build-report.json`
- [ ] Archive verified output
- [ ] Persist jobs/state across restarts
- [ ] Run without `/var/run/docker.sock`
- [ ] Run without an external `.gisobuild-tool` checkout

## Major workstreams

- [ ] Complete repository audit
- [ ] Canonical package/inventory model
- [ ] Upstream-driven platform/capability model
- [ ] ISO metadata inspection
- [ ] RPM metadata inspection
- [ ] CSC grouping and supersedence model
- [ ] Unified automatic/manual selection engine
- [ ] Immutable BuildPlan
- [ ] Inventory revision + stale-state prevention
- [ ] Self-contained Docker image
- [ ] GisoBuildRunner abstraction
- [ ] Persistent state/database
- [ ] Artifact verification/reporting
- [ ] Security hardening
- [ ] Comprehensive tests
- [ ] CI/CD and image publishing

## Suggested implementation order

- [ ] Phase 1 — tests + package identity model
- [ ] Phase 2 — inventory + BuildPlan
- [ ] Phase 3 — metadata-based ISO/RPM detection
- [ ] Phase 4 — unified automatic/manual CSC selection
- [ ] Phase 5 — GisoBuildRunner abstraction
- [ ] Phase 6 — self-contained Docker image
- [ ] Phase 7 — remove Docker socket/nested builder
- [ ] Phase 8 — persistent state/inventory DB
- [ ] Phase 9 — UI simplification
- [ ] Phase 10 — security/observability hardening

## Acceptance criteria

- [ ] Generic eXR support
- [ ] Generic LNT support
- [ ] Capability-driven UI
- [ ] Upstream-driven platform support
- [ ] Unknown-but-upstream-supported platforms are not blocked
- [ ] No hard dependency on static router lists
- [ ] No Docker socket required
- [ ] No separate gisobuild checkout required
- [ ] Regression coverage for all bugs fixed
