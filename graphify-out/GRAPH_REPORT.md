# Graph Report - gisobuild-cisco-download  (2026-09-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 286 nodes · 545 edges · 18 communities (10 shown, 5 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1e3e4796`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- GisoWebTests
- log_event
- app.js
- CiscoDownloadError
- CiscoDownloadTests
- patch
- validate_smu_selection
- BuildScriptTests
- rehearse.py
- build-giso.sh
- e2e_real_iso.py
- coord.sh script
- worktree.sh
- dict

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 70 edges
2. `CiscoDownloadError` - 21 edges
3. `CiscoSoftwareClient` - 19 edges
4. `log_event()` - 14 edges
5. `CiscoDownloadTests` - 13 edges
6. `api()` - 12 edges
7. `create_job()` - 11 edges
8. `enforce_archive_policy()` - 10 edges
9. `cisco_search()` - 10 edges
10. `run_cisco_download()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `cisco_accept()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_config()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_download_start()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `cisco_search()` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/app.py → giso-webui/cisco_download.py
- `CiscoDownloadTests` --uses--> `CiscoDownloadError`  [INFERRED]
  giso-webui/tests/test_cisco_download.py → giso-webui/cisco_download.py

## Import Cycles
- None detected.

## Communities (18 total, 5 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.08
Nodes (54): before_request, delete, errorhandler, get, activity(), append_log(), archive_checksums(), archive_delete() (+46 more)

### Community 2 - "log_event"
Cohesion: 0.13
Nodes (31): after_request, Exception, append_activity(), cancel_upload(), cisco_accept(), cisco_client(), cisco_download_running(), cisco_download_start() (+23 more)

### Community 3 - "app.js"
Cohesion: 0.16
Nodes (27): api(), checkCompatibility(), checksumRow(), copyText(), drop, fileRow(), health(), inputs (+19 more)

### Community 4 - "CiscoDownloadError"
Cohesion: 0.16
Nodes (9): CiscoDownloadError, CiscoSoftwareClient, DownloadResult, _NoRedirect, Path, Cisco Automated Software Distribution client with strict download controls., Safe error suitable for returning to the local UI., Read a secret from NAME_FILE first, then NAME, without logging either. (+1 more)

### Community 7 - "validate_smu_selection"
Cohesion: 0.25
Nodes (8): check_upgrade_matrix(), infer_platform(), normalize_platform(), Platform-aware validation for Cisco IOS XR GISO build options., Check deterministic filename compatibility before upstream dependency…, validate_platform_options(), validate_smu_selection(), PlatformCompatibilityTests

### Community 9 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 10 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 12 - "e2e_real_iso.py"
Cohesion: 0.50
Nodes (4): Path, Upload a licensed XR ISO and verify real ISO plus USB build artifacts., request(), upload_path()

### Community 13 - "coord.sh script"
Cohesion: 0.83
Nodes (3): coord.sh script, slug(), usage()

### Community 14 - "worktree.sh"
Cohesion: 0.83
Nodes (3): worktree.sh script, usage(), validate()

## Knowledge Gaps
- **2 isolated node(s):** `drop`, `inputs`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 94 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CiscoSoftwareClient` connect `CiscoDownloadError` to `app.py`, `log_event`, `CiscoDownloadTests`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `GisoWebTests` connect `GisoWebTests` to `.test_build_waits_for_tar_extraction_to_finish`, `.upload`, `patch`, `dict`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `CiscoDownloadTests` connect `CiscoDownloadTests` to `CiscoDownloadError`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `CiscoDownloadError` (e.g. with `cisco_accept()` and `cisco_config()`) actually correct?**
  _`CiscoDownloadError` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07532467532467532 - nodes in this community are weakly interconnected._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.043478260869565216 - nodes in this community are weakly interconnected._