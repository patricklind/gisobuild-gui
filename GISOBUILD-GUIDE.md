# Cisco IOS XR Golden ISO Build and Upgrade Guide

[Project setup](README.md) · [Platform matrix](docs/platform-support.md) ·
[Testing levels](docs/testing.md) · [Operations](docs/operations.md)

This guide covers the common workflow for building, validating, transferring,
installing, and rolling back a Golden ISO (GISO) across Cisco IOS XR platforms.
It is platform-aware: Cisco command syntax, image limits, supported packages,
and upgrade paths vary by router family and release.

> [!CAUTION]
> Never treat an installation command as universal. Before a production change,
> read the Cisco System Setup and Software Installation Guide and release notes
> for the exact platform, source release, target release, route processor, and
> hardware inventory. Confirm uncertain upgrade paths with Cisco TAC.

> [!WARNING]
> This project does not provide Cisco software. Use only properly licensed files
> obtained for the exact platform and release. Do not rename a completed GISO.

## 1. Determine the platform and install architecture

Collect this information from the router before downloading or building files:

```text
show version
show platform
show inventory
show redundancy
show install active summary
show install committed summary
show install request
show install history last transaction verbose
show filesystem
show alarms brief system active
```

Use the output to identify:

- Router family and exact product IDs (PIDs)
- Current IOS XR release and architecture
- Active and committed package sets
- Redundancy state and available disk space
- Whether an install operation is already pending

The current `ios-xr/gisobuild` project handles eXR/IOS XR 64-bit and LNT/IOS XR7
images, with some options restricted to one architecture. Examples include
`--migration` for ASR 9000 migration builds, `--full-iso` for IOS XRv 9000,
and `--skip-usb-image` or `--remove-packages` for LNT builds.

The Web UI validates the eXR families declared by the upstream tool—ASR 9000,
NCS 1000/1001/1004, NCS 5000/540/5500/560/6000, IOS XR whitebox, and XRv9K—plus
the metadata-driven IOS XR7 families Cisco 8000/8800, NCS 1010/1014, NCS 540L,
and NCS 5700. This catches obvious option mistakes; inspect ISO metadata with
upstream `isols.py --dump-mdata` before using PID filtering.

See the maintained [platform matrix](docs/platform-support.md) for the exact UI
selection keys, option gates, and automatic USB expectations.

### Installation command families

| Router software family | Typical workflow | Important note |
| --- | --- | --- |
| Modern IOS XR7/LNT | `install package replace`, then `install apply`, then `install commit` | Provides control over when changes are applied; confirm whether `reload` or `restart` is required. |
| IOS XR 64-bit/eXR 6.5.2 and later | `install replace <absolute-GISO-path>` | The operation can apply or reload automatically depending on platform and release. |
| Older IOS XR releases | Legacy `install update source ... replace` workflow | Use only the exact syntax in the release-specific Cisco guide. |
| ASR 9000 32-bit to 64-bit migration | Dedicated migration procedure and migration TAR | This is not a normal GISO replacement. Follow Cisco's ASR 9000 migration guide. |

Cisco 8000, NCS 1010, and newer IOS XR7 documentation may offer both an
immediate `install replace` workflow and a staged `install package replace`
workflow. Prefer the staged workflow when the release supports it and operational
control of the apply/reload point is required.

## 2. Validate the supported upgrade path

Before building:

1. Open the Cisco release notes and installation guide for the target release.
2. Confirm that a direct upgrade from the source release is supported.
3. Check for mandatory intermediate releases, ROMMON/BIOS/FPD requirements, and
   required bridging bug-fix RPMs.
4. Check platform-specific GISO size and filename limits.
5. Confirm that every optional package and SMU matches the base ISO platform,
   release, architecture, and signing requirements.
6. Review Cisco field notices and open caveats that apply to the hardware.
7. Record the rollback method and the last known-good committed transaction.

Do not mix RPMs from different platforms or target releases. Do not assume a
package is applicable merely because the build tool accepts it. For upgrades or
downgrades that need bridging fixes, include the fixes for the active source
release as directed by Cisco.

## 3. Prepare the build inputs

Use a separate directory for each platform and target release:

```text
inputs/
  <platform>-<target-release>/
    <platform>-<base-or-mini-image>.iso
    README-<platform>-<release>.txt
    optional-rpms/
      *.rpm
    smus/
      <bug-id>/
        *.rpm
        *.txt
    bridging-fixes/
      <source-release>/
        *.rpm
    config/
      xr-config.cfg
      ztp.ini
```

SMUs are often delivered in tar archives. The Web UI extracts supported tar
uploads safely. For manual builds, extract each archive while keeping its RPM
and Cisco README together. Validate Cisco-provided hashes before using a file.

Configuration embedded in a GISO can be applied during boot or installation.
The build tool does not prove that the configuration is operationally correct;
validate it separately and omit it when it is not required.

## 4. Build the GISO

### Recommended: Web UI

Start the local application:

```bash
git clone --depth 1 https://github.com/ios-xr/gisobuild.git .gisobuild-tool
cd giso-webui
cp .env.example .env
docker compose up --build -d
```

Open <http://127.0.0.1:8080>, upload the base ISO and packages, select only the
options valid for the detected image architecture, and start the build. The UI
supports ISO and optional USB artifact archiving, SHA-256 verification, a 30-day
retention period, and a 50 GiB combined archive quota by default.

The default package mode selects only RPMs whose filename proves the same
platform and release as the base ISO. Expert settings show CSC package groups,
component overlap, processor architecture, duplicate versions, and optional
upgrade-matrix bridge SMUs. These deterministic checks catch obvious bad mixes;
Cisco `gisobuild` remains authoritative for dependencies and supersedence. Use
manual package selection only with an approved Cisco package list.

`Clear workspace files` removes uploads, partial uploads, work directories and
raw failed-build output. It also clears the corresponding persisted diagnostic
download links from the build view and job history. Verified ISO and USB links
under the GISO Archive are preserved until retention or quota cleanup removes
the archive.

### Direct `gisobuild.py` workflow

The upstream tool supports CLI and YAML input. A representative CLI build is:

```bash
./src/gisobuild.py \
  --iso /absolute/path/to/base.iso \
  --repo /absolute/path/to/rpm-repository \
  --pkglist package-one.rpm package-two.rpm \
  --label CHANGE_1234 \
  --out-directory /absolute/path/to/output \
  --create-checksum \
  --clean
```

Use `./src/gisobuild.py --help` from the checked-out version before building.
Do not copy architecture-specific options between platforms without confirming
support. The upstream `gisobuild_options.yaml` file is the starting template for
YAML-driven builds.

### Bundled NCS5500 helper

`build-giso.sh` automates an NCS5500 directory convention and package naming
pattern. It is not a universal wrapper for all IOS XR platforms.

```bash
chmod +x ./build-giso.sh
./build-giso.sh \
  --iso ./NCS5500-iosxr-k9-<release>/ncs5500-mini-x-<release>.iso \
  --label CHANGE_1234
```

Use the Web UI or upstream tool directly for ASR 9000, Cisco 8000, NCS 1000,
NCS 500/540/560, NCS 5500/5700, IOS XRv 9000, and other supported image families
unless you have deliberately adapted and tested the helper's discovery rules.

## 5. Validate the build output

A successful process should complete signature, compatibility, dependency, and
Golden ISO creation checks. Review the logs even when the command exits cleanly.

```bash
find output_gisobuild* -maxdepth 2 -type f -print
cat output_gisobuild*/checksums.json
cat output_gisobuild*/rpms_packaged_in_giso.txt
```

Keep these items in the change record:

- Original GISO filename, size, MD5, and SHA-256
- Optional USB boot package and checksum
- Packaged RPM/SMU inventory
- Complete build logs
- Source and target release information
- Build tool commit and container image identifier
- Change approval, rollback plan, and validation evidence

Do not install when a signature, dependency, compatibility, or checksum check
fails. Do not rename the generated ISO after validation.

## 6. Prepare the router and change window

Before transfer or installation:

1. Back up the running configuration and operational state.
2. Verify out-of-band console access and recovery media.
3. Confirm both route processors and all critical cards are healthy.
4. Resolve active alarms and pending install operations.
5. Confirm adequate space in an approved local filesystem such as `harddisk:`.
6. Confirm the maintenance window allows for package staging, reload, rollback,
   and post-change observation.
7. Disable automation that could conflict with reload or configuration changes.

Transfer the GISO with SCP, SFTP, HTTPS, or another method supported by the
specific platform and release. Use binary transfer and compare the router-side
checksum with the recorded build checksum:

```text
dir harddisk:
show md5 file /harddisk:/<giso-file>.iso
```

Never proceed if the filename, size, or checksum differs.

## 7. Install the GISO

### Option A: staged IOS XR7 workflow

Use this only when the platform and release documentation supports these
commands. Staging separates package preparation from the disruptive apply step:

```text
install package replace /harddisk:/<giso-file>.iso
show install request
install apply reload
```

For a small same-release package change, Cisco may permit `install apply restart`
instead. Use `show install request` and the platform guide to determine the
required action. Do not substitute `restart` merely to avoid a reload.

After the router returns and validation succeeds:

```text
install commit
show install committed summary
```

### Option B: immediate replace workflow

Many eXR and IOS XR7 releases support:

```text
install replace /harddisk:/<giso-file>.iso
```

This workflow can apply changes and trigger a restart or reload as soon as
package preparation completes. Add `commit`, `reload`, or `noprompt` only when
the exact platform guide documents the option and the change plan requires it.
Avoid `noprompt` during manual supervised changes.

### Option C: legacy releases

Some releases before IOS XR 6.5.2 use a form of:

```text
install update source <absolute-source-path> <giso-name> replace
```

Syntax and prerequisites differ. Copy the exact command from the release-specific
Cisco guide instead of adapting a modern example.

### ASR 9000 32-bit to 64-bit migration

Do not use the normal replacement examples. Cisco requires a dedicated migration
workflow and, for supported releases, a migration TAR built with the ASR 9000
GISO migration option. Intermediate releases, filename length, image size, and
hardware restrictions can apply.

## 8. Post-upgrade validation

After the router returns, compare the same checks collected before the change:

```text
show version
show platform
show redundancy
show install active summary
show install committed summary
show install history last transaction verbose
show alarms brief system active
show interfaces summary
show logging last 100
```

Also validate platform-specific services, routing adjacencies, forwarding,
telemetry, timing, optics, licensing, and application traffic. Confirm embedded
configuration only if the GISO intentionally contained one.

Do not run `install commit` until the target image, packages, hardware, control
plane, and traffic checks pass. Observe the router for the duration required by
the approved change plan.

## 9. Rollback and recovery

Rollback is a separate maintenance operation. Do not assume that “abort,”
“rollback,” and “boot the old ISO” are interchangeable. First identify whether
the package request is pending, applied but uncommitted, or committed.

Capture the current state and available transactions before the upgrade and
again before rollback:

```text
show install request
show install active summary
show install committed summary
show install rollback list-ids
show install history
```

### IOS XR7/LNT: pending request

If a package operation has been prepared but not applied, supported releases can
abort the latest request:

```text
show install request
install package abort latest
```

Some releases also support `all-since-apply`. Confirm the available keywords
with contextual `?` help. Abort is not a rollback for software already applied.

### IOS XR7/LNT: saved transaction

Inspect a candidate transaction before selecting it:

```text
show install rollback list-ids
show install rollback id <TRANSACTION-ID> changes
install package rollback <TRANSACTION-ID>
show install request
install apply reload
```

The staged `install package rollback` form does not apply the change immediately.
Use `show install request` and the release-specific guide to determine whether
`reload` or `restart` is required. Some releases also provide an immediate
`install rollback <TRANSACTION-ID>` form that applies automatically and may
reload the router.

After the router returns, perform the complete post-upgrade validation. Commit
only when the recovered state is healthy:

```text
install commit
show install committed summary
```

### IOS XR 64-bit/eXR

Available rollback points and syntax vary across releases. Common command
patterns include:

```text
show install rollback ?
install rollback to committed
install rollback to <ROLLBACK-POINT>
```

Run them only in the mode and form documented for the exact router release.
Rollback can require a reload of impacted nodes and can restore configuration
state associated with the selected software set.

### Legacy IOS XR and ASR 9000 migration

Do not adapt IOS XR7 commands. Use the exact rollback, ROMMON, eUSB, migration,
or disaster-recovery procedure for the source and target architecture. Preserve
the last-known-good image, configuration, console access, and recovery media.
Contact Cisco TAC when a supported migration rollback path is not explicit.

If the router cannot boot normally, use the platform's documented USB, PXE,
ROMMON, or disaster-recovery procedure. A generated USB ZIP is not automatically
valid for every router family, route processor, or boot mode.

## Troubleshooting

- **No packages found:** Confirm RPM files are physical files, match the ISO,
  and are included in the selected repository or package list.
- **Dependency or compatibility failure:** Stop. Check bridging fixes, optional
  base packages, architecture, release alignment, and `gisobuild.log`.
- **GISO exceeds platform limits:** Remove unnecessary packages only after
  verifying requirements. ASR 9000 route processors can have specific limits.
- **USB artifact is absent:** USB output is platform-dependent and may be skipped
  or unsupported. Use the platform recovery guide.
- **Install command is rejected:** Re-check whether the router uses the eXR or
  IOS XR7 package-management command family and consult contextual `?` help.
- **Reload requirement is unexpected:** Review `show install request`; package
  differences and restart types determine whether a process restart is enough.
- **Build succeeds but a package is missing:** Compare
  `rpms_packaged_in_giso.txt` with the approved package manifest before transfer.

## Official references

- [`ios-xr/gisobuild` source and usage](https://github.com/ios-xr/gisobuild)
- [Cisco ASR 9000 GISO guide, IOS XR 7.9.x](https://www.cisco.com/c/en/us/td/docs/routers/asr9000/software/asr9k-r7-9/system-setup/configuration/guide/b-system-setup-cg-asr9000-79x/customize-install-using-giso.html)
- [Cisco ASR 9000 32-bit to 64-bit migration guide](https://www.cisco.com/c/en/us/td/docs/routers/asr9000/migration/guide/b-migration-to-ios-xr-64-bit/m-migration-overview.html)
- [Cisco 8000 setup and upgrade guide](https://www.cisco.com/c/en/us/td/docs/iosxr/cisco8000/b-setup-and-upgrade-cisco8k.pdf)
- [Cisco NCS 540 GISO guide, IOS XR 7.7.x](https://www.cisco.com/c/en/us/td/docs/iosxr/ncs5xx/system-setup/77x/b-system-setup-cg-77x-ncs540/build-and-install-golden-iso.html)
- [Cisco NCS 1010 software upgrade methods](https://www.cisco.com/c/en/us/td/docs/optical/ncs1010/system-setup-install/system-setup-software-install-guide/upgrade-wrapper/upgrade-software.html)
- [Cisco IOS XRv 9000 GISO guide](https://www.cisco.com/c/en/us/td/docs/routers/virtual-routers/configuration/guide/b-xrv9k-cg/m-golden-iso-xrv9k.html)

Always replace these examples with the documentation for the exact target
release. Cisco changes supported paths, prerequisites, and command behavior over
time.

## Disclaimer

This guide and tooling are provided without warranty and are used at your own
risk. You are responsible for validating Cisco compatibility, licensing,
checksums, backups, maintenance procedures, rollback, and recovery plans. The
authors accept no liability for outages, data loss, device failure, or damage.
