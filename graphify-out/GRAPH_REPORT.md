# Graph Report - project  (2026-09-16)

## Corpus Check
- 49 files · ~66,642 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: (none) 7, .css 4, .Dockerfile 1)

## Summary
- 854 nodes · 1334 edges · 56 communities (39 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 21 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `459c50d0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- create_build_plan
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
- releasing.md
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
- Path
- app.py
- RuntimeError
- maintenance.py
- run_cisco_download
- create_job
- initialize_job_store
- check_graphify_freshness.py
- build_command
- staging/README.md

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 158 edges
2. `PlatformCompatibilityTests` - 27 edges
3. `BuildScriptTests` - 22 edges
4. `CiscoDownloadError` - 21 edges
5. `validate_smu_selection()` - 21 edges
6. `CiscoSoftwareClient` - 19 edges
7. `AI Master Prompt — Cisco IOS-XR GISO Build Web UI` - 18 edges
8. `recommend_smu_selection()` - 16 edges
9. `create_build_plan()` - 15 edges
10. `api()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/maintenance.py → giso-webui/app.py
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

## Communities (56 total, 11 thin omitted)

### Community 0 - "create_build_plan"
Cohesion: 0.11
Nodes (24): active_rpm_names(), add_superseded_exclusions(), build_plan(), confidence_report(), create_build_plan(), current_inventory_revision(), discover(), glob_metacharacters() (+16 more)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.06
Nodes (12): cisco_config(), CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, RuntimeError, Cisco Automated Software Distribution client with strict download controls. (+4 more)

### Community 3 - "app.js"
Cohesion: 0.08
Nodes (49): api(), applyArchiveFilter(), applySmuRecommendation(), buildReportField(), checkCompatibility(), checksumRow(), compatibilityList(), compatibilityMetric() (+41 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "PlatformCompatibilityTests"
Cohesion: 0.08
Nodes (19): platforms(), capabilities_for_platform(), check_upgrade_matrix(), matrix_platform(), GisoBuildCapabilities, infer_platform(), normalize_architecture(), normalize_platform() (+11 more)

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

### Community 28 - "AI Master Prompt — Cisco IOS-XR GISO Build Web UI"
Cohesion: 0.11
Nodes (18): AI Master Prompt — Cisco IOS-XR GISO Build Web UI, Artifacts and reproducibility, Automatic package handling, Beginner and advanced modes, BuildPlan, Capability-driven UI, Compatibility matrix, Completion criteria (+10 more)

### Community 31 - "TODO — Concrete Bug Audit"
Cohesion: 0.04
Nodes (44): A CSC group's "select all" checkbox could never show fully checked when the group had a conflicted duplicate (2026-09-16), A single failed archive-policy cycle crashed the maintenance daemon entirely (2026-09-16), A stale partial file from a crashed download made the next attempt fail too (2026-09-16), `/api/inputs` can race cleanup/deletion, app.js and manual-packages.js both defined the manual-package-list logic, one of them dead (2026-09-16), Archive maintenance runs in a separate process with no cross-process lock (2026-09-16), `ARCHIVE_RETENTION_DAYS`/`MAX_ARCHIVE_BYTES` were never validated (2026-09-16), Bridge-SMU presence check can produce substring false positives (+36 more)

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

### Community 45 - "Path"
Cohesion: 0.19
Nodes (15): archive_giso_artifacts_and_cleanup(), archive_source_for_extraction(), command_preview(), extract_cisco_archive(), extraction_path(), file_sha256(), giso_artifact_candidates(), Path (+7 more)

### Community 47 - "app.py"
Cohesion: 0.09
Nodes (39): errorhandler, get, activity(), archive_checksums(), archive_delete(), archive_download(), archive_list(), archive_size() (+31 more)

### Community 48 - "RuntimeError"
Cohesion: 0.25
Nodes (8): BuildCancelled, prepare_destructive_finalization(), RuntimeError, Commit the final state transition before any owned input is removed., Stop a build lifecycle without converting cancellation into failure., validate_archive_retention_days(), validate_image_reference(), validate_max_archive_bytes()

### Community 50 - "run_cisco_download"
Cohesion: 0.20
Nodes (19): Exception, append_activity(), cisco_accept(), cisco_client(), cisco_download_start(), cisco_failure(), cisco_response_requires(), cisco_search() (+11 more)

### Community 51 - "create_job"
Cohesion: 0.18
Nodes (18): after_request, delete, append_log(), cancel_job(), cancel_upload(), cancellation_requested(), cisco_download_running(), cleanup() (+10 more)

### Community 52 - "initialize_job_store"
Cohesion: 0.29
Nodes (7): before_request, expire_upload_sessions(), initialize_job_store(), Remove licensed or sensitive artifact names from operator-visible logs., Create the job store and restore safe job history once per process., safe_log_text(), validate_host()

### Community 53 - "check_graphify_freshness.py"
Cohesion: 0.50
Nodes (7): check(), main(), normalized_graph(), Path, Regenerate the tracked code graph from tracked files and compare it…, tracked_files(), verify_ignore_policy()

### Community 54 - "build_command"
Cohesion: 0.17
Nodes (12): build_cleanup_paths(), build_command(), child_mount_args(), inspect_iso_architecture(), iso_architectures_from_listing(), iso_architectures_from_mdata(), Share only required storage with the build container, never docker.sock., Resolve only inputs explicitly owned by this build request. RPMs must come from… (+4 more)

## Knowledge Gaps
- **231 isolated node(s):** `inputs`, `platformProfiles`, `CONFIDENCE_LABELS`, `READY_CHECK_LABELS`, `drop` (+226 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 457 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `patch`, `IsoArchitectureInspectionTests`, `.test_discover_tolerates_file_removed_during_scan`, `.upload`, `dict`, `Path`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `CiscoSoftwareClient` connect `CiscoDownloadError` to `run_cisco_download`, `app.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **What connects `inputs`, `platformProfiles`, `CONFIDENCE_LABELS` to the rest of the system?**
  _231 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `create_build_plan` be split into smaller, more focused modules?**
  _Cohesion score 0.11231884057971014 - nodes in this community are weakly interconnected._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.02 - nodes in this community are weakly interconnected._
- **Should `CiscoDownloadError` be split into smaller, more focused modules?**
  _Cohesion score 0.06429070580013976 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.08245981830887492 - nodes in this community are weakly interconnected._