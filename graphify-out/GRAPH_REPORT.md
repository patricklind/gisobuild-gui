# Graph Report - gisobuild-buildplan-core  (2026-09-15)

## Corpus Check
- 47 files · ~40,046 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 13 file(s) not represented in the graph (top: (none) 8, .css 4, .example 1)

## Summary
- 653 nodes · 1034 edges · 49 communities (34 shown, 6 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `adccf20b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- log_event
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
- rehearse.py
- build-giso.sh
- Release notes
- coord.sh script
- worktree.sh
- dict
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
- app.py
- inventory_files
- BuildCancelled
- Path
- run_cisco_download
- safe_data_path
- check_graphify_freshness.py
- initialize_job_store
- find_cisco_images

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 100 edges
2. `CiscoDownloadError` - 21 edges
3. `CiscoSoftwareClient` - 19 edges
4. `PlatformCompatibilityTests` - 18 edges
5. `validate_smu_selection()` - 16 edges
6. `log_event()` - 14 edges
7. `BuildScriptTests` - 14 edges
8. `TODO — Automation, Inventory & BuildPlan` - 14 edges
9. `create_job()` - 13 edges
10. `api()` - 13 edges

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

## Communities (49 total, 6 thin omitted)

### Community 0 - "log_event"
Cohesion: 0.20
Nodes (16): after_request, append_log(), cancel_job(), cancellation_requested(), cisco_download_running(), cleanup(), create_job(), docker_build_running() (+8 more)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.07
Nodes (12): cisco_config(), CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, RuntimeError, Cisco Automated Software Distribution client with strict download controls. (+4 more)

### Community 3 - "app.js"
Cohesion: 0.11
Nodes (41): api(), applySmuRecommendation(), checkCompatibility(), checksumRow(), compatibilityList(), compatibilityMetric(), copyText(), drop (+33 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "PlatformCompatibilityTests"
Cohesion: 0.10
Nodes (18): create_build_plan(), Create one immutable, backend-owned build decision from current inventory., capabilities_for_platform(), check_upgrade_matrix(), matrix_platform(), GisoBuildCapabilities, infer_platform(), normalize_platform() (+10 more)

### Community 7 - "System architecture"
Cohesion: 0.13
Nodes (14): Data lifecycle, High: Docker socket is a host-administration boundary, Low: The Cisco build image identity is mutable, Medium: Persistent volumes are a single point of failure, Medium: Running builds cannot resume after a web-service restart, Resolved: archive cleanup is independent of web traffic, Resolved: container health reflects required local dependencies, Review outcome (+6 more)

### Community 9 - "AGENTS.md"
Cohesion: 0.17
Nodes (8): Gotchas, Hard rules, Mandatory project roadmap and Graphify — read before doing anything, Parallel work — do this first, Project overview, Required verification, Module coordination board, Parallel work with Git worktrees

### Community 10 - "e2e_real_iso.py"
Cohesion: 0.31
Nodes (10): ArgumentParser, Namespace, main(), parse_args(), Path, Upload a licensed XR ISO and verify real ISO plus USB build artifacts., Upload one file and return the server-assigned path., request() (+2 more)

### Community 11 - "IOS XR GISO Web UI"
Cohesion: 0.18
Nodes (11): Build workflow, Configuration, Data lifecycle, IOS XR GISO Web UI, Optional Cisco software download, Requirements, Security and disclaimer, Start (+3 more)

### Community 12 - "Cisco IOS XR GISO Builder"
Cohesion: 0.20
Nodes (10): Cisco IOS XR GISO Builder, Components, License, Operational limitations, Quick start, Real ISO/USB acceptance test, Requirements, Security (+2 more)

### Community 13 - "docs/README.md"
Cohesion: 0.07
Nodes (31): Contributing, Coordination and branches, Local verification, Back up and restore state, Decommission, Failure handling, Logs and capacity, Operations runbook (+23 more)

### Community 15 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 17 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 20 - "Release notes"
Cohesion: 0.40
Nodes (4): Release notes, Release safety, Unreleased, Validation status

### Community 23 - "coord.sh script"
Cohesion: 0.83
Nodes (3): coord.sh script, slug(), usage()

### Community 24 - "worktree.sh"
Cohesion: 0.83
Nodes (3): worktree.sh script, usage(), validate()

### Community 31 - "TODO — Concrete Bug Audit"
Cohesion: 0.09
Nodes (21): `/api/inputs` can race cleanup/deletion, Bridge-SMU presence check can produce substring false positives, Cancellation during image pull cannot reliably cancel the build, Cancelled build may still archive output and delete inputs, Filename heuristics can report confidence stronger than the evidence supports, Mandatory Docker pull makes builds depend on registry availability even when the builder image is already cached, Manual package UI collapses duplicate RPM basenames before the operator can inspect them, Multiple ISOs can result in the frontend silently selecting the first ISO (+13 more)

### Community 32 - "TODO — Self-contained Docker Image"
Cohesion: 0.12
Nodes (15): Build the image around upstream gisobuild requirements, Cancellation, Compose, Goal, Multi-stage image, Optional publishing, Replace nested Docker, Reproducibility (+7 more)

### Community 33 - "TODO — Automation, Inventory & BuildPlan"
Cohesion: 0.13
Nodes (14): Automatic refresh, BuildPlan, BuildPlan fingerprint, Canonical inventory, CSC grouping, Duplicate handling, Inventory revision, ISO inspection (+6 more)

### Community 34 - "TODO — State, Security & Observability"
Cohesion: 0.14
Nodes (13): `/api/health`, `/api/ready`, Caching, Cisco secrets, Concurrency, Error taxonomy, Health and readiness, Job model (+5 more)

### Community 35 - "TODO — Upstream Platform & Capability Support"
Cohesion: 0.17
Nodes (11): Capability-driven UI, Hardware aliases, Implemented capability slice, LNT, Representative eXR families, Required capability model, Scope, Tests (+3 more)

### Community 36 - "TODO — Testing & CI"
Cohesion: 0.18
Nodes (10): Browser/DOM tests, CI pipeline, Graphify CI guard, Integration test, Merge policy, Regression tests, Representative platform fixtures, Security tests (+2 more)

### Community 37 - "TODO — Operator UX"
Cohesion: 0.18
Nodes (10): Automatic by default, Confidence display, Expert settings, Explain decisions, Normal workflow, Primary UX goal, Step 1 — Files, Step 2 — Review BuildPlan (+2 more)

### Community 38 - "AI-INSTRUCTIONS.md"
Cohesion: 0.25
Nodes (6): Do not fake completion, Mandatory Graphify workflow, Mandatory startup workflow, Mandatory TODO workflow, Source-of-truth rule, TODO ownership by topic

### Community 39 - "GISOBuild GUI — Master TODO"
Cohesion: 0.29
Nodes (6): Acceptance criteria, Final operator workflow, GISOBuild GUI — Master TODO, Immediate bug-fix priority, Major workstreams, Suggested implementation order

### Community 40 - "TODO roadmap for AI-assisted development"
Cohesion: 0.50
Nodes (3): Files, TODO roadmap for AI-assisted development, Update policy

### Community 47 - "app.py"
Cohesion: 0.19
Nodes (18): errorhandler, get, activity(), archive_checksums(), archive_download(), archive_list(), bad_request(), cisco_download_status() (+10 more)

### Community 48 - "inventory_files"
Cohesion: 0.18
Nodes (14): active_rpm_names(), build_command(), current_inventory_revision(), discover(), inventory_files(), inventory_id(), package_names_for_validation(), Return an opaque, stable identity without exposing an absolute path. (+6 more)

### Community 49 - "BuildCancelled"
Cohesion: 0.25
Nodes (8): BuildCancelled, child_mount_args(), prepare_destructive_finalization(), RuntimeError, Stop a build lifecycle without converting cancellation into failure., Share only required storage with the build container, never docker.sock., Commit the final state transition before any owned input is removed., validate_image_reference()

### Community 50 - "Path"
Cohesion: 0.20
Nodes (14): archive_giso_artifacts_and_cleanup(), archive_size(), archive_timestamp(), enforce_archive_policy(), extract_cisco_archive(), extraction_path(), file_sha256(), giso_artifact_candidates() (+6 more)

### Community 51 - "run_cisco_download"
Cohesion: 0.22
Nodes (18): Exception, append_activity(), build_plan(), cisco_accept(), cisco_client(), cisco_download_start(), cisco_failure(), cisco_response_requires() (+10 more)

### Community 52 - "safe_data_path"
Cohesion: 0.25
Nodes (8): delete, archive_delete(), build_cleanup_paths(), cancel_upload(), delete_upload(), glob_metacharacters(), Resolve only inputs explicitly owned by this build request., safe_data_path()

### Community 53 - "check_graphify_freshness.py"
Cohesion: 0.50
Nodes (7): check(), main(), normalized_graph(), Path, Regenerate the tracked code graph from tracked files and compare it…, tracked_files(), verify_ignore_policy()

### Community 54 - "initialize_job_store"
Cohesion: 0.29
Nodes (7): before_request, expire_upload_sessions(), initialize_job_store(), Remove licensed or sensitive artifact names from operator-visible logs., Create the job store and restore safe job history once per process., safe_log_text(), validate_host()

## Knowledge Gaps
- **183 isolated node(s):** `inputs`, `platformProfiles`, `drop`, `GitHub Copilot repository instructions`, `Mandatory project roadmap and Graphify — read before doing anything` (+178 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 335 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `patch`, `.test_run_job_honors_cancellation_during_image_pull`, `.test_discover_tolerates_file_removed_during_scan`, `.upload`, `dict`, `.test_build_waits_for_tar_extraction_to_finish`, `.test_failed_multi_file_cisco_download_removes_partial_results`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `CiscoSoftwareClient` connect `CiscoDownloadError` to `run_cisco_download`, `app.py`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `CiscoDownloadError` (e.g. with `cisco_accept()` and `cisco_config()`) actually correct?**
  _`CiscoDownloadError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `inputs`, `platformProfiles`, `drop` to the rest of the system?**
  _183 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.031746031746031744 - nodes in this community are weakly interconnected._
- **Should `CiscoDownloadError` be split into smaller, more focused modules?**
  _Cohesion score 0.07102040816326531 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.10676532769556026 - nodes in this community are weakly interconnected._