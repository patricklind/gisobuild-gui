# Parallel work with Git worktrees

Keep the primary checkout on `main` and use one branch and worktree per task.

```bash
./scripts/worktree.sh new platform-validation
cd ../gisobuild-platform-validation
./scripts/coord.sh claim web-platform "Validate platform-specific options"
```

Commit only the claimed module, run its verification, push `codex/<name>`, and
open a pull request. After merge, release the claim from the primary checkout
and remove the worktree. Never force-remove a worktree with uncommitted changes.

```bash
cd ../gisobuild
./scripts/coord.sh release web-platform
./scripts/worktree.sh remove platform-validation
```

The coordination board is deliberately outside every worktree at
`../.gisobuild-coordination`, so claims are visible across concurrent sessions
without becoming repository content.
