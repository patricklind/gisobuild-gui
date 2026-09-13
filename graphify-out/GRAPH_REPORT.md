# Graph Report - gisobuild-ui-security  (2026-09-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 195 nodes · 331 edges · 15 communities (9 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `32216bfe`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- GisoWebTests
- app.py
- log_event
- app.js
- patch
- rehearse.py
- build-giso.sh
- platform_validation.py
- BuildScriptTests
- e2e_real_iso.py
- coord.sh script
- worktree.sh
- Path

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 62 edges
2. `log_event()` - 12 edges
3. `enforce_archive_policy()` - 10 edges
4. `create_job()` - 10 edges
5. `api()` - 9 edges
6. `archive_giso_artifacts_and_cleanup()` - 7 edges
7. `append_activity()` - 7 edges
8. `append_log()` - 7 edges
9. `persist_job()` - 7 edges
10. `run_job()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `build_command()` --calls--> `validate_platform_options()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/platform_validation.py
- `main()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/maintenance.py → giso-webui/app.py
- `run()` --calls--> `execute()`  [EXTRACTED]
  staging/rehearse.py → staging/xr_simulator.py

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 1 - "app.py"
Cohesion: 0.09
Nodes (40): before_request, errorhandler, get, activity(), archive_checksums(), archive_download(), archive_giso_artifacts_and_cleanup(), archive_list() (+32 more)

### Community 2 - "log_event"
Cohesion: 0.13
Nodes (27): after_request, delete, append_activity(), append_log(), archive_delete(), cancel_job(), cancel_upload(), cleanup() (+19 more)

### Community 3 - "app.js"
Cohesion: 0.19
Nodes (21): api(), checksumRow(), copyText(), drop, fileRow(), health(), inputs, lines() (+13 more)

### Community 5 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 6 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 7 - "platform_validation.py"
Cohesion: 0.60
Nodes (4): infer_platform(), normalize_platform(), Platform-aware validation for Cisco IOS XR GISO build options., validate_platform_options()

### Community 10 - "e2e_real_iso.py"
Cohesion: 0.50
Nodes (4): Path, Upload a licensed XR ISO and verify real ISO plus USB build artifacts., request(), upload_path()

### Community 11 - "coord.sh script"
Cohesion: 0.83
Nodes (3): coord.sh script, slug(), usage()

### Community 12 - "worktree.sh"
Cohesion: 0.83
Nodes (3): worktree.sh script, usage(), validate()

## Knowledge Gaps
- **2 isolated node(s):** `drop`, `inputs`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 71 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `.upload`, `patch`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Why does `enforce_archive_policy()` connect `app.py` to `log_event`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Why does `log_event()` connect `log_event` to `app.py`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09080841638981174 - nodes in this community are weakly interconnected._
- **Should `log_event` be split into smaller, more focused modules?**
  _Cohesion score 0.12535612535612536 - nodes in this community are weakly interconnected._