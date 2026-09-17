# Real-browser tests for the operator UI (giso-webui/browser_tests), run
# only in Docker like every other project tool - see AGENTS.md. The pinned
# Playwright image already carries Chromium and its system libraries; only
# the matching Python client and the web app's own requirements are added.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble@sha256:640d578aae63cfb632461d1b0aecb01414e4e020864ac3dd45a868dc0eff3078

COPY giso-webui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages \
    playwright==1.55.0 \
    -r /tmp/requirements.txt

WORKDIR /work/giso-webui
CMD ["python3", "-m", "unittest", "discover", "-s", "browser_tests", "-v"]
