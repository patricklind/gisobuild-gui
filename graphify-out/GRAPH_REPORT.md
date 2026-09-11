# Graph Report - project  (2026-09-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 134 nodes · 228 edges · 15 communities (10 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- GisoWebTests
- app.js
- app.py
- enforce_archive_policy
- Path
- patch
- create_job
- archive_giso_artifacts_and_cleanup
- build-giso.sh
- safe_data_path
- persist_job
- errorhandler
- security_headers
- upload_chunk

## God Nodes (most connected - your core abstractions)
1. `GisoWebTests` - 45 edges
2. `enforce_archive_policy()` - 9 edges
3. `create_job()` - 8 edges
4. `api()` - 7 edges
5. `loadArchive()` - 7 edges
6. `persist_job()` - 7 edges
7. `archive_giso_artifacts_and_cleanup()` - 6 edges
8. `build_command()` - 6 edges
9. `loadInputs()` - 5 edges
10. `poll()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `enforce_archive_policy()`  [EXTRACTED]
  giso-webui/maintenance.py → giso-webui/app.py

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 1 - "app.js"
Cohesion: 0.20
Nodes (17): api(), checksumRow(), drop, fileRow(), health(), inputs, loadArchive(), loadInputs() (+9 more)

### Community 2 - "app.py"
Cohesion: 0.30
Nodes (10): get, archive_checksums(), archive_download(), download(), file_checksums(), get_job(), health(), index() (+2 more)

### Community 3 - "enforce_archive_policy"
Cohesion: 0.20
Nodes (10): before_request, archive_list(), archive_size(), archive_timestamp(), enforce_archive_policy(), initialize_job_store(), Remove expired archive jobs, then oldest jobs until the archive fits its quota., Create the job store and restore safe job history once per process. (+2 more)

### Community 4 - "Path"
Cohesion: 0.24
Nodes (7): discover(), extraction_path(), inputs(), rel_data(), upload_complete(), BuildScriptTests, Path

### Community 6 - "create_job"
Cohesion: 0.43
Nodes (7): cleanup(), create_job(), docker_build_running(), json_object(), upload_init(), validate_build_payload(), post

### Community 7 - "archive_giso_artifacts_and_cleanup"
Cohesion: 0.33
Nodes (6): archive_giso_artifacts_and_cleanup(), build_command(), child_mount_args(), file_sha256(), Archive verified Golden ISO and USB boot files, then remove build inputs/output., Share only required storage with the build container, never docker.sock.

### Community 8 - "build-giso.sh"
Cohesion: 0.70
Nodes (4): die(), md5_file(), build-giso.sh script, usage()

### Community 10 - "safe_data_path"
Cohesion: 0.50
Nodes (4): delete, archive_delete(), delete_upload(), safe_data_path()

### Community 11 - "persist_job"
Cohesion: 0.83
Nodes (4): append_log(), cancel_job(), persist_job(), run_job()

### Community 12 - "errorhandler"
Cohesion: 0.67
Nodes (3): errorhandler, bad_request(), request_too_large()

## Knowledge Gaps
- **2 isolated node(s):** `drop`, `inputs`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 46 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GisoWebTests` connect `GisoWebTests` to `.upload`, `Path`, `patch`?**
  _High betweenness centrality (0.392) - this node is a cross-community bridge._
- **Why does `archive_giso_artifacts_and_cleanup()` connect `archive_giso_artifacts_and_cleanup` to `persist_job`, `app.py`, `enforce_archive_policy`, `Path`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `build_command()` connect `archive_giso_artifacts_and_cleanup` to `app.py`, `safe_data_path`, `Path`, `create_job`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Path` (e.g. with `.setUp()` and `.test_archive_delete_rejects_path_traversal()`) actually correct?**
  _`Path` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `drop`, `inputs` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GisoWebTests` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._