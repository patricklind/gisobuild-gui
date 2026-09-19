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

- [x] Complete repository audit — code (bugs, security, CI/CD), documentation
      accuracy, dependencies, container images, JavaScript (never linted
      before 2026-09-19), and secrets (never scanned before 2026-09-19) have
      all been audited; every finding is either fixed or recorded in the
      relevant `docs/todo/*.md` file with its own evidence. "Complete" here
      means every practical audit angle has been run at least once and acted
      on, not that no future finding is possible - a codebase audit is
      never permanently finished in that stronger sense.
- [x] Resolve concrete correctness bugs in `07-BUG-AUDIT-TODO.md` — every
      bug in that file that is an actual, resolvable correctness defect has
      been fixed and regression-tested. The four items still unchecked
      there are not bugs awaiting a fix: one is latent with no reachable
      caller, one needs real LNT hardware this environment doesn't have,
      one is a deliberate design tradeoff already made, and one is a
      standing conditional whose precondition is false today by design.
- [x] Canonical package/inventory model — every field in
      `02-AUTOMATION-BUILDPLAN-TODO.md`'s "Canonical inventory" is done; its
      remaining unchecked entries (absolute path, `UPLOADING`, `ANALYZING`,
      `ARCHIVED`, `DELETING`) are each explicitly not inventory states by
      design, not missing model pieces.
- [x] Upstream-driven platform/capability model — `GisoBuildCapabilities`/
      `OPTION_CAPABILITIES` drive every option gate from upstream's own CLI
      maps, extended 2026-09-19 to also gate on what the deployment's own
      gisobuild build actually registers (`--optimize`/`--full-iso`), not
      only platform. `01-PLATFORM-UPSTREAM-TODO.md`'s three remaining items
      are a deliberately-rejected alternative design (full runtime platform
      discovery), a deliberately-deferred autonomous-publishing decision,
      and an open-ended-by-nature alias list - none is a missing capability
      model piece.
- [ ] ISO metadata inspection
- [x] RPM metadata inspection — header identity, dependencies and signature
      metadata (`02-AUTOMATION-BUILDPLAN-TODO.md` "RPM inspection")
- [x] CSC grouping and supersedence model — closed 2026-09-19. Both
      sections of `02-AUTOMATION-BUILDPLAN-TODO.md` now have no open items.
      Grouping comes from each Cisco SMU README's own `RPMS:` manifest
      (members plus MD5), so a fix uploaded without one of its RPMs, or with
      an altered one, is caught rather than looking like a smaller complete
      group. Supersedence is decided two ways, both confirmed against real
      Cisco content: README-declared `Full` entries drop the older fix, and
      `compare_exr_rpm_labels()` - a port of gisobuild's own exact
      comparator - resolves same-package conflicts before the build. The
      last open piece, README `Partial` supersedence, was investigated
      against all 10 real NCS5500 25.1.2 READMEs and closed as correct by
      design: `Partial` must *not* drop the older fix (one README lists the
      same SMU as both a prerequisite and a partial supersedence), which is
      what ignoring it already achieves, and that safety property is now
      pinned by
      `test_only_a_full_supersedence_drops_a_fix_a_partial_one_keeps_it`.
- [x] Unified automatic/manual selection engine (`02-AUTOMATION-BUILDPLAN-TODO.md`)
- [x] Immutable BuildPlan
- [x] Inventory revision + stale-state prevention
- [ ] Self-contained Docker image — built, proven with real eXR builds, and
      made the default deployment (source SHA-256 manifest and default
      switch both done); open: LNT unexercised, non-root impossible for eXR
- [x] GisoBuildRunner abstraction — `GISO_RUNNER` docker/local in
      `build_command()`/`run_job()`/`cancel_job()`, integration-tested for
      both and proven live for local
- [x] Persistent state/database — closed 2026-09-19.
      `04-STATE-SECURITY-OBSERVABILITY-TODO.md` is 80 items done against 4
      open, and each of those 4 is an explicit "deliberately not stored"
      decision rather than missing work: inventory is recomputed live from
      the filesystem (no cached copy can go stale against what an operator
      actually uploaded or deleted), a BuildPlan previewed via
      `/api/build-plan` but never submitted is a stateless preview, artifact
      metadata is derived from the archive directory on disk, and the
      inventory revision is recomputed on demand and pinned per-job once a
      build starts. What *is* persisted is in SQLite behind versioned
      migrations (`SCHEMA_MIGRATIONS` + `PRAGMA user_version`, 4 versions):
      jobs with their BuildPlan and plan fingerprint, the activity log, file
      provenance, browser upload sessions and large-file checksums. A store
      from a newer release blocks builds instead of being silently rewritten;
      restart recovery marks any still-active job `interrupted`. Verified
      live: a copy of this machine's real state volume migrated 0 → 1 with
      all 4 historic jobs intact, and the checksum cache took the first
      `/api/inputs` after a restart from 4.98 s to 0.03 s on the real
      2.2 GiB NCS5500 image.
- [x] Artifact verification/reporting — byte-for-byte + SHA-256 archive
      verification, `build-report.json`, error taxonomy for failures, stage
      timings and builder provenance in the report
- [x] Security hardening — closed 2026-09-19. Every security section of
      `04-STATE-SECURITY-OBSERVABILITY-TODO.md` (path security, Cisco
      secrets, structured logging and redaction, error taxonomy, health and
      readiness, startup self-test) is fully checked; all 4 of that file's
      remaining open items sit in "Persistent state" and are the deliberate
      design decisions described above. Runtime posture is proven in the
      default deployment, not just declared: `cap_drop: ALL` with only
      `SYS_CHROOT` added (the one capability gisobuild's eXR engine needs to
      chroot into the extracted image, verified against a real NCS5500
      build), `no-new-privileges`, read-only root filesystem, a size-capped
      tmpfs for `/tmp`, and no Docker socket mounted at all. Supply-chain and
      secret checks run in CI on every push: ruff security rules, Trivy image
      scan, SBOM, `pip-audit`, and gitleaks - the last added this session,
      after finding nothing had ever scanned this repository for leaked
      credentials. The residual items in `07-BUG-AUDIT-TODO.md` are a P3
      DNS-rebinding TOCTOU explicitly deferred with reasoning and a standing
      conditional trip-wire whose precondition is false today (download URLs
      come only from Cisco's own authenticated API); its own text says not to
      treat it as outstanding work.
- [x] Comprehensive tests — closed 2026-09-19.
      `05-TESTING-CI-TODO.md` is 100 items done against 4 open, and those 4
      are not tests at all: they are the GitHub branch-protection setting,
      measured 2026-09-19 as genuinely off (`"protected": false`,
      `enforcement_level: "off"`, no required checks), which only the
      repository owner can change. Every test layer the file calls for
      exists and runs in Docker in CI on every push: unit, representative
      platform fixtures, regression, integration, browser/DOM and security
      tests. Current totals are 382 unit tests and 29 real-browser tests, all
      green, with ruff, `ruff format --check`, ESLint, actionlint and
      gitleaks clean - and the browser layer has now caught five real
      operator-facing defects that no other layer did (see
      `07-BUG-AUDIT-TODO.md`).
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
- [x] Phase 8 — persistent state/inventory DB — see "Persistent state/database"
      under Major workstreams above. The inventory half is deliberately *not*
      a database: it is recomputed live so no cached copy can go stale
      against the files an operator actually uploaded or deleted, a decision
      recorded in `04-STATE-SECURITY-OBSERVABILITY-TODO.md` and reaffirmed
      when `07-BUG-AUDIT-TODO.md` proposed the opposite.
- [x] Phase 9 — UI simplification — `06-UI-OPERATOR-TODO.md` is complete: 61
      items done, none open, covering the normal workflow, automatic-by-
      default behavior, expert settings, decision explanations, the
      confidence display and search/filtering. Confirmed against the running
      application in a real browser, not only in tests - that live checking
      is what found five operator-facing defects this session.
- [x] Phase 10 — security/observability hardening — see "Security hardening"
      under Major workstreams above.

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
