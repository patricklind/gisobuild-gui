# TODO — Testing & CI

## Unit tests

Cover:

- [ ] platform alias normalization
- [ ] eXR capability discovery
- [ ] LNT capability discovery
- [ ] ISO metadata detection
- [ ] filename fallback detection
- [ ] RPM metadata parsing
- [ ] CSC grouping
- [ ] duplicate checksums
- [ ] same filename/different content
- [ ] release mismatch
- [ ] architecture mismatch
- [ ] incomplete CSC
- [ ] supersedence
- [ ] BuildPlan generation
- [ ] BuildPlan fingerprint
- [ ] inventory revision invalidation
- [ ] command generation
- [ ] artifact verification
- [ ] cleanup
- [ ] restart recovery
- [ ] malicious paths

## Representative platform fixtures

Use synthetic/mocked fixtures, not licensed Cisco artifacts.

- [ ] ASR9000
- [ ] NCS1000-class where applicable
- [ ] NCS5000
- [ ] NCS540
- [ ] NCS5500
- [ ] NCS560
- [ ] NCS6000 where pinned upstream supports it
- [ ] NCS5700 / NCS57C3 class
- [ ] Cisco 8000-class LNT
- [ ] XRv9000
- [ ] whitebox variants where upstream supports them
- [ ] unknown/future upstream-supported platform

## Regression tests

Mandatory regression coverage for:

- [ ] manual RPM path vs basename bug
- [ ] manual mode empty-selection bug
- [ ] CSC group selection mismatch
- [ ] "No RPM packages uploaded" despite inventory containing compatible RPMs
- [ ] NCS-57C3 SKU normalization

## Integration test

Synthetic workflow:

```text
upload
→ extract
→ inspect
→ inventory
→ BuildPlan
→ mocked gisobuild
→ output verification
→ archive
```

- [ ] eXR integration
- [ ] LNT integration

## Browser/DOM tests

- [ ] automatic selection
- [ ] manual CSC selection
- [ ] upload while manual mode open
- [ ] manual → automatic
- [ ] inventory refresh
- [ ] no RPM state
- [ ] failed compatibility
- [ ] successful preflight
- [ ] Build button enable/disable
- [ ] unknown platform presentation

## Security tests

- [ ] TAR traversal
- [ ] symlink archive member
- [ ] absolute path
- [ ] oversized expansion
- [ ] duplicate filename conflict
- [ ] malicious job/artifact path
- [ ] secret redaction

## CI pipeline

Run:

- [ ] Python tests
- [ ] JS/DOM tests
- [ ] lint
- [ ] formatting check
- [ ] static security checks
- [ ] Docker build
- [ ] synthetic eXR integration
- [ ] synthetic LNT integration
- [ ] SBOM generation

Optional:

- [ ] Trivy image scan
- [ ] dependency vulnerability scan

## Merge policy

Package-selection or build-runner changes must not merge unless:

- [ ] unit tests pass
- [ ] integration tests pass
- [ ] Docker image builds
- [ ] regression suite passes
