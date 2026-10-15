# Splitsing in drie sites: Open Gods Woord, Open Vertaling, Open Parafrase Vertaling

## Doel

De huidige site (openvertaling.nl) wordt drie aparte websites, elk met een
eigen repository waarin verder gewerkt wordt:

| Site | Map (lokaal) | Inhoud |
|---|---|---|
| **Open Gods Woord** (OGW) | `../website-open-gods-woord` | Volledige kopie van deze repo: lezer, wiki, Bijbelachtergrond en broninformatie. |
| **Open Vertaling** (OV) | deze repo | Alleen de herziening van de Statenvertaling met alle opties; geen wiki en geen Bijbelachtergrond. |
| **Open Parafrase Vertaling** (OPV) | `../website-open-parafrase-vertaling` | Lezer met de parafrase als hoofdtekst; SV1888/OV als vergelijkingskolom. |

OV en OPV verwijzen voor achtergrond- en broninformatie naar OGW.

## Uitgangspunten

- **Niets naar productie.** Tot de splitsing is goedgekeurd gaat er niets naar
  openvertaling.nl. In OV gebeurt het werk op de lokale branch
  `splitsing-drie-sites`; `main` blijft onaangeroerd. De push-URL van `origin`
  is lokaal geblokkeerd. In OGW en OPV is `deploy.yml` uitgeschakeld en is
  `origin` (wijst nog naar de OV-repo) verwijderd.
- **Geschiedenis behouden.** OGW en OPV ontstaan met `git clone` van deze repo,
  zodat `git log`/`git blame` blijven werken.
- **Eén plek voor de site-adressen.** `js/sites.js` (`window.KASites`) kent de
  adressen van de drie sites. Lokaal (localhost/127.0.0.1) wijst het naar
  `:8000` (OV), `:8001` (OGW) en `:8002` (OPV). In productie naar
  placeholder-domeinen (`opengodsword.com`, `openvertaling.nl`,
  `open-parafrase-weergave.nl`), die vóór livegang worden vastgesteld.
  Statische links gebruiken `data-ogw-href="pad"`; `sites.js` vult de `href`.

## Indeling OV

**Blijft:** lezer (`index.html`, `lees.html`), alle opties, kolommen
SV1637/SV1888/grondtekst/kanttekeningen, Strong's-popup, audio, drukversie,
downloads, principes, uitgangspunten, statistieken, changelog, grondteksten,
strongs-en-grondtekst, bronnen, citaatvragen, insluiten, voor-ai, review- en
samenwerkingspagina's, server/ (samenwerkings-API).

**Gaat eruit (staat op OGW):** wiki-onderwerpen en naslag (afgoden,
bomen-planten, dieren, gebeden, gereedschap, liederen, materialen,
muziekinstrumenten, personen, voedsel, volken-naties), onderwerpen, kaart,
plaats, geografie, stamboom, lexicon-pagina's (lexicon, woordenboeken,
lexicon-viewer, -bdb, -abbott), handschriften (+ `handschriften/`),
maateenheden, tijdsaanduidingen, homerus, aratus, wiki-overzicht, plus de
bijbehorende JS/CSS/data, beelden (`images/wiki/`) en tests.

**Wiki-shell:** `wiki.html` blijft als documentatie-shell met alleen de groepen
"De vertaling" en "Downloaden" (titel "Over de vertaling"), zodat bestaande
links en de uitgangspunten-modal blijven werken. De topnavigatie krijgt
"Over de vertaling" en een externe link "Achtergrond ↗" naar OGW.

**Haken in de lezer → links naar OGW:**
- Tekstverbanden-stippen (`tags.js`) → naslagpagina's op OGW.
- Plaatsnamen (`opties.js`, geoMarkeren) → `geografie.html` op OGW.
- Strong's-popup "volledig lemma" (`lexicon.js`, `geez-lexicon.js`) →
  `lexicon-viewer.html` op OGW.
- Handschriften (`app.js` datering, `verse-witness-reader.js`) → OGW.
- Opties-links naar maateenheden/tijdsaanduidingen → OGW.
- Documentatiepagina's die naar wiki-onderwerpen linken → OGW.

**Build:** `build_review_catalog.py` maakt geografie-items alleen als
`data/geografie-runtime.geojson` aanwezig is. De naslag-builds vallen uit de
OV-deploy. `sw.js` krijgt een nieuwe cacheversie.

## Indeling OPV

Afgeleid van OV (na de wiki-strip), daarna:
- Standaardeditie `nl-opv`; keuze beperkt tot `nl-opv` en `nl-ov` (OV als
  vergelijkingskolom). Buitenlandse edities blijven in de OV-repo.
- De werkbron van de parafrase (`data/edities/opv`, `scripts/opv_leeseditie.py`,
  `scripts/validate_opv.py`, de OPV-tests en `docs/opv/`) hoort hier: in deze
  repo wordt aan de parafrase gewerkt. De OV-repo houdt voorlopig een kopie,
  zodat de OV-lezer de OPV als vergelijkingseditie kan blijven tonen.
- Weg: review/samenwerking (pagina's, server/, migrations/), principes en
  OV-specifieke documentatie, audio, drukversie, downloads van OV.
- Branding: naam "Open Parafrase Vertaling", eigen `manifest.json`, CNAME,
  `robots.txt`; broninformatie via links naar OGW.

## Indeling OGW

Volledige kopie, met minimale aanpassingen: deploy uit, `origin` weg, CNAME,
naam in `manifest.json` en topnavigatie "Open Gods Woord", `sites.js`
aanwezig.

## Controle

- Elke site start lokaal (`python3 -m http.server`) op zijn eigen poort.
- Browsertests (Playwright/Chromium) per site: alle overgebleven pagina's laden
  zonder console-fouten en zonder 404's op eigen bronnen; de lezer toont
  Johannes 1 en Genesis 1; opties (Godsnaam, kolommen) werken; links naar OGW
  wijzen naar de juiste OGW-pagina en die pagina bestaat daar.
- OV/OPV bevatten geen links meer naar verwijderde lokale pagina's
  (linkcrawl).
- De bestaande Python-tests draaien per repo; tests van verwijderde onderdelen
  verhuizen mee naar OGW.
