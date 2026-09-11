# Graph Report - project  (2026-09-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 116 nodes · 195 edges · 14 communities (9 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- GisoWebTests
- app.js
- Path
- app.py
- create_job
- run_job
- patch
- build-giso.sh
- build_command
- errorhandler
- discover
- security_headers
- upload_chunk

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 36 edges
2. `api()` - 7 edges
3. `loadArchive()` - 7 edges
4. `enforce_archive_policy()` - 7 edges
5. `create_job()` - 7 edges
6. `archive_giso_artifacts_and_cleanup()` - 6 edges
7. `build_command()` - 6 edges
8. `loadInputs()` - 5 edges
9. `poll()` - 5 edges
10. `renderInputs()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `create_job()` --indirect_call--> `run_job()`  [INFERRED]
  giso-webui/app.py → giso-webui/app.py  _Bridges community 4 → community 5_
- `discover()` --calls--> `Path`  [EXTRACTED]
  giso-webui/app.py →   _Bridges community 11 → community 2_
- `inputs()` --references--> `get`  [EXTRACTED]
  giso-webui/app.py →   _Bridges community 11 → community 3_
- `run_job()` --calls--> `archive_giso_artifacts_and_cleanup()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/app.py  _Bridges community 2 → community 5_
- `archive_list()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/app.py → giso-webui/app.py  _Bridges community 2 → community 3_

## Import Cycles
- None detected.

## Communities (14 total, 4 thin omitted)

### Community 1 - "app.js"
Cohesion: 0.22
Nodes (17): api(), checksumRow(), drop, fileRow(), health(), inputs, loadArchive(), loadInputs() (+9 more)

### Community 2 - "Path"
Cohesion: 0.15
Nodes (13): before_request, archive_giso_artifacts_and_cleanup(), archive_size(), archive_timestamp(), enforce_archive_policy(), extraction_path(), file_sha256(), Remove expired archive jobs, then oldest jobs until the archive fits its quota. (+5 more)

### Community 3 - "app.py"
Cohesion: 0.33
Nodes (10): get, archive_checksums(), archive_download(), archive_list(), download(), file_checksums(), get_job(), health() (+2 more)

### Community 4 - "create_job"
Cohesion: 0.43
Nodes (7): cleanup(), create_job(), docker_build_running(), json_object(), upload_init(), validate_build_payload(), post

### Community 5 - "run_job"
Cohesion: 0.33
Nodes (6): delete, append_log(), archive_delete(), cancel_job(), delete_upload(), run_job()

### Community 7 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 8 - "build_command"
Cohesion: 0.50
Nodes (4): build_command(), child_mount_args(), Share only required storage with the build container, never docker.sock., safe_data_path()

### Community 10 - "errorhandler"
Cohesion: 0.67
Nodes (3): errorhandler, bad_request(), request_too_large()

### Community 11 - "discover"
Cohesion: 0.67
Nodes (3): discover(), inputs(), rel_data()

## Knowledge Gaps
- **2 isolated node(s):** `drop`, `inputs`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 36 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `.upload`, `Path`, `patch`?**
  _High betweenness centrality (0.350) - this node is a cross-community bridge._
- **Why does `archive_giso_artifacts_and_cleanup()` connect `Path` to `app.py`, `run_job`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `build_command()` connect `build_command` to `Path`, `app.py`, `create_job`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Path` (e.g. with `.setUp()` and `.test_archive_delete_rejects_path_traversal()`) actually correct?**
  _`Path` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._