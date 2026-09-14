# Module coordination board

The filesystem-backed board gives each module one owner at a time. Claim names
should describe a stable ownership boundary, for example `web-api`, `web-ui`,
`platform-validation`, `staging`, `release`, `documentation`, or `graphify`.

```bash
./scripts/coord.sh status
./scripts/coord.sh claim web-api "Add validation endpoint"
./scripts/coord.sh done web-api
./scripts/coord.sh release web-api
```

Claim creation uses an atomic directory operation. A failed claim means another
session already owns that module. `done` keeps ownership while review or merge
is pending; `release` removes it only after merge. Set `GISO_COORD_DIR` when the
default board location is unsuitable.

Do not reuse another session's claim merely because its branch looks inactive.
Contact its owner or inspect the associated worktree first. Stale claims protect
uncommitted work until ownership is explicitly transferred.
