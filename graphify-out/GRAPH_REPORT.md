# Graph Report - work  (2026-09-17)

## Corpus Check
- 52 files · ~88,741 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: (none) 7, .css 4, .Dockerfile 2)

## Summary
- 1043 nodes · 1727 edges · 64 communities (41 shown, 15 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 31 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c2d75fa9`
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
- Release process
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
- create_job
- enforce_archive_policy
- Path
- check_graphify_freshness.py
- SyntheticBuildIntegrationTests
- RuntimeError
- staging/README.md
- create_build_plan
- MaintenanceTests
- explain_with_prerequisites
- inspect_iso_shipped_packages
- find_cisco_images
- iso_architectures_from_mdata

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 203 edges
2. `PlatformCompatibilityTests` - 35 edges
3. `create_build_plan()` - 27 edges
4. `validate_smu_selection()` - 26 edges
5. `BuildScriptTests` - 26 edges
6. `OperatorFlowTests` - 24 edges
7. `CiscoDownloadError` - 21 edges
8. `CiscoSoftwareClient` - 19 edges
9. `recommend_smu_selection()` - 19 edges
10. `AI Master Prompt — Cisco IOS-XR GISO Build Web UI` - 18 edges

## Surprising Connections (you probably didn't know these)
- `cisco_config()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_search()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_download_start()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_accept()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_client()` --calls--> `CiscoSoftwareClient`  [EXTRACTED]
  giso-webui/app.py → giso-webui/cisco_download.py

## Import Cycles
- None detected.

## Communities (64 total, 15 thin omitted)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.07
Nodes (11): CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, RuntimeError, Cisco Automated Software Distribution client with strict download controls., Safe error suitable for returning to the local UI. (+3 more)

### Community 3 - "app.js"
Cohesion: 0.07
Nodes (60): api(), applyArchiveFilter(), applySmuRecommendation(), applySmuReviewFilter(), buildReportField(), checkCompatibility(), checkInventoryChanged(), checksumRow() (+52 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "PlatformCompatibilityTests"
Cohesion: 0.06
Nodes (25): iso_architectures_from_listing(), Fall back to the ISO's own RPM repository when no eXR metadata file exists. LNT…, _bundle_files_by_csc(), capabilities_for_platform(), check_upgrade_matrix(), matrix_platform(), GisoBuildCapabilities, infer_platform() (+17 more)

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
Cohesion: 0.20
Nodes (10): Cisco IOS XR GISO Builder, Components, License, Operational limitations, Quick start, Real ISO/USB acceptance test, Requirements, Security (+2 more)

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
Cohesion: 0.33
Nodes (6): 1. Static and unit verification, 2. Container smoke test, 3. Licensed-ISO acceptance test, 4. Matching-hardware validation, Reporting results, Testing and acceptance

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
Cohesion: 0.10
Nodes (4): fake_disk_usage(), fake_disk_usage(), Path, skipUnless

### Community 28 - "AI Master Prompt — Cisco IOS-XR GISO Build Web UI"
Cohesion: 0.11
Nodes (18): AI Master Prompt — Cisco IOS-XR GISO Build Web UI, Artifacts and reproducibility, Automatic package handling, Beginner and advanced modes, BuildPlan, Capability-driven UI, Compatibility matrix, Completion criteria (+10 more)

### Community 31 - "TODO — Concrete Bug Audit"
Cohesion: 0.04
Nodes (47): A CSC group's "select all" checkbox could never show fully checked when the group had a conflicted duplicate (2026-09-16), A single failed archive-policy cycle crashed the maintenance daemon entirely (2026-09-16), A stale partial file from a crashed download made the next attempt fail too (2026-09-16), `/api/inputs` can race cleanup/deletion, app.js and manual-packages.js both defined the manual-package-list logic, one of them dead (2026-09-16), Archive maintenance runs in a separate process with no cross-process lock (2026-09-16), `ARCHIVE_RETENTION_DAYS`/`MAX_ARCHIVE_BYTES` were never validated (2026-09-16), Bridge-SMU presence check can produce substring false positives (+39 more)

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
Cohesion: 0.08
Nodes (42): errorhandler, get, activity(), archive_checksums(), archive_delete(), archive_download(), archive_list(), bad_request() (+34 more)

### Community 48 - "create_job"
Cohesion: 0.11
Nodes (38): after_request, delete, Exception, append_activity(), append_log(), build_environment_blockers(), build_plan(), cancel_job() (+30 more)

### Community 49 - "enforce_archive_policy"
Cohesion: 0.11
Nodes (18): before_request, archive_size(), archive_timestamp(), build_space_blockers(), build_volume_free_bytes(), enforce_archive_policy(), expire_upload_sessions(), initialize_job_store() (+10 more)

### Community 52 - "Path"
Cohesion: 0.13
Nodes (23): archive_giso_artifacts_and_cleanup(), archive_source_for_extraction(), archive_suffix(), build_cleanup_paths(), command_preview(), extract_cisco_archive(), extraction_path(), file_sha256() (+15 more)

### Community 53 - "check_graphify_freshness.py"
Cohesion: 0.50
Nodes (7): check(), main(), normalized_graph(), Path, Regenerate the tracked code graph from tracked files and compare it…, tracked_files(), verify_ignore_policy()

### Community 54 - "SyntheticBuildIntegrationTests"
Cohesion: 0.24
Nodes (4): Synthetic end-to-end build integration: the real job pipeline, a fake engine.…, The real browser upload protocol: init, chunked PUT, complete., A Cisco-style SMU tar: the RPMs plus a README whose RPMS block lists them., SyntheticBuildIntegrationTests

### Community 55 - "RuntimeError"
Cohesion: 0.20
Nodes (10): BuildCancelled, child_mount_args(), prepare_destructive_finalization(), RuntimeError, Stop a build lifecycle without converting cancellation into failure., Share only required storage with the build container, never docker.sock., Commit the final state transition before any owned input is removed., validate_archive_retention_days() (+2 more)

### Community 57 - "create_build_plan"
Cohesion: 0.08
Nodes (49): active_rpm_names(), add_superseded_exclusions(), build_command(), cisco_text(), compatibility(), confidence_report(), create_build_plan(), current_inventory_revision() (+41 more)

### Community 59 - "explain_with_prerequisites"
Cohesion: 0.25
Nodes (8): explain_with_prerequisites(), Every bounded-size .txt in the workspace - Cisco ships one README per SMU., {SMU name: {rpm basename: md5}} from each Cisco SMU README's "RPMS:" block.…, {SMU name: {package name: prerequisite SMU name}} from each README. A Cisco SMU…, Name the Cisco SMU that supplies each unsatisfiable requirement, when a README…, smu_readme_manifests(), smu_readme_prerequisites(), smu_readme_texts()

### Community 60 - "inspect_iso_shipped_packages"
Cohesion: 0.33
Nodes (6): inspect_iso_shipped_packages(), iso_shipped_packages_from_mdata(), Map package name -> version for everything the base ISO itself ships. Read from…, The base ISO's own ``iosxr_image_mdata.yml`` text, capped, or "" if…, Package name -> version for what the base ISO itself ships, or {} if unknown.…, read_iso_mdata()

## Knowledge Gaps
- **235 isolated node(s):** `inputs`, `platformProfiles`, `VOLUME_LABELS`, `CONFIDENCE_LABELS`, `READY_CHECK_LABELS` (+230 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 518 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `patch`, `IsoArchitectureInspectionTests`, `.test_discover_tolerates_file_removed_during_scan`, `.test_build_waits_for_tar_extraction_to_finish`, `._smu_fix`, `.upload`, `dict`, `Path`, `.test_failed_multi_file_cisco_download_removes_partial_results`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `patch` (e.g. with `.setUpClass()` and `.test_dependency_blocker_names_the_prerequisite_smu()`) actually correct?**
  _`patch` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `inputs`, `platformProfiles`, `VOLUME_LABELS` to the rest of the system?**
  _235 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.017857142857142856 - nodes in this community are weakly interconnected._
- **Should `CiscoDownloadError` be split into smaller, more focused modules?**
  _Cohesion score 0.06531204644412192 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.06971153846153846 - nodes in this community are weakly interconnected._
- **Should `Cisco IOS XR Golden ISO Build and Upgrade Guide` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._