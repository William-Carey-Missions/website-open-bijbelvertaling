# Externe assets

Grote binaire audiobestanden staan niet in Git. Ze worden publiek aangeboden
vanaf:

```text
https://kleineark.com/assets/openvertaling/audio/
```

Op de server verwijst Nginx dit URL-pad naar:

```text
/srv/openvertaling/assets/audio/
```

De algemene browserresolver staat in `js/assets.js`. Alle runtimecode bouwt
asset-URL's met `window.OV_ASSETS.url(...)`; verander bij een verhuizing alleen
de basis-URL in dat bestand. Een host die de standaard wil overschrijven kan
vóór `js/assets.js` een `window.OV_ASSET_BASE_URL` instellen.

## Lokale ontwikkeling

Een lokale kopie van de audio is niet nodig. Start de statische site normaal:

```bash
python3 -m http.server 8000
```

Ook vanaf `http://localhost:8000` haalt de browser audio bij Kleine Ark op. De
assetlocatie stuurt daarvoor `Access-Control-Allow-Origin: *` mee. Zonder
internetverbinding is voorlezing niet beschikbaar.

## Nieuwe audio publiceren

De TTS-scripts schrijven nog steeds naar `audio/`. MP3-, Opus- en WAV-uitvoer
in die map wordt door Git genegeerd; JSON-manifesten blijven wel in Git.
Publiceer alleen de bestanden of mappen die bewust zijn gegenereerd:

```bash
scripts/publish_audio.sh audio/genesis/1-m.mp3
scripts/publish_audio.sh audio/genesis/1/m audio/genesis/1/v
```

Het script bewaart relatieve paden, uploadt geen logbestanden en controleert de
gepubliceerde inhoud daarna met checksums. Het verwijdert nooit andere
serverbestanden. Publiceer audio vóór een wijziging in `js/audio-available.js`
die deze audio zichtbaar maakt.

Voor een andere SSH-doelserver of opslagmap kunnen beheerders gebruiken:

```bash
OV_ASSET_SSH_TARGET=root@example.org \
OV_ASSET_REMOTE_ROOT=/srv/project/assets \
scripts/publish_audio.sh audio/genesis/1-m.mp3
```

## Lokale Higgs-generatie van november 2026

De gecontroleerde nieuwe versbestanden en daaruit samengevoegde hoofdstukken
staan onder `/audio/higgs-20261109/` op openvertaling.nl. `nl-ov`, `nl-opv` en
`nl-et-basis` houden de drie tekstbronnen gescheiden. De bestaande externe
assetlocatie blijft de oudere opnames aanbieden.

`catalogus.json` wordt pas na alle uploads, SHA256-controles en hoofdstukbouw
atomair geplaatst. De speler leest deze catalogus en biedt uitsluitend volledige
hoofdstukken in de juiste editie aan. Tijdmarkeringen komen uit de afzonderlijke
versduren; samenvoegen kopieert de MP3-frames zonder een nieuwe spraakgeneratie
of extra audiocompressie. Een bestaande vrouwenstem blijft beschikbaar.

`Publish finished audio` gebruikt de bestaande deploysleutel op GitHub Actions.
De workflow haalt de expliciet gekozen publieke `higgs-audio-*`-release op en
installeert de pakketten met `scripts/audio/install_release.py`. Hij verwijdert
geen bestaande audio. Een lege release-tag test alleen de uploadbestemming.
