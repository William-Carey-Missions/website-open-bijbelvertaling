# Repository-instructies

## Google Analytics behouden

Deze repository publiceert **Open Vertaling** op `openvertaling.nl`.
De GA4-meet-ID is **`G-BZGB0WJVD7`**. De bronconfiguratie staat in
`js/analytics.js`; de beheer- en testinstructies staan in [docs/analytics.md](docs/analytics.md).

- Houd deze meet-ID gekoppeld aan dit domein. Neem geen meet-ID van een zustersite over.
- Nieuwe HTML-pagina's en paginageneratoren laden in de head `/js/theme.js`.
  Die bootstrap laadt `/js/analytics.js` één keer. Voeg geen losse Google-tag,
  tweede Analytics-loader of extra automatische `page_view` toe.
- Behoud de bestaande toestemmingskeuze: vóór toestemming en na weigeren
  wordt de Google-tag niet geladen. Verander de standaard niet naar toestemming.
- Behoud de opschoning van URL's en verwijzingen. Verstuur geen zoektermen,
  formulierinhoud, accountgegevens of vrije hashfragmenten als meetgegevens.
- Behoud het onderscheid tussen productiedomein, lokale ontwikkeling en embeds:
  localhost, andere hosts en iframes initialiseren geen statistieken.
- Controleer ook gegenereerde hoofdstukken en nieuwe taalroutes. Pas de generator
  aan als de bootstrap daar ontbreekt; handmatige edits aan gegenereerde HTML zijn onvoldoende.
- Voer bij wijzigingen aan Analytics, de bootstrap of hoofdstuknavigatie
  `node --test tests/analytics.test.cjs` uit. Zie de handleiding voor vereisten
  en de aanvullende controle na publicatie.
