#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ISO=""
INPUT_ROOT="$SCRIPT_DIR"
LABEL="SEC_HARDENING"
OUTPUT_DIR=""
TOOL_DIR="$SCRIPT_DIR/.gisobuild-tool"
DOCKER_IMAGE="ciscogisobuild/cisco-xr-gisobuild:2.3.4"
CLEAN=false

usage() {
  cat <<'EOF'
Usage:
  ./build-giso.sh --iso PATH [options]

Options:
  --iso PATH          Base/mini ISO (required)
  --input-root PATH   Directory containing optional RPMs and SMU directories
                      (default: directory containing this script)
  --label LABEL       GISO label; letters, numbers and underscore only
  --output PATH       Output directory (default: output_gisobuild_LABEL)
  --tool-dir PATH     Existing ios-xr/gisobuild checkout
  --image IMAGE       Docker image (default: ciscogisobuild/cisco-xr-gisobuild:2.3.4)
  --clean             Permit replacement of an existing output directory
  -h, --help          Show this help
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --iso) ISO=${2:?Missing value for --iso}; shift 2 ;;
    --input-root) INPUT_ROOT=${2:?Missing value for --input-root}; shift 2 ;;
    --label) LABEL=${2:?Missing value for --label}; shift 2 ;;
    --output) OUTPUT_DIR=${2:?Missing value for --output}; shift 2 ;;
    --tool-dir) TOOL_DIR=${2:?Missing value for --tool-dir}; shift 2 ;;
    --image) DOCKER_IMAGE=${2:?Missing value for --image}; shift 2 ;;
    --clean) CLEAN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[ -n "$ISO" ] || { usage; die "--iso is required"; }
case "$LABEL" in *[!A-Za-z0-9_]*) die "Label must contain only letters, numbers and underscore" ;; esac

ISO=$(cd "$(dirname "$ISO")" && pwd)/$(basename "$ISO")
INPUT_ROOT=$(cd "$INPUT_ROOT" && pwd)
if [ -z "$OUTPUT_DIR" ]; then
  OUTPUT_DIR="$SCRIPT_DIR/output_gisobuild_$LABEL"
elif [ "${OUTPUT_DIR#/}" = "$OUTPUT_DIR" ]; then
  OUTPUT_DIR="$SCRIPT_DIR/$OUTPUT_DIR"
fi
if [ "${TOOL_DIR#/}" = "$TOOL_DIR" ]; then
  TOOL_DIR="$SCRIPT_DIR/$TOOL_DIR"
fi

[ -f "$ISO" ] || die "ISO not found: $ISO"
command -v docker >/dev/null || die "docker is not installed"
docker info >/dev/null 2>&1 || die "Docker is not running"

if [ -e "$OUTPUT_DIR" ]; then
  $CLEAN || die "Output exists: $OUTPUT_DIR (use --clean to replace it)"
  OUTPUT_DIR=$(cd "$(dirname "$OUTPUT_DIR")" && pwd -P)/$(basename "$OUTPUT_DIR")
  case "$OUTPUT_DIR" in
    "$SCRIPT_DIR"/output_gisobuild_*) rm -rf "$OUTPUT_DIR" ;;
    *) die "Refusing to clean a non-standard output path: $OUTPUT_DIR" ;;
  esac
fi

if [ ! -x "$TOOL_DIR/src/gisobuild.py" ]; then
  command -v git >/dev/null || die "git is required to download gisobuild"
  [ ! -e "$TOOL_DIR" ] || die "Tool directory exists but is incomplete: $TOOL_DIR"
  git clone --depth 1 https://github.com/ios-xr/gisobuild.git "$TOOL_DIR"
fi

md5_file() {
  if command -v md5 >/dev/null 2>&1; then
    md5 -q "$1"
  else
    md5sum "$1" | awk '{print $1}'
  fi
}

printf 'Validating input checksums...\n'
BASE_README=$(find "$(dirname "$ISO")" -maxdepth 1 -type f -name 'README-*.txt' -print -quit)
if [ -n "$BASE_README" ]; then
  while read -r expected name; do
    case "$expected" in
      [0-9a-fA-F][0-9a-fA-F]*) ;;
      *) continue ;;
    esac
    candidate=$(find "$(dirname "$ISO")" -type f -name "$name" -print -quit)
    [ -n "$candidate" ] || die "File listed in README is missing: $name"
    actual=$(md5_file "$candidate")
    [ "$actual" = "$expected" ] || die "Checksum mismatch: $candidate"
  done < "$BASE_README"
else
  printf 'WARNING: no base-image README checksum file found\n' >&2
fi

find "$INPUT_ROOT" -type f -name '*.txt' -print | while read -r readme; do
  expected=$(awk '/^MD5:[[:space:]]*/ {print $2; exit}' "$readme")
  [ -n "$expected" ] || continue
  rpm=$(find "$(dirname "$readme")" -maxdepth 1 -type f -name '*.rpm' -print -quit)
  [ -n "$rpm" ] || die "No RPM beside $readme"
  actual=$(md5_file "$rpm")
  [ "$actual" = "$expected" ] || die "Checksum mismatch: $rpm"
done

STAGING="$SCRIPT_DIR/.giso-build-staging-$LABEL"
case "$STAGING" in "$SCRIPT_DIR"/.giso-build-staging-*) ;; *) die "Unsafe staging path" ;; esac
rm -rf "$STAGING"
mkdir -p "$STAGING/repo"
trap 'rm -rf "$STAGING"' EXIT INT TERM

SUPERSEDED="$STAGING/superseded.txt"
find "$INPUT_ROOT" -type f -name '*.txt' -exec awk '
  /ncs5500-[0-9]+\.[0-9]+\.[0-9]+\.CSC[A-Za-z0-9]+[[:space:]]+Full/ {
    for (i=1; i<=NF; i++) if ($i ~ /^ncs5500-/) print $i
  }
' {} + | sort -u > "$SUPERSEDED"

PKGLIST="$STAGING/pkglist.txt"
: > "$PKGLIST"
RPM_INPUTS="$STAGING/rpm-inputs.txt"
: > "$RPM_INPUTS"
if [ -d "$(dirname "$ISO")/optional-rpms" ]; then
  find "$(dirname "$ISO")/optional-rpms" -type f -name '*.rpm' -print >> "$RPM_INPUTS"
fi
find "$INPUT_ROOT" -mindepth 2 -maxdepth 2 -type f \
  -path "$INPUT_ROOT/ncs5500-*.CSC*/*.rpm" -print >> "$RPM_INPUTS"
sort -u "$RPM_INPUTS" -o "$RPM_INPUTS"

while read -r rpm; do
  smu_dir=$(basename "$(dirname "$rpm")")
  if grep -Fxq "$smu_dir" "$SUPERSEDED"; then
    printf 'Skipping superseded SMU: %s\n' "$smu_dir"
    continue
  fi
  name=$(basename "$rpm")
  [ ! -e "$STAGING/repo/$name" ] || die "Duplicate RPM filename: $name"
  cp -p "$rpm" "$STAGING/repo/$name"
  printf '%s\n' "$name" >> "$PKGLIST"
done < "$RPM_INPUTS"

[ -s "$PKGLIST" ] || die "No RPMs found below $INPUT_ROOT"
printf '\nPackages selected (%s):\n' "$(wc -l < "$PKGLIST" | tr -d ' ')"
sed 's/^/  /' "$PKGLIST"

docker pull --platform linux/amd64 "$DOCKER_IMAGE"
mkdir -p "$OUTPUT_DIR"

DOCKER_ARGS=(
  docker run --platform linux/amd64 --rm
  -v "$TOOL_DIR/src:/app/gisobuild:ro"
  -v "$ISO:/input/base.iso:ro"
  -v "$STAGING/repo:/input/repo:ro"
  -v "$OUTPUT_DIR:/output"
  "$DOCKER_IMAGE"
  /app/gisobuild/gisobuild.py
  --iso /input/base.iso
  --repo /input/repo
  --pkglist
)

while read -r pkg; do DOCKER_ARGS+=("$pkg"); done < "$PKGLIST"
DOCKER_ARGS+=(
  --label "$LABEL"
  --out-directory /output
  --create-checksum
  --clean
)

printf '\nStarting Docker GISO build...\n'
"${DOCKER_ARGS[@]}"

RESULT=$(find "$OUTPUT_DIR" -maxdepth 1 -type f -name '*.iso' -print -quit)
[ -n "$RESULT" ] || die "Build finished without an ISO; inspect $OUTPUT_DIR/logs"

printf '\nBuild complete\n'
printf 'ISO: %s\n' "$RESULT"
printf 'Size: %s bytes\n' "$(wc -c < "$RESULT" | tr -d ' ')"
printf 'MD5: %s\n' "$(md5_file "$RESULT")"
if command -v shasum >/dev/null 2>&1; then
  printf 'SHA256: %s\n' "$(shasum -a 256 "$RESULT" | awk '{print $1}')"
else
  printf 'SHA256: %s\n' "$(sha256sum "$RESULT" | awk '{print $1}')"
fi
