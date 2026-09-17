# Graph Report - work  (2026-09-17)

## Corpus Check
- 55 files · ~102,589 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: (none) 7, .css 4, .Dockerfile 3)

## Summary
- 1178 nodes · 1987 edges · 73 communities (50 shown, 17 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `010ac8a0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PlatformFixtureTests
- GisoWebTests
- CiscoDownloadError
- app.js
- Cisco IOS XR Golden ISO Build and Upgrade Guide
- PlatformCompatibilityTests
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
- Contributing
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
- app.py
- Path
- log_event
- SelfContainedPackagingTests
- run_job
- check_graphify_freshness.py
- SyntheticBuildIntegrationTests
- create_build_plan
- _screened_rpms
- DockerOnlyCheckTests
- .test_cisco_downloads_are_recorded_as_such_in_the_inventory
- run_cisco_download
- releasing.md
- check_docker_only.py
- enforce_archive_policy
- P1 — Wrong file/package selection
- P2 — Inventory consistency and races
- MaintenanceTests
- P1/P2 — Platform and compatibility validation
- staging/README.md
- P1 — Misleading UI status
- P0/P1 — Build lifecycle and destructive cleanup
- P2 — CI process fidelity
- .test_automatic_selection_leaves_out_fixes_that_cannot_install
- P2 — Tooling reliability

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 224 edges
2. `PlatformCompatibilityTests` - 36 edges
3. `create_build_plan()` - 32 edges
4. `OperatorFlowTests` - 30 edges
5. `validate_smu_selection()` - 29 edges
6. `BuildScriptTests` - 26 edges
7. `inventory_files()` - 21 edges
8. `CiscoDownloadError` - 21 edges
9. `CiscoSoftwareClient` - 19 edges
10. `recommend_smu_selection()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `cisco_search()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_download_start()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_accept()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_client()` --calls--> `CiscoSoftwareClient`  [EXTRACTED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_client()` --calls--> `secret_value()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/cisco_download.py

## Import Cycles
- None detected.

## Communities (73 total, 17 thin omitted)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.06
Nodes (12): cisco_config(), CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, RuntimeError, Cisco Automated Software Distribution client with strict download controls. (+4 more)

### Community 3 - "app.js"
Cohesion: 0.06
Nodes (68): api(), applyArchiveFilter(), applySmuRecommendation(), applySmuReviewFilter(), buildReportField(), checkCompatibility(), checkInventoryChanged(), checksumRow() (+60 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "PlatformCompatibilityTests"
Cohesion: 0.06
Nodes (24): platforms(), _bundle_files_by_csc(), capabilities_for_platform(), check_upgrade_matrix(), matrix_platform(), GisoBuildCapabilities, infer_platform(), is_lnt_platform() (+16 more)

### Community 7 - "System architecture"
Cohesion: 0.13
Nodes (14): Data lifecycle, High: Docker socket is a host-administration boundary, Low: The Cisco build image identity is mutable, Medium: Persistent volumes are a single point of failure, Medium: Running builds cannot resume after a web-service restart, Resolved: archive cleanup is independent of web traffic, Resolved: container health reflects required local dependencies, Review outcome (+6 more)

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
Cohesion: 0.18
Nodes (11): Cisco IOS XR GISO Builder, Components, License, Operational limitations, Quick start, Real ISO/USB acceptance test, Requirements, Security (+3 more)

### Community 15 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 16 - "Operations runbook"
Cohesion: 0.29
Nodes (7): Back up and restore state, Decommission, Failure handling, Logs and capacity, Operations runbook, Start and verify, Stop and upgrade

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

### Community 27 - "Path"
Cohesion: 0.09
Nodes (4): fake_disk_usage(), fake_disk_usage(), Path, skipUnless

### Community 28 - "AI Master Prompt — Cisco IOS-XR GISO Build Web UI"
Cohesion: 0.11
Nodes (18): AI Master Prompt — Cisco IOS-XR GISO Build Web UI, Artifacts and reproducibility, Automatic package handling, Beginner and advanced modes, BuildPlan, Capability-driven UI, Compatibility matrix, Completion criteria (+10 more)

### Community 29 - "Contributing"
Cohesion: 0.67
Nodes (3): Contributing, Coordination and branches, Local verification

### Community 31 - "TODO — Concrete Bug Audit"
Cohesion: 0.17
Nodes (11): `ARCHIVE_RETENTION_DAYS`/`MAX_ARCHIVE_BYTES` were never validated (2026-09-16), DNS-rebinding TOCTOU in the Cisco download SSRF guard (2026-09-16), P1 — Automatic selection kept packages it had proven cannot install (2026-09-17), P1 — Misconfiguration can silently destroy archived artifacts, P1/P2 — Found by the first real self-contained build (2026-09-17), P2 — Graphify / repository correctness, P2 — Operator UI defects found by the first real-browser tests (2026-09-17), P3 — Cisco download hardening (residual, deferred) (+3 more)

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
Cohesion: 0.13
Nodes (14): A capability giso-webui cannot currently verify: `--optimize`/`--full-iso` gating, Capability-driven UI, CLI option compatibility matrix (2026-09-16), Hardware aliases, Implemented capability slice, LNT, Representative eXR families, Required capability model (+6 more)

### Community 36 - "TODO — Testing & CI"
Cohesion: 0.18
Nodes (10): Browser/DOM tests, CI pipeline, Graphify CI guard, Integration test, Merge policy, Regression tests, Representative platform fixtures, Security tests (+2 more)

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

### Community 47 - "app.py"
Cohesion: 0.06
Nodes (45): after_request, errorhandler, get, activity(), archive_download(), bad_request(), cisco_download_status(), classify_api_error() (+37 more)

### Community 48 - "Path"
Cohesion: 0.06
Nodes (45): archive_giso_artifacts_and_cleanup(), archive_source_for_extraction(), command_preview(), current_inventory_revision(), file_checksums(), file_metadata_provenance(), file_sha256(), file_source() (+37 more)

### Community 49 - "log_event"
Cohesion: 0.07
Nodes (34): before_request, Connection, delete, append_log(), apply_schema_migrations(), archive_delete(), cancel_job(), cancel_upload() (+26 more)

### Community 52 - "run_job"
Cohesion: 0.09
Nodes (25): build_report(), BuildCancelled, builder_process_environment(), cancellation_requested(), child_mount_args(), discard_job_work_directory(), gisobuild_commit(), local_builder_image_id() (+17 more)

### Community 53 - "check_graphify_freshness.py"
Cohesion: 0.50
Nodes (7): check(), main(), normalized_graph(), Path, Regenerate the tracked code graph from tracked files and compare it…, tracked_files(), verify_ignore_policy()

### Community 54 - "SyntheticBuildIntegrationTests"
Cohesion: 0.17
Nodes (8): LocalRunnerIntegrationTests, process_is_running(), Synthetic end-to-end build integration: the real job pipeline, a fake engine.…, The real browser upload protocol: init, chunked PUT, complete., A Cisco-style SMU tar: the RPMs plus a README whose RPMS block lists them., True for a live process; a zombie (exited, not yet reaped) counts as gone., The same pipeline with GISO_RUNNER=local: gisobuild as a child process, no…, SyntheticBuildIntegrationTests

### Community 55 - "create_build_plan"
Cohesion: 0.09
Nodes (46): active_rpm_names(), build_cleanup_paths(), build_command(), build_environment_blockers(), build_plan(), cisco_download_running(), cisco_text(), cleanup() (+38 more)

### Community 56 - "_screened_rpms"
Cohesion: 0.11
Nodes (21): add_superseded_exclusions(), assign_lifecycle(), explain_with_prerequisites(), is_iso9660_image(), Set each item's lifecycle from what the workspace proves about it. INVALID…, Whether a file carries the ISO 9660 primary volume descriptor signature. Every…, A package's containing directory names the Cisco supersedence identifier it…, Explain, rather than silently drop, RPMs active_rpm_names() already filtered… (+13 more)

### Community 57 - "DockerOnlyCheckTests"
Cohesion: 0.28
Nodes (3): DockerOnlyCheckTests, load_checker(), The Docker-only documentation guard (scripts/check_docker_only.py).

### Community 59 - "run_cisco_download"
Cohesion: 0.16
Nodes (20): Exception, append_activity(), archive_suffix(), cisco_accept(), cisco_client(), cisco_download_start(), cisco_failure(), cisco_response_requires() (+12 more)

### Community 61 - "check_docker_only.py"
Cohesion: 0.42
Nodes (8): command_lines(), logical_lines(), main(), Path, Flag instructions and scripts that run project tooling on the host. AGENTS.md…, Join backslash continuations so a multi-line docker command is one unit., tracked_files(), violations()

### Community 62 - "enforce_archive_policy"
Cohesion: 0.13
Nodes (15): archive_checksums(), archive_list(), archive_size(), archive_timestamp(), build_space_blockers(), build_volume_free_bytes(), cross_process_archive_lock(), enforce_archive_policy() (+7 more)

### Community 63 - "P1 — Wrong file/package selection"
Cohesion: 0.25
Nodes (8): A CSC group's "select all" checkbox could never show fully checked when the group had a conflicted duplicate (2026-09-16), app.js and manual-packages.js both defined the manual-package-list logic, one of them dead (2026-09-16), Manual package UI collapses duplicate RPM basenames before the operator can inspect them, Multiple ISOs can result in the frontend silently selecting the first ISO, P1 — Wrong file/package selection, RPM processor architecture is not checked against the selected ISO, RPM selection uses a glob expression instead of an exact package identity, The immutable BuildPlan preview did not apply the RPM/ISO architecture check

### Community 64 - "P2 — Inventory consistency and races"
Cohesion: 0.33
Nodes (6): A single failed archive-policy cycle crashed the maintenance daemon entirely (2026-09-16), `/api/inputs` can race cleanup/deletion, Archive maintenance runs in a separate process with no cross-process lock (2026-09-16), Mandatory Docker pull makes builds depend on registry availability even when the builder image is already cached, P2 — Inventory consistency and races, Target release can remain stale after the selected ISO changes

### Community 66 - "P1/P2 — Platform and compatibility validation"
Cohesion: 0.33
Nodes (6): Bridge-SMU presence check can produce substring false positives, Filename heuristics can report confidence stronger than the evidence supports, Hardware alias matching used loose substrings instead of word boundaries, Ownership vouchers/certificate could be submitted one without the other with no warning (2026-09-16), P1/P2 — Platform and compatibility validation, Upgrade-matrix platform normalization is inconsistent

### Community 68 - "P1 — Misleading UI status"
Cohesion: 0.33
Nodes (6): "Detailed dependency check" defaulted to off for no real reason (2026-09-16), No free-space check exists for the volumes a build actually writes to (found 2026-09-16, fixed 2026-09-17), P1 — Misleading UI status, The base ISO already tells us which packages/versions it ships (found and fixed 2026-09-17), The header "System ready" pill checked only bare liveness, not actual readiness (2026-09-16), The "Start build" disabled hint could name a requirement that was already satisfied (2026-09-16)

### Community 69 - "P0/P1 — Build lifecycle and destructive cleanup"
Cohesion: 0.40
Nodes (5): Cancellation during image pull cannot reliably cancel the build, Cancelled build may still archive output and delete inputs, P0/P1 — Build lifecycle and destructive cleanup, Post-build cleanup could delete an unselected duplicate-basename RPM (2026-09-16), Successful build deletes unrelated files from the entire upload workspace

### Community 70 - "P2 — CI process fidelity"
Cohesion: 0.50
Nodes (4): A stale partial file from a crashed download made the next attempt fail too (2026-09-16), CI ran the unit test suite on the GitHub Actions host Python instead of inside the built container, P2 — CI process fidelity, Superseded RPMs were silently dropped instead of being explained (2026-09-16)

### Community 72 - "P2 — Tooling reliability"
Cohesion: 0.67
Nodes (3): `gisobuild_commit()` silently returned null due to git's ownership check (2026-09-16), P2 — Tooling reliability, `ruff` is installed unpinned in CI, so its rule set can change without a code change

## Knowledge Gaps
- **239 isolated node(s):** `inputs`, `platformProfiles`, `VOLUME_LABELS`, `CONFIDENCE_LABELS`, `READY_CHECK_LABELS` (+234 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 578 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `validate_smu_selection()` connect `PlatformCompatibilityTests` to `create_build_plan`, `IsoArchitectureInspectionTests`, `app.py`?**
  _High betweenness centrality (0.217) - this node is a cross-community bridge._
- **Why does `GisoWebTests` connect `GisoWebTests` to `PlatformCompatibilityTests`, `patch`, `.test_automatic_selection_leaves_out_fixes_that_cannot_install`, `IsoArchitectureInspectionTests`, `.test_discover_tolerates_file_removed_during_scan`, `._smu_fix`, `.upload`, `dict`, `.test_cisco_downloads_are_recorded_as_such_in_the_inventory`, `Path`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `patch` (e.g. with `.setUpClass()` and `.test_unsatisfiable_fix_is_left_out_and_names_the_smu_to_download()`) actually correct?**
  _`patch` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `inputs`, `platformProfiles`, `VOLUME_LABELS` to the rest of the system?**
  _239 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.016260162601626018 - nodes in this community are weakly interconnected._
- **Should `CiscoDownloadError` be split into smaller, more focused modules?**
  _Cohesion score 0.06429070580013976 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.06164383561643835 - nodes in this community are weakly interconnected._