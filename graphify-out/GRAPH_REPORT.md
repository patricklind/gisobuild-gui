# Graph Report - gisobuild  (2026-09-16)

## Corpus Check
- 47 files · ~47,926 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 7, .css 4, .example 1)

## Summary
- 728 nodes · 1176 edges · 57 communities (38 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `141ef7ed`
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
- Contributing
- Path
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
- app.py
- Path
- persist_job
- enforce_archive_policy
- create_job
- run_job
- check_graphify_freshness.py
- find_cisco_images
- add_superseded_exclusions
- staging/README.md

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 122 edges
2. `PlatformCompatibilityTests` - 24 edges
3. `CiscoDownloadError` - 21 edges
4. `validate_smu_selection()` - 21 edges
5. `CiscoSoftwareClient` - 19 edges
6. `create_build_plan()` - 15 edges
7. `log_event()` - 14 edges
8. `recommend_smu_selection()` - 14 edges
9. `BuildScriptTests` - 14 edges
10. `TODO — Automation, Inventory & BuildPlan` - 14 edges

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

## Communities (57 total, 11 thin omitted)

### Community 0 - "log_event"
Cohesion: 0.18
Nodes (14): after_request, append_activity(), cancel_upload(), extract_cisco_archive(), extraction_path(), log_event(), Validate a client filename without silently rewriting path components., Write a compact operational event without sensitive filenames or payloads. (+6 more)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.07
Nodes (11): CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, RuntimeError, Cisco Automated Software Distribution client with strict download controls., Safe error suitable for returning to the local UI. (+3 more)

### Community 3 - "app.js"
Cohesion: 0.10
Nodes (43): api(), applySmuRecommendation(), checkCompatibility(), checksumRow(), compatibilityList(), compatibilityMetric(), CONFIDENCE_LABELS, confidenceGrid() (+35 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "PlatformCompatibilityTests"
Cohesion: 0.07
Nodes (28): active_rpm_names(), build_command(), create_build_plan(), inspect_iso_architecture(), iso_architectures_from_listing(), iso_architectures_from_mdata(), Read the canonical arch families straight from an eXR…, Fall back to the ISO's own RPM repository when no eXR metadata file exists. LNT… (+20 more)

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

### Community 26 - "Contributing"
Cohesion: 0.67
Nodes (3): Contributing, Coordination and branches, Local verification

### Community 31 - "TODO — Concrete Bug Audit"
Cohesion: 0.06
Nodes (32): `/api/inputs` can race cleanup/deletion, Archive maintenance runs in a separate process with no cross-process lock (2026-09-16), Bridge-SMU presence check can produce substring false positives, Cancellation during image pull cannot reliably cancel the build, Cancelled build may still archive output and delete inputs, CI ran the unit test suite on the GitHub Actions host Python instead of inside the built container, DNS-rebinding TOCTOU in the Cisco download SSRF guard (2026-09-16), Filename heuristics can report confidence stronger than the evidence supports (+24 more)

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
Cohesion: 0.15
Nodes (23): errorhandler, get, activity(), archive_checksums(), archive_delete(), archive_download(), archive_list(), bad_request() (+15 more)

### Community 48 - "Path"
Cohesion: 0.10
Nodes (29): archive_giso_artifacts_and_cleanup(), archive_source_for_extraction(), build_cleanup_paths(), confidence_report(), current_inventory_revision(), discover(), file_checksums(), file_sha256() (+21 more)

### Community 49 - "persist_job"
Cohesion: 0.28
Nodes (9): delete, append_log(), cancel_job(), delete_upload(), initialize_job_store(), persist_job(), Remove licensed or sensitive artifact names from operator-visible logs., Create the job store and restore safe job history once per process. (+1 more)

### Community 50 - "enforce_archive_policy"
Cohesion: 0.25
Nodes (8): before_request, archive_size(), archive_timestamp(), enforce_archive_policy(), expire_upload_sessions(), Remove expired archive jobs, then oldest jobs until the archive fits its quota., validate_host(), main()

### Community 51 - "create_job"
Cohesion: 0.23
Nodes (19): Exception, build_plan(), cisco_accept(), cisco_client(), cisco_download_running(), cisco_download_start(), cisco_failure(), cisco_response_requires() (+11 more)

### Community 52 - "run_job"
Cohesion: 0.24
Nodes (10): BuildCancelled, cancellation_requested(), child_mount_args(), prepare_destructive_finalization(), RuntimeError, Share only required storage with the build container, never docker.sock., Stop a build lifecycle without converting cancellation into failure., Commit the final state transition before any owned input is removed. (+2 more)

### Community 53 - "check_graphify_freshness.py"
Cohesion: 0.50
Nodes (7): check(), main(), normalized_graph(), Path, Regenerate the tracked code graph from tracked files and compare it…, tracked_files(), verify_ignore_policy()

### Community 55 - "add_superseded_exclusions"
Cohesion: 0.50
Nodes (4): add_superseded_exclusions(), A package's containing directory names the Cisco supersedence identifier it…, Explain, rather than silently drop, RPMs active_rpm_names() already filtered…, rpm_is_superseded()

## Knowledge Gaps
- **192 isolated node(s):** `inputs`, `platformProfiles`, `CONFIDENCE_LABELS`, `drop`, `GitHub Copilot repository instructions` (+187 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 366 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `patch`, `.test_run_job_honors_cancellation_during_image_pull`, `IsoArchitectureInspectionTests`, `.test_discover_tolerates_file_removed_during_scan`, `.upload`, `dict`, `Path`, `.test_build_waits_for_tar_extraction_to_finish`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `CiscoSoftwareClient` connect `CiscoDownloadError` to `create_job`, `app.py`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `CiscoDownloadError` (e.g. with `cisco_accept()` and `cisco_config()`) actually correct?**
  _`CiscoDownloadError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `inputs`, `platformProfiles`, `CONFIDENCE_LABELS` to the rest of the system?**
  _192 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.028169014084507043 - nodes in this community are weakly interconnected._
- **Should `CiscoDownloadError` be split into smaller, more focused modules?**
  _Cohesion score 0.07227891156462585 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.10048309178743961 - nodes in this community are weakly interconnected._