# IOS XR GISO Web UI

A trusted, local Docker interface for building Cisco IOS XR Golden ISO (GISO)
images and optional USB boot packages with `ios-xr/gisobuild`. It provides
chunked uploads, common eXR and LNT options, live logs, checksums, downloads,
and a persistent artifact archive.

> [!CAUTION]
> The application controls Docker through `/var/run/docker.sock`, which is
> effectively administrative access to the Docker host. Keep the default
> localhost binding and do not deploy this as an untrusted or multi-user service.

## Requirements

- Docker Desktop or Docker Engine with Compose v2
- An x86_64 host, or x86_64 emulation on Apple Silicon
- Approximately 25 GB of free disk space
- A checkout of [`ios-xr/gisobuild`](https://github.com/ios-xr/gisobuild) at
  `../.gisobuild-tool`
- Properly licensed Cisco IOS XR ISO, RPM, and SMU files

The expert form requires a recognizable ISO filename or an explicit platform
family. It rejects architecture-specific option combinations before starting a
build and shows whether upstream automatic USB output is expected.

## Start

From the repository root:

```bash
git clone --depth 1 https://github.com/ios-xr/gisobuild.git .gisobuild-tool
cd giso-webui
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Open <http://127.0.0.1:8080>. The service is ready when `docker compose ps`
reports `healthy`. Check it directly with:

```bash
curl --fail http://127.0.0.1:8080/api/health
```

## Build workflow

1. Upload the base ISO and matching RPM, SMU, or configuration files.
2. Review the discovered packages and select the required build options.
3. Start the build. Only one build can run, and it starts only after every
   upload and archive extraction has completed.
4. Follow the live log until the job succeeds or fails.
5. Download the Golden ISO, optional USB ZIP, and displayed checksums.

Cisco `.tar` files are transport archives. The UI safely extracts them and
passes discovered `.rpm` files to `--pkglist`; do not select the tar file itself
as a package.

After a successful build, the application copies the Golden ISO and optional
USB package into the archive and verifies each copy with SHA-256. Only then does
it remove the build's source and working files. If no ISO is produced or archive
verification fails, sources are retained for diagnosis.

The **Clean temporary files** action removes incomplete upload fragments and
temporary work directories. It does not remove completed archives or normal
uploaded Cisco files.

## Configuration

Edit `.env` before starting Compose. Changes take effect after recreating the
container with `docker compose up -d --force-recreate`.

| Variable | Default | Purpose |
| --- | ---: | --- |
| `GISO_IMAGE` | `ciscogisobuild/cisco-xr-gisobuild:2.3.4` | Cisco build image |
| `WEB_BIND_ADDRESS` | `127.0.0.1` | Host interface exposed by Compose |
| `WEB_PORT` | `8080` | Host HTTP port |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost,giso-webui` | Accepted HTTP Host values |
| `MAX_UPLOAD_BYTES` | `8589934592` | Maximum bytes per uploaded file (8 GiB) |
| `MAX_CHUNK_BYTES` | `16777216` | Maximum request chunk size (16 MiB) |
| `MAX_EXTRACTED_BYTES` | `17179869184` | Maximum extracted tar contents (16 GiB) |
| `MAX_TAR_MEMBERS` | `10000` | Maximum files in an uploaded tar archive |
| `MAX_LOG_BYTES` | `10485760` | In-memory log limit per build (10 MiB) |
| `MAX_JOB_HISTORY` | `100` | Maximum completed or interrupted jobs retained in SQLite |
| `ARCHIVE_RETENTION_DAYS` | `30` | Maximum artifact retention period |
| `MAX_ARCHIVE_BYTES` | `53687091200` | Combined ISO and USB archive quota (50 GiB) |
| `ARCHIVE_CLEANUP_INTERVAL_SECONDS` | `3600` | Maintenance interval; minimum 60 seconds |

The `DATA_ROOT`, `OUTPUT_ROOT`, `TOOL_ROOT`, `WORK_ROOT`, `ARCHIVE_ROOT`, and `STATE_ROOT`
variables are container paths matched to Compose mounts. Change them only when
you also update the corresponding volume destinations.

## Data lifecycle

Uploads, output, archives, and working files use persistent Docker volumes. The
archive volume is named `giso-webui_giso-archive` by default. Archives expire
after 30 days, and the oldest complete job archives are deleted first whenever
the combined ISO and USB size exceeds 50 GiB.

The `archive-maintenance` container enforces retention and quota every hour even
when the UI is idle. Completed job history and bounded logs are stored in SQLite
in `giso-webui_giso-state`. If the web container restarts during a build, the
restored job is marked `interrupted`; inspect Docker and the saved log before
starting another build. Back up required artifacts outside Docker volumes before
they expire. To inspect the volumes and maintenance logs:

```bash
docker volume ls --filter name=giso-webui
docker compose exec giso-webui df -h /uploads /archive /output /work
docker compose logs --tail=100 archive-maintenance
```

## Test and verify

```bash
docker compose config -q
docker compose build giso-webui
docker compose run --rm --no-deps \
  -v "$(cd .. && pwd):/project:ro" \
  -w /project/giso-webui \
  giso-webui python -B -m unittest discover -s tests -v
```

The repository CI also runs Ruff, `pip-audit`, shell syntax validation, Compose
validation, and a production container build. A real GISO build is not part of
CI because it requires licensed Cisco inputs and substantial compute resources.

## Troubleshooting

- **Health check is failing:** Run `docker info`, then inspect
  `docker compose logs --tail=200 giso-webui`.
- **Build cannot start:** Confirm `.gisobuild-tool/src/gisobuild.py` exists and
  no container named `giso-build-*` is already running.
- **Apple Silicon build is slow:** The Cisco image runs with `linux/amd64`
  emulation; longer build times are expected.
- **Upload is rejected:** Check the file extension and the upload, extraction,
  and free-space limits in `.env`.
- **Host header is rejected:** Keep the service local or add the exact trusted
  hostname to `ALLOWED_HOSTS`; do not use a wildcard.
- **Build was interrupted by restart:** The job and log remain visible. Check
  running `giso-build-*` containers and application logs before starting again.
- **Need a clean reset:** `docker compose down` preserves volumes. Adding `-v`
  permanently deletes uploads and archives and should only be used intentionally.

## Stop

```bash
docker compose down
```

## Security and disclaimer

The web container uses a read-only root filesystem, has all Linux capabilities
dropped, and gives child build containers only the required mounts. Uploaded tar
paths, symlinks, hard links, request origins, host headers, and size limits are
validated. These controls reduce risk but do not remove the Docker-socket trust
boundary. See [`../SECURITY.md`](../SECURITY.md).

This tooling is provided without warranty and is used at your own risk. You are
responsible for validating Cisco compatibility, checksums, backups, change
procedures, and recovery plans. The authors accept no liability for outages,
data loss, device failure, or other damage.
