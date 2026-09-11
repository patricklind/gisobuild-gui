# Genbrugelig GISO-buildguide til NCS5500

Denne guide bygger et NCS5500 Golden ISO med Docker. Scriptet kontrollerer inputfiler, finder optional RPM'er og SMU'er, frasorterer SMU'er som er markeret `Full` superseded i Cisco-readmefilerne og kører Cisco `gisobuild` i en x86_64-container.

## 1. Forbered mappen

Læg følgende under samme overordnede mappe:

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

SMU-downloads leveres ofte som `.tar`. Pak hver tar-fil ud i sin egen mappe, så både `.txt`-readme og `.rpm` ligger der. Brug kun pakker for præcis samme platform og IOS XR-release som base-ISO'en.

## 2. Kontrollér Cisco-advisory og downloadliste

Før build:

1. Find den berørte IOS XR-release og platform i advisory-tabellen.
2. Filtrér Cisco Software Download på den konkrete platform og release.
3. Download alle SMU'er, som Cisco viser som applicable/recommended.
4. Behold ældre SMU'er i inputmappen; scriptet frasorterer dem, når en nyere README udtrykkeligt angiver `Supercedes ... Full`.

Automatisk supersedence erstatter ikke en menneskelig applicability-kontrol. Hvis advisory og downloadlisten er uenige, bør Cisco TAC bekræfte pakken før produktion.

## 3. Krav

- Docker Desktop eller Docker Engine skal køre.
- Mindst cirka 25 GB ledig diskplads anbefales.
- Internetadgang til GitHub og Docker Hub første gang.
- På Apple Silicon anvendes Docker-emulering af Cisco-containerens x86_64-image. Det er normalt, at buildet tager 15-30 minutter.

Kontrollér Docker:

```bash
docker info
```

## 4. Kør buildet

Fra denne mappe:

```bash
chmod +x ./build-giso.sh

./build-giso.sh \
  --iso ./NCS5500-iosxr-k9-26.1.2/ncs5500-mini-x-26.1.2.iso \
  --label SEC_HARDENING_SEP2026
```

Standard-output bliver:

```text
output_gisobuild_SEC_HARDENING_SEP2026/
```

Hvis outputmappen allerede findes, stopper scriptet. Genbyg bevidst med:

```bash
./build-giso.sh \
  --iso ./NCS5500-iosxr-k9-26.1.2/ncs5500-mini-x-26.1.2.iso \
  --label SEC_HARDENING_SEP2026 \
  --clean
```

`--clean` tillades af sikkerhedsgrunde kun for outputmapper med navnet `output_gisobuild_*` ved siden af scriptet.

## 5. Godkend buildresultatet

Et vellykket build skal vise:

```text
RPM signature check [PASS]
RPM compatibility check [PASS]
Golden ISO creation SUCCESS
```

Kontrollér output:

```bash
ls -lh output_gisobuild_SEC_HARDENING_SEP2026/
cat output_gisobuild_SEC_HARDENING_SEP2026/checksums.json
cat output_gisobuild_SEC_HARDENING_SEP2026/rpms_packaged_in_giso.txt
```

Gem mindst disse artefakter sammen:

- Golden ISO-filen
- USB boot-pakken (`usb_boot-*.zip`), hvis den blev oprettet
- `checksums.json`
- `rpms_packaged_in_giso.txt`
- hele `logs/`-mappen

## 6. Overfør til routeren

Brug SFTP eller SCP i binær tilstand. Kontrollér altid checksum efter overførsel:

```text
dir harddisk:/<giso-fil>.iso
show md5 file /harddisk:/<giso-fil>.iso
```

Routerens MD5 skal være identisk med den MD5, scriptet udskriver. Start aldrig installationen ved checksumforskel.

## 7. Installér i et servicevindue

Udfør pre-checks via konsol eller OOB-management:

```text
show version
show platform
show redundancy
show install request
show install active summary
show filesystem
show alarms brief system active
```

Start derefter installationen uden `noprompt`:

```text
install replace harddisk:/<giso-fil>.iso
```

Efter reload kontrolleres software, platform, redundans, alarmer, interfaces og routing. Commit først, når efterkontrollen er godkendt:

```text
show install active summary
show install history last transaction verbose
install commit
show install committed summary
```

## Fejlfinding

- **Checksum mismatch:** Slet routerkopien, overfør igen med SFTP og verificér på ny.
- **0 RPMs found:** Repository skal indeholde fysiske RPM-filer, ikke symlinks.
- **Signature/compatibility failure:** Installér ikke. Læs `logs/gisobuild.log-*` og kontrollér platform, release og SMU-afhængigheder.
- **Docker image not found:** Kontrollér tilgængelige tags på Docker Hub og opdatér kun `--image`, når tagget er kompatibelt med den anvendte gisobuild-version.
