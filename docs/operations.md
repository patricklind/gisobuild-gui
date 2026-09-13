# Operations runbook

This runbook covers the local, single-user Docker deployment. The service is
not designed for an untrusted network or multiple users.

## Start and verify

```bash
git clone --depth 1 https://github.com/ios-xr/gisobuild.git .gisobuild-tool
cp giso-webui/.env.example giso-webui/.env
docker compose -f giso-webui/compose.yaml up --build -d
docker compose -f giso-webui/compose.yaml ps
curl --fail http://127.0.0.1:8080/api/health
```

Expected services:

- `giso-webui`: healthy and published only on `127.0.0.1:8080` by default.
- `archive-maintenance`: running without a published port.

## Logs and capacity

```bash
docker compose -f giso-webui/compose.yaml logs --tail=200 giso-webui
docker compose -f giso-webui/compose.yaml logs --tail=100 archive-maintenance
docker compose -f giso-webui/compose.yaml exec giso-webui \
  df -h /uploads /output /archive /work /state
```

Use `--follow` to watch uploads, request IDs, build phases, failures, and cleanup
totals in real time. Container event logs intentionally omit Cisco filenames,
request payloads, configuration content, and raw build output.

The Web UI health check returns HTTP 503 when Docker, required storage mounts,
or the local `gisobuild` tool entry point is unavailable. Image pulls are
bounded by `GISO_PULL_TIMEOUT_SECONDS` (600 seconds by default); a timeout marks
the job failed and preserves uploaded inputs for diagnosis or retry.

The application accepts one build at a time. A separate maintenance service
removes complete archives older than 30 days and then removes the oldest
complete archives until combined ISO/USB use is at or below 50 GiB. Both values
are configurable in `.env`. Incomplete upload sessions expire after 24 hours by
default (`UPLOAD_SESSION_TTL=86400`), which also removes their partial files.

## Stop and upgrade

Do not recreate services during an active build.

```bash
docker compose -f giso-webui/compose.yaml down
git pull --ff-only
docker compose -f giso-webui/compose.yaml up --build -d
```

`down` preserves named volumes. Never add `-v` unless permanent deletion of all
uploads, job history, work files, and archived artifacts is intentional.

## Back up and restore state

Completed artifacts contain licensed Cisco software. Copy them only to storage
approved for that content. Stop the application before a consistent backup:

```bash
docker compose -f giso-webui/compose.yaml down
GISO_BACKUP_DIR=/absolute/path/to/approved-backup
mkdir -p "$GISO_BACKUP_DIR"
docker run --rm \
  -v giso-webui_giso-state:/source:ro \
  -v "$GISO_BACKUP_DIR":/backup \
  alpine:3.22 tar -czf /backup/giso-state.tgz -C /source .
```

Restore only into an empty, stopped state volume:

```bash
GISO_BACKUP_DIR=/absolute/path/to/approved-backup
docker run --rm \
  -v giso-webui_giso-state:/target \
  -v "$GISO_BACKUP_DIR":/backup:ro \
  alpine:3.22 tar -xzf /backup/giso-state.tgz -C /target
docker compose -f giso-webui/compose.yaml up -d
```

Back up `giso-archive` with the same pattern only when the destination is
licensed and protected appropriately. Test restore procedures periodically.

## Failure handling

| Symptom | Check | Safe action |
| --- | --- | --- |
| Health endpoint fails | `docker info`, `/tool/src/gisobuild.py`, mounted storage, and web logs | Restore the failed dependency; do not expose the service remotely |
| Build will not start | Active jobs/uploads and `giso-build-*` containers | Wait, cancel the active upload, or investigate the surviving build container before cleanup |
| Job is `interrupted` | Saved log and Docker container list | Reconcile the old container; do not assume the build failed cleanly |
| Upload rejected | Extension, configured limits, and free space | Correct the input or increase a reviewed limit |
| No USB artifact | Platform matrix and build log | Use the documented platform recovery method |
| Archive removed | Age and combined archive size | Restore an approved external backup; retention deletion is intentional |

The **Clear workspace files** button deletes all uploads, partial uploads, build
work, and raw output after confirming that no upload or build is active. It
preserves the verified GISO Archive and persisted job history.

## Decommission

Export required evidence and artifacts first. `docker compose down -v` deletes
the project's Docker volumes and is not recoverable through this application.
Never run it as routine cleanup.
