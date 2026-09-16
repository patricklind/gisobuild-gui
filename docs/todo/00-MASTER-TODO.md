# GISOBuild GUI — Master TODO

Repository: `patricklind/gisobuild-gui`

Goal: Turn the project into a secure, automated frontend and orchestration layer for **everything supported by the pinned upstream `ios-xr/gisobuild` version**.

Core principle:

> Do not build a GUI for a handful of router models. Build a generic frontend for Cisco `ios-xr/gisobuild`.

## Final operator workflow

- [x] Start the application with `docker compose up -d`
- [x] Upload/select one IOS XR ISO
- [x] Upload/select RPM/SMU/TAR files or use Cisco download integration
- [x] Automatically inspect ISO metadata — `inspect_iso_architecture()`
      (processor architecture only; platform/release still come from the
      filename, see the "Confidence display" honesty note in
      `06-UI-OPERATOR-TODO.md`).
- [x] Automatically determine eXR vs LNT — `platform_profile()["engine"]`,
      derived from the detected/selected platform.
- [x] Automatically determine release/platform/capabilities — filename
      inference plus `capabilities_for_platform()`; platform/release are
      `INFERRED`, not upstream-metadata-`VERIFIED` (same honesty note).
- [x] Automatically extract TAR/TGZ safely — `upload_complete()`'s
      symlink/hardlink/absolute-path/member-count/size-limit checks.
- [ ] Automatically inspect RPM metadata — not implemented; RPM
      architecture/release/CSC are all filename-derived, no RPM header
      parser exists (tracked as future work in `06-UI-OPERATOR-TODO.md`).
- [x] Automatically group RPMs by CSC — `package_groups`/`smuGroupCard()`.
- [x] Automatically exclude incompatible packages with reasons — wrong
      platform/release/architecture, superseded, and duplicate-conflict all
      report a specific reason (see "Explain decisions" in
      `06-UI-OPERATOR-TODO.md`).
- [x] Automatically generate one authoritative BuildPlan —
      `create_build_plan()`, checksum-fingerprinted, re-validated against
      the live inventory at job creation (`confirmed_plan_fingerprint`).
- [x] Show warnings/blockers before build — fixed 2026-09-16
      (`recommend_smu_selection()` was silently dropping its own computed
      `warnings`); still only itemized in full at the final confirmation,
      not the entire time during Step 2 review (open gap, see
      `06-UI-OPERATOR-TODO.md`'s Step 2 checklist).
- [x] Build using bundled/pinned upstream gisobuild — `IMAGE` is pinned to
      `ciscogisobuild/cisco-xr-gisobuild:2.3.4` by default and validated as
      a well-formed reference; "bundled" (no external `.gisobuild-tool`
      checkout) is not done, see below.
- [x] Verify output artifacts — `giso_artifact_candidates()` plus a
      byte-for-byte + SHA-256 comparison between source and archived copy
      before anything is deleted.
- [x] Produce checksums and `build-report.json` — `--create-checksum`
      produces gisobuild's own `checksums.json` as a downloadable artifact;
      a separate `build-report.json` (web UI/gisobuild version, exact
      BuildPlan, generated command, output checksums) is now written into
      the archive alongside the ISO on every successful build — see
      `06-UI-OPERATOR-TODO.md`.
- [x] Archive verified output — `archive_giso_artifacts_and_cleanup()`,
      with retention/quota enforcement now cross-process-safe (see the
      2026-09-16 fix in `07-BUG-AUDIT-TODO.md`).
- [x] Persist jobs/state across restarts — sqlite-backed `jobs`/`activity`
      tables; a restart marks any active job `"interrupted"` rather than
      leaving it stuck. Uploads and in-flight Cisco downloads are the
      remaining process-local-only state (see `04-STATE-SECURITY-OBSERVABILITY-TODO.md`).
- [ ] Run without `/var/run/docker.sock` — explicitly deferred; requires the
      security review and self-contained-image rewrite tracked in
      `03-DOCKER-SELF-CONTAINED-TODO.md`.
- [ ] Run without an external `.gisobuild-tool` checkout — `build_command()`
      still runs `/tool/src/gisobuild.py` from the mounted checkout inside
      the build container rather than a path baked into `IMAGE`; same
      dependency as above.

## Major workstreams

- [ ] Complete repository audit
- [ ] Resolve concrete correctness bugs in `07-BUG-AUDIT-TODO.md`
- [ ] Canonical package/inventory model
- [ ] Upstream-driven platform/capability model
- [ ] ISO metadata inspection
- [ ] RPM metadata inspection
- [ ] CSC grouping and supersedence model
- [ ] Unified automatic/manual selection engine
- [x] Immutable BuildPlan
- [x] Inventory revision + stale-state prevention
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
