# Pinned tooling container for everything AGENTS.md forbids on the host:
# Graphify, ruff, pip-audit. Build once, reuse - installing these from PyPI
# in a fresh throwaway container on every invocation is slow and, on a flaky
# connection, times out outright (graphifyy pulls in heavy ML/embedding
# dependencies). See "CRITICAL: Docker-only execution boundary" in AGENTS.md.
FROM python:3.12-slim

# git is required by scripts/check_graphify_freshness.py (git ls-files).
# The mounted repo is owned by the host user, not this container's root, so
# git's "dubious ownership" check refuses to run there otherwise; this
# container only ever runs against a repo mounted by its own caller, never a
# shared multi-tenant checkout, so trusting every directory is safe here.
RUN apt-get update && apt-get install --no-install-recommends -y git=1:2.47.3-0+deb13u1 \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

RUN pip install --no-cache-dir \
    graphifyy==0.9.61 \
    ruff==0.16.7 \
    pip-audit==2.7.3

WORKDIR /project
