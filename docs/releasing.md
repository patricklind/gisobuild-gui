# Release process

Published versions are listed on the
[GitHub Releases page](https://github.com/patricklind/gisobuild-gui/releases).
The current documentation follows `main`; use the matching Git tag when
operating an older release.

The **Release** workflow can create both the version tag and GitHub Release from
the GitHub Actions page. It runs the complete CI workflow first, creates an
annotated semantic-version tag, builds `linux/amd64` and `linux/arm64`
application images, publishes the version and `latest` tags to GitHub Container
Registry, attaches provenance and an SBOM, and creates a GitHub Release with
automatically generated release notes. A manually pushed tag matching `v*`
continues to trigger the same verified image and release process.

Cisco's `gisobuild` runtime image and all Cisco input/output artifacts are
outside the application image and must never be attached to a release.

## Release checklist

1. Merge through a pull request with required CI checks passing. Trusted
   same-repository `codex/*` pull requests are squash-merged automatically after
   successful CI; all other pull requests require an explicit merge.
2. Decide the next semantic version, such as `v1.2.3`.
3. Run the staging rehearsal and application container smoke test.
4. For build-path changes, record a successful licensed-ISO acceptance test.
5. Confirm `git status --short` is empty on `main` and `main` matches origin.
6. Open **Actions**, select **Release**, choose **Run workflow**, keep the branch
   set to `main`, enter the version, choose whether it is a pre-release, and run
   it. The workflow rejects invalid or existing versions and only creates the
   tag after its CI job succeeds.
7. Wait for the Release workflow to succeed.
8. Verify the GitHub Release, GHCR version tag, `latest` tag, SBOM, provenance,
   and image pull on a clean host.

```bash
docker pull ghcr.io/patricklind/gisobuild-gui:vX.Y.Z
docker image inspect ghcr.io/patricklind/gisobuild-gui:vX.Y.Z \
  --format '{{json .RepoDigests}}'
```

Do not move or reuse a published tag. Correct a failed release with a new patch
version after fixing the cause.
