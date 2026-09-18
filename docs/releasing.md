# Release process

Published versions are listed on the
[GitHub Releases page](https://github.com/patricklind/gisobuild-gui/releases).
The current documentation follows `main`; use the matching Git tag when
operating an older release.

## Automatic releases

Every push to `main` that passes the full **CI** workflow is released
automatically, at most once per hour: the **Auto-tag release** workflow
(`.github/workflows/auto-release.yml`) waits for CI to complete on that exact
commit, skips releasing if less than an hour has passed since the last
release tag was created (several commits landing close together get one
release, not one each - the next push after the hour passes releases
everything accumulated since then), otherwise computes the next version from
the highest existing `v*` tag and pushes that tag. Patch and minor each roll
over at 9 into the next component, like an odometer, rather than counting
patches without bound: `v1.2.3` → `v1.2.4`, `v0.0.9` → `v0.1.0`, `v0.9.9` →
`v1.0.0`. It never builds or publishes anything itself; pushing the tag is
what triggers the **Release** workflow below, which re-runs the complete CI
suite against that commit a second time and only builds/publishes if that
also passes - the same gate a manual release always went through. A failed or
skipped CI run creates no tag
and no release.

The **Release** workflow builds `linux/amd64` and `linux/arm64` images,
publishes the `linux/amd64` default image as the `<version>` and `latest`
tags and the socket deployment's `linux/amd64,linux/arm64` web image as
`<version>-socket` / `latest-socket` in GitHub Container Registry, attaches
provenance and an SBOM, and creates a GitHub Release with automatically
generated release notes.

Cisco's `gisobuild` runtime image and all Cisco input/output artifacts are
outside the application images and must never be attached to a release. The
default image contains only the open-source `ios-xr/gisobuild` tool at a pinned
commit and SHA-256 manifest, never Cisco software images or packages.

## Deliberate out-of-sequence bumps and pre-releases

A normal release needs no action - it happens on the next push to `main`,
including the automatic rollover into a new minor or major version. To jump
ahead of where that rollover would naturally land (for example, releasing
`v1.0.0` for an announcement before the version has actually counted up to
it), or to publish a pre-release, run the **Release** workflow manually:

1. Merge through a pull request with required CI checks passing. Trusted
   same-repository `codex/*` pull requests are squash-merged automatically
   after successful CI; all other pull requests require an explicit merge.
2. Decide the next semantic version, such as `v1.3.0`.
3. Run the staging rehearsal and application container smoke test.
4. For build-path changes, record a successful licensed-ISO acceptance test.
5. Confirm `git status --short` is empty on `main` and `main` matches origin.
6. Open **Actions**, select **Release**, choose **Run workflow**, keep the branch
   set to `main`, enter the version, choose whether it is a pre-release, and run
   it. The workflow rejects invalid or existing versions and only creates the
   tag after its CI job succeeds.
7. Wait for the Release workflow to succeed.
8. Verify the GitHub Release, GHCR version tag, `latest` tag, the `-socket`
   tags, SBOM, provenance, and image pull on a clean host.

```bash
docker pull ghcr.io/patricklind/gisobuild-gui:vX.Y.Z
docker image inspect ghcr.io/patricklind/gisobuild-gui:vX.Y.Z \
  --format '{{json .RepoDigests}}'
```

Do not move or reuse a published tag. Correct a failed release with a new patch
version after fixing the cause - the next push to `main` does this
automatically once the fix lands, or run the manual workflow to do it sooner.
