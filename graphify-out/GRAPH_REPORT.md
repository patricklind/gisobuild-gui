# Graph Report - project  (2026-09-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 123 nodes · 205 edges · 8 communities (5 shown, 2 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- GisoWebTests
- app.py
- Path
- app.js
- patch
- create_job
- build-giso.sh

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 41 edges
2. `enforce_archive_policy()` - 7 edges
3. `api()` - 7 edges
4. `loadArchive()` - 7 edges
5. `create_job()` - 7 edges
6. `archive_giso_artifacts_and_cleanup()` - 6 edges
7. `build_command()` - 6 edges
8. `loadInputs()` - 5 edges
9. `poll()` - 5 edges
10. `renderInputs()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `create_job()` --indirect_call--> `run_job()`  [INFERRED]
  giso-webui/app.py → giso-webui/app.py  _Bridges community 1 → community 5_
- `archive_list()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/app.py  _Bridges community 1 → community 2_
- `create_job()` --calls--> `build_command()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/app.py  _Bridges community 2 → community 5_

## Import Cycles
- None detected.

## Communities (8 total, 2 thin omitted)

### Community 1 - "app.py"
Cohesion: 0.11
Nodes (27): after_request, delete, errorhandler, get, append_log(), archive_checksums(), archive_delete(), archive_download() (+19 more)

### Community 2 - "Path"
Cohesion: 0.13
Nodes (16): before_request, archive_giso_artifacts_and_cleanup(), archive_size(), archive_timestamp(), build_command(), child_mount_args(), enforce_archive_policy(), extraction_path() (+8 more)

### Community 3 - "app.js"
Cohesion: 0.22
Nodes (17): api(), checksumRow(), drop, fileRow(), health(), inputs, loadArchive(), loadInputs() (+9 more)

### Community 5 - "create_job"
Cohesion: 0.43
Nodes (7): cleanup(), create_job(), docker_build_running(), json_object(), upload_init(), validate_build_payload(), post

### Community 6 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

## Knowledge Gaps
- **2 isolated node(s):** `drop`, `inputs`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 41 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `Path`, `patch`, `.upload`?**
  _High betweenness centrality (0.383) - this node is a cross-community bridge._
- **Why does `archive_giso_artifacts_and_cleanup()` connect `Path` to `app.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `build_command()` connect `Path` to `app.py`, `create_job`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Path` (e.g. with `.setUp()` and `.test_archive_delete_rejects_path_traversal()`) actually correct?**
  _`Path` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.06666666666666667 - nodes in this community are weakly interconnected._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11083743842364532 - nodes in this community are weakly interconnected._