# Security policy

## Supported version

Security fixes are applied to the latest release and the latest commit on
`main`. Older releases and unversioned container images are not supported.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not
open a public issue containing exploit details, Cisco software, configurations,
credentials, logs, or customer information.

## Deployment boundary

This application is designed for trusted, local operation and binds to
`127.0.0.1` by default. The default deployment (`giso-webui/compose.yaml`) has
no Docker socket, runs read-only with only the `SYS_CHROOT` capability, and
verifies its bundled gisobuild against a pinned SHA-256 manifest at build time
and at startup. The alternative `giso-webui/compose.socket.yaml` gives the web
container the Docker socket, which is equivalent to administrative access to the
Docker host. Do not expose either to an untrusted network or deploy it as a multi-user service without adding authentication,
authorization, TLS, and stronger workload isolation.

Cisco software images, RPMs, SMUs, generated Golden ISOs, and USB boot packages
must not be committed to this repository.

## Sensitive data

Treat Cisco software, embedded router configurations, ownership vouchers, key
requests, certificates, build logs, customer names, device identifiers, and
archive checksums as potentially sensitive. Keep `.env` local and never include
secrets in issues, pull requests, test fixtures, Graphify output, or releases.
Cisco API client secrets, OAuth tokens, session download URLs, EULA/K9 responses,
and download transaction identifiers must likewise remain server-side and out
of logs and persisted job history.

## Operational controls

- Keep the default localhost bind and exact `ALLOWED_HOSTS` values.
- Prefer the default deployment; with `compose.socket.yaml`, restrict access to
  the Docker host and its socket.
- Store archives and backups only in approved locations; automatic retention is
  not a secure-erasure guarantee for storage snapshots or external backups.
- Verify Cisco-provided hashes, generated checksums, and the exact supported
  upgrade path before a maintenance operation.
- Review dependency, container, and workflow changes before deployment.

See the [operations runbook](docs/operations.md) for backup, restore, logs, and
safe failure handling.
