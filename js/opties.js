/* Open Vertaling — Vertalingsopties (parametrische rendering) */

const Opties = {
    ...OptieMaten,
    STORAGE_KEY: 'sv2026_vertaalopties',

    DEFAULTS: {
        godsnaam: 'yhwh',          // 'ov' (JAHWEH) | 'klassiek' (HEERE) | 'jehovah' (Jehovah) | 'yehovah' (Yehováh) | 'jhwh' (יהוה) | 'yhwh' (YHWH)
        godsnaamOPV: 'yhwh',    // Open Parafrase Weergave: 'heere' (zoals geschreven) | 'jahweh' | 'jehovah' | 'yehovah' | 'jhwh' | 'yhwh'
        heereNT: 'heere',        // NT-aanspreektitel (Kurios): 'heere' (OSV) | 'here' (Heere → Here)
        kolomLayout: 'naast',    // 'naast' (parallelle kolom) | 'eronder' (nieuwe regel onder OV2026)
        boekvolgorde: 'canoniek',// 'canoniek' | 'tenach' | 'chronologisch' | 'auteur' | 'lengte'
        versnummers: 'aan',      // 'aan' | 'uit'
        citaten: 'aan',          // 'aan' | 'uit' — citaatmarkering en sprekerkleuren
        spoor: 'aan',            // 'aan' | 'uit' — het spoor: woorden die afwijken van SV1888 gestippeld onderstrepen
        otSheol: 'dodenrijk',    // 'dodenrijk' (OT-context, modern) | 'hel' (SV-traditioneel)
        thema: 'auto',           // 'auto' (systeem) | 'licht' | 'donker'
        arabischeNamen: 'uit',   // 'uit' (Nederlandse namen) | 'aan' (Musa, Ibrahim, Isa …) — alleen OV-tekst
        jezusNaam: 'nl',         // 'nl' (Jezus Christus) | 'hebreeuws' (Yeshua HaMashiach) | 'koranisch' (Isa) | 'arabisch' (Yasūʿ al-Masīḥ)
        geoMarkeren: 'uit',      // 'uit' | 'aan' — geografische locaties in de tekst markeren (Torah)
        maatstelsel: 'metrisch', // 'bijbels' (el, efa, sikkel) | 'metrisch' (meter, liter, gram) | 'imperiaal' (voet, gallon, pond)
        //                          Standaard metrisch: de Bijbelse maat blijft staan en de
        //                          moderne waarde volgt tussen haakjes, zodat een lezer
        //                          meteen ziet hoe groot 'driehonderd ellen' is.
        getalweergave: 'woorden', // 'woorden' | 'cijfers' — zet aantallen vanaf 21 ook tussen haakjes in cijfers
        tijdrekening: 'bijbels', // 'bijbels' (de derde ure) | 'modern' (omstreeks negen uur 's ochtends)
        strongs: 'uit',          // 'uit' | 'aan' — bronvaste Strong-nummers bij grondtekstwoorden
        apocriefeBoeken: 'aan',
        ethiopischeBoeken: 'uit',
        teksteditie: 'nl-ov',    // actieve Bijbeltekst; de interface blijft Nederlands
        parallelEdities: [],     // maximaal drie extra edities naast de primaire tekst
        lettertype: 'klassiek',
        regelafstand: 'normaal',
    },

    state: {},

    enforceReaderOptions() {
        Object.assign(this.state, {
            heereNT: 'heere', otSheol: 'dodenrijk',
            arabischeNamen: 'uit', jezusNaam: 'nl', maatstelsel: 'metrisch',
            getalweergave: 'woorden', tijdrekening: 'bijbels', spoor: 'uit',
            geoMarkeren: 'uit', strongs: 'uit', ethiopischeBoeken: 'uit', teksteditie: 'nl-ov', parallelEdities: [],
        });
    },

    // Vervang-paren voor Arabische namen ([regex, translit]); lui geladen uit data/namen-arabisch.json
    _arNamen: null,
    _geoData: {},            // per boek: { namen:{naam:{type}}, verzen:{"ch:vs":[substrings]} }
    _eenheden: null,         // omrekentabel + uitzonderingen; lui geladen uit data/eenheden.json
    _tijden: null,           // uren, nachtwaken en vaste tijdsfrasen; lui geladen uit data/tijden.json

    init() {
        if (this._initialized) return;
        this._initialized = true;
        const saved = localStorage.getItem(this.STORAGE_KEY);
        // Mobiele default: kolommen 'eronder' i.p.v. 'naast' — beter leesbaar op smal scherm
        const defaults = { ...this.DEFAULTS };
        if (window.innerWidth <= 768) defaults.kolomLayout = 'eronder';
        let savedState = {};
        try {
            savedState = saved ? JSON.parse(saved) : {};
            this.state = { ...defaults, ...savedState };
        } catch (e) {
            this.state = { ...defaults };
        }
        this.enforceReaderOptions();
        if (!['canoniek', 'tenach', 'chronologisch', 'auteur', 'lengte', 'katholiek', 'orthodox'].includes(this.state.boekvolgorde)) this.state.boekvolgorde = 'canoniek';
        // Een geldige URL-keuze heeft in deze tab voorrang op de opslag.
        if (typeof TekstEditie !== 'undefined') this.state.teksteditie = TekstEditie.code();
        // Een oudere versie bewaarde citaatopmaak onder een losse sleutel.
        // Neem die eenmalig over zolang de centrale opties nog geen keuze bevatten.
        if (!Object.prototype.hasOwnProperty.call(savedState, 'citaten')) {
            const legacyCitaten = localStorage.getItem('citaatopmaak');
            if (legacyCitaten !== null) this.state.citaten = legacyCitaten === 'false' ? 'uit' : 'aan';
        }

        // Sync radio buttons + selects
        document.querySelectorAll('[data-optie]').forEach(input => {
            const optie = input.dataset.optie;
            if (input.type === 'range' && optie === 'regelafstand') {
                input.value = String({ compact: 0, normaal: 1, ruim: 2 }[this.state.regelafstand] ?? 1);
                this.updateRangeLabel(input);
            } else if (input.tagName === 'SELECT') {
                input.value = this.state[optie];
            } else {
                input.checked = this.state[optie] === input.value;
            }
        });

        // Pas layout-class direct toe (geen re-render nodig — pure CSS)
        this.applyLayoutClass();
        this.applyVerseNumbersClass();
        this.applyCitationsClass();
        OVTheme.apply(this.state.thema);
        this.applyReaderStyleClasses();
        document.body.classList.toggle('show-tags', this.state.geoMarkeren === 'aan');

        // Arabische namen lui laden (en, indien al ingeschakeld, hoofdstuk herrenderen).
        // De geodata van de Tora is alleen nodig voor Tekstverbanden; die komt pas
        // als de optie aan staat of aangezet wordt.
        this.ready = this.loadEenheden();

        // Klik op een gemarkeerde geografische locatie -> geografie-pagina op Open Gods Woord
        document.addEventListener('click', function (e) {
            var geo = e.target.closest && e.target.closest('.geo-locatie');
            if (geo) { window.location.href = KASites.url('ogw', 'geografie.html'); }
        });

        // Versnummers-checkbox (in 'Pagina & leeshulp') synchroniseren met state
        const vnCb = document.getElementById('toggle-versnummers');
        if (vnCb) vnCb.checked = this.state.versnummers !== 'uit';

        if (!Array.isArray(this.state.parallelEdities)) this.state.parallelEdities = [];
        this.state.parallelEdities = [...new Set(this.state.parallelEdities)].slice(0, 3);
        const parallelInputs = [...document.querySelectorAll('[data-parallel-editie]')];
        const syncParallelInputs = () => {
            const selected = this.state.parallelEdities;
            parallelInputs.forEach(input => {
                input.checked = selected.includes(input.dataset.parallelEditie);
                input.disabled = !input.checked && selected.length >= 3;
            });
        };
        parallelInputs.forEach(input => input.addEventListener('change', () => {
            const code = input.dataset.parallelEditie;
            let selected = this.state.parallelEdities.filter(item => item !== code);
            if (input.checked && selected.length < 3) selected.push(code);
            this.state.parallelEdities = selected;
            syncParallelInputs();
            this.save();
            this.applyToCurrentChapter();
        }));
        syncParallelInputs();

        // Snelle Strong-schakelaar boven de leestekst. Deze bedient bewust de
        // bestaande optie, zodat opslag, hertekenen en alle spiegels gelijklopen.
        const quickStrongs = document.getElementById('quick-strongs-btn');
        const strongsCb = document.getElementById('toggle-strongs');
        const syncQuickStrongs = () => {
            if (!quickStrongs) return;
            const enabled = this.state.strongs === 'aan';
            quickStrongs.setAttribute('aria-pressed', String(enabled));
            quickStrongs.classList.toggle('is-on', enabled);
        };
        if (quickStrongs && strongsCb) {
            quickStrongs.addEventListener('click', () => {
                strongsCb.checked = this.state.strongs !== 'aan';
                strongsCb.dispatchEvent(new Event('change', { bubbles: true }));
                syncQuickStrongs();
            });
            strongsCb.addEventListener('change', syncQuickStrongs);
        }
        window.addEventListener('ov:opties-gewijzigd', syncQuickStrongs);
        syncQuickStrongs();

        const alternatiefLettertype = document.getElementById('toggle-lettertype-alternatief');
        if (alternatiefLettertype) {
            alternatiefLettertype.checked = this.state.lettertype === 'rustig';
            alternatiefLettertype.addEventListener('change', () => {
                this.state.lettertype = alternatiefLettertype.checked ? 'rustig' : 'klassiek';
                this.save();
                this.applyReaderStyleClasses();
            });
        }

        // Listen to changes
        document.querySelectorAll('[data-optie]').forEach(input => {
            input.addEventListener('change', () => {
                // Een checkbox moet ook op uitvinken reageren; radio's en selects
                // vuren alleen bij de nieuwe keuze.
                if (input.type === 'checkbox') {
                    this.state[input.dataset.optie] = input.checked ? input.value : 'uit';
                    if (input.id === 'toggle-contextmarkeringen') {
                        document.body.classList.toggle('show-tags', input.checked);
                    }
                    if (input.dataset.optie === 'geoMarkeren' && input.checked) this.loadGeoData();
                    this.save();
                    if (input.dataset.optie === 'apocriefeBoeken' || input.dataset.optie === 'ethiopischeBoeken') {
                        if (typeof Sidebar !== 'undefined' && Sidebar.renderTree) Sidebar.renderTree();
                        if (typeof Navigation !== 'undefined' && Navigation.renderBookNav) Navigation.renderBookNav();
                        return;
                    }
                    this.applyToCurrentChapter();
                    return;
                }
                if (input.type === 'range' && input.dataset.optie === 'regelafstand') {
                    this.state.regelafstand = ['compact', 'normaal', 'ruim'][Number(input.value)] || 'normaal';
                    this.updateRangeLabel(input);
                    this.save();
                    this.applyReaderStyleClasses();
                    return;
                }
                if (input.tagName === 'SELECT' || input.checked) {
                    this.state[input.dataset.optie] = input.value;
                    this.save();
                    const optie = input.dataset.optie;
                    if (optie === 'kolomLayout') {
                        this.applyLayoutClass();
                    } else if (optie === 'versnummers') {
                        // Pure CSS-toggle — geen re-render
                        this.applyVerseNumbersClass();
                    } else if (optie === 'citaten') {
                        this.applyCitationsClass();
                        this.applyToCurrentChapter();
                    } else if (optie === 'thema') {
                        OVTheme.apply(this.state.thema);
                    } else if (optie === 'lettertype' || optie === 'regelafstand') {
                        this.applyReaderStyleClasses();
                    } else if (optie === 'boekvolgorde' || optie === 'apocriefeBoeken' || optie === 'ethiopischeBoeken') {
                        // Sidebar + topnav opnieuw renderen, geen hoofdstuk-rerender
                        if (typeof Sidebar !== 'undefined' && Sidebar.renderTree) Sidebar.renderTree();
                        if (typeof Navigation !== 'undefined' && Navigation.renderBookNav) Navigation.renderBookNav();
                    } else if (optie === 'teksteditie') {
                        if (typeof TekstEditie !== 'undefined') TekstEditie.setCode(input.value);
                        this.applyToCurrentChapter();
                    } else {
                        this.applyToCurrentChapter();
                    }
                }
            });
        });
    },

    updateRangeLabel(input) {
        const label = document.getElementById(`${input.id}-value`);
        if (!label) return;
        label.textContent = ['Compact', 'Normaal', 'Ruim'][Number(input.value)] || 'Normaal';
    },

    applyLayoutClass() {
        const content = document.getElementById('content');
        if (!content) return;
        content.classList.remove('layout-naast', 'layout-eronder');
        const mode = this.state.kolomLayout === 'eronder' ? 'eronder' : 'naast';
        content.classList.add('layout-' + mode);
        content.querySelectorAll('.edition-comparison').forEach(comparison => {
            comparison.dataset.layout = mode;
        });
    },

    applyVerseNumbersClass() {
        // Toggle een class op <body> zodat CSS de versnummers kan verbergen.
        document.body.classList.toggle('hide-verse-numbers', this.state.versnummers === 'uit');
    },

    applyCitationsClass() {
        document.body.classList.toggle('citaten-uit', this.state.citaten === 'uit');
    },

    applyReaderStyleClasses() {
        const font = this.state.lettertype === 'rustig' ? 'rustig' : 'klassiek';
        const spacing = ['compact', 'normaal', 'ruim'].includes(this.state.regelafstand)
            ? this.state.regelafstand
            : 'normaal';
        document.body.classList.remove('reader-font-klassiek', 'reader-font-rustig');
        document.body.classList.remove(
            'reader-spacing-compact',
            'reader-spacing-normaal',
            'reader-spacing-ruim'
        );
        document.body.classList.add(`reader-font-${font}`, `reader-spacing-${spacing}`);
    },

    save() {
        this.enforceReaderOptions();
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.state));
        window.dispatchEvent(new CustomEvent('ov:opties-gewijzigd', {
            detail: { state: { ...this.state } }
        }));
    },

    /**
     * Transformeer een OV-tekst-fragment volgens de huidige opties.
     * Werkt op zowel platte tekst als HTML — we doen alleen tekst-vervangingen
     * en blijven van HTML-tags af.
     */
    transformOV(html, testament) {
        this.enforceReaderOptions();
        if (!html) return html;
        let out = html;

        // === Heere → Here (alleen NT; Kurios) ===
        // In het NT is "Heere" de weergave van het Griekse κύριος (Kurios). Optioneel
        // tonen we de modernere vorm "Here". Hoofdletter-"HEERE" (OT-Godsnaam) blijft ongemoeid.
        if (testament === 'NT' && this.state.heereNT === 'here') {
            out = this._replaceOutsideTags(out, [
                [/\bHeere/g, 'Here'],   // vangt ook "Heeren" → "Heren"
            ]);
        }

        // === OT-Sheol: dodenrijk → hel (optioneel) ===
        if (this.state.otSheol === 'hel') {
            out = this._replaceOutsideTags(out, [
                [/\bdodenrijk\b/g, 'hel'],
                [/\bDodenrijk\b/g, 'Hel'],
            ]);
        }

        // === Godsnaam ===
        if (this.state.godsnaam === 'klassiek') {
            // Volgorde belangrijk: composiet eerst, daarna prep+vocatief, daarna default
            out = this._replaceOutsideTags(out, [
                [/\bGod JAHWEH\b/g, 'de HEERE God'],
                [/\bJAHWEH van de legermachten\b/g, 'de HEERE der heirscharen'],
                // Voorzetsels: "op JAHWEH" → "op de HEERE"
                [/\b(op|van|aan|voor|tot|door|in|met|bij|over|onder|naast|achter|jegens|uit|na|sinds) JAHWEH\b/gi, '$1 de HEERE'],
                // Echte vocatief alleen na "O " of "o "
                [/\b([Oo]) JAHWEH\b/g, '$1 HEERE'],
                // JAHWEH! als uitroep blijft vocatief zonder "de"
                [/\bJAHWEH!/g, 'HEERE!'],
                // Begin van zin (na . ! ? of regel-begin): "De HEERE"
                [/(^|[.!?]\s+)JAHWEH\b/g, '$1De HEERE'],
                // Default mid-zin: "de HEERE"
                [/\bJAHWEH\b/g, 'de HEERE'],
                // Cleanup: "de de HEERE" → "de HEERE" (in geval voorzetsel ontbrak)
                [/\bde de HEERE\b/g, 'de HEERE'],
                [/\bDe de HEERE\b/g, 'De HEERE'],
            ]);
        } else if (this.state.godsnaam === 'jehovah') {
            out = this._replaceOutsideTags(out, [
                [/\bGod JAHWEH\b/g, 'God Jehovah'],
                [/\bJAHWEH\b/g, 'Jehovah'],
            ]);
        } else if (this.state.godsnaam === 'yehovah') {
            out = this._replaceOutsideTags(out, [
                [/\bGod JAHWEH\b/g, 'God Yehováh'],
                [/\bJAHWEH\b/g, 'Yehováh'],
            ]);
        } else if (this.state.godsnaam === 'jhwh') {
            out = this._replaceOutsideTags(out, [
                [/\bGod JAHWEH\b/g, 'God יהוה'],
                [/\bJAHWEH\b/g, 'יהוה'],
            ]);
        } else if (this.state.godsnaam === 'yhwh') {
            // De vier medeklinkers in Latijnse letters: de naam zonder klinkers,
            // zoals de Hebreeuwse tekst hem schrijft.
            out = this._replaceOutsideTags(out, [
                [/\bGod JAHWEH\b/g, 'God YHWH'],
                [/\bJAHWEH\b/g, 'YHWH'],
            ]);
        }
        // 'ov': geen transformatie

        // === Naam van Jezus ===
        // Vier keuzes. "Jezus Sirach" blijft altijd ongemoeid: dat is Ben Sira,
        // een andere persoon, en de boektitel hoort niet te wijzigen.
        //
        // De samenstelling "Jezus Christus" moet vóór de losse naam staan,
        // anders wordt eerst "Jezus" vervangen en blijft "Christus" los achter.
        var NAAMVORMEN = {
            hebreeuws: { vol: 'Yeshua HaMashiach', kort: 'Yeshua',
                         volHoofd: 'YESHUA HAMASHIACH', kortHoofd: 'YESHUA' },
            koranisch: { vol: 'Isa al-Masih', kort: 'Isa',
                         volHoofd: 'ISA AL-MASIH', kortHoofd: 'ISA' },
            arabisch:  { vol: 'Yasūʿ al-Masīḥ', kort: 'Yasūʿ',
                         volHoofd: 'YASŪʿ AL-MASĪḤ', kortHoofd: 'YASŪʿ' },
        };
        var vorm = NAAMVORMEN[this.state.jezusNaam];
        if (vorm) {
            out = this._replaceOutsideTags(out, [
                // De Statenvertaling zet de naam in hoofdletters waar hij
                // gegeven wordt (Mattheüs 1:21, 1:25). Dat blijft zo.
                [/\bJEZUS CHRISTUS\b/g, vorm.volHoofd],
                [/\bJezus Christus\b/g, vorm.vol],
                [/\bJEZUS\b/g, vorm.kortHoofd],
                [/\bJezus\b(?! Sirach)/g, vorm.kort],
            ]);
        }

        // === Arabische (islamitische) namen (optioneel) ===
        // Vervangt gevestigde bijbelse figuren/begrippen door hun Arabische naamvorm.
        // Alleen op de OV-tekst; historische kolommen blijven ongemoeid.
        if (this.state.arabischeNamen === 'aan' && this._arNamen) {
            out = this._replaceOutsideTags(out, this._arNamen);
        }

        // Aantallen blijven uitgeschreven en krijgen desgewenst een compact
        // cijferbeeld ernaast, bijvoorbeeld "drie (3)" of "... duizend (57.400)".
        out = this.toonGetalcijfers(out);

        return out;
    },

    /** Laad de Arabische-namen-tabel en bouw vervang-paren (whole-word). */
    loadArabischeNamen() {
        return fetch('data/namen-arabisch.json')
            .then(r => (r.ok ? r.json() : null))
            .then(d => {
                if (!d || !Array.isArray(d.namen)) return;
                const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const pairs = [];
                d.namen.forEach(n => {
                    if (!n.translit) return;
                    [n.nl].concat(n.varianten || []).forEach(f => {
                        if (f) pairs.push([new RegExp('\\b' + esc(f) + '\\b', 'g'), n.translit]);
                    });
                });
                this._arNamen = pairs;
                // Als de optie al aan stond: alleen her-renderen als er al een hoofdstuk staat.
                // NOOIT location.reload() hier (zou een herlaad-lus bij het opstarten geven).
                if (this.state.arabischeNamen === 'aan' &&
                    typeof Navigation !== 'undefined' && Navigation.currentBook && Navigation.currentChapter &&
                    typeof App !== 'undefined' && App.renderChapter) {
                    App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
                }
            })
            .catch(() => {});
    },

    /** Laad de geografische-locatie-data voor de vijf boeken van de Torah. */
    loadGeoData() {
        if (this._geoLaden) return this._geoLaden;
        var boeken = ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'];
        return this._geoLaden = Promise.all(boeken.map(function (boek) {
            return fetch('data/' + boek + '-geo.json')
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) { return [boek, data]; });
        }))
            .then(resultaten => {
                resultaten.forEach(paar => {
                    if (paar[1] && paar[1].verzen) this._geoData[paar[0]] = paar[1];
                });
                if (this.state.geoMarkeren === 'aan' &&
                    typeof Navigation !== 'undefined' && Navigation.currentBook && Navigation.currentChapter &&
                    typeof App !== 'undefined' && App.renderChapter) {
                    App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
                }
            })
            .catch(() => {});
    },

    /** Markeer geografische locaties in een OV-vers (buiten HTML-tags). */
    markeerGeo(html, book, ch, vnum) {
        if (this.state.geoMarkeren !== 'aan' || !this._geoData[book]) return html;
        var boekData = this._geoData[book];
        var locs = boekData.verzen[ch + ':' + vnum];
        if (!locs || !locs.length) return html;
        var namen = boekData.namen || {};
        var esc = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
        var uniq = Object.keys(locs.reduce(function (a, l) { a[l] = 1; return a; }, {}))
            .sort(function (a, b) { return b.length - a.length; });
        var re = new RegExp('(' + uniq.map(esc).join('|') + ')', 'g');
        var tokenRegex = /(<[^>]+>)|([^<]+)/g, result = '', m;
        while ((m = tokenRegex.exec(html)) !== null) {
            if (m[1]) { result += m[1]; continue; }
            result += m[2].replace(re, function (mm) {
                var type = (namen[mm] && namen[mm].type) ? ' — ' + namen[mm].type : '';
                return '<span class="geo-locatie" data-geo="' + mm.replace(/"/g, '') + '" title="Geografische locatie' + type + '">' + mm + '</span>';
            });
        }
        return result;
    },

    // ===================================================================
    // Tijdsaanduidingen — omrekenen naar moderne kloktijd
    // -------------------------------------------------------------------
    // Bij `tijdrekening: 'modern'` wordt "het negende uur" in de OV-tekst
    // VERVANGEN door "ongeveer drie uur 's middags"; het origineel blijft in
    // het title-attribuut staan. Bij 'bijbels' (de standaard) verandert er
    // niets. De brondata in data/ blijft hoe dan ook ongemoeid — dit is een
    // weergave-optie, geen tekstwijziging.
    //
    // De Bijbelse dag loopt van zonsopgang tot zonsondergang en telt twaalf
    // uren, dus het eerste uur begint omstreeks zes uur 's ochtends. Het zijn
    // seizoensuren: 's zomers duurt een uur ruim zeventig minuten, 's winters
    // nog geen vijftig. Daarom staat er altijd "ongeveer" of "omstreeks" bij,
    // en daarom is er ook geen exactere weergave dan hele uren.
    //
    // Rekenwaarden, de nachtwaken (drie in het OT, vier in het NT) en de vaste
    // frasen staan in data/tijden.json, zodat ze bij te werken zijn zonder deze
    // code aan te raken.
    //
    // De hulpfuncties _maatPlatteTekst / _maatBehoudTags / _maatAttr /
    // _maatInBereik zijn niet maat-specifiek en worden hier hergebruikt: ze
    // lossen precies hetzelfde probleem op (tekst herkennen dwars door
    // nootcijfers en citaat-spans heen, zonder de HTML te beschadigen).
    //
    // Let op: geen RegExp-lookbehind — Safari < 16.4 (iPadOS 15.4) kent die niet.
    // ===================================================================

    /** Laad de omrekentabel voor Bijbelse tijdsaanduidingen. */
    loadTijden() {
        return fetch('data/tijden.json')
            .then(r => (r.ok ? r.json() : null))
            .then(d => {
                if (!d || !d.uren) return;
                this._tijden = this._tijdIndex(d);
                if (this.state.tijdrekening === 'modern' &&
                    typeof Navigation !== 'undefined' && Navigation.currentBook && Navigation.currentChapter &&
                    typeof App !== 'undefined' && App.renderChapter) {
                    App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
                }
            })
            .catch(() => {});
    },

    /** Bouw eenmalig de zoekpatronen uit data/tijden.json. */
    _tijdIndex(d) {
        var LET = '[A-Za-zÀ-ÖØ-öø-ÿ]';
        var rangen = Object.keys(d.rangtelwoorden || {}).join('|');
        // "den nacht" (4 Baruch) naast "de nacht"; "overdag" naast "van de dag"
        var dagdeel = '(?:\\s+van\\s+(?:de|den|het)\\s+(?:nacht|dag)|\\s+in\\s+de\\s+nacht|\\s+overdag)?';
        var lidwoord = '(?:(?:het|den|de|dit|dat|die)\\s+)?';

        // Hoofdletter-ongevoelig: "Tussen de twee avonden zult u vlees eten"
        // (Exodus 16:12) staat aan het begin van de zin. De vervanging krijgt
        // die hoofdletter later terug.
        //
        // Het voorzetsel wordt meegenomen omdat "op het negende uur" in modern
        // Nederlands "omstreeks drie uur" wordt, niet "op ongeveer drie uur".
        var uurRe = new RegExp(
            '\\b(?:(ongeveer|omtrent|omstreeks|circa)\\s+)?(?:(op|om|te|ten|ter)\\s+)?' +
            lidwoord + '(' + rangen + ')' +
            '(?:\\s+en\\s+' + lidwoord + '(' + rangen + '))?' +
            '\\s+(?:uur|ure)(' + dagdeel + ')(?!' + LET + ')', 'gi');

        // "waak op!" is een oproep, geen nachtwake — die mag niet meegenomen worden
        var waakRe = new RegExp(
            '\\b(' + rangen + ')\\s+(?:nachtwake|nachtwaak|wake|waak)(?!\\s+op\\b)' +
            '(?:\\s+in\\s+de\\s+nacht)?(?!' + LET + ')', 'gi');

        var bouw = function (lijst) {
            return (lijst || []).map(function (f) {
                return {
                    id: f.id,
                    re: new RegExp('\\b(?:' + f.patroon + ')(?!' + LET + ')', 'gi'),
                    enkel: new RegExp('^(?:' + f.patroon + ')$', 'i'),
                    vervang: f.vervang,
                    uitleg: f.uitleg,
                    alleenIn: f.alleenIn,
                };
            });
        };

        return {
            rangtelwoorden: d.rangtelwoorden || {},
            uren: d.uren, uurUitleg: d.uurUitleg || {}, waken: d.waken || {},
            uurRe: uurRe, waakRe: waakRe,
            genoemdeWaken: bouw(d.genoemdeWaken),
            frases: bouw(d.frases),
            toelichtingen: bouw(d.toelichtingen),
        };
    },

    /**
     * Vervang Bijbelse tijdsaanduidingen in een OV-vers door moderne kloktijd.
     * Geeft de HTML ongewijzigd terug als de optie uit staat, als de tabel nog
     * niet geladen is, of als er niets te vervangen valt.
     */
    rekenTijden(html, book, ch, vnum, testament) {
        if (!html || !this._tijden) return html;
        if (this.state.tijdrekening !== 'modern') return html;
        var T = this._tijden, zelf = this;
        var proj = this._maatPlatteTekst(html);
        var plain = proj.plain, map = proj.map;
        var bezet = [], stukken = [];
        ch = +ch; vnum = +vnum;

        // Elke plaats wordt hooguit één keer aangepakt. De regels lopen in
        // volgorde van bepaald naar algemeen, zodat de losse toelichting op
        // "nachtwake" alleen overblijft waar géén rangtelwoord stond.
        function vrij(a, b) {
            for (var i = 0; i < bezet.length; i++) {
                if (a < bezet[i][1] && b > bezet[i][0]) return false;
            }
            return true;
        }
        function neem(a, b, klasse, tekst, titel) {
            bezet.push([a, b]);
            var binnen = html.slice(map[a], map[b]);
            var inhoud = tekst === null
                ? binnen                                        // tekst blijft staan, alleen een toelichting
                : tekst + zelf._maatBehoudTags(binnen);         // nootcijfers mogen niet verdwijnen
            stukken.push({
                van: map[a], tot: map[b],
                nieuw: '<span class="' + klasse + '" title="' + zelf._maatAttr(titel) + '">' + inhoud + '</span>',
            });
        }
        // Stond het origineel aan het begin van een zin, dan hoort de
        // vervanging ook met een hoofdletter te beginnen.
        function volgHoofdletter(origineel, nieuw) {
            return /^[A-ZÀ-ÖØ-Þ]/.test(origineel)
                ? nieuw.charAt(0).toUpperCase() + nieuw.slice(1) : nieuw;
        }

        // === Uren: "ongeveer het zesde uur", "tegen het derde uur in de nacht" ===
        var m;
        T.uurRe.lastIndex = 0;
        while ((m = T.uurRe.exec(plain)) !== null) {
            var start = m.index, eind = start + m[0].length;
            if (!vrij(start, eind)) continue;
            var snacht = /nacht/.test(m[5] || '');
            var tabel = T.uren[snacht ? 'nacht' : 'dag'];
            var e1 = tabel[String(T.rangtelwoorden[m[3].toLowerCase()])];
            var e2 = m[4] ? tabel[String(T.rangtelwoorden[m[4].toLowerCase()])] : null;
            if (!e1 || (m[4] && !e2)) continue;
            var tijd;
            if (e2) {
                // "het zesde en het negende uur" — het dagdeel hoeft maar één keer
                tijd = (!e1.los && !e2.los && e1.deel === e2.deel)
                    ? e1.getal + ' en ' + e2.getal + ' uur ' + e1.deel
                    : this._tijdTekst(e1) + ' en ' + this._tijdTekst(e2);
            } else {
                tijd = this._tijdTekst(e1);
            }
            // Met voorzetsel of "ongeveer" ervoor leest "omstreeks" beter;
            // zonder die aanloop hoort er alsnog een slag om de arm bij.
            var nieuw = ((m[1] || m[2]) ? 'omstreeks ' : 'ongeveer ') + tijd;
            neem(start, eind, 'tijd-omgerekend', volgHoofdletter(m[0], nieuw),
                 'Oorspronkelijk: ' + m[0] + ' · ' + (T.uurUitleg[snacht ? 'nacht' : 'dag'] || ''));
        }

        // === Nachtwaken met rangtelwoord: "ter vierde wake in de nacht" ===
        var schema = T.waken[testament === 'NT' ? 'nt' : 'ot'] || {};
        T.waakRe.lastIndex = 0;
        while ((m = T.waakRe.exec(plain)) !== null) {
            var wStart = m.index, wEind = wStart + m[0].length;
            if (!vrij(wStart, wEind)) continue;
            var nr = T.rangtelwoorden[m[1].toLowerCase()];
            var bereik = schema[String(nr)];
            if (!bereik) continue;                  // "vierde wake" bestaat niet in een driedeling
            neem(wStart, wEind, 'tijd-omgerekend',
                 volgHoofdletter(m[0], 'nachtwake ' + bereik),
                 'Oorspronkelijk: ' + m[0] + ' · ' + (schema.uitleg || ''));
        }

        // === Vaste frasen: morgenwake, middelste nachtwaak, tussen twee avonden ===
        var regels = T.genoemdeWaken.concat(T.frases);
        for (var r = 0; r < regels.length; r++) {
            var g = regels[r];
            if (g.alleenIn && !this._maatInBereik(g.alleenIn, book, ch, vnum)) continue;
            g.re.lastIndex = 0;
            while ((m = g.re.exec(plain)) !== null) {
                var fStart = m.index, fEind = fStart + m[0].length;
                if (!vrij(fStart, fEind)) continue;
                neem(fStart, fEind, 'tijd-omgerekend',
                     volgHoofdletter(m[0], m[0].replace(g.enkel, g.vervang)),
                     'Oorspronkelijk: ' + m[0] + ' · ' + (g.uitleg || ''));
            }
        }

        // === Alleen toelichten: het avondoffer blijft een offer, geen kloktijd ===
        for (var t = 0; t < T.toelichtingen.length; t++) {
            var u = T.toelichtingen[t];
            u.re.lastIndex = 0;
            while ((m = u.re.exec(plain)) !== null) {
                var tStart = m.index, tEind = tStart + m[0].length;
                if (!vrij(tStart, tEind)) continue;
                neem(tStart, tEind, 'tijd-toelichting', null, u.uitleg || '');
            }
        }

        if (!stukken.length) return html;
        stukken.sort(function (a, b) { return a.van - b.van; });
        var uit = '', vorig = 0;
        for (var i = 0; i < stukken.length; i++) {
            if (stukken[i].van < vorig) continue;
            uit += html.slice(vorig, stukken[i].van) + stukken[i].nieuw;
            vorig = stukken[i].tot;
        }
        return uit + html.slice(vorig);
    },

    /** Eén kloktijd uitschrijven; middernacht krijgt geen "uur" achter zich. */
    _tijdTekst(e) {
        return e.los ? e.los : (e.getal + ' uur ' + e.deel);
    },

    /**
     * De Godsnaam in de Open Parafrase Weergave. Die tekst schrijft HEERE, dus
     * dit werkt andersom dan transformOV: HEERE is de bron, JAHWEH de keuze.
     * Een eigen optie, omdat de OPV een andere brontekst heeft dan de OV.
     *
     * "de HEERE" wordt de naam zonder lidwoord, zodat "van de HEERE" vanzelf
     * "van JAHWEH" wordt en "De HEERE God maakte" "JAHWEH God maakte".
     * "Heere" (Adonai, of Jezus in het NT) is een ander woord en blijft staan.
     */
    transformOPV(html) {
        if (!html) return html;
        const naam = { jahweh: 'JAHWEH', jehovah: 'Jehovah', yehovah: 'Yehováh', jhwh: 'יהוה', yhwh: 'YHWH' }[this.state.godsnaamOPV];
        if (!naam) return html;
        return this._replaceOutsideTags(html, [
            [/\b(?:[Dd]e|DE) HEERE\b/g, naam],
            [/\bHEERE\b/g, naam],
        ]);
    },

    /**
     * Pas regex-replacements toe alleen op tekstdelen, niet binnen HTML-tags.
     */
    _replaceOutsideTags(html, pairs) {
        const tokenRegex = /(<[^>]+>)|([^<]+)/g;
        let result = '';
        let m;
        while ((m = tokenRegex.exec(html)) !== null) {
            if (m[1]) {
                result += m[1];           // HTML tag: laat staan
            } else {
                let txt = m[2];
                for (const [re, repl] of pairs) {
                    txt = txt.replace(re, repl);
                }
                result += txt;
            }
        }
        return result;
    },

    /**
     * Re-render het huidige hoofdstuk zodat opties-veranderingen direct zichtbaar zijn.
     */
    applyToCurrentChapter() {
        if (typeof Navigation !== 'undefined' && Navigation.currentBook && Navigation.currentChapter) {
            App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
        } else {
            // Naslag- en wikipagina's hebben geen hoofdstukrouter. Hun
            // citaten luisteren naar ov:opties-gewijzigd en worden daar via
            // de gedeelde tekstcomponent vernieuwd, zonder navigatie.
            if (typeof OVTekstweergave !== 'undefined' && OVTekstweergave.verversCitaten) {
                OVTekstweergave.verversCitaten(document);
            }
        }
    },
};

// Globaal beschikbaar maken: een top-level `const` komt niet op window terecht,
// terwijl mobile-nav.js en app.js (boekvolgorde, doorlopend lezen) `window.Opties`
// gebruiken. Zonder deze regel valt de boekvolgorde altijd terug op 'canoniek'.
if (typeof window !== 'undefined') window.Opties = Opties;
