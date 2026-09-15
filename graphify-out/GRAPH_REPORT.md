# Graph Report - gisobuild-phase0-lifecycle  (2026-09-15)

## Corpus Check
- 46 files · ~37,966 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 13 file(s) not represented in the graph (top: (none) 8, .css 4, .example 1)

## Summary
- 601 nodes · 933 edges · 46 communities (30 shown, 8 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6bab6e2b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- GisoWebTests
- CiscoDownloadError
- app.js
- Cisco IOS XR Golden ISO Build and Upgrade Guide
- validate_smu_selection
- patch
- System architecture
- BuildScriptTests
- AGENTS.md
- e2e_real_iso.py
- IOS XR GISO Web UI
- Cisco IOS XR GISO Builder
- docs/README.md
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
- CONTRIBUTING.md
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
- staging/README.md

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 89 edges
2. `CiscoDownloadError` - 21 edges
3. `CiscoSoftwareClient` - 19 edges
4. `validate_smu_selection()` - 15 edges
5. `log_event()` - 14 edges
6. `TODO — Automation, Inventory & BuildPlan` - 14 edges
7. `api()` - 13 edges
8. `CiscoDownloadTests` - 13 edges
9. `PlatformCompatibilityTests` - 13 edges
10. `Cisco IOS XR Golden ISO Build and Upgrade Guide` - 13 edges

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

## Communities (46 total, 8 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.05
Nodes (94): after_request, before_request, delete, errorhandler, Exception, get, active_rpm_names(), activity() (+86 more)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.07
Nodes (12): cisco_config(), CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, RuntimeError, Cisco Automated Software Distribution client with strict download controls. (+4 more)

### Community 3 - "app.js"
Cohesion: 0.11
Nodes (40): api(), applySmuRecommendation(), checkCompatibility(), checksumRow(), compatibilityList(), compatibilityMetric(), copyText(), drop (+32 more)

### Community 4 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 5 - "validate_smu_selection"
Cohesion: 0.17
Nodes (10): check_upgrade_matrix(), infer_platform(), normalize_platform(), Platform-aware validation for Cisco IOS XR GISO build options., Select every deterministic platform/release match for upstream dependency…, Check deterministic filename compatibility before upstream dependency…, recommend_smu_selection(), validate_platform_options() (+2 more)

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

### Community 26 - "CONTRIBUTING.md"
Cohesion: 0.50
Nodes (3): Contributing, Coordination and branches, Local verification

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
Cohesion: 0.18
Nodes (10): Capability-driven UI, Hardware aliases, LNT, Representative eXR families, Required capability model, Scope, Tests, TODO — Upstream Platform & Capability Support (+2 more)

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

## Knowledge Gaps
- **182 isolated node(s):** `inputs`, `platformProfiles`, `drop`, `GitHub Copilot repository instructions`, `Mandatory project roadmap and Graphify — read before doing anything` (+177 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 315 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `patch`, `.test_run_job_honors_cancellation_during_image_pull`, `.upload`, `dict`, `.test_build_waits_for_tar_extraction_to_finish`, `.test_failed_multi_file_cisco_download_removes_partial_results`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `CiscoSoftwareClient` connect `CiscoDownloadError` to `app.py`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `Cisco IOS XR Golden ISO Build and Upgrade Guide` connect `Cisco IOS XR Golden ISO Build and Upgrade Guide` to `docs/README.md`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `CiscoDownloadError` (e.g. with `cisco_accept()` and `cisco_config()`) actually correct?**
  _`CiscoDownloadError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `inputs`, `platformProfiles`, `drop` to the rest of the system?**
  _182 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.053479381443298966 - nodes in this community are weakly interconnected._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.03508771929824561 - nodes in this community are weakly interconnected._