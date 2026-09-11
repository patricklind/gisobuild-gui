# Cisco IOS XR GISO Builder

A local Docker-based interface and CLI for building Cisco IOS XR Golden ISO
(GISO) images and USB boot packages with Cisco's `gisobuild` tool.

> [!WARNING]
> This project does not contain or distribute Cisco software. Supply your own
> properly licensed IOS XR ISO, RPM, and SMU files. These files are excluded by
> `.gitignore` and must never be committed.

## Components

- `giso-webui/` — Flask web interface for uploads, builds, checksums, downloads,
  and persistent ISO/USB archives.
- `build-giso.sh` — reusable command-line workflow for NCS5500 builds.
- `GISOBUILD-GUIDE.md` — Danish operational build and installation guide.

The web process starts an isolated Cisco build container. Input and tool mounts
are read-only; only dedicated output and working volumes are writable. The web
container itself uses a read-only root filesystem with all Linux capabilities
dropped.

## Requirements

- Docker Desktop or Docker Engine with Compose v2
- An x86_64 host, or x86_64 emulation on Apple Silicon
- Approximately 25 GB of free disk space
- A local checkout of [`ios-xr/gisobuild`](https://github.com/ios-xr/gisobuild)
  at `.gisobuild-tool/`, or permission for `build-giso.sh` to clone it
- Properly licensed Cisco IOS XR input files

## Quick start

```bash
git clone https://github.com/patricklind/gisobuild-gui.git
cd gisobuild-gui
git clone --depth 1 https://github.com/ios-xr/gisobuild.git .gisobuild-tool
cd giso-webui
docker compose up --build -d
```

Open <http://127.0.0.1:8080> and upload the Cisco base ISO and relevant update
packages. Successful builds archive both the Golden ISO and, when supported, the
USB boot ZIP.

Detailed web usage is documented in [`giso-webui/README.md`](giso-webui/README.md).
The CLI workflow is documented in [`GISOBUILD-GUIDE.md`](GISOBUILD-GUIDE.md).

## Test and verify

```bash
cd giso-webui
docker compose config -q
docker compose build giso-webui
docker compose run --rm --no-deps \
  -v "$(cd .. && pwd):/project:ro" \
  -w /project/giso-webui \
  giso-webui python -B -m unittest discover -s tests -v
cd ..
bash -n build-giso.sh
```

GitHub Actions runs unit tests, Ruff, `pip-audit`, Compose validation, shell
syntax validation, and a production container build for every pull request.

## Security

The service binds only to localhost because the web container has access to the
Docker socket. Do not expose port 8080 to an untrusted network. See
[`SECURITY.md`](SECURITY.md) for the deployment boundary and reporting process.

## License

No open-source license has been selected yet. Until one is added, copyright law
reserves all rights to the repository owner.
# gisobuild-gui
