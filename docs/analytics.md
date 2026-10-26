# Google Analytics voor Open Vertaling

## Vaste configuratie

| Onderdeel | Waarde |
|---|---|
| Website | https://openvertaling.nl |
| Productiehost | `openvertaling.nl` |
| GA4-meet-ID | `G-BZGB0WJVD7` |
| Centrale koppeling | `js/analytics.js` |
| Bootstrap voor HTML | `js/theme.js` |
| Toestemmingsopslag | `ogw_statistics_consent_v1` |
| Regressietests | `tests/analytics.test.cjs` |

De meet-ID is een openbare configuratiewaarde, geen wachtwoord of API-sleutel.
Gebruik hem uitsluitend voor dit domein. Een gewijzigde property of webstream
vereist een gecontroleerde wijziging in `js/analytics.js` én deze documentatie.

De drie websites hebben afzonderlijke meet-ID's:

| Website | Meet-ID |
|---|---|
| Open Vertaling — openvertaling.nl | `G-BZGB0WJVD7` |
| Open Parafrase Weergave — open-parafrase-weergave.nl | `G-ECBHJXXSEM` |
| Open Gods Word — opengodsword.com | `G-P06GG401K0` |

## Nieuwe pagina's en herontwerpen

Laad de bestaande bootstrap in de head van elke zelfstandige HTML-pagina:

```html
<script src="/js/theme.js"></script>
```

`theme.js` voegt de lokale Analytics-loader één keer toe. Die beslist vervolgens
op basis van host en toestemming of de Google-tag mag laden. Kopieer geen
installatiesnippet uit Google Analytics naast deze bootstrap.

Controleer zowel gewone pagina's als de templates en generatoren die nieuwe
hoofdstukken, naslagpagina's of taalroutes produceren. Laat de lokale scripts
en de toestemmingsinterface meegaan in de publicatie. Bij wijzigingen aan
gecachete assets moet de gebruikelijke serviceworker-cacheversie mee veranderen.

De bestaande loader verwerkt navigatie via laden, `pushState`, `replaceState`,
`popstate` en hashwissels. Behoud `send_page_view: false` en de ontdubbeling:
alleen de opgeschoonde handmatige `page_view` wordt aangemaakt.

## Toestemming en meetgegevens

De implementatie gebruikt Basic Consent Mode: de Google-tag wordt pas geladen
na de keuze **Toestaan**. **Weigeren** laadt de tag niet. Intrekken schakelt de
tag uit en verwijdert de bijbehorende Analytics-cookies.

Behoud de bestaande instellingen voor uitgeschakelde advertentiesignalen en
personalisatie. Meet pagina's met de vaste sitenaam als titel, een opgeschoonde
locatie en alleen de oorsprong van een verwijzende site. Alleen geldige
Bijbelboek/hoofdstukroutes worden uit hashes overgenomen; querystrings en vrije
hashes niet. Voeg geen zoektermen, formulierwaarden of accountgegevens toe.

De bootstrap werkt alleen op HTTPS voor de exacte productiehost, zonder
afwijkende poort, en alleen in het hoofddocument. Lokale tests, previewhosts en
ingesloten kaarten/teksten mogen daardoor geen extra bezoekersmetingen veroorzaken.

## Instellingen in Google Analytics

Selecteer de property van deze website en open **Beheerder → Gegevensstreams**.
Controleer dat de webstream het domein en de meet-ID uit de tabel bevat.
Houd **Verbeterde meting** en automatische browsergeschiedenis-metingen uit voor
deze implementatie; de code verzorgt zelf de opgeschoonde paginaweergaven.
Controleer dit in de beheerinterface: de repository kan deze accountinstelling
niet vaststellen of wijzigen.

## Verificatie

1. Voer `node --test tests/analytics.test.cjs` uit met Node.js en Playwright
   beschikbaar. De tests gebruiken een geïsoleerd transport en sturen geen echte
   bezoekersmetingen naar Google.
2. De testbrowser gebruikt `CHROME_PATH` als die is ingesteld; anders de in het
   testbestand beschreven standaardlocatie van Chrome. Installeer deze vereisten
   in de ontwikkel- of CI-omgeving voordat je de tests uitvoert.
3. Controleer na publicatie in een schone browser op de echte website:
   vóór een keuze geen Google-tagverzoek, na weigeren nog steeds geen tag,
   en na toestaan precies één tag met `G-BZGB0WJVD7`.
4. Open een hoofdstuk en blader naar het volgende. Controleer dat er één nieuwe
   opgeschoonde paginaweergave ontstaat, zonder zoekopdracht of formulierinhoud.
   Controleer ook een gewone informatiepagina en een gegenereerde hoofdstukpagina.
5. Controleer in de juiste GA4-property **Rapporten → Realtime** of een toegestaan
   testbezoek aankomt. Een lokale test of geslaagde deploy bevestigt op zichzelf
   geen ontvangst door Google Analytics.

## Officiële uitleg

- [Google: Consent Mode](https://developers.google.com/tag-platform/security/concepts/consent-mode)
- [Google: gebeurtenissen voor verbeterde meting](https://support.google.com/analytics/answer/9216061?hl=nl)
- [Google: Realtime-rapport](https://support.google.com/analytics/answer/9271392?hl=nl)

