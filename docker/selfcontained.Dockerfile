# Self-contained giso-webui: the web app and a pinned ios-xr/gisobuild in one
# image. Builds run as child processes (GISO_RUNNER=local) - no Docker socket,
# no second builder container, no registry pull at build time, no host
# checkout. See docs/todo/03-DOCKER-SELF-CONTAINED-TODO.md.
#
# Build (from the repository root):
#   docker build --platform linux/amd64 -f docker/selfcontained.Dockerfile -t giso-webui-selfcontained .

# --- Stage 1: the exact upstream gisobuild source -------------------------
FROM alpine/git:v2.49.1@sha256:c0280cf9572316299b08544065d3bf35db65043d5e3963982ec50647d2746e26 AS source
ARG GISOBUILD_REPOSITORY=https://github.com/ios-xr/gisobuild.git
ARG GISOBUILD_COMMIT=0388af2989bb7022d780a8732dbfbfeb77a70ee7
# SHA-256 of the file manifest below (sha256sum of every file, C-sorted). The
# commit pin is a SHA-1 git object name; this binds the exact bytes copied into
# the image with SHA-256 as well, and the web app re-checks them at startup.
ARG GISOBUILD_SOURCE_SHA256=9d03ff0ccf5ccf1c5d3d75b14b29258272bd9d50109e4ace283e02e8eac3836d
RUN git clone --quiet "$GISOBUILD_REPOSITORY" /src \
    && git -C /src checkout --quiet "$GISOBUILD_COMMIT" \
    && test "$(git -C /src rev-parse HEAD)" = "$GISOBUILD_COMMIT" \
    && rm -rf /src/.git \
    && cd /src \
    && test -z "$(find . ! -type f ! -type d)" \
    && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > /gisobuild.sha256sums \
    && echo "$GISOBUILD_SOURCE_SHA256  /gisobuild.sha256sums" | sha256sum -c -

# --- Stage 2: runtime = upstream's own base and dependency set ------------
# Upstream's Dockerfile builds on almalinux:8.10 with setup/prep_dependency.sh.
# Pinned to the linux/amd64 manifest: gisobuild and Cisco images are x86_64.
FROM almalinux:8.10@sha256:158fba66c3434c58d07fb48cb6f19e3da84a7d9494cb07774d5d36a746136dce

# prep_dependency.sh's Red Hat package list, installed system-wide. Its pip
# step uses --user (root's home); the web app runs gisobuild with a minimal
# environment whose HOME is the job's work directory, so the Python modules
# are installed for every user instead, at the versions Cisco's own
# ciscogisobuild/cisco-xr-gisobuild:2.3.4 image ships. EL8 packages follow
# AlmaLinux 8.10 errata; the SBOM records exactly what a build installed.
# python3.12 is only for the web app; gisobuild runs on the platform python3.
# hadolint ignore=DL3041
RUN dnf -y install epel-release \
    && dnf -y install cpio createrepo_c file genisoimage gzip libcdio openssl \
        p7zip-plugins python3 python3-pip python3-rpm rpm squashfs-tools unzip zip \
        python3.12 python3.12-pip \
    && python3 -m pip install --no-cache-dir dataclasses==0.8 defusedxml==0.7.1 \
        packaging==21.3 PyYAML==6.0.1 \
    # vim-minimal comes with the base image, is not used by gisobuild or the
    # app, and carries fixed HIGH CVEs (Trivy, 2026-09-17).
    && dnf -y remove vim-minimal \
    && dnf clean all && rm -rf /var/cache/dnf

WORKDIR /opt/app
COPY giso-webui/requirements.txt .
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt
COPY giso-webui/app.py giso-webui/cisco_download.py giso-webui/maintenance.py giso-webui/platform_validation.py ./
COPY giso-webui/templates templates
COPY giso-webui/static static
COPY --from=source /src /opt/gisobuild
COPY --from=source /gisobuild.sha256sums /opt/gisobuild.sha256sums

ARG GISOBUILD_REPOSITORY=https://github.com/ios-xr/gisobuild.git
ARG GISOBUILD_COMMIT=0388af2989bb7022d780a8732dbfbfeb77a70ee7
ARG GISOBUILD_SOURCE_SHA256=9d03ff0ccf5ccf1c5d3d75b14b29258272bd9d50109e4ace283e02e8eac3836d
ARG SOURCE_REVISION=unknown
ARG BUILD_DATE=unknown
ARG APP_VERSION=0.0.1
LABEL org.opencontainers.image.title="giso-webui-selfcontained" \
      org.opencontainers.image.description="Web UI and pinned ios-xr/gisobuild for building Cisco IOS XR Golden ISOs" \
      org.opencontainers.image.source="https://github.com/patricklind/gisobuild-gui" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${APP_VERSION}" \
      io.github.ios-xr.gisobuild.repository="${GISOBUILD_REPOSITORY}" \
      io.github.ios-xr.gisobuild.commit="${GISOBUILD_COMMIT}" \
      io.github.ios-xr.gisobuild.source-sha256="${GISOBUILD_SOURCE_SHA256}"
ENV GISO_RUNNER=local \
    GISOBUILD_PYTHON=/usr/bin/python3 \
    TOOL_ROOT=/opt/gisobuild \
    GISOBUILD_REPOSITORY=${GISOBUILD_REPOSITORY} \
    GISOBUILD_COMMIT=${GISOBUILD_COMMIT} \
    GISOBUILD_SOURCE_SHA256=${GISOBUILD_SOURCE_SHA256} \
    GISOBUILD_SOURCE_MANIFEST=/opt/gisobuild.sha256sums \
    SOURCE_REVISION=${SOURCE_REVISION} \
    BUILD_DATE=${BUILD_DATE} \
    APP_VERSION=${APP_VERSION} \
    ISOINFO_BIN=/usr/bin/isoinfo \
    RPM_BIN=/usr/bin/rpm \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD ["python3.12", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"]
CMD ["python3.12", "-m", "gunicorn", "--workers", "1", "--threads", "8", "--timeout", "0", "--bind", "0.0.0.0:8080", "--error-logfile", "-", "--capture-output", "--log-level", "info", "app:app"]
