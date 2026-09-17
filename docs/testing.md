# Testing and acceptance

The project uses four distinct validation levels. Report them separately.

## 1. Static and unit verification

Run the `giso-webui` unit tests only inside the built container image (the
`docker run ... giso-webui-giso-webui python -B -m unittest ...` line below).
Never invoke `python -m unittest` or `pytest` directly against the host Python
interpreter for this module — the host has neither the pinned dependency
versions nor OS tools such as `isoinfo` that the image provides, so a host run
is not equivalent to CI.

```bash
docker compose -f giso-webui/compose.yaml config -q
docker compose -f staging/compose.yaml config -q
docker compose -f giso-webui/compose.yaml build giso-webui
docker run --rm -v "$(pwd):/project:ro" -w /project/giso-webui \
  giso-webui-giso-webui python -B -m unittest discover -s tests -v
docker build -f docker/tooling.Dockerfile -t gisobuild-tooling .
docker run --rm -v "$(pwd):/project:ro" -w /project/staging gisobuild-tooling python -B rehearse.py
bash -n build-giso.sh scripts/coord.sh scripts/worktree.sh
git diff --check
```

Never run `python3 staging/rehearse.py` (or any project Python) directly
against the host interpreter — see "CRITICAL: Docker-only execution
boundary" in `AGENTS.md`. `docker/tooling.Dockerfile` is a small, pinned
container (Python 3.12 + git) that `rehearse.py`'s pure-stdlib logic runs in
unmodified; build it once and reuse the image.

CI additionally runs Ruff and `pip-audit`. Locally, run the pinned
equivalents from the same `gisobuild-tooling` image built above — never
`pip install ruff`/`pip install pip-audit` on the host:

```bash
docker run --rm -v "$(pwd):/project:ro" -w /project gisobuild-tooling \
  ruff check giso-webui staging scripts --cache-dir=/tmp/ruff-cache
docker run --rm -v "$(pwd):/project:ro" -w /project gisobuild-tooling \
  pip-audit -r giso-webui/requirements.txt
```

Operator UI behaviour is covered by real-browser tests
(`giso-webui/browser_tests/`, Playwright + Chromium). They run the Flask app
in-process against synthetic placeholder files - no Cisco content, Docker or
gisobuild - and assert on what the page renders. Only in their own pinned
image:

```bash
docker build -f docker/browser-tests.Dockerfile -t gisobuild-browser-tests .
docker run --rm -v "$(pwd):/work:ro" -e PYTHONDONTWRITEBYTECODE=1 \
  gisobuild-browser-tests python3 -m unittest discover -s browser_tests -v
```

Workflow and Dockerfile changes should also pass Actionlint and Hadolint —
both already run as containers (`docker run --rm ... rhysd/actionlint:1.7.7`,
`docker run --rm -i hadolint/hadolint:2.12.0 < <file>`), matching
`.github/workflows/ci.yml`.

Pull requests from trusted, same-repository `codex/*` branches are squash-merged
automatically only after the `CI` workflow succeeds. External forks and other
branch prefixes are never selected by this automation.

## 2. Container smoke test

```bash
docker compose -f giso-webui/compose.yaml up --build -d
curl --fail http://127.0.0.1:8080/api/health
curl --fail http://127.0.0.1:8080/api/ready
curl --fail http://127.0.0.1:8080/api/platforms
docker compose -f giso-webui/compose.yaml ps
```

This verifies the application and Docker connection, not `gisobuild` output.

## 3. Licensed-ISO acceptance test

Use a Cisco base ISO and matching packages that the operator is authorized to
use. Select a family for which automatic USB output is expected:

`scripts/e2e_real_iso.py` is pure-stdlib Python, so it runs unmodified in the
same `gisobuild-tooling` image built in step 1 above — never on the host.
`--add-host` makes the `giso-webui` container's published port reachable
from inside the tooling container on both Linux and Docker Desktop:

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v "$(pwd)/scripts:/scripts:ro" \
  -v /path/to/base.iso:/input/base.iso:ro \
  -v /path/to/matching/optional-rpms:/input/optional-rpms:ro \
  gisobuild-tooling python -B /scripts/e2e_real_iso.py /input/base.iso \
  --platform ncs5500 --rpm-dir /input/optional-rpms \
  --url http://host.docker.internal:8080
```

The runner uploads the files, waits for the real Cisco build container, requires
both a Golden ISO and USB ZIP, and prints SHA-256 checksums. Do not commit the
input files, output files, logs, filenames containing customer data, or secrets.

Record the tool image digest, input ISO release and platform, selected package
inventory, exit status, artifact sizes, and generated checksums in an approved
private change record. A passing synthetic test or staging rehearsal must never
be reported as licensed-ISO acceptance.

## 4. Matching-hardware validation

Only a lab router matching the production PID, route processor, source release,
target release, ROMMON/BIOS/FPD state, and package set can validate the actual
upgrade and rollback. Use an approved maintenance procedure and the
[GISO guide](../GISOBUILD-GUIDE.md). The staging simulator is a workflow-order
test and is never hardware acceptance.

## Reporting results

Use one of these exact outcomes for every validation level: **passed**,
**failed**, or **not run**. Include the command or procedure, timestamp, tested
commit or image digest, and relevant limitations. Never promote a lower-level
result to a higher validation level.
