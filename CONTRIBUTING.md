# Contributing

## Coordination and branches

Read [`AGENTS.md`](AGENTS.md) before editing. Check the shared board, create a
task worktree, and claim the module:

```bash
./scripts/coord.sh status
./scripts/worktree.sh new <task-name>
cd ../gisobuild-<task-name>
./scripts/coord.sh claim <module> "short note"
```

Keep commits focused. Mark the claim done, push `codex/<task-name>`, and open a
pull request. Release the claim and remove the worktree only after merge.

## Local verification

Run these checks before opening a pull request:

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
docker compose -f staging/compose.yaml config -q
bash -n build-giso.sh scripts/coord.sh scripts/worktree.sh
docker build -f docker/tooling.Dockerfile -t gisobuild-tooling .
docker run --rm -v "$(pwd):/project:ro" -w /project/staging gisobuild-tooling python -B rehearse.py
git diff --check
```

Never run `python3`, `pip`, `ruff`, or Graphify directly on the host — see
"CRITICAL: Docker-only execution boundary" in [`AGENTS.md`](AGENTS.md).
`docker/tooling.Dockerfile` is a small, pinned container (Python 3.12 + git
+ Ruff + Graphify + pip-audit) for everything that policy forbids on the
host; build it once and reuse the image. See
[`docs/testing.md`](docs/testing.md) for the Ruff/pip-audit/Graphify
invocations.

Never add Cisco-distributed software, generated images, device configuration,
credentials, build logs, or customer data to commits or test fixtures.

UI changes also need the Playwright browser tests, and platform or packaging
changes the default image build and its upstream drift tests; the exact
commands are in [`docs/testing.md`](docs/testing.md).

Keep changes focused and add a regression test for every bug fix where practical.
Use [`docs/testing.md`](docs/testing.md) for the complete validation ladder.

After the checks pass:

```bash
./scripts/coord.sh done <module>
git push -u origin codex/<task-name>
```

Open a pull request and wait for CI. After merge, release the module claim from
the primary checkout and remove the worktree with
`./scripts/worktree.sh remove <task-name>`.
