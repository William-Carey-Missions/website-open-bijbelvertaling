# Plan: splitsing in drie sites

Spec: `docs/superpowers/specs/2026-10-08-splitsing-drie-sites-design.md`

Rooktest: `smoke.py` (Playwright/Chromium) laadt elke top-level pagina en meldt
JS-fouten, mislukte eigen requests en dode links, ook naar de zustersites.
Nulmeting op de ongewijzigde site: 54 pagina's, 0 dode links; 5 al bestaande
404's (3 ontbrekende boomafbeeldingen, `downloads/index.json` dat op de server
gebouwd wordt, `data/wizard-queue.json`).

## Taken

1. **Veiligheid.** OV: lokale branch `splitsing-drie-sites`, push-URL van
   `origin` geblokkeerd. OGW/OPV: kloon, `origin` weg, `deploy.yml` uit.
2. **`js/sites.js`** met `KASites.url(site, pad)` en `data-ogw-href`-links;
   geladen vanuit `topnav.js`-pagina's en de lezer.
3. **OV — haken in de lezer** omzetten naar OGW-links (tags.js, opties.js,
   lexicon.js, geez-lexicon.js, app.js, verse-witness-reader.js, index.html).
4. **OV — wiki-shell** terugbrengen tot "Over de vertaling"; topnav aanpassen.
5. **OV — verwijderen** van wiki-pagina's, JS, CSS, data, beelden en tests;
   documentatiepagina's linken naar OGW.
6. **OV — build/deploy-scripts**: `build_review_catalog.py` zonder geografie,
   naslag-builds uit `deploy.yml`, `sw.js`-versie, sitemap/llms/robots.
7. **OV — tests**: rooktest + linkcrawl + bestaande Python-tests.
8. **OPV** klonen vanaf de OV-branch; editie standaard `nl-opv`, OV-specifieke
   onderdelen eruit, branding; tests.
9. **OGW** branding, deploy uit, links naar OV/OPV; tests.
10. **Drie servers** (:8000/:8001/:8002) en een kruislinkcontrole.
