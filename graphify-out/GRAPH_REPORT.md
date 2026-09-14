# Graph Report - gisobuild-full-review-3  (2026-09-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 446 nodes · 763 edges · 24 communities (16 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 21 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b4473428`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- GisoWebTests
- CiscoDownloadError
- docs/README.md
- app.js
- Cisco IOS XR Golden ISO Build and Upgrade Guide
- validate_smu_selection
- patch
- Architecture Review
- AGENTS.md
- e2e_real_iso.py
- IOS XR GISO Web UI
- BuildScriptTests
- Cisco IOS XR GISO Builder
- rehearse.py
- build-giso.sh
- Release notes — v1.0.0
- coord.sh script
- worktree.sh
- dict

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 84 edges
2. `CiscoDownloadError` - 21 edges
3. `CiscoSoftwareClient` - 19 edges
4. `validate_smu_selection()` - 15 edges
5. `log_event()` - 14 edges
6. `CiscoDownloadTests` - 13 edges
7. `api()` - 13 edges
8. `Cisco IOS XR Golden ISO Build and Upgrade Guide` - 13 edges
9. `PlatformCompatibilityTests` - 11 edges
10. `create_job()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `cisco_accept()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_config()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_download_start()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_search()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `extract_cisco_archive()` --calls--> `CiscoDownloadError`  [EXTRACTED]
  giso-webui/app.py → giso-webui/cisco_download.py

## Import Cycles
- None detected.

## Communities (24 total, 4 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.06
Nodes (87): after_request, before_request, delete, errorhandler, Exception, get, active_rpm_names(), activity() (+79 more)

### Community 2 - "CiscoDownloadError"
Cohesion: 0.07
Nodes (10): CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, Cisco Automated Software Distribution client with strict download controls., Safe error suitable for returning to the local UI., Read a secret from NAME_FILE first, then NAME, without logging either. (+2 more)

### Community 3 - "docs/README.md"
Cohesion: 0.07
Nodes (29): Contributing, Coordination and branches, Local verification, Back up and restore state, Decommission, Failure handling, Logs and capacity, Operations runbook (+21 more)

### Community 4 - "app.js"
Cohesion: 0.12
Nodes (34): api(), applySmuRecommendation(), checkCompatibility(), checksumRow(), compatibilityList(), compatibilityMetric(), copyText(), drop (+26 more)

### Community 5 - "Cisco IOS XR Golden ISO Build and Upgrade Guide"
Cohesion: 0.08
Nodes (25): 1. Determine the platform and install architecture, 2. Validate the supported upgrade path, 3. Prepare the build inputs, 4. Build the GISO, 5. Validate the build output, 6. Prepare the router and change window, 7. Install the GISO, 8. Post-upgrade validation (+17 more)

### Community 6 - "validate_smu_selection"
Cohesion: 0.17
Nodes (10): check_upgrade_matrix(), infer_platform(), normalize_platform(), Platform-aware validation for Cisco IOS XR GISO build options., Select every deterministic platform/release match for upstream dependency…, Check deterministic filename compatibility before upstream dependency…, recommend_smu_selection(), validate_platform_options() (+2 more)

### Community 8 - "Architecture Review"
Cohesion: 0.13
Nodes (14): Architecture Review, Data lifecycle, High: Docker socket is a host-administration boundary, Low: The Cisco build image identity is mutable, Medium: Persistent volumes are a single point of failure, Medium: Running builds cannot resume after a web-service restart, Resolved: archive cleanup is independent of web traffic, Resolved: container health reflects required local dependencies (+6 more)

### Community 9 - "AGENTS.md"
Cohesion: 0.18
Nodes (7): Gotchas, Hard rules, Parallel work — do this first, Project overview, Required verification, Module coordination board, Parallel work with Git worktrees

### Community 10 - "e2e_real_iso.py"
Cohesion: 0.31
Nodes (10): ArgumentParser, Namespace, main(), parse_args(), Path, Upload a licensed XR ISO and verify real ISO plus USB build artifacts., Upload one file and return the server-assigned path., request() (+2 more)

### Community 11 - "IOS XR GISO Web UI"
Cohesion: 0.18
Nodes (11): Build workflow, Configuration, Data lifecycle, IOS XR GISO Web UI, Optional Cisco software download, Requirements, Security and disclaimer, Start (+3 more)

### Community 13 - "Cisco IOS XR GISO Builder"
Cohesion: 0.20
Nodes (10): Cisco IOS XR GISO Builder, Components, License, Operational limitations, Quick start, Real ISO/USB acceptance test, Requirements, Security (+2 more)

### Community 14 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 15 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 17 - "Release notes — v1.0.0"
Cohesion: 0.40
Nodes (4): Acceptance evidence, Highlights, Release notes — v1.0.0, Safety

### Community 18 - "coord.sh script"
Cohesion: 0.83
Nodes (3): coord.sh script, slug(), usage()

### Community 19 - "worktree.sh"
Cohesion: 0.83
Nodes (3): worktree.sh script, usage(), validate()

## Knowledge Gaps
- **86 isolated node(s):** `Build workflow`, `Configuration`, `Data lifecycle`, `Optional Cisco software download`, `Requirements` (+81 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 192 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `app.py`, `patch`, `.upload`, `dict`, `.test_build_waits_for_tar_extraction_to_finish`, `.test_failed_multi_file_cisco_download_removes_partial_results`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Why does `CiscoDownloadError` connect `CiscoDownloadError` to `app.py`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `CiscoDownloadError` (e.g. with `cisco_accept()` and `cisco_config()`) actually correct?**
  _`CiscoDownloadError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Build workflow`, `Configuration`, `Data lifecycle` to the rest of the system?**
  _86 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.056654456654456654 - nodes in this community are weakly interconnected._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.037037037037037035 - nodes in this community are weakly interconnected._
- **Should `CiscoDownloadError` be split into smaller, more focused modules?**
  _Cohesion score 0.07446808510638298 - nodes in this community are weakly interconnected._