# Contributing

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
```

Never add Cisco-distributed software, generated images, device configuration,
credentials, build logs, or customer data to commits or test fixtures.

Keep changes focused and add a regression test for every bug fix where practical.
