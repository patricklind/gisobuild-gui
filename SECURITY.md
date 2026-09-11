# Security policy

## Supported version

Security fixes are applied to the latest commit on `main`.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not
open a public issue containing exploit details, Cisco software, configurations,
credentials, logs, or customer information.

## Deployment boundary

This application is designed for trusted, local operation and binds to
`127.0.0.1` by default. It has access to the Docker socket, which is equivalent
to administrative access to the Docker host. Do not expose it to an untrusted
network or deploy it as a multi-user service without adding authentication,
authorization, TLS, and stronger workload isolation.

Cisco software images, RPMs, SMUs, generated Golden ISOs, and USB boot packages
must not be committed to this repository.
