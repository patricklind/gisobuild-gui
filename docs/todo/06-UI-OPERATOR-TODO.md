# TODO — Operator UX

## Primary UX goal

The UI should immediately answer:

1. What base image did you find?
2. Which platform/release/build engine is it?
3. Which fixes will be included?
4. Is anything wrong?
5. Can I start the build?

## Normal workflow

### Step 1 — Files

- [ ] drag/drop ISO
- [ ] drag/drop TAR/RPM/SMU
- [ ] Cisco download integration
- [ ] automatic analysis starts immediately

### Step 2 — Review BuildPlan

Show:

- [ ] ISO
- [ ] release
- [ ] engine
- [ ] platform
- [ ] confidence/source
- [ ] CSC groups
- [ ] excluded packages
- [ ] warnings
- [ ] blockers
- [ ] expected output
- [ ] free disk estimate

### Step 3 — Build

- [ ] clear progress
- [ ] current phase
- [ ] cancellation
- [ ] friendly error
- [ ] technical details collapsed by default
- [ ] artifact download
- [ ] checksums
- [ ] build report

## Automatic by default

Do not ask for these unless ambiguous:

- [ ] platform
- [ ] architecture
- [ ] target release
- [ ] repo path
- [ ] package list
- [ ] build engine

## Expert settings

Keep advanced controls, but:

- [ ] capability-driven
- [ ] hide unsupported settings
- [ ] server validates everything
- [ ] warn before unsafe/manual overrides

## Explain decisions

Every exclusion must explain why:

- [ ] wrong release
- [ ] wrong platform
- [ ] wrong architecture
- [ ] superseded
- [ ] duplicate
- [ ] malformed metadata
- [ ] ambiguous metadata

## Confidence display

Use:

- [ ] `VERIFIED`
- [ ] `INFERRED`
- [ ] `UNKNOWN`

Examples:

- [ ] Platform — VERIFIED from ISO metadata
- [ ] Release — VERIFIED from ISO metadata
- [ ] RPM architecture — VERIFIED from RPM header
- [ ] CSC — INFERRED from filename
- [ ] Dependency closure — UNKNOWN until gisobuild validation

Never present heuristic guesses as verified facts.
