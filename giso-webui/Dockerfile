FROM python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a

RUN apk add --no-cache docker-cli=29.5.3-r1 cdrkit=1.1.11-r6 git=2.54.0-r0 \
    # The mounted .gisobuild-tool checkout is owned by the host user, not
    # this container, so git's "dubious ownership" check refuses to read it
    # for gisobuild_commit() otherwise. This container only ever reads a
    # checkout mounted read-only by its own operator, never a shared
    # multi-tenant one, so trusting every directory is safe here.
    && git config --system --add safe.directory '*'
WORKDIR /app
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
