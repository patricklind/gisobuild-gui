# Graph Report - project  (2026-09-12)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 154 nodes · 257 edges · 11 communities (7 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- app.py
- GisoWebTests
- app.js
- Path
- patch
- create_job
- rehearse.py
- build-giso.sh
- platform_validation.py
- e2e_real_iso.py

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 48 edges
2. `enforce_archive_policy()` - 9 edges
3. `api()` - 8 edges
4. `create_job()` - 8 edges
5. `persist_job()` - 7 edges
6. `loadArchive()` - 7 edges
7. `build_command()` - 7 edges
8. `archive_giso_artifacts_and_cleanup()` - 6 edges
9. `run_job()` - 5 edges
10. `loadInputs()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/maintenance.py → giso-webui/app.py
- `build_command()` --calls--> `validate_platform_options()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/platform_validation.py
- `run()` --calls--> `execute()`  [EXTRACTED]
  staging/rehearse.py → staging/xr_simulator.py

## Import Cycles
- None detected.

## Communities (11 total, 3 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.10
Nodes (34): after_request, before_request, delete, errorhandler, get, append_log(), archive_checksums(), archive_delete() (+26 more)

### Community 2 - "app.js"
Cohesion: 0.19
Nodes (18): api(), checksumRow(), drop, fileRow(), health(), inputs, loadArchive(), loadInputs() (+10 more)

### Community 3 - "Path"
Cohesion: 0.14
Nodes (15): archive_giso_artifacts_and_cleanup(), archive_size(), archive_timestamp(), build_command(), child_mount_args(), enforce_archive_policy(), extraction_path(), file_sha256() (+7 more)

### Community 5 - "create_job"
Cohesion: 0.43
Nodes (7): cleanup(), create_job(), docker_build_running(), json_object(), upload_init(), validate_build_payload(), post

### Community 6 - "rehearse.py"
Cohesion: 0.43
Nodes (5): Verify upgrade and rollback state transitions against the XR simulator., run(), execute(), main(), Non-networked IOS XR transaction simulator for rehearsal only.

### Community 7 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 8 - "platform_validation.py"
Cohesion: 0.60
Nodes (4): infer_platform(), normalize_platform(), Platform-aware validation for Cisco IOS XR GISO build options., validate_platform_options()

## Knowledge Gaps
- **2 isolated node(s):** `drop`, `inputs`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 52 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `.upload`, `Path`, `patch`?**
  _High betweenness centrality (0.342) - this node is a cross-community bridge._
- **Why does `build_command()` connect `Path` to `app.py`, `platform_validation.py`, `create_job`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `archive_giso_artifacts_and_cleanup()` connect `Path` to `app.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Path` (e.g. with `.setUp()` and `.test_archive_delete_rejects_path_traversal()`) actually correct?**
  _`Path` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09682539682539683 - nodes in this community are weakly interconnected._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.058823529411764705 - nodes in this community are weakly interconnected._