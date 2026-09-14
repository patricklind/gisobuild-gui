# TODO — Automation, Inventory & BuildPlan

## Canonical inventory

Create one canonical inventory model.

- [ ] every file receives stable ID
- [ ] basename
- [ ] relative path
- [ ] absolute path
- [ ] size
- [ ] SHA-256
- [ ] source (`upload`, `tar`, `cisco-download`)
- [ ] metadata source/confidence
- [ ] lifecycle state

Suggested lifecycle:

- [ ] `UPLOADING`
- [ ] `READY`
- [ ] `ANALYZING`
- [ ] `VALID`
- [ ] `INVALID`
- [ ] `IN_USE`
- [ ] `ARCHIVED`
- [ ] `DELETING`

## ISO inspection

Detection order:

- [ ] ISO metadata
- [ ] upstream gisobuild inspection/isoinfo
- [ ] image/package metadata
- [ ] known platform signatures
- [ ] hardware PID mapping
- [ ] filename inference
- [ ] manual override

Return:

- [ ] release
- [ ] platform identifier
- [ ] engine
- [ ] architecture
- [ ] detected_by
- [ ] confidence

## RPM inspection

Prefer metadata over filename parsing.

- [ ] RPM name
- [ ] version
- [ ] release
- [ ] architecture
- [ ] provides
- [ ] requires
- [ ] signature metadata where available
- [ ] CSC ID
- [ ] component
- [ ] metadata confidence

## TAR/TGZ handling

- [ ] safe extraction
- [ ] reject traversal
- [ ] reject symlinks/hardlinks
- [ ] expansion-size limit
- [ ] member-count limit
- [ ] source provenance
- [ ] no duplicate extraction
- [ ] automatically inventory extracted RPMs

## CSC grouping

- [ ] group packages by CSC
- [ ] select complete groups by default
- [ ] warn/block incomplete CSC groups
- [ ] show components
- [ ] preserve exclusion reason
- [ ] advanced RPM-level manipulation only in Expert mode

## Duplicate handling

- [ ] same filename + same SHA → deduplicate
- [ ] same filename + different SHA → hard error
- [ ] multiple versions same component → conflict
- [ ] overlapping CSCs → show conflict/supersedence

## Supersedence

Create an explicit supersedence model.

- [ ] bundle metadata
- [ ] RPM metadata
- [ ] README metadata
- [ ] compatibility metadata
- [ ] gisobuild dependency output

Never silently exclude without a reason.

## Unified selection engine

- [ ] automatic mode and manual mode use the same backend model
- [ ] manual mode modifies BuildPlan
- [ ] no separate incompatible selection path
- [ ] never submit workspace paths as package identifiers

## BuildPlan

Create backend-owned immutable BuildPlan.

Required content:

- [ ] base ISO metadata/checksum
- [ ] engine
- [ ] release
- [ ] platform
- [ ] selected packages
- [ ] selected CSC groups
- [ ] excluded packages + reasons
- [ ] capabilities
- [ ] options
- [ ] blockers
- [ ] warnings
- [ ] inventory revision
- [ ] plan fingerprint

## BuildPlan fingerprint

Hash together:

- [ ] ISO checksum
- [ ] selected RPM checksums
- [ ] configuration files
- [ ] gisobuild version/commit
- [ ] application version
- [ ] build options

## Inventory revision

- [ ] increment after upload
- [ ] increment after extraction
- [ ] increment after delete
- [ ] increment after cleanup
- [ ] increment after Cisco download
- [ ] invalidate BuildPlan if revision changes
- [ ] frontend never owns authoritative build state

## Automatic refresh

After upload/download:

- [ ] classify
- [ ] checksum
- [ ] extract if needed
- [ ] inspect metadata
- [ ] refresh inventory
- [ ] refresh recommendation
- [ ] regenerate BuildPlan
- [ ] update UI automatically

"Check files again" and "Recalculate" become troubleshooting controls only.

## Preflight

One authoritative preflight must decide whether Build is enabled.

- [ ] base image valid
- [ ] engine known
- [ ] release known
- [ ] compatible package set
- [ ] duplicate conflicts resolved
- [ ] CSC completeness checked
- [ ] disk space sufficient
- [ ] gisobuild available
- [ ] required tools available
- [ ] no conflicting job
- [ ] expected outputs supported
