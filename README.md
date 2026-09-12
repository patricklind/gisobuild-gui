# Cisco IOS XR GISO Builder

A local Docker-based interface and CLI for building Cisco IOS XR Golden ISO
(GISO) images and USB boot packages with Cisco's `gisobuild` tool.

> [!WARNING]
> This project does not contain or distribute Cisco software. Supply your own
> properly licensed IOS XR ISO, RPM, and SMU files. These files are excluded by
> `.gitignore` and must never be committed.

> [!CAUTION]
> Use this software at your own risk. It is provided without warranty. You are
> responsible for validating compatibility, checksums, backups and operational
> procedures. The authors accept no liability for outages, data loss, device
> failure or other damage.

## Components

- `giso-webui/` — Flask web interface for uploads, builds, checksums, downloads,
  and persistent ISO/USB archives.
- `build-giso.sh` — command-line helper for the documented NCS5500 directory
  and package naming convention.
- `GISOBUILD-GUIDE.md` — platform-aware build, upgrade, validation, and rollback
  guide for Cisco IOS XR families supported by the upstream GISO tool.
- `staging/` — isolated upgrade and rollback workflow simulator.
- `scripts/e2e_real_iso.py` — licensed-ISO end-to-end ISO/USB verification.

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
cp .env.example .env
docker compose up --build -d
```

Open <http://127.0.0.1:8080> and upload the Cisco base ISO and relevant update
packages. Successful builds archive both the Golden ISO and, when supported, the
USB boot ZIP.

The expert form validates the selected platform family and rejects options from
the wrong eXR or IOS XR7/LNT workflow. The ISO remains the authority for exact
hardware PIDs and package compatibility.

Only one build runs at a time. Archived ISO and USB artifacts are retained for
30 days. If their combined size exceeds 50 GiB, the oldest complete build
archives are removed first.

Detailed web usage is documented in [`giso-webui/README.md`](giso-webui/README.md).
The CLI workflow is documented in [`GISOBUILD-GUIDE.md`](GISOBUILD-GUIDE.md).
System boundaries and improvement priorities are documented in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Real ISO/USB acceptance test

With the application running, provide a properly licensed Cisco base ISO for a
platform with USB support:

```bash
python3 scripts/e2e_real_iso.py /path/to/licensed-image.iso --platform ncs5500 \
  --rpm-dir /path/to/matching/optional-rpms
```

The test requires both an ISO and USB ZIP and prints SHA-256 evidence. Cisco
images are neither included nor downloaded by this repository.

## Staging and releases

Run `python3 staging/rehearse.py` to safely exercise pre-check, staged upgrade,
commit, rollback, and recovery sequencing. This simulator does not replace a
test on matching lab hardware. Tags matching `v*` publish multi-architecture
images to `ghcr.io/patricklind/gisobuild-gui` and create a GitHub Release.

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

## Operational limitations

- This is a single-host, single-user tool. It intentionally allows only one
  build at a time.
- Completed job history and bounded logs are stored in SQLite. A build that was
  active during a web-service restart is retained as `interrupted` and must be
  checked before another build is started.
- A dedicated maintenance container enforces archive expiry and quota every
  hour, including while the Web UI is idle.
- A complete Cisco GISO build requires licensed inputs and is therefore not run
  by the public CI workflow.

## License

No open-source license has been selected yet. Until one is added, copyright law
reserves all rights to the repository owner.
