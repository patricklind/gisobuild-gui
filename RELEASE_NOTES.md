# Release notes — v1.0.0

First production-ready release of the Cisco IOS XR Golden ISO web interface.

## Highlights

- Builds and archives Golden ISO and supported USB boot artifacts.
- Validates platform-specific eXR and IOS XR7/LNT build options before execution.
- Provides safe upgrade and rollback documentation plus an isolated staging rehearsal.
- Persists job history in SQLite and records interrupted jobs after service restart.
- Deletes archives after 30 days and enforces a combined 50 GiB limit.
- Publishes a multi-architecture container image to GitHub Container Registry.

## Safety

The project does not include Cisco software and cannot validate a hardware
upgrade path. Use properly licensed images and Cisco documentation for the exact
platform and release. Test on equivalent lab hardware before production use.

## Acceptance evidence

A real NCS5500 25.1.2 build with 12 matching optional RPMs completed using
`ciscogisobuild/cisco-xr-gisobuild:2.3.4`:

- Golden ISO SHA-256: `95f3860b538c689ded4021d13679eb5f04177dc7ba9838f0034d6baae65410e7`
- USB boot ZIP SHA-256: `e4f24b053b38118b7de664155a6a71f2a6726746849f6cdf864c61c54510e0cc`

The isolated staging rehearsal also completed the pre-check, staged upgrade,
commit, rollback, recovery, and recommit sequence. It does not claim hardware
validation; that final step requires a matching lab router.
