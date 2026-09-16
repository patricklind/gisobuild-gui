# TODO — Testing & CI

## Unit tests

Cover:

- [ ] platform alias normalization
- [x] eXR capability discovery
- [x] LNT capability discovery
- [ ] ISO metadata detection
- [ ] filename fallback detection
- [ ] RPM metadata parsing
- [ ] CSC grouping
- [x] duplicate checksums
- [x] same filename/different content
- [ ] release mismatch
- [x] architecture mismatch (`test_rpm_architecture_mismatched_with_iso_is_rejected`,
      `test_rpm_architecture_matching_iso_is_accepted`,
      `test_unknown_iso_architecture_does_not_block_selection`; this was
      already implemented and tested by the merged ISO/RPM architecture
      change, just left unchecked here)
- [ ] incomplete CSC
- [ ] supersedence
- [ ] BuildPlan generation
- [ ] BuildPlan fingerprint
- [ ] inventory revision invalidation
- [ ] command generation
- [ ] artifact verification
- [ ] cleanup
- [ ] restart recovery
- [x] malicious paths (TAR traversal/symlink/hardlink/absolute-path members,
      `safe_data_path` traversal, and archive-delete traversal — see
      Security tests below for the specific tests)

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
- [x] cancel during builder preparation/pull
- [x] cancel during finalization
- [x] successful build preserves unrelated workspace inputs
- [ ] two uploaded ISOs never silently select the first candidate
- [ ] RPM CPU architecture must match the selected ISO/build architecture
- [x] package names containing glob metacharacters cannot select unintended files
- [x] duplicate basename + same hash is deterministic and keeps provenance
- [x] duplicate basename + different hash is a blocking conflict
- [x] upgrade-matrix aliases use the canonical platform resolver
- [x] bridge-SMU near-match does not satisfy exact package/CSC presence
- [x] discovery remains safe while cleanup/delete runs concurrently
- [x] auto-derived target release refreshes when base ISO changes
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

- [x] TAR traversal (`test_tar_path_traversal_is_rejected`; the protective
      code already existed, this section was just under-checked)
- [x] symlink archive member (`test_tar_symlink_member_is_rejected`,
      `test_tar_hardlink_member_is_rejected` — new, closing a real gap: the
      rejection code existed in both `extract_cisco_archive()` and the
      upload-completion TAR path, but nothing exercised it)
- [x] absolute path (`test_tar_absolute_path_member_is_rejected` — new)
- [x] oversized expansion (`test_tar_expansion_size_limit_is_enforced` — new,
      covers `MAX_EXTRACTED_BYTES` directly; the pre-existing
      `test_tar_extraction_requires_reserved_free_space` only covered the
      separate free-disk-space guard)
- [x] duplicate filename conflict
- [x] malicious job/artifact path (`test_archive_delete_rejects_path_traversal`,
      `test_path_traversal_is_rejected`; pre-existing, just under-checked)
- [x] package glob metacharacters
- [x] secret redaction (`test_cisco_config_only_exposes_availability` proves
      Cisco credentials never leave the config-check endpoint beyond a
      yes/no; `test_quoted_artifact_path_with_spaces_is_fully_redacted` and
      `test_build_output_is_redacted_and_written_to_service_log` cover
      filename/command redaction in logs)

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
- [x] Graphify freshness validation for code-changing PRs

Optional:

- [ ] Trivy image scan
- [ ] dependency vulnerability scan

## Graphify CI guard

- [x] Regenerate from the PR/head tracked source tree and compare the structural graph (commit metadata is intentionally ignored)
- [x] Fail the CI merge gate when tracked `graphify-out/graph.json` is stale
- [x] Verify `.graphifyignore` still excludes Cisco licensed/sensitive inputs and build outputs

## Merge policy

Package-selection or build-runner changes must not merge unless:

- [ ] unit tests pass
- [ ] integration tests pass
- [ ] Docker image builds
- [ ] regression suite passes
- [x] Graphify output is current when the change affects code/architecture
