# Reusable GISO Build Guide for NCS5500

This guide builds an NCS5500 Golden ISO with Docker. The script validates input files, discovers optional RPMs and SMUs, excludes SMUs marked as `Full` superseded in Cisco README files, and runs Cisco `gisobuild` in an x86_64 container.

## 1. Prepare the directory

Place the following files below the same parent directory:

```text
NCS5500-iosxr-k9-26.1.2/
  ncs5500-mini-x-26.1.2.iso
  README-NCS5500-iosxr-k9-26.1.2.txt
  optional-rpms/
    ...

ncs5500-26.1.2.CSCxxxxxxx/
  ncs5500-26.1.2.CSCxxxxxxx.txt
  *.rpm
```

SMU downloads are often distributed as `.tar` archives. Extract each archive into its own directory so that the `.txt` README and `.rpm` files remain together. Use only packages for the exact same platform and IOS XR release as the base ISO.

## 2. Verify the Cisco advisory and download list

Before building:

1. Find the affected IOS XR release and platform in the advisory table.
2. Filter Cisco Software Download for the specific platform and release.
3. Download every SMU Cisco lists as applicable or recommended.
4. Keep older SMUs in the input directory. The script excludes them when a newer README explicitly marks them as `Supercedes ... Full`.

Automated supersedence handling does not replace a manual applicability review. If the advisory and download list disagree, ask Cisco TAC to confirm the package before production use.

## 3. Requirements

- Docker Desktop or Docker Engine must be running.
- Approximately 25 GB of free disk space is recommended.
- Internet access to GitHub and Docker Hub is required for the first run.
- On Apple Silicon, Docker emulates Cisco's x86_64 container image. A build time of 15–30 minutes is normal.

Verify Docker:

```bash
docker info
```

## 4. Run the build

From the project directory:

```bash
chmod +x ./build-giso.sh

./build-giso.sh \
  --iso ./NCS5500-iosxr-k9-26.1.2/ncs5500-mini-x-26.1.2.iso \
  --label SEC_HARDENING_SEP2026
```

The default output directory is:

```text
output_gisobuild_SEC_HARDENING_SEP2026/
```

The script stops if the output directory already exists. To rebuild intentionally, run:

```bash
./build-giso.sh \
  --iso ./NCS5500-iosxr-k9-26.1.2/ncs5500-mini-x-26.1.2.iso \
  --label SEC_HARDENING_SEP2026 \
  --clean
```

For safety, `--clean` may only replace an `output_gisobuild_*` directory located next to the script.

## 5. Validate the build result

A successful build should report:

```text
RPM signature check [PASS]
RPM compatibility check [PASS]
Golden ISO creation SUCCESS
```

Inspect the output:

```bash
ls -lh output_gisobuild_SEC_HARDENING_SEP2026/
cat output_gisobuild_SEC_HARDENING_SEP2026/checksums.json
cat output_gisobuild_SEC_HARDENING_SEP2026/rpms_packaged_in_giso.txt
```

Keep at least these artifacts together:

- The Golden ISO file
- The USB boot package (`usb_boot-*.zip`), if created
- `checksums.json`
- `rpms_packaged_in_giso.txt`
- The complete `logs/` directory

## 6. Transfer the image to the router

Use SFTP or SCP in binary mode. Always verify the checksum after transfer:

```text
dir harddisk:/<giso-file>.iso
show md5 file /harddisk:/<giso-file>.iso
```

The router's MD5 must match the MD5 produced by the script. Never begin installation if the checksums differ.

## 7. Install during a maintenance window

Run pre-checks through the console or out-of-band management:

```text
show version
show platform
show redundancy
show install request
show install active summary
show filesystem
show alarms brief system active
```

Start the installation without `noprompt`:

```text
install replace harddisk:/<giso-file>.iso
```

After the reload, verify software, platform, redundancy, alarms, interfaces, and routing. Commit only after all post-checks succeed:

```text
show install active summary
show install history last transaction verbose
install commit
show install committed summary
```

## Troubleshooting

- **Checksum mismatch:** Delete the router copy, transfer it again with SFTP, and verify it again.
- **0 RPMs found:** The repository must contain physical RPM files, not symlinks.
- **Signature or compatibility failure:** Do not install the image. Inspect `logs/gisobuild.log-*` and verify the platform, release, and SMU dependencies.
- **Docker image not found:** Review the available Docker Hub tags. Change `--image` only when the tag is compatible with the installed `gisobuild` version.

## Disclaimer

This tooling is provided without warranty and is used at your own risk. You are responsible for validating Cisco compatibility, checksums, backups, maintenance procedures, and recovery plans. The authors accept no liability for outages, data loss, device failure, or other damage.
