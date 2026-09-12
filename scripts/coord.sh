#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
board="${GISO_COORD_DIR:-$(dirname "$root")/.gisobuild-coordination}"
claims="$board/claims"
mkdir -p "$claims"

usage() { echo "Usage: $0 status | claim <module> <note> | done <module> | release <module>" >&2; exit 2; }
slug() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || { echo "Invalid module name: $1" >&2; exit 2; }
  printf '%s' "$1"
}

command="${1:-}"
case "$command" in
  status)
    found=0
    for claim in "$claims"/*; do
      [[ -d "$claim" ]] || continue
      found=1
      module="$(basename "$claim")"
      owner="$(sed -n '1p' "$claim/owner" 2>/dev/null || echo unknown)"
      state="$(sed -n '1p' "$claim/state" 2>/dev/null || echo claimed)"
      note="$(sed -n '1p' "$claim/note" 2>/dev/null || true)"
      printf '%-24s %-10s %-24s %s\n' "$module" "$state" "$owner" "$note"
    done
    [[ "$found" == 1 ]] || echo "No active module claims."
    ;;
  claim)
    [[ $# -eq 3 ]] || usage
    module="$(slug "$2")"; target="$claims/$module"
    if ! mkdir "$target" 2>/dev/null; then
      echo "Module '$module' is already claimed:" >&2
      sed -n '1p' "$target/owner" "$target/note" 2>/dev/null >&2 || true
      exit 1
    fi
    git_branch="$(git branch --show-current)"
    printf '%s\n' "${USER:-unknown}@$(hostname):$git_branch" > "$target/owner"
    printf '%s\n' "$3" > "$target/note"
    printf '%s\n' claimed > "$target/state"
    echo "Claimed '$module'."
    ;;
  done)
    [[ $# -eq 2 ]] || usage
    module="$(slug "$2")"; target="$claims/$module"
    [[ -d "$target" ]] || { echo "Module '$module' is not claimed." >&2; exit 1; }
    printf '%s\n' done > "$target/state"
    echo "Marked '$module' done."
    ;;
  release)
    [[ $# -eq 2 ]] || usage
    module="$(slug "$2")"; target="$claims/$module"
    [[ -d "$target" ]] || { echo "Module '$module' is not claimed." >&2; exit 1; }
    find "$target" -type f -delete
    rmdir "$target"
    echo "Released '$module'."
    ;;
  *) usage ;;
esac
