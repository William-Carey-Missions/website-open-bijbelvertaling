# Open Vertaling

Beheer van de bezoekersstatistieken: [Google Analytics en meet-ID](docs/analytics.md).

![Logo van Open Vertaling](images/branding/open-vertaling-logo.svg)

De Open Vertaling (OV) is een herziening van de Statenvertaling in hedendaags Nederlands. De tekst is vrij te gebruiken onder CC0.

**[Lees op openvertaling.nl](https://openvertaling.nl)**

## Lezen en gebruiken

De website publiceert één Nederlandse leeseditie met de Godsnaam **HEERE**. Je kunt hoofdstukken lezen, zoeken, kanttekeningen raadplegen, leesinstellingen aanpassen en de tekst laten voorlezen. Downloads en een Markdown-uitgave maken de tekst ook buiten de lezer toegankelijk.

De Statenvertaling van 1888 vormt de controlebron. De oorspronkelijke teksten en kanttekeningen blijven in de hoofdstukdata beschikbaar. De leesuitgave is nagekeken en toont geen conceptlabels of openbare beoordelingsknoppen. De technische controlehistorie blijft bewaard; zie [accounts en verificatie](docs/collaboration-review.md).

## Drie samenwerkende sites

| Site | Inhoud |
|---|---|
| [Open Vertaling](https://openvertaling.nl) | De herziene Statenvertaling, kanttekeningen en downloads |
| [Open Parafrase Weergave](https://open-parafrase-weergave.nl) | Gods Woord in begrijpelijke taal, als parafrase in concept |
| [Open Gods Word](https://opengodsword.com) | Encyclopedie, kaarten, grondteksten, woordenboeken en broninformatie |

## Lokaal ontwikkelen

Serveer de repository vanuit de hoofdmap:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open [localhost:8000](http://127.0.0.1:8000/). De statische lezer werkt zonder frontend-bundler. Accountfuncties vereisen daarnaast de samenwerkings-API; de installatie en het beheer staan in `server/` en [docs/collaboration-review.md](docs/collaboration-review.md). Audio wordt vanaf de externe assetserver geladen; zie [externe assets](docs/external-assets.md).

| Map | Inhoud |
|---|---|
| `data/` | Boek- en hoofdstukdata, kanttekeningen en afgeleide gegevens |
| `js/`, `css/` | Lezer en vormgeving |
| `server/`, `migrations/` | Samenwerkings-API en databaseschema |
| `scripts/` | Bouw-, export- en controlescripts |
| `tests/` | Automatische controles |

De publicatie bouwt onder meer de HTML-leespagina's, Markdown-uitgave, zoekindex, sitemap en citaatdata. De precieze opdrachten staan in [de deploy-workflow](.github/workflows/deploy.yml). Python-tests draaien met:

```sh
python3 -m pytest tests
node --test tests/test_simple_reader.cjs
```

## Publicatie

Een push naar `main` of **Actions → Deploy website → Run workflow** start de publicatie naar `/var/www/openvertaling.nl/site`. De workflow gebruikt `DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER` en het secret `DEPLOY_SSH_KEY`. Na de statische bestanden wordt de samenwerkings-API geïnstalleerd en worden de gecontroleerde publicatiestatus en downloads op de server opgebouwd.

## Bijdragen en licenties

Correcties en suggesties zijn welkom via de site, een issue of een pull request. Wijzigingen aan OV-tekst en kanttekeningen horen in deze repository; Open Gods Word neemt deze bron over.

De **OV-tekst** wordt aangeboden onder **CC0 / publiek domein** en mag worden gekopieerd, bewerkt, gedrukt en verspreid. Deze tekstlicentie geldt niet automatisch voor externe afbeeldingen, audio, grondteksten of ander bronmateriaal. Controleer voor hergebruik de bronvermelding en de licentie van het betreffende bestand; zie ook [bronnen en licenties op Open Gods Word](https://opengodsword.com/bronnen.html).
