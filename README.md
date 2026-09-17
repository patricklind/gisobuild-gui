# Cisco IOS XR GISO Builder

A local Docker-based interface and CLI for building Cisco IOS XR Golden ISO
(GISO) images and USB boot packages with Cisco's `gisobuild` tool.

[Documentation](docs/README.md) · [Operations](docs/operations.md) ·
[Testing](docs/testing.md) · [Releases](https://github.com/patricklind/gisobuild-gui/releases)

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
- `docker/` — the default image (web app plus pinned gisobuild, no Docker
  socket) and the tooling and browser-test images.
- `staging/` — isolated upgrade and rollback workflow simulator.
- `scripts/e2e_real_iso.py` — licensed-ISO end-to-end ISO/USB verification.

See the [documentation index](docs/README.md) for operations, platform support,
testing, releases, architecture, security, and contribution guidance.

The default deployment runs gisobuild inside the web container, from a copy
pinned by commit and SHA-256: no Docker socket, no second container and no host
gisobuild checkout. A socket-based alternative that starts Cisco's builder image
is described under [deployment options](#deployment-options).

## Requirements

- Docker Desktop or Docker Engine with Compose v2
- An x86_64 host, or x86_64 emulation on Apple Silicon
- Approximately 25 GB of free disk space
- Only for the socket deployment or `build-giso.sh`: a checkout of
  [`ios-xr/gisobuild`](https://github.com/ios-xr/gisobuild) at `.gisobuild-tool/`
- Properly licensed Cisco IOS XR input files

Keep at least 25 GB free beyond the input files. A build temporarily stores the
upload, extracted packages, working data, and generated output at the same time.

## Quick start

```bash
git clone https://github.com/patricklind/gisobuild-gui.git
cd gisobuild-gui/giso-webui
cp .env.example .env
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8080/api/ready
```

Open <http://127.0.0.1:8080> and upload the Cisco base ISO and relevant update
packages. Successful builds archive both the Golden ISO and, when supported, the
USB boot ZIP.

Watch upload and build activity with:

```bash
docker compose logs --follow --tail=200 giso-webui archive-maintenance
```

The automatic package plan reads each RPM header and Cisco SMU README, leaves
out with a reason any package it can prove will not install, and names the SMU
to download. The expert form validates the selected platform family and rejects
options from the wrong eXR or IOS XR7/LNT workflow. Cisco `gisobuild` and the
ISO remain the authority for exact hardware PIDs and package compatibility.

Only one build runs at a time. Archived ISO and USB artifacts are retained for
30 days. If their combined size exceeds 50 GiB, the oldest complete build
archives are removed first.

Next: read the [Web UI guide](giso-webui/README.md), then use the
[GISO build and change guide](GISOBUILD-GUIDE.md) before handling a router.

## Real ISO/USB acceptance test

With the application running, provide a properly licensed Cisco base ISO for a
platform with USB support:

```bash
docker build -f docker/tooling.Dockerfile -t gisobuild-tooling .
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)/scripts:/scripts:ro" \
  -v /path/to/licensed-image.iso:/input/base.iso:ro \
  -v /path/to/matching/optional-rpms:/input/optional-rpms:ro \
  gisobuild-tooling python -B /scripts/e2e_real_iso.py /input/base.iso \
  --platform ncs5500 --rpm-dir /input/optional-rpms \
  --url http://host.docker.internal:8080
```

The test requires both an ISO and USB ZIP and prints SHA-256 evidence. Cisco
images are neither included nor downloaded by this repository. This (and every
project Python invocation) always runs inside the pinned `gisobuild-tooling`
container, never against the host interpreter — see "CRITICAL: Docker-only
execution boundary" in [`AGENTS.md`](AGENTS.md).

## Staging

Run the staged upgrade/rollback simulator inside the same tooling container to
safely exercise pre-check, staged upgrade, commit, rollback, and recovery
sequencing:

```bash
docker run --rm -v "$(pwd):/project:ro" -w /project/staging gisobuild-tooling \
  python -B rehearse.py
```

This simulator does not replace a test on matching lab hardware. See
[testing](docs/testing.md) for the four validation levels.

## Test and verify

```bash
cd giso-webui
docker compose config -q
docker compose -f compose.socket.yaml config -q
docker compose -f compose.socket.yaml build giso-webui
docker compose -f compose.socket.yaml run --rm --no-deps \
  -v "$(cd .. && pwd):/project:ro" \
  -w /project/giso-webui \
  giso-webui python -B -m unittest discover -s tests -v
cd ..
bash -n build-giso.sh scripts/coord.sh scripts/worktree.sh
```

Unit tests run in the lighter socket-deployment web image because they set
their own runner environment. Browser tests, lint, dependency audit, Graphify
and the default image checks are listed in [testing](docs/testing.md#developer-command-reference).

GitHub Actions runs, for every pull request: unit and synthetic integration
tests inside the built container image, Playwright browser tests, the staging
rehearsal, Ruff (including flake8-bandit rules), `pip-audit`, Actionlint,
Hadolint, Compose and shell syntax validation, a Graphify freshness check, a
guard against host-side tooling in docs and scripts, both container builds,
Trivy scans, an SBOM, and the platform drift tests against the gisobuild
bundled in the default image.
See the [release process](docs/releasing.md) for versioned GHCR publication.

## Deployment options

### Default: `compose.yaml` (no Docker socket)

`docker/selfcontained.Dockerfile` bundles the web app with
[`ios-xr/gisobuild`](https://github.com/ios-xr/gisobuild) at a pinned, verified
commit on upstream's own AlmaLinux 8.10 base. The image build also checks every
bundled gisobuild file against a pinned SHA-256 manifest, and the web app checks
it again at startup; a mismatch fails `/api/ready` and blocks builds. Builds run as child processes of
the web app: no Docker socket, no second builder container, no builder image
pull and no host `.gisobuild-tool` checkout.

```bash
cd giso-webui
docker compose up -d --build
curl --fail http://127.0.0.1:8080/api/ready
```

The container runs as root with a read-only root filesystem, `no-new-privileges`
and every Linux capability dropped except `SYS_CHROOT`, which gisobuild's eXR
engine needs to inspect RPMs inside the extracted image. Without it the build
plan is blocked with an explanation. `/api/version` reports `runner: local`, the
bundled gisobuild commit and its source SHA-256. Releases publish this image as
`ghcr.io/patricklind/gisobuild-gui:<version>` and `:latest` (`linux/amd64`). Real
NCS5500 25.1.2 Golden ISOs have been built this way; LNT images have not yet
been exercised in this deployment.

### Alternative: `compose.socket.yaml` (Docker socket)

The original architecture: the web container gets `/var/run/docker.sock` and
starts a child container from Cisco's `ciscogisobuild/cisco-xr-gisobuild` image
(pinned by digest) for each build. That image carries only gisobuild's runtime;
the gisobuild code is the host checkout at `.gisobuild-tool/`, which is not
pinned. Socket access is equivalent to administrative access to the Docker host.
Use it only where the default image cannot run.

```bash
git clone --depth 1 https://github.com/ios-xr/gisobuild.git .gisobuild-tool
cd giso-webui
docker compose -f compose.socket.yaml up -d --build
```

Both files use the same volumes; stop one before starting the other. Releases
publish its web image as `<version>-socket` / `latest-socket`.

### Moving an existing installation to the default

Earlier versions used the socket deployment as `compose.yaml`. After updating
the checkout, `docker compose down` then `docker compose up -d --build` switches
to the default image and keeps the same `giso-webui_*` volumes (uploads, job
history, archive). Wait for any active build to finish first. `GISO_IMAGE`,
`GISO_PULL_TIMEOUT_SECONDS` and the storage-path settings in an existing `.env`
are ignored by the default deployment, and `.gisobuild-tool/` is no longer
needed. To keep the old behaviour, use `-f compose.socket.yaml`.

## Security

Both deployments bind only to localhost. The socket deployment's web container
has access to the Docker socket; the default one has none, but the application
still has no authentication. Do not expose port 8080 to an untrusted network. See
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

[patricklind/gisobuild-gui](https://github.com/patricklind/gisobuild-gui)
