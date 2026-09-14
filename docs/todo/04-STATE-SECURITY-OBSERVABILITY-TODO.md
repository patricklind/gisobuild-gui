# TODO — State, Security & Observability

## Persistent state

SQLite is acceptable for a single-node appliance.

Persist:

- [ ] jobs
- [ ] inventory
- [ ] metadata cache
- [ ] BuildPlans
- [ ] activity log
- [ ] artifact metadata
- [ ] inventory revision

- [ ] schema migrations
- [ ] restart recovery
- [ ] no critical state only in Python globals

## Job model

Explicit states:

- [ ] queued
- [ ] analyzing
- [ ] preflight
- [ ] building
- [ ] verifying
- [ ] archiving
- [ ] success
- [ ] failed
- [ ] cancelling
- [ ] cancelled
- [ ] interrupted

## Concurrency

Guarantee:

- [ ] build/upload cannot corrupt same inventory
- [ ] cleanup cannot remove active inputs
- [ ] archive maintenance cannot delete active artifact
- [ ] Cisco download cannot collide with cleanup
- [ ] restart recovery is deterministic

## Path security

Audit every:

- [ ] filename
- [ ] relative path
- [ ] archive member
- [ ] job ID
- [ ] artifact path

Protect against:

- [ ] `../`
- [ ] absolute paths
- [ ] symlink escapes
- [ ] Unicode normalization tricks
- [ ] duplicate aliases

## Cisco secrets

- [ ] never return secrets to browser
- [ ] never log secrets
- [ ] never store secrets in jobs
- [ ] never bake secrets into image
- [ ] prefer secret files
- [ ] browser sees only configured yes/no

## Structured logging

Every event should support:

- [ ] request_id
- [ ] job_id
- [ ] inventory_revision
- [ ] plan_fingerprint
- [ ] event
- [ ] duration
- [ ] result

## Error taxonomy

Implement codes such as:

- [ ] `UPLOAD_ERROR`
- [ ] `ARCHIVE_ERROR`
- [ ] `ISO_METADATA_ERROR`
- [ ] `PLATFORM_AMBIGUOUS`
- [ ] `RELEASE_MISMATCH`
- [ ] `RPM_METADATA_ERROR`
- [ ] `RPM_ARCH_MISMATCH`
- [ ] `CSC_INCOMPLETE`
- [ ] `DUPLICATE_CONFLICT`
- [ ] `DEPENDENCY_ERROR`
- [ ] `GISOBUILD_ERROR`
- [ ] `OUTPUT_VALIDATION_ERROR`
- [ ] `STORAGE_ERROR`
- [ ] `CISCO_AUTH_ERROR`

Return:

- [ ] code
- [ ] human_message
- [ ] technical_message
- [ ] recoverable
- [ ] suggested_action

## Health and readiness

### `/api/health`

- [ ] process alive

### `/api/ready`

- [ ] storage
- [ ] gisobuild
- [ ] binaries
- [ ] DB/state
- [ ] free disk
- [ ] no fatal startup error

## Startup self-test

- [ ] gisobuild exists
- [ ] required binaries exist
- [ ] DB schema valid
- [ ] writable directories
- [ ] alias/config data valid
- [ ] minimum free storage
- [ ] architecture supported

## Caching

Cache expensive metadata by:

- [ ] path
- [ ] size
- [ ] mtime
- [ ] checksum where known

Do not repeatedly rehash multi-GB files on browser refresh.
