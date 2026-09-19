# Graph Report - project  (2026-09-19)

## Corpus Check
- 56 files · ~129,198 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: (none) 7, .css 4, .Dockerfile 3)

## Summary
- 1338 nodes · 2291 edges · 90 communities (58 shown, 19 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 44 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f8616b2f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PlatformFixtureTests
- GisoWebTests
- CiscoDownloadError
- app.js
- Cisco IOS XR Golden ISO Build and Upgrade Guide
- _screened_rpms
- patch
- System architecture
- BuildScriptTests
- AGENTS.md
- e2e_real_iso.py
- IOS XR GISO Web UI
- Cisco IOS XR GISO Builder
- docs/README.md
- IsoArchitectureInspectionTests
- rehearse.py
- Operations runbook
- build-giso.sh
- Testing and acceptance
- Release notes
- Security policy
- Platform support and validation
- coord.sh script
- worktree.sh
- dict
- AGENTS.md
- Path
- AI Master Prompt — Cisco IOS-XR GISO Build Web UI
- app.py
- TODO — Concrete Bug Audit
- TODO — Self-contained Docker Image
- TODO — Automation, Inventory & BuildPlan
- TODO — State, Security & Observability
- TODO — Upstream Platform & Capability Support
- TODO — Testing & CI
- TODO — Operator UX
- AI-INSTRUCTIONS.md
- GISOBuild GUI — Master TODO
- TODO roadmap for AI-assisted development
- copilot-instructions.md
- manual-packages.js
- OperatorFlowTests
- file_checksums
- enforce_archive_policy
- get
- SelfContainedPackagingTests
- infer_platform
- check_graphify_freshness.py
- SyntheticBuildIntegrationTests
- platform_validation.py
- Path
- DockerOnlyCheckTests
- .test_cisco_downloads_are_recorded_as_such_in_the_inventory
- CiscoDownloadTests
- create_build_plan
- check_docker_only.py
- log_event
- P1 — Wrong file/package selection
- P2 — Inventory consistency and races
- PlatformCompatibilityTests
- P1/P2 — Platform and compatibility validation
- recommend_smu_selection
- P1 — Misleading UI status
- P0/P1 — Build lifecycle and destructive cleanup
- P2 — CI process fidelity
- .test_automatic_selection_leaves_out_fixes_that_cannot_install
- P2 — Tooling reliability
- compare_exr_rpm_labels
- upstream_gisobuild_file
- secret_value
- test_platform_compatibility.py
- Release process
- .test_component_conflict_resolution_does_not_desync_plan_from_job_or_preview
- _JsonResponse
- find_cisco_images
- .test_redirect_is_revalidated_before_download
- maintenance.py

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 254 edges
2. `PlatformCompatibilityTests` - 47 edges
3. `OperatorFlowTests` - 35 edges
4. `create_build_plan()` - 34 edges
5. `CiscoDownloadTests` - 32 edges
6. `validate_smu_selection()` - 29 edges
7. `BuildScriptTests` - 26 edges
8. `inventory_files()` - 21 edges
9. `CiscoDownloadError` - 21 edges
10. `CiscoSoftwareClient` - 20 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/maintenance.py → giso-webui/app.py
- `cisco_config()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_search()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_download_start()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_accept()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py

## Import Cycles
- None detected.

## Communities (90 total, 19 thin omitted)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.24
Nodes (5): CiscoDownloadError, CiscoSoftwareClient, DownloadResult, RuntimeError, Safe error suitable for returning to the local UI.

### Community 3 - "app.js"
Cohesion: 0.06
Nodes (74): api(), applyArchiveFilter(), applySmuRecommendation(), applySmuReviewFilter(), buildPayload(), buildReportField(), checkCompatibility(), checkInventoryChanged() (+66 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "_screened_rpms"
Cohesion: 0.12
Nodes (20): add_superseded_exclusions(), assign_lifecycle(), exr_package_type_and_vm_type(), file_metadata_provenance(), is_iso9660_image(), Read one RPM's own identity and Requires/Provides from its header. One `rpm -qp…, The canonical filename an RPM's own header implies, if its real name differs.…, Where this file's platform/release identity comes from: (source, confidence,… (+12 more)

### Community 7 - "System architecture"
Cohesion: 0.12
Nodes (15): Data lifecycle, Default deployment (no Docker socket), High: Docker socket is a host-administration boundary (default deployment), Low: The Cisco build image identity is mutable, Medium: Persistent volumes are a single point of failure, Medium: Running builds cannot resume after a web-service restart, Resolved: archive cleanup is independent of web traffic, Resolved: container health reflects required local dependencies (+7 more)

### Community 9 - "AGENTS.md"
Cohesion: 0.17
Nodes (11): Allowed host commands, CRITICAL: Docker-only execution boundary, Docker boundary applies to all environments, Forbidden on the local host, Gotchas, Hard rules, Mandatory project roadmap and Graphify — read before doing anything, No host fallback (+3 more)

### Community 10 - "e2e_real_iso.py"
Cohesion: 0.31
Nodes (10): ArgumentParser, Namespace, main(), parse_args(), Path, Upload a licensed XR ISO and verify real ISO plus USB build artifacts., Upload one file and return the server-assigned path., request() (+2 more)

### Community 11 - "IOS XR GISO Web UI"
Cohesion: 0.18
Nodes (11): Build workflow, Configuration, Data lifecycle, IOS XR GISO Web UI, Optional Cisco software download, Requirements, Security and disclaimer, Start (+3 more)

### Community 12 - "Cisco IOS XR GISO Builder"
Cohesion: 0.14
Nodes (14): Alternative: `compose.socket.yaml` (Docker socket), Cisco IOS XR GISO Builder, Components, Default: `compose.yaml` (no Docker socket), Deployment options, License, Moving an existing installation to the default, Operational limitations (+6 more)

### Community 15 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 16 - "Operations runbook"
Cohesion: 0.25
Nodes (8): Back up and restore state, Decommission, Failure handling, Logs and capacity, Operations runbook, Running behind a reverse proxy or tunnel, Start and verify, Stop and upgrade

### Community 17 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 18 - "Testing and acceptance"
Cohesion: 0.29
Nodes (7): 1. Static and unit verification, 2. Container smoke test, 3. Licensed-ISO acceptance test, 4. Matching-hardware validation, Developer command reference, Reporting results, Testing and acceptance

### Community 20 - "Release notes"
Cohesion: 0.40
Nodes (4): Release notes, Release safety, Unreleased, Validation status

### Community 21 - "Security policy"
Cohesion: 0.33
Nodes (6): Deployment boundary, Operational controls, Reporting a vulnerability, Security policy, Sensitive data, Supported version

### Community 22 - "Platform support and validation"
Cohesion: 0.40
Nodes (5): Option rules, Platform matrix, Platform support and validation, SMU compatibility checks, Source of truth

### Community 23 - "coord.sh script"
Cohesion: 0.83
Nodes (3): coord.sh script, slug(), usage()

### Community 24 - "worktree.sh"
Cohesion: 0.83
Nodes (3): worktree.sh script, usage(), validate()

### Community 26 - "AGENTS.md"
Cohesion: 0.22
Nodes (5): Contributing, Coordination and branches, Local verification, Module coordination board, Parallel work with Git worktrees

### Community 27 - "Path"
Cohesion: 0.07
Nodes (5): fake_disk_usage(), fake_disk_usage(), rmtree(), Path, skipUnless

### Community 28 - "AI Master Prompt — Cisco IOS-XR GISO Build Web UI"
Cohesion: 0.11
Nodes (18): AI Master Prompt — Cisco IOS-XR GISO Build Web UI, Artifacts and reproducibility, Automatic package handling, Beginner and advanced modes, BuildPlan, Capability-driven UI, Compatibility matrix, Completion criteria (+10 more)

### Community 29 - "app.py"
Cohesion: 0.06
Nodes (61): Connection, errorhandler, append_log(), apply_schema_migrations(), archive_giso_artifacts_and_cleanup(), bad_request(), build_report(), BuildCancelled (+53 more)

### Community 31 - "TODO — Concrete Bug Audit"
Cohesion: 0.13
Nodes (14): `ARCHIVE_RETENTION_DAYS`/`MAX_ARCHIVE_BYTES` were never validated (2026-09-16), DNS-rebinding TOCTOU in the Cisco download SSRF guard (2026-09-16), P1 — A verified, archived build was reported as failed (2026-09-17), P1 — Automatic selection kept packages it had proven cannot install (2026-09-17), P1 — CI would fail on a clean checkout (2026-09-17), P1 — Misconfiguration can silently destroy archived artifacts, P1/P2 — Found by the first real self-contained build (2026-09-17), P2 — Graphify / repository correctness (+6 more)

### Community 32 - "TODO — Self-contained Docker Image"
Cohesion: 0.11
Nodes (18): Build the image around upstream gisobuild requirements, Cancellation, Compose, Developer experience acceptance criteria, Docker-only enforcement, Goal, Multi-stage image, Optional publishing (+10 more)

### Community 33 - "TODO — Automation, Inventory & BuildPlan"
Cohesion: 0.12
Nodes (15): Automatic refresh, BuildPlan, BuildPlan fingerprint, Canonical inventory, CSC grouping, Duplicate handling, Found 2026-09-16: `isols.py` is the real upstream tool for exactly this, for LNT, Inventory revision (+7 more)

### Community 34 - "TODO — State, Security & Observability"
Cohesion: 0.14
Nodes (13): `/api/health`, `/api/ready`, Caching, Cisco secrets, Concurrency, Error taxonomy, Health and readiness, Job model (+5 more)

### Community 35 - "TODO — Upstream Platform & Capability Support"
Cohesion: 0.12
Nodes (15): A capability giso-webui cannot currently verify: `--optimize`/`--full-iso` gating, Capability-driven UI, CLI option compatibility matrix (2026-09-16), Detecting an upstream commit bump (2026-09-19), Hardware aliases, Implemented capability slice, LNT, Representative eXR families (+7 more)

### Community 36 - "TODO — Testing & CI"
Cohesion: 0.17
Nodes (11): Browser/DOM tests, CI pipeline, Graphify CI guard, Integration test, Merge policy, Regression tests, Release automation, Representative platform fixtures (+3 more)

### Community 37 - "TODO — Operator UX"
Cohesion: 0.17
Nodes (11): Automatic by default, Confidence display, Expert settings, Explain decisions, Normal workflow, Primary UX goal, Search and filtering (`docs/AI-MASTER-PROMPT.md` section 55), Step 1 — Files (+3 more)

### Community 38 - "AI-INSTRUCTIONS.md"
Cohesion: 0.22
Nodes (7): Do not fake completion, Mandatory Graphify workflow, Mandatory startup workflow, Mandatory TODO workflow, Non-negotiable Docker-only execution policy, Source-of-truth rule, TODO ownership by topic

### Community 39 - "GISOBuild GUI — Master TODO"
Cohesion: 0.29
Nodes (6): Acceptance criteria, Final operator workflow, GISOBuild GUI — Master TODO, Immediate bug-fix priority, Major workstreams, Suggested implementation order

### Community 40 - "TODO roadmap for AI-assisted development"
Cohesion: 0.50
Nodes (3): Files, TODO roadmap for AI-assisted development, Update policy

### Community 47 - "file_checksums"
Cohesion: 0.14
Nodes (15): archive_checksums(), explain_with_prerequisites(), file_checksums(), persist_checksums(), persisted_checksums(), A checksum recorded by an earlier process for exactly this path, size and mtime., Every bounded-size .txt in the workspace - Cisco ships one README per SMU., {SMU name: {rpm basename: md5}} from each Cisco SMU README's "RPMS:" block.… (+7 more)

### Community 48 - "enforce_archive_policy"
Cohesion: 0.09
Nodes (21): before_request, archive_delete(), archive_list(), archive_size(), archive_timestamp(), build_space_blockers(), build_volume_free_bytes(), cross_process_archive_lock() (+13 more)

### Community 49 - "get"
Cohesion: 0.09
Nodes (23): after_request, get, activity(), archive_download(), cisco_config(), cisco_download_status(), classify_api_error(), download() (+15 more)

### Community 52 - "infer_platform"
Cohesion: 0.29
Nodes (3): _bundle_files_by_csc(), infer_platform(), Map each CSC bug ID to every candidate filename belonging to it. Mirrors…

### Community 53 - "check_graphify_freshness.py"
Cohesion: 0.50
Nodes (7): check(), main(), normalized_graph(), Path, Regenerate the tracked code graph from tracked files and compare it…, tracked_files(), verify_ignore_policy()

### Community 54 - "SyntheticBuildIntegrationTests"
Cohesion: 0.16
Nodes (8): LocalRunnerIntegrationTests, process_is_running(), Synthetic end-to-end build integration: the real job pipeline, a fake engine.…, The real browser upload protocol: init, chunked PUT, complete., A Cisco-style SMU tar: the RPMs plus a README whose RPMS block lists them., True for a live process; a zombie (exited, not yet reaped) counts as gone., The same pipeline with GISO_RUNNER=local: gisobuild as a child process, no…, SyntheticBuildIntegrationTests

### Community 55 - "platform_validation.py"
Cohesion: 0.13
Nodes (14): classify_exclusion(), _compare_exr_rpm_field(), describe_package(), _exr_rpm_subfields(), GisoBuildCapabilities, lnt_rpm_release(), normalize_architecture(), Platform-aware validation for Cisco IOS XR GISO build options. (+6 more)

### Community 56 - "Path"
Cohesion: 0.10
Nodes (26): context_processor, archive_source_for_extraction(), archive_suffix(), asset_version(), build_cleanup_paths(), _check_gisobuild_source(), command_preview(), extract_cisco_archive() (+18 more)

### Community 57 - "DockerOnlyCheckTests"
Cohesion: 0.28
Nodes (3): DockerOnlyCheckTests, load_checker(), The Docker-only documentation guard (scripts/check_docker_only.py).

### Community 60 - "create_build_plan"
Cohesion: 0.05
Nodes (72): active_rpm_names(), build_command(), cisco_text(), compatibility(), confidence_report(), create_build_plan(), current_inventory_revision(), dependency_blocker_text() (+64 more)

### Community 61 - "check_docker_only.py"
Cohesion: 0.42
Nodes (8): command_lines(), logical_lines(), main(), Path, Flag instructions and scripts that run project tooling on the host. AGENTS.md…, Join backslash continuations so a multi-line docker command is one unit., tracked_files(), violations()

### Community 62 - "log_event"
Cohesion: 0.09
Nodes (43): delete, Exception, append_activity(), build_environment_blockers(), build_plan(), cancel_upload(), cisco_accept(), cisco_client() (+35 more)

### Community 63 - "P1 — Wrong file/package selection"
Cohesion: 0.25
Nodes (8): A CSC group's "select all" checkbox could never show fully checked when the group had a conflicted duplicate (2026-09-16), app.js and manual-packages.js both defined the manual-package-list logic, one of them dead (2026-09-16), Manual package UI collapses duplicate RPM basenames before the operator can inspect them, Multiple ISOs can result in the frontend silently selecting the first ISO, P1 — Wrong file/package selection, RPM processor architecture is not checked against the selected ISO, RPM selection uses a glob expression instead of an exact package identity, The immutable BuildPlan preview did not apply the RPM/ISO architecture check

### Community 64 - "P2 — Inventory consistency and races"
Cohesion: 0.33
Nodes (6): A single failed archive-policy cycle crashed the maintenance daemon entirely (2026-09-16), `/api/inputs` can race cleanup/deletion, Archive maintenance runs in a separate process with no cross-process lock (2026-09-16), Mandatory Docker pull makes builds depend on registry availability even when the builder image is already cached, P2 — Inventory consistency and races, Target release can remain stale after the selected ISO changes

### Community 65 - "PlatformCompatibilityTests"
Cohesion: 0.11
Nodes (5): check_upgrade_matrix(), matrix_platform(), Check deterministic filename compatibility before upstream dependency…, validate_smu_selection(), PlatformCompatibilityTests

### Community 66 - "P1/P2 — Platform and compatibility validation"
Cohesion: 0.33
Nodes (6): Bridge-SMU presence check can produce substring false positives, Filename heuristics can report confidence stronger than the evidence supports, Hardware alias matching used loose substrings instead of word boundaries, Ownership vouchers/certificate could be submitted one without the other with no warning (2026-09-16), P1/P2 — Platform and compatibility validation, Upgrade-matrix platform normalization is inconsistent

### Community 67 - "recommend_smu_selection"
Cohesion: 0.22
Nodes (3): is_lnt_platform(), Select every deterministic platform/release match for upstream dependency…, recommend_smu_selection()

### Community 68 - "P1 — Misleading UI status"
Cohesion: 0.33
Nodes (6): "Detailed dependency check" defaulted to off for no real reason (2026-09-16), No free-space check exists for the volumes a build actually writes to (found 2026-09-16, fixed 2026-09-17), P1 — Misleading UI status, The base ISO already tells us which packages/versions it ships (found and fixed 2026-09-17), The header "System ready" pill checked only bare liveness, not actual readiness (2026-09-16), The "Start build" disabled hint could name a requirement that was already satisfied (2026-09-16)

### Community 69 - "P0/P1 — Build lifecycle and destructive cleanup"
Cohesion: 0.33
Nodes (6): A failed build's work directory could still exist for a moment after the API reported "failed" (found 2026-09-19, real CI), Cancellation during image pull cannot reliably cancel the build, Cancelled build may still archive output and delete inputs, P0/P1 — Build lifecycle and destructive cleanup, Post-build cleanup could delete an unselected duplicate-basename RPM (2026-09-16), Successful build deletes unrelated files from the entire upload workspace

### Community 70 - "P2 — CI process fidelity"
Cohesion: 0.50
Nodes (4): A stale partial file from a crashed download made the next attempt fail too (2026-09-16), CI ran the unit test suite on the GitHub Actions host Python instead of inside the built container, P2 — CI process fidelity, Superseded RPMs were silently dropped instead of being explained (2026-09-16)

### Community 72 - "P2 — Tooling reliability"
Cohesion: 0.67
Nodes (3): `gisobuild_commit()` silently returned null due to git's ownership check (2026-09-16), P2 — Tooling reliability, `ruff` is installed unpinned in CI, so its rule set can change without a code change

### Community 73 - "compare_exr_rpm_labels"
Cohesion: 0.27
Nodes (5): compare_exr_rpm_labels(), Compare two eXR RPMs' (version, release), the way gisobuild's own…, ExrRpmLabelCompareTests, compare_exr_rpm_labels() vs. the real pinned upstream algorithm. See…, Execute the real upstream functions from the pinned source itself. Deliberately…

### Community 74 - "upstream_gisobuild_file"
Cohesion: 0.33
Nodes (4): Path, A file from the pinned upstream gisobuild source, or skip the test. Looked up…, upstream_gisobuild_file(), TestCase

### Community 76 - "secret_value"
Cohesion: 0.25
Nodes (5): _NoRedirect, Path, Cisco Automated Software Distribution client with strict download controls., Read a secret from NAME_FILE first, then NAME, without logging either., secret_value()

### Community 77 - "test_platform_compatibility.py"
Cohesion: 0.20
Nodes (7): capabilities_for_platform(), normalize_platform(), platform_profile(), platforms_supporting(), Return the UI/adapter capabilities for one normalized platform.…, Labels of the real platforms whose capabilities include `capability`. Used to…, validate_platform_options()

### Community 78 - "Release process"
Cohesion: 0.67
Nodes (3): Automatic releases, Deliberate out-of-sequence bumps and pre-releases, Release process

## Knowledge Gaps
- **251 isolated node(s):** `inputs`, `platformProfiles`, `VOLUME_LABELS`, `neededPrerequisiteSmus`, `CONFIDENCE_LABELS` (+246 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 638 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `validate_smu_selection()` connect `PlatformCompatibilityTests` to `recommend_smu_selection`, `test_platform_compatibility.py`, `IsoArchitectureInspectionTests`, `infer_platform`, `platform_validation.py`, `create_build_plan`, `app.py`?**
  _High betweenness centrality (0.194) - this node is a cross-community bridge._
- **Why does `GisoWebTests` connect `GisoWebTests` to `PlatformCompatibilityTests`, `patch`, `.test_automatic_selection_leaves_out_fixes_that_cannot_install`, `.test_build_waits_for_tar_extraction_to_finish`, `IsoArchitectureInspectionTests`, `.test_component_conflict_resolution_does_not_desync_plan_from_job_or_preview`, `.test_discover_tolerates_file_removed_during_scan`, `._smu_fix`, `.upload`, `.test_run_job_honors_cancellation_during_image_pull`, `dict`, `.test_cisco_downloads_are_recorded_as_such_in_the_inventory`, `Path`?**
  _High betweenness centrality (0.184) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `patch` (e.g. with `.setUpClass()` and `.test_build_preview_shows_an_unresolved_conflict_before_building()`) actually correct?**
  _`patch` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `inputs`, `platformProfiles`, `VOLUME_LABELS` to the rest of the system?**
  _251 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.015037593984962405 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.05582603050957481 - nodes in this community are weakly interconnected._
- **Should `Cisco IOS XR Golden ISO Build and Upgrade Guide` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._