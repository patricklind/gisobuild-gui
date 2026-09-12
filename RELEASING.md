# Maintainer release procedure

## Tag and release

Before tagging, confirm the working tree is clean, the branch matches
`origin/main`, and every local and CI check is green. Always use a new semantic
version. Published Git tags must never be moved, deleted, or reused.

1. Set the version in `VERSION` without a leading `v`.
2. Update `RELEASE_NOTES.md` for that exact version.
3. Commit the version and notes through a pull request and merge them to `main`.
4. Update the primary checkout and verify it is clean:

   ```bash
   git switch main
   git pull --ff-only
   test -z "$(git status --short)"
   version="$(tr -d '[:space:]' < VERSION)"
   ```

5. Create and push a tag consisting of `v` followed by the file version:

   ```bash
   git tag -a "v${version}" -m "GISO Builder v${version}"
   git push origin "v${version}"
   ```

The tag-triggered Release workflow rejects a tag that does not match `VERSION`.
It then builds and publishes the application image for `linux/amd64` and
`linux/arm64`, attaches provenance and an SBOM, and publishes the GitHub Release
using `RELEASE_NOTES.md`.

After pushing the tag, verify that both CI and Release are green, the release is
public, and both versioned and `latest` images are available from GHCR. If any
gate fails, fix the issue and publish a new patch version. Never replace the
failed tag.

## Caution

Releases contain only this application's source and container image. Never
publish Cisco ISO, RPM, SMU, TAR, USB, configuration, key, certificate,
ownership-voucher, build-log, or generated GISO artifacts. A software release
does not approve an IOS XR upgrade or prove compatibility with router hardware.
