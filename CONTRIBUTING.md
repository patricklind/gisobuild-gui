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
docker compose build giso-webui
docker compose run --rm --no-deps \
  -v "$(cd .. && pwd):/project:ro" \
  -w /project/giso-webui \
  giso-webui python -B -m unittest discover -s tests -v
cd ..
bash -n build-giso.sh
python3 staging/rehearse.py
```

Never add Cisco-distributed software, generated images, device configuration,
credentials, build logs, or customer data to commits or test fixtures.

Keep changes focused and add a regression test for every bug fix where practical.
Use [`docs/testing.md`](docs/testing.md) for the complete validation ladder.
