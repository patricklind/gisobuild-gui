#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
repo="$(basename "$root")"
usage() { echo "Usage: $0 new <name> | remove <name> | list" >&2; exit 2; }
validate() { [[ "$1" =~ ^[a-z0-9][a-z0-9-]{0,47}$ ]] || { echo "Use a lowercase task name with letters, numbers, or hyphens." >&2; exit 2; }; }

case "${1:-}" in
  new)
    [[ $# -eq 2 ]] || usage; validate "$2"
    target="$(dirname "$root")/${repo}-$2"; branch="codex/$2"
    [[ ! -e "$target" ]] || { echo "Worktree already exists: $target" >&2; exit 1; }
    git -C "$root" worktree add -b "$branch" "$target" main
    echo "Created $target on $branch"
    ;;
  remove)
    [[ $# -eq 2 ]] || usage; validate "$2"
    target="$(dirname "$root")/${repo}-$2"
    git -C "$root" worktree remove "$target"
    ;;
  list) git -C "$root" worktree list ;;
  *) usage ;;
esac
