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
- [ ] cancel during builder preparation/pull
- [ ] cancel during finalization
- [ ] successful build preserves unrelated workspace inputs
- [ ] two uploaded ISOs never silently select the first candidate
- [ ] RPM CPU architecture must match the selected ISO/build architecture
- [ ] package names containing glob metacharacters cannot select unintended files
- [ ] duplicate basename + same hash is deterministic and keeps provenance
- [ ] duplicate basename + different hash is a blocking conflict
- [ ] upgrade-matrix aliases use the canonical platform resolver
- [ ] bridge-SMU near-match does not satisfy exact package/CSC presence
- [ ] discovery remains safe while cleanup/delete runs concurrently
- [ ] auto-derived target release refreshes when base ISO changes
- [ ] cached builder behavior is defined when registry access fails during the migration period

See `07-BUG-AUDIT-TODO.md` for the implementation details and failure scenarios behind these tests.

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
- [ ] cancellation state-machine integration
- [ ] multiple-build-inventory isolation integration

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
- [ ] multiple ISO ambiguity blocks Build
- [ ] duplicate RPM basename conflict is visible
- [ ] ISO switch refreshes auto-derived release

## Security tests

- [ ] TAR traversal
- [ ] symlink archive member
- [ ] absolute path
- [ ] oversized expansion
- [ ] duplicate filename conflict
- [ ] malicious job/artifact path
- [ ] package glob metacharacters
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
- [ ] Graphify freshness validation for code-changing PRs

Optional:

- [ ] Trivy image scan
- [ ] dependency vulnerability scan

## Graphify CI guard

- [ ] Compare Graphify's recorded source revision with the PR/head revision after relevant code changes
- [ ] Fail or clearly block merge when tracked `graphify-out/` is stale
- [ ] Verify `.graphifyignore` still excludes Cisco licensed/sensitive inputs and build outputs

## Merge policy

Package-selection or build-runner changes must not merge unless:

- [ ] unit tests pass
- [ ] integration tests pass
- [ ] Docker image builds
- [ ] regression suite passes
- [ ] Graphify output is current when the change affects code/architecture
