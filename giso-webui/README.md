# IOS XR GISO Web UI

Lokal Docker-webgrænseflade til `ios-xr/gisobuild`. UI'et eksponerer fælles, eXR- og LNT-parametre, YAML-mode, live build-log og download af artefakter.

## Start

Fra `giso-webui`:

```bash
mkdir -p output
docker compose up --build -d
```

Åbn <http://127.0.0.1:8080>.

Uploads, output, arkiv og build-arbejdsfiler gemmes i persistente Docker-volumes. GISO-arkivet ligger i `giso-webui_giso-archive`.

Efter et vellykket build kopieres Golden ISO og den eventuelle USB boot-pakke til arkivet og SHA-256-verificeres. Derefter slettes alle uploads, RPM/TAR-kilder, øvrige outputfiler og arbejdsfiler automatisk. Ved manglende ISO eller verifikationsfejl foretages oprydningen ikke.

Knappen **Clean temporary files** fjerner kun ufuldstændige uploaddele og midlertidige build-arbejdsmapper. Uploadede Cisco-filer og færdige images slettes aldrig af oprydningen.

Cisco `.tar`-filer er transportarkiver: UI'et pakker dem ud automatisk og sender kun de fundne `.rpm`-pakker til `--pkglist`. En tar-fil må ikke selv stå i pakkelisten.

## Stop

```bash
docker compose down
```

## Sikkerhed

Appen er kun bundet til localhost. Webcontaineren har adgang til Docker-socket for at kunne starte Cisco GISO-buildcontaineren. Buildcontaineren får kun input (read-only), output, værktøj (read-only) og arbejdsmappe monteret; Docker-socket videregives ikke. Eksponér aldrig porten på et ukontrolleret netværk; Docker-socket-adgang i webcontaineren svarer praktisk til administratoradgang på Docker-værten.

Webcontainerens eget root-filsystem er read-only, og alle Linux capabilities er fjernet. Kun de deklarerede data-, output-, arkiv- og arbejdsvolumes er skrivbare.

Standardgrænserne er 8 GiB per upload, 16 MiB per upload-chunk, 16 GiB udpakket tar, 10.000 tar-elementer og 10 MiB buildlog i hukommelsen. Symlinks, hardlinks og stier uden for udpakningsmappen afvises.
