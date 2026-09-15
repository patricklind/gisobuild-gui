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
python3 staging/rehearse.py
bash -n build-giso.sh scripts/coord.sh scripts/worktree.sh
git diff --check
```

CI additionally runs Ruff and `pip-audit`. Workflow and Dockerfile changes
should also pass Actionlint and Hadolint.

Pull requests from trusted, same-repository `codex/*` branches are squash-merged
automatically only after the `CI` workflow succeeds. External forks and other
branch prefixes are never selected by this automation.

## 2. Container smoke test

```bash
docker compose -f giso-webui/compose.yaml up --build -d
curl --fail http://127.0.0.1:8080/api/health
curl --fail http://127.0.0.1:8080/api/platforms
docker compose -f giso-webui/compose.yaml ps
```

This verifies the application and Docker connection, not `gisobuild` output.

## 3. Licensed-ISO acceptance test

Use a Cisco base ISO and matching packages that the operator is authorized to
use. Select a family for which automatic USB output is expected:

```bash
python3 scripts/e2e_real_iso.py /path/to/base.iso \
  --platform ncs5500 \
  --rpm-dir /path/to/matching/optional-rpms
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
