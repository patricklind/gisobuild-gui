# IOS XR GISO Web UI

A local Docker web interface for `ios-xr/gisobuild`. The UI exposes common eXR and LNT options, YAML mode, live build logs, and artifact downloads.

## Start

From `giso-webui`:

```bash
mkdir -p output
docker compose up --build -d
```

Open <http://127.0.0.1:8080>.

Uploads, output, archives, and build working files are stored in persistent Docker volumes. The GISO archive is stored in `giso-webui_giso-archive`.

After a successful build, the application copies the Golden ISO and optional USB boot package to the archive and verifies each copy with SHA-256. It then removes all uploads, RPM/TAR sources, other build output, and working files. Cleanup does not run when the ISO is missing or archive verification fails.

The **Clean temporary files** button removes only incomplete upload fragments and temporary build directories. It never removes uploaded Cisco files or completed images.

Cisco `.tar` files are transport archives. The UI extracts them automatically and passes only discovered `.rpm` packages to `--pkglist`. Do not add a tar file itself to the package list.

Only one build can run at a time. Archived ISO and USB files are retained for no more than 30 days. If their combined size exceeds 50 GiB, the oldest complete job archives are deleted first. Configure these limits with `ARCHIVE_RETENTION_DAYS` and `MAX_ARCHIVE_BYTES`.

For local configuration, copy `.env.example` to `.env` and edit the values before starting Docker Compose. The local `.env` file is excluded from Git.

## Stop

```bash
docker compose down
```

## Security

The application binds only to localhost. The web container can access the Docker socket so that it can start the Cisco GISO build container. The build container receives only read-only input and tool mounts plus dedicated output and working mounts; it never receives the Docker socket.

Never expose this service to an untrusted network. Docker socket access is effectively administrative access to the Docker host.

The web container uses a read-only root filesystem and has all Linux capabilities removed. Only the declared data, output, archive, and working volumes are writable.

Default limits are 8 GiB per upload, 16 MiB per upload chunk, 16 GiB per extracted tar archive, 10,000 tar members, and a 10 MiB in-memory build log. Symlinks, hard links, and paths outside the extraction directory are rejected.

## Disclaimer

This tooling is provided without warranty and is used at your own risk. You are responsible for validating Cisco compatibility, checksums, backups, change procedures, and recovery plans. The authors accept no liability for outages, data loss, device failure, or other damage.
