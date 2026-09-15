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
- [ ] Resolve concrete correctness bugs in `07-BUG-AUDIT-TODO.md`
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

Current capability progress: the API, expert UI, and server adapter share one
tested eXR/LNT capability map derived from upstream CLI maps. The workstream
remains open until upstream source is pinned/bundled and unknown upstream-valid
platforms can be discovered without the local presentation list.

## Immediate bug-fix priority

Before large refactors hide the current failure modes, add regression tests and fix or preserve explicit coverage for:

- [x] cancellation during builder preparation/pull
- [x] cancellation during finalization
- [x] successful build must not delete unrelated inputs
- [x] multiple ISOs must never silently select the first candidate
- [x] RPM CPU architecture must match the selected ISO/build architecture
- [x] RPM selection must use exact identity, never glob matching
- [x] duplicate basenames must remain distinguishable by identity/checksum
- [x] compatibility matrix platform aliases must use one canonical resolver
- [x] bridge-SMU presence must use exact package/CSC identity
- [x] inventory discovery must tolerate concurrent cleanup/delete
- [x] auto-derived target release must not become stale when the ISO changes
- [x] Graphify output must be refreshed and freshness checked in CI

See `07-BUG-AUDIT-TODO.md` for detailed scenarios and required regression tests.

## Suggested implementation order

- [ ] Phase 0 — lock down current bugs with regression tests from `07-BUG-AUDIT-TODO.md`
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
- [ ] No destructive cleanup outside the active BuildPlan
- [ ] Build lifecycle transitions are race-safe and cancellable
- [ ] Graphify output is current for code-changing merges
