# Operations runbook

This runbook covers the local, single-user Docker deployment. The service is
not designed for an untrusted network or multiple users.

## Start and verify

```bash
cp giso-webui/.env.example giso-webui/.env
docker compose -f giso-webui/compose.yaml up --build -d
docker compose -f giso-webui/compose.yaml ps
curl --fail http://127.0.0.1:8080/api/health
curl --fail http://127.0.0.1:8080/api/ready
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

Use `--follow` to watch upload progress, request IDs, build phases, redacted
build-output lines, failures, and cleanup totals in real time. The Web UI's
technical-details panel reads the same persistent activity stream for upload,
extraction, build, and cleanup events. Cisco artifact names are replaced with
`[artifact]`; request payloads and configuration content are omitted.

`/api/health` reports only whether the process itself is alive (always `200`
once the server is up) and is what the container `HEALTHCHECK` and an
orchestrator's restart policy should watch. `/api/ready` returns HTTP 503 when
Docker, required storage mounts, the state database, free disk space, or the
local `gisobuild` tool entry point is unavailable — use it to decide whether
to route traffic or investigate a degraded-but-alive container, not whether to
restart it. Its `self_test` object names each startup check (gisobuild, runner
binary, job store schema, writable volumes, configuration, free space, CPU
architecture, and `gisobuild_source` in the self-contained image) with a short
reason. The default deployment needs no registry: gisobuild is part of the
image. With `compose.socket.yaml`, builder-image pulls are bounded by
`GISO_PULL_TIMEOUT_SECONDS` (600 seconds by default); if the pull fails or times
out, a builder image already on the host is used and the job log says so (the
default reference is digest-pinned, so it is identical). Without a cached image
the job fails and uploaded inputs are preserved.

The application accepts one build at a time. A separate maintenance service
removes complete archives older than 30 days and then removes the oldest
complete archives until combined ISO/USB use is at or below 50 GiB. Both values
are configurable in `.env`. Incomplete upload sessions survive a service
restart and can be resumed by selecting the same file again; they expire after
24 hours by default (`UPLOAD_SESSION_TTL=86400`), which also removes their
partial files. A session idle for `UPLOAD_ACTIVE_SECONDS` (600) no longer blocks
builds or cleanup.

The commands above use the default deployment, which needs no `.gisobuild-tool`
checkout and no Docker socket. Its `/api/ready` self-test also re-checks the
bundled gisobuild against the image's pinned SHA-256 manifest. A failed or
cancelled build's work files and extracted image are removed automatically
(logs are kept), and so are those of a build interrupted by a restart.

The socket deployment is operated the same way with
`-f giso-webui/compose.socket.yaml`; it also needs the `.gisobuild-tool`
checkout. Both use the same volumes, so run only one at a time.

Upgrading from a version where `compose.yaml` was the socket deployment: stop
the service, update the checkout, and start it again with the same commands.
The volumes are unchanged, so uploads, job history and archives are kept; the
Docker socket, the `.gisobuild-tool` mount and `GISO_IMAGE` are no longer used.
Keep the old behaviour with `-f giso-webui/compose.socket.yaml`.

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

## Running behind a reverse proxy or tunnel

The service expects to be reached directly on localhost. When a proxy, tunnel
or CDN is in front of it (for example Cloudflare):

- Add the hostname to `ALLOWED_HOSTS`, exactly, with no wildcard.
- Static files are versioned per build (`/static/app.js?v=<revision>`), so an
  upgrade always produces new URLs. Do not rewrite or strip that query string
  in the proxy, or browsers will keep the previous page against the new API.
- A proxy error such as `502 Bad gateway` means the proxy could not reach this
  service; the page reports it as a status. Check the container and
  `/api/health` on the host itself before looking at the application.
- `/api/health` only says the process is alive; `/api/ready` says whether it
  can build. Point the proxy's own health probe at `/api/health`.

## Failure handling

| Symptom | Check | Safe action |
| --- | --- | --- |
| `/api/ready` fails | Its `self_test` details, `gisobuild_source` (the bundled gisobuild no longer matches its pinned SHA-256 manifest - rebuild or pull the image again), `docker info` (socket deployment), gisobuild presence, mounted storage, the state database, free disk space, and web logs | Restore the failed dependency; do not expose the service remotely |
| Build plan says the job store cannot be used | Web log `job_store_schema_unsupported` | The state volume was written by a newer release; run that release or restore a matching backup |
| Plan blocked: SYS_CHROOT | Compose `cap_add` | Add `SYS_CHROOT`; gisobuild's eXR engine needs it |
| `/api/health` fails | Container/process state and web logs | The process itself is down or unresponsive; restart the service |
| Build will not start | Active jobs/uploads, and with the socket deployment `giso-build-*` containers | Wait, cancel the active upload, or investigate the surviving build container before cleanup |
| Job is `interrupted` | Saved log and Docker container list | Reconcile the old container; do not assume the build failed cleanly |
| Upload rejected | Extension, configured limits, and free space | Correct the input or increase a reviewed limit |
| Upload paused | Network and service availability | Select the same file again; it resumes from the bytes already received |
| No USB artifact | Platform matrix and build log | Use the documented platform recovery method |
| Archive removed | Age and combined archive size | Restore an approved external backup; retention deletion is intentional |

The **Clear workspace files** button deletes all uploads, partial uploads, build
work, and raw output after confirming that no upload or build is active. It
preserves the verified GISO Archive and persisted job history, but removes stale
raw-output download references from failed jobs. The confirmation reports both
deleted top-level items and cleared links.

## Decommission

Export required evidence and artifacts first. `docker compose down -v` deletes
the project's Docker volumes and is not recoverable through this application.
Never run it as routine cleanup.
