FROM python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a

# rpm is used read-only, via `rpm -qp --requires/--provides --nosignature`, to
# read an uploaded RPM's own dependency metadata for the pre-build dependency
# check. No RPM is ever installed, and no RPM database is created in this
# image - see rpm_dependency_metadata() in app.py.
# libuuid is pinned past the base image's 2.42.1-r0: that build carries seven
# fixed HIGH util-linux CVEs (Trivy, 2026-09-17; see
# docs/todo/05-TESTING-CI-TODO.md "Trivy image scan").
RUN apk add --no-cache docker-cli=29.5.3-r1 cdrkit=1.1.11-r6 git=2.54.0-r0 rpm=4.19.1.1-r5 \
    libuuid=2.42.3-r1 \
    # The mounted .gisobuild-tool checkout is owned by the host user, not
    # this container, so git's "dubious ownership" check refuses to read it
    # for gisobuild_commit() otherwise. This container only ever reads a
    # checkout mounted read-only by its own operator, never a shared
    # multi-tenant one, so trusting every directory is safe here.
    && git config --system --add safe.directory '*'
WORKDIR /app
# Traceability: which commit and when this image was built. Supplied by
# compose/CI build args; "unknown" for an ad-hoc local build.
ARG SOURCE_REVISION=unknown
ARG BUILD_DATE=unknown
ARG APP_VERSION=0.0.1
LABEL org.opencontainers.image.title="giso-webui" \
      org.opencontainers.image.description="Web UI for building Cisco IOS XR Golden ISOs with ios-xr/gisobuild" \
      org.opencontainers.image.source="https://github.com/patricklind/gisobuild-gui" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${APP_VERSION}"
ENV SOURCE_REVISION=${SOURCE_REVISION} BUILD_DATE=${BUILD_DATE} APP_VERSION=${APP_VERSION}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY cisco_download.py .
COPY maintenance.py .
COPY platform_validation.py .
COPY templates templates
COPY static static
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD ["wget", "-qO-", "http://127.0.0.1:8080/api/ready"]
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "0", "--bind", "0.0.0.0:8080", "--error-logfile", "-", "--capture-output", "--log-level", "info", "app:app"]
