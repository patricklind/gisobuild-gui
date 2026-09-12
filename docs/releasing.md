# Release process

Tags matching `v*` trigger `.github/workflows/release.yml`. The workflow builds
`linux/amd64` and `linux/arm64` application images, publishes the version and
`latest` tags to GitHub Container Registry, attaches provenance and an SBOM, and
creates a GitHub Release from `RELEASE_NOTES.md`.

Cisco's `gisobuild` runtime image and all Cisco input/output artifacts are
outside the application image and must never be attached to a release.

## Release checklist

1. Merge through a pull request with required CI checks passing. Trusted
   same-repository `codex/*` pull requests are squash-merged automatically after
   successful CI; all other pull requests require an explicit merge.
2. Confirm the version and statements in `RELEASE_NOTES.md`.
3. Run the staging rehearsal and application container smoke test.
4. For build-path changes, record a successful licensed-ISO acceptance test.
5. Confirm `git status --short` is empty on `main` and `main` matches origin.
6. Create and push an annotated semantic-version tag:

   ```bash
   git tag -a v1.0.0 -m "GISO Builder v1.0.0"
   git push origin v1.0.0
   ```

7. Wait for both the CI and Release workflows to succeed.
8. Verify the GitHub Release, GHCR version tag, `latest` tag, SBOM, provenance,
   and image pull on a clean host.

Do not move or reuse a published tag. Correct a failed release with a new patch
version after fixing the cause.
