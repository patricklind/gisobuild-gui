# Graph Report - gisobuild-full-review-2  (2026-09-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 185 nodes · 304 edges · 15 communities (9 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7d1c8b4b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- GisoWebTests
- app.js
- log_event
- patch
- build_command
- rehearse.py
- build-giso.sh
- BuildScriptTests
- e2e_real_iso.py
- coord.sh script
- worktree.sh
- Path

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 57 edges
2. `enforce_archive_policy()` - 10 edges
3. `log_event()` - 10 edges
4. `api()` - 8 edges
5. `create_job()` - 8 edges
6. `loadArchive()` - 7 edges
7. `archive_giso_artifacts_and_cleanup()` - 7 edges
8. `persist_job()` - 7 edges
9. `run_job()` - 7 edges
10. `upload_init()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/maintenance.py → giso-webui/app.py
- `build_command()` --calls--> `validate_platform_options()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/platform_validation.py
- `run()` --calls--> `execute()`  [EXTRACTED]
  staging/rehearse.py → staging/xr_simulator.py

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.09
Nodes (40): before_request, delete, errorhandler, get, archive_checksums(), archive_delete(), archive_download(), archive_list() (+32 more)

### Community 2 - "app.js"
Cohesion: 0.19
Nodes (20): api(), checksumRow(), copyText(), drop, fileRow(), health(), inputs, lines() (+12 more)

### Community 3 - "log_event"
Cohesion: 0.16
Nodes (19): after_request, append_log(), archive_giso_artifacts_and_cleanup(), cancel_job(), cleanup(), create_job(), docker_build_running(), giso_artifact_candidates() (+11 more)

### Community 5 - "build_command"
Cohesion: 0.28
Nodes (8): build_command(), child_mount_args(), file_sha256(), Share only required storage with the build container, never docker.sock., infer_platform(), normalize_platform(), Platform-aware validation for Cisco IOS XR GISO build options., validate_platform_options()

### Community 6 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 7 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

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
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 67 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `.upload`, `patch`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `enforce_archive_policy()` connect `app.py` to `log_event`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **Why does `log_event()` connect `log_event` to `app.py`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08748615725359911 - nodes in this community are weakly interconnected._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.047619047619047616 - nodes in this community are weakly interconnected._