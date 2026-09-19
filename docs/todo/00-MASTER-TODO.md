# GISOBuild GUI — Master TODO

Repository: `patricklind/gisobuild-gui`

Goal: Turn the project into a secure, automated frontend and orchestration layer for **everything supported by the pinned upstream `ios-xr/gisobuild` version**.

Core principle:

> Do not build a GUI for a handful of router models. Build a generic frontend for Cisco `ios-xr/gisobuild`.

## Final operator workflow

- [x] Start the application with `docker compose up -d`
- [x] Upload/select one IOS XR ISO
- [x] Upload/select RPM/SMU/TAR files or use Cisco download integration
- [x] Automatically inspect ISO metadata — architecture, and for eXR also
      platform/release from the image's own `iosxr_image_mdata.yml`
      (`iso_identity()`), plus the ISO 9660 signature. LNT platform/release
      still come from the filename (`isols.py` route blocked on having a
      real LNT image; see `02-AUTOMATION-BUILDPLAN-TODO.md`).
- [x] Automatically determine eXR vs LNT — `platform_profile()["engine"]`,
      derived from the detected/selected platform.
- [x] Automatically determine release/platform/capabilities — metadata for
      eXR, filename inference otherwise, plus `capabilities_for_platform()`
      aligned with upstream's CLI maps (incl. the eXR/LNT USB difference).
- [x] Automatically extract TAR/TGZ/TAR.GZ safely — `upload_complete()`'s
      symlink/hardlink/absolute-path/member-count/size-limit checks.
- [x] Automatically inspect RPM metadata — 2026-09-17: each RPM's header
      (name, version, release, arch, requires, provides) via read-only
      `rpm -qp`; renamed files, unreadable files, incomplete fixes and MD5
      mismatches against Cisco's SMU README are excluded with reasons, and
      unsatisfiable dependencies block the plan naming the prerequisite SMU.
      Header signature algorithm/key ID is read (not verified; gisobuild
      verifies), and automatic selection leaves out packages proven unable
      to install - proven by a real 19-RPM NCS5500 build.
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
      `warnings`); blockers, warnings and dependency problems are itemized
      during Step 2 review as well as at Start (`06-UI-OPERATOR-TODO.md`),
      now with an error code and suggested action per problem.
- [x] Build using bundled/pinned upstream gisobuild — socket deployment:
      `IMAGE` pinned to `ciscogisobuild/cisco-xr-gisobuild:2.3.4`;
      self-contained deployment: gisobuild bundled at a verified commit
      (see below).
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
- [x] Run without `/var/run/docker.sock` — 2026-09-17: the self-contained
      deployment (`docker/selfcontained.Dockerfile`,
      `giso-webui/compose.yaml`, `GISO_RUNNER=local`) built a real NCS5500
      25.1.2 Golden ISO with no socket, read-only root and only
      `SYS_CHROOT`. 2026-09-18: this is now the documented default —
      `compose.yaml` builds it directly, and the original socket deployment
      moved to `giso-webui/compose.socket.yaml` as the explicit alternative
      (see `03-DOCKER-SELF-CONTAINED-TODO.md`).
- [x] Run without an external `.gisobuild-tool` checkout — same deployment:
      gisobuild is baked into the image at a pinned, verified commit.

## Major workstreams

- [ ] Complete repository audit
- [ ] Resolve concrete correctness bugs in `07-BUG-AUDIT-TODO.md`
- [ ] Canonical package/inventory model
- [ ] Upstream-driven platform/capability model
- [ ] ISO metadata inspection
- [x] RPM metadata inspection — header identity, dependencies and signature
      metadata (`02-AUTOMATION-BUILDPLAN-TODO.md` "RPM inspection")
- [ ] CSC grouping and supersedence model
- [x] Unified automatic/manual selection engine (`02-AUTOMATION-BUILDPLAN-TODO.md`)
- [x] Immutable BuildPlan
- [x] Inventory revision + stale-state prevention
- [ ] Self-contained Docker image — built, proven with real eXR builds, and
      made the default deployment (source SHA-256 manifest and default
      switch both done); open: LNT unexercised, non-root impossible for eXR
- [x] GisoBuildRunner abstraction — `GISO_RUNNER` docker/local in
      `build_command()`/`run_job()`/`cancel_job()`, integration-tested for
      both and proven live for local
- [ ] Persistent state/database
- [x] Artifact verification/reporting — byte-for-byte + SHA-256 archive
      verification, `build-report.json`, error taxonomy for failures, stage
      timings and builder provenance in the report
- [ ] Security hardening
- [ ] Comprehensive tests
- [x] CI/CD and image publishing — full pipeline (unit/integration/browser
      tests, lint incl. security rules, Trivy, SBOM, Graphify freshness,
      platform drift) has run on real GitHub Actions for a while; the
      remaining gap was that automatic tagging/publishing was silently a
      no-op due to a `GITHUB_TOKEN` restriction. Fixed and confirmed
      end-to-end 2026-09-19 (`05-TESTING-CI-TODO.md` "Release automation"):
      a real push produced a real `v0.1.4` tag, GitHub Release, and
      published `linux/amd64`/`linux/arm64` images on GHCR with provenance
      and SBOM attached, with no manual step.

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

- [x] Phase 0 — lock down current bugs with regression tests from `07-BUG-AUDIT-TODO.md`
- [x] Phase 1 — tests + package identity model (unit, integration, browser, platform fixtures)
- [x] Phase 2 — inventory + BuildPlan
- [ ] Phase 3 — metadata-based ISO/RPM detection — done for eXR ISOs and all RPMs; LNT ISO metadata open
- [x] Phase 4 — unified automatic/manual CSC selection
- [x] Phase 5 — GisoBuildRunner abstraction
- [x] Phase 6 — self-contained Docker image (real build proven)
- [x] Phase 7 — remove Docker socket/nested builder — 2026-09-18: the
      self-contained deployment is now the default (`compose.yaml`); the
      socket deployment remains available as an explicit opt-in
      (`compose.socket.yaml`, its builder image now pinned by digest) - see
      `03-DOCKER-SELF-CONTAINED-TODO.md`
- [ ] Phase 8 — persistent state/inventory DB
- [ ] Phase 9 — UI simplification
- [ ] Phase 10 — security/observability hardening

## Acceptance criteria

- [x] Generic eXR support — all 12 upstream eXR platforms through the real
      BuildPlan (synthetic fixtures), `exr-generic` override, real NCS5500 builds
- [ ] Generic LNT support — LNT naming, options and USB handling follow
      upstream and are fixture-tested, but no real LNT image has been built
- [x] Capability-driven UI (`updatePlatformControls()` from upstream-aligned capabilities)
- [ ] Upstream-driven platform support
- [x] Unknown-but-upstream-supported platforms are not blocked (`exr-generic`/`lnt-generic`,
      `test_unknown_future_platform_pauses_automatic_selection_until_overridden`)
- [ ] No hard dependency on static router lists
- [x] No Docker socket required (self-contained deployment, real build)
- [x] No separate gisobuild checkout required (same)
- [x] Regression coverage for all bugs fixed (each fix in `07-BUG-AUDIT-TODO.md` names its test)
- [x] No destructive cleanup outside the active BuildPlan (`cleanup_paths` from the plan; integration tests)
- [x] Build lifecycle transitions are race-safe and cancellable (operation/job locks, plan fingerprint,
      cancellation tests for pull, build, finalization, and local process groups)
- [x] Graphify output is current for code-changing merges (CI freshness check)
