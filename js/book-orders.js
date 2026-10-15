/* Open Vertaling — Boek-orderings
 *
 * Centrale definitie van alle ondersteunde boek-orderings.
 * Elke ordering is een object met groep-labels als keys en book-id arrays als values.
 * Gebruikt door Sidebar.renderTree() en Navigation.renderBookNav().
 */

const BookOrders = {

    // === Canoniek (Statenvertaling / Westerse Christelijke canon) ===
    // Pentateuch → historisch → poëtisch → profeten → apocriefen → NT
    canoniek: {
        label: 'Canoniek (SV)',
        groups: {
            'Pentateuch': ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Historische boeken': ['jozua', 'richteren', 'ruth', '1samuel', '2samuel', '1koningen', '2koningen', '1kronieken', '2kronieken', 'ezra', 'nehemia', 'esther'],
            'Poëtische boeken': ['job', 'psalmen', 'spreuken', 'prediker', 'hooglied'],
            'Grote profeten': ['jesaja', 'jeremia', 'klaagliederen', 'ezechiel', 'daniel'],
            'Kleine profeten': ['hosea', 'joel', 'amos', 'obadja', 'jona', 'micha', 'nahum', 'habakuk', 'zefanja', 'haggai', 'zacharia', 'maleachi'],
            'Apocriefen': ['3ezra', '4ezra', 'tobit', 'judith', 'boekderwijsheid', 'jezussirach', 'baruch', 'estherapocrief', 'gebedvanazaria', 'gezangindevuuroven', 'susanna', 'belenddedraak', 'gebedvanmanasse', '1makkabeeen', '2makkabeeen', '3makkabeeen'],
            'Evangeliën': ['mattheus', 'markus', 'lukas', 'johannes'],
            'Handelingen': ['handelingen'],
            'Brieven van Paulus': ['romeinen', '1korinthiers', '2korinthiers', 'galaten', 'efeziers', 'filippenzen', 'kolossenzen', '1tessalonicensen', '2tessalonicensen', '1timotheus', '2timotheus', 'titus', 'filemon'],
            'Algemene brieven': ['hebreeen', 'jakobus', '1petrus', '2petrus', '1johannes', '2johannes', '3johannes', 'judas'],
            'Openbaring': ['openbaring'],
        }
    },

    // === Joodse Tenach (TNK) ===
    // Torah → Nevi'im (vroege+late+twaalf) → Ketuvim (incl. 5 megillot)
    // Eindigt met 2 Kronieken — apocriefen + NT volgen daarna in westerse volgorde
    tenach: {
        label: 'Joodse Tenach',
        groups: {
            'Torah (Wet)': ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Vroege Profeten': ['jozua', 'richteren', '1samuel', '2samuel', '1koningen', '2koningen'],
            'Late Profeten': ['jesaja', 'jeremia', 'ezechiel'],
            'De Twaalf (kleine profeten)': ['hosea', 'joel', 'amos', 'obadja', 'jona', 'micha', 'nahum', 'habakuk', 'zefanja', 'haggai', 'zacharia', 'maleachi'],
            'Geschriften — poëtisch': ['psalmen', 'spreuken', 'job'],
            'Geschriften — Megillot (5 rollen)': ['hooglied', 'ruth', 'klaagliederen', 'prediker', 'esther'],
            'Geschriften — overig': ['daniel', 'ezra', 'nehemia', '1kronieken', '2kronieken'],
            'Apocriefen': ['3ezra', '4ezra', 'tobit', 'judith', 'boekderwijsheid', 'jezussirach', 'baruch', 'estherapocrief', 'gebedvanazaria', 'gezangindevuuroven', 'susanna', 'belenddedraak', 'gebedvanmanasse', '1makkabeeen', '2makkabeeen', '3makkabeeen'],
            'Nieuwe Testament': ['mattheus', 'markus', 'lukas', 'johannes', 'handelingen', 'romeinen', '1korinthiers', '2korinthiers', 'galaten', 'efeziers', 'filippenzen', 'kolossenzen', '1tessalonicensen', '2tessalonicensen', '1timotheus', '2timotheus', 'titus', 'filemon', 'hebreeen', 'jakobus', '1petrus', '2petrus', '1johannes', '2johannes', '3johannes', 'judas', 'openbaring'],
        }
    },

    // === Orthodox (Septuaginta / LXX) ===
    // Oosters-Orthodoxe canon op basis van de Septuaginta:
    //  - deuterocanonieke boeken geïntegreerd tussen de historische en wijsheidsboeken
    //  - De Twaalf (kleine profeten) VÓÓR de grote profeten
    //  - 1 Esdras = 3 Ezra; 2 Esdras = Ezra + Nehemia; Brief van Jeremia = Baruch 6
    orthodox: {
        label: 'Orthodox (Septuaginta)',
        groups: {
            'Pentateuch (Wet)': ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Historische boeken': ['jozua', 'richteren', 'ruth', '1samuel', '2samuel', '1koningen', '2koningen', '1kronieken', '2kronieken', '3ezra', 'ezra', 'nehemia', 'tobit', 'judith', 'esther', 'estherapocrief', '1makkabeeen', '2makkabeeen', '3makkabeeen'],
            'Wijsheid & poëzie': ['psalmen', 'gebedvanmanasse', 'job', 'spreuken', 'prediker', 'hooglied', 'boekderwijsheid', 'jezussirach'],
            'De Twaalf (kleine profeten)': ['hosea', 'amos', 'micha', 'joel', 'obadja', 'jona', 'nahum', 'habakuk', 'zefanja', 'haggai', 'zacharia', 'maleachi'],
            'Grote profeten': ['jesaja', 'jeremia', 'baruch', 'klaagliederen', 'ezechiel', 'daniel', 'gebedvanazaria', 'gezangindevuuroven', 'susanna', 'belenddedraak'],
            '4 Ezra (aanhangsel)': ['4ezra'],
            'Evangeliën': ['mattheus', 'markus', 'lukas', 'johannes'],
            'Handelingen': ['handelingen'],
            'Algemene brieven': ['jakobus', '1petrus', '2petrus', '1johannes', '2johannes', '3johannes', 'judas'],
            'Brieven van Paulus': ['romeinen', '1korinthiers', '2korinthiers', 'galaten', 'efeziers', 'filippenzen', 'kolossenzen', '1tessalonicensen', '2tessalonicensen', '1timotheus', '2timotheus', 'titus', 'filemon', 'hebreeen'],
            'Openbaring': ['openbaring'],
        }
    },

    // === Chronologisch (gebeurtenissen-tijdlijn) ===
    // Op basis van wanneer de gebeurtenissen plaatsvonden (niet schrijftijd).
    // Globale ordening; sommige boeken gelijktijdig — vrije keuze in plaatsing.
    chronologisch: {
        label: 'Chronologisch',
        groups: {
            'Oer-geschiedenis (Gen 1-11)': ['genesis'],
            'Patriarchen + Job': ['job'],
            'Exodus & woestijnreis': ['exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Verovering & Richters': ['jozua', 'richteren', 'ruth'],
            'Koningstijd vroeg (Saul, David)': ['1samuel', '2samuel', 'psalmen'],
            'Koningstijd (Salomo, scheuring, profeten)': ['1koningen', 'spreuken', 'prediker', 'hooglied', 'jona', 'amos', 'hosea', 'jesaja', 'micha'],
            'Vóór de ballingschap': ['2koningen', '1kronieken', '2kronieken', 'nahum', 'zefanja', 'habakuk', 'jeremia', 'klaagliederen'],
            'Ballingschap': ['ezechiel', 'daniel', 'obadja', 'joel'],
            'Na de ballingschap': ['ezra', 'haggai', 'zacharia', 'esther', 'nehemia', 'maleachi'],
            'Intertestamentaire periode (apocriefen)': ['3ezra', '4ezra', 'tobit', 'judith', 'boekderwijsheid', 'jezussirach', 'baruch', 'estherapocrief', 'gebedvanazaria', 'gezangindevuuroven', 'susanna', 'belenddedraak', 'gebedvanmanasse', '1makkabeeen', '2makkabeeen', '3makkabeeen'],
            'Evangeliën (leven Jezus)': ['mattheus', 'markus', 'lukas', 'johannes'],
            'Vroege kerk + Paulus-brieven': ['handelingen', 'galaten', '1tessalonicensen', '2tessalonicensen', '1korinthiers', '2korinthiers', 'romeinen', 'jakobus', 'efeziers', 'kolossenzen', 'filemon', 'filippenzen', '1timotheus', 'titus', '2timotheus', '1petrus', '2petrus', 'hebreeen', 'judas'],
            'Johannes-geschriften': ['1johannes', '2johannes', '3johannes', 'openbaring'],
        }
    },

    // === Vermoedelijke schrijftijd (wanneer geschreven) ===
    // Op basis van de geschatte ontstaanstijd van de TEKST (niet de gebeurtenissen).
    // Datering is onzeker en omstreden; hier een gangbare, traditioneel-behoudende
    // schatting met periode-labels.
    schrijftijd: {
        label: 'Vermoedelijke schrijftijd',
        groups: {
            'Patriarchale tijd (Job, zeer oud)': ['job'],
            'Mozes — Pentateuch (±1440–1400 v.Chr.)': ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Intrede & Richtertijd (±1400–1050)': ['jozua', 'richteren', 'ruth'],
            'Verenigd koninkrijk — David & Salomo (±1010–930)': ['psalmen', 'spreuken', 'prediker', 'hooglied'],
            '8e eeuw v.Chr. (vroege schrijvende profeten)': ['obadja', 'joel', 'jona', 'amos', 'hosea', 'jesaja', 'micha'],
            '7e eeuw v.Chr. (vóór de ballingschap)': ['nahum', 'zefanja', 'habakuk', 'jeremia', 'klaagliederen'],
            'Ballingschap — 6e eeuw v.Chr.': ['ezechiel', 'daniel', '1samuel', '2samuel', '1koningen', '2koningen'],
            'Na de ballingschap (±520–430)': ['haggai', 'zacharia', 'maleachi', 'ezra', 'nehemia', 'esther', '1kronieken', '2kronieken'],
            'Intertestamentair — apocriefen (±300–50 v.Chr.)': ['3ezra', '4ezra', 'tobit', 'judith', 'boekderwijsheid', 'jezussirach', 'baruch', 'estherapocrief', 'gebedvanazaria', 'gezangindevuuroven', 'susanna', 'belenddedraak', 'gebedvanmanasse', '1makkabeeen', '2makkabeeen', '3makkabeeen'],
            'Vroege brieven (±45–52 n.Chr.)': ['jakobus', 'galaten', '1tessalonicensen', '2tessalonicensen'],
            'Grote Paulus-brieven (±55–57)': ['1korinthiers', '2korinthiers', 'romeinen'],
            'Evangeliën & Handelingen (±60–65)': ['markus', 'mattheus', 'lukas', 'handelingen'],
            'Gevangenisbrieven (±60–62)': ['efeziers', 'filippenzen', 'kolossenzen', 'filemon'],
            'Latere brieven (±63–68)': ['1timotheus', 'titus', '1petrus', '2timotheus', '2petrus', 'hebreeen', 'judas'],
            'Johannes-geschriften (±85–95)': ['johannes', '1johannes', '2johannes', '3johannes', 'openbaring'],
        }
    },

    // === Op auteur / traditie ===
    auteur: {
        label: 'Op auteur',
        groups: {
            'Mozes (Pentateuch)': ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Anoniem-historisch (DtrH)': ['jozua', 'richteren', 'ruth', '1samuel', '2samuel', '1koningen', '2koningen'],
            'Kroniekschrijver': ['1kronieken', '2kronieken', 'ezra', 'nehemia', 'esther'],
            'David & andere psalmisten': ['psalmen'],
            'Salomo (wijsheid)': ['spreuken', 'prediker', 'hooglied'],
            'Job (anoniem)': ['job'],
            'Klaagliederen (Jeremia)': ['klaagliederen'],
            'Profeten (elk eigen auteur)': ['jesaja', 'jeremia', 'ezechiel', 'daniel', 'hosea', 'joel', 'amos', 'obadja', 'jona', 'micha', 'nahum', 'habakuk', 'zefanja', 'haggai', 'zacharia', 'maleachi'],
            'Apocriefen (diverse auteurs)': ['3ezra', '4ezra', 'tobit', 'judith', 'boekderwijsheid', 'jezussirach', 'baruch', 'estherapocrief', 'gebedvanazaria', 'gezangindevuuroven', 'susanna', 'belenddedraak', 'gebedvanmanasse', '1makkabeeen', '2makkabeeen', '3makkabeeen'],
            'Mattheüs': ['mattheus'],
            'Markus': ['markus'],
            'Lukas (Lk + Hd)': ['lukas', 'handelingen'],
            'Johannes (Ev + brieven + Openb)': ['johannes', '1johannes', '2johannes', '3johannes', 'openbaring'],
            'Paulus': ['romeinen', '1korinthiers', '2korinthiers', 'galaten', 'efeziers', 'filippenzen', 'kolossenzen', '1tessalonicensen', '2tessalonicensen', '1timotheus', '2timotheus', 'titus', 'filemon'],
            'Hebreeën (anoniem)': ['hebreeen'],
            'Jakobus': ['jakobus'],
            'Petrus': ['1petrus', '2petrus'],
            'Judas': ['judas'],
        }
    },

    // === Op lengte (aantal hoofdstukken — groot naar klein) ===
    // Volgorde wordt dynamisch berekend in getGroups() o.b.v. manifest.
    lengte: {
        label: 'Op lengte',
        groups: null,  // dynamisch
        dynamic: 'lengte',
    },
};

// === Ethiopische (Tewahedo) toevoegingen ===
// De extra boeken van de Ethiopisch-Orthodoxe canon (Henoch, Jubileeën, 1-3 Meqabyan, 4 Baruch).
// Deze worden in ELKE volgorde getoond als aparte groep direct ná de apocriefen (zie
// getBookOrderGroups) — standaard ingeklapt in de zijbalk (zie Sidebar.renderTree).
const ETHIOPIC_BOOKS = ['henoch', 'jubileeen', '1meqabyan', '2meqabyan', '3meqabyan', '4baruch'];
const ETHIOPIC_GROUP_LABEL = 'Ethiopische boeken (buiten de canon)';

function isBookVisibleInNavigation(book) {
    if (!book) return false;
    const options = (typeof window !== 'undefined' && window.Opties && Opties.state) || {};
    const isEthiopic = book.ethiopic || book.testament === 'ET' || ETHIOPIC_BOOKS.includes(book.id);
    if (isEthiopic) return false;
    if (book.testament === 'AP') return options.apocriefeBoeken !== 'uit';
    return true;
}

function onlyVisibleBooks(groups, manifest) {
    const byId = Object.fromEntries((manifest.books || []).map(book => [book.id, book]));
    return Object.fromEntries(Object.entries(groups).map(([label, ids]) => [
        label,
        ids.filter(id => isBookVisibleInNavigation(byId[id])),
    ]));
}

// Aparte 'ethiopisch'-volgorde blijft bestaan (canonieke ordening; de groep wordt
// automatisch toegevoegd door getBookOrderGroups, dus hier niet nogmaals opnemen).
BookOrders.ethiopisch = {
    label: 'Ethiopisch (Tewahedo)',
    groups: Object.assign({}, BookOrders.canoniek.groups),
};

/**
 * Geef de groepen voor een gegeven ordering.
 * Voor dynamische orderings (lengte) wordt het manifest gebruikt.
 *
 * @param {string} mode - ordering-key uit BookOrders
 * @param {object} manifest - { books: [...] } met chaptersIncluded per boek
 * @returns {Object<string, string[]>}  groepen → array van book-ids
 */
// Voeg de Ethiopische-boeken-groep in, direct ná de laatste groep die een
// apocrief boek bevat (1 Makkabeeën komt in elke apocrifen-groep voor). Bestaat
// de groep al, of ontbreken de boeken in het manifest, dan gebeurt er niets.
function withEthiopic(groups, manifest) {
    const present = new Set((manifest && manifest.books ? manifest.books : []).map(b => b.id));
    const eth = ETHIOPIC_BOOKS.filter(id => present.has(id));
    if (eth.length === 0) return groups;
    const keys = Object.keys(groups);
    if (keys.some(k => groups[k].some(id => ETHIOPIC_BOOKS.includes(id)))) return groups; // al aanwezig
    // Hang de Ethiopische boeken als subcategorie ACHTER de apocriefen (groep met 1 Makkabeeën),
    // binnen diezelfde groep — dus geen eigen top-categorie meer. De zijbalk toont er een sub-kop.
    const apoKey = keys.find(k => groups[k].includes('1makkabeeen'));
    const out = {};
    keys.forEach(k => {
        out[k] = (k === apoKey) ? groups[k].concat(eth) : groups[k]; // concat = kopie, muteert bron-array niet
    });
    if (!apoKey) out[ETHIOPIC_GROUP_LABEL] = eth; // geen apocriefen-groep → dan toch eigen groep achteraan
    return out;
}

function getBookOrderGroups(mode, manifest) {
    const ordering = BookOrders[mode] || BookOrders.canoniek;

    if (ordering.dynamic === 'lengte') {
        // Sorteer alle boeken op aantal hoofdstukken (groot → klein), per categorie
        const buckets = {
            'Zeer lang (≥40 hfdst)': [],
            'Lang (20–39 hfdst)': [],
            'Middel (10–19 hfdst)': [],
            'Kort (4–9 hfdst)': [],
            'Zeer kort (1–3 hfdst)': [],
        };
        const sorted = [...manifest.books].filter(b => !b.ethiopic).sort((a, b) => (b.totalChapters || 0) - (a.totalChapters || 0));
        for (const b of sorted) {
            const n = b.totalChapters || (b.chaptersIncluded ? b.chaptersIncluded.length : 0);
            if (n >= 40) buckets['Zeer lang (≥40 hfdst)'].push(b.id);
            else if (n >= 20) buckets['Lang (20–39 hfdst)'].push(b.id);
            else if (n >= 10) buckets['Middel (10–19 hfdst)'].push(b.id);
            else if (n >= 4) buckets['Kort (4–9 hfdst)'].push(b.id);
            else buckets['Zeer kort (1–3 hfdst)'].push(b.id);
        }
        return onlyVisibleBooks(withEthiopic(buckets, manifest), manifest);
    }

    return onlyVisibleBooks(withEthiopic(ordering.groups, manifest), manifest);
}

/**
 * Geef een flat-list van alle book-ids in volgorde voor de gekozen ordening.
 * Voegt boeken toe die nog niet in een groep zitten als 'Overig'.
 */
function getFlatBookOrder(mode, manifest) {
    const groups = getBookOrderGroups(mode, manifest);
    const allIds = new Set(manifest.books.filter(isBookVisibleInNavigation).map(b => b.id));
    const ordered = [];
    const seen = new Set();
    for (const ids of Object.values(groups)) {
        for (const id of ids) {
            if (allIds.has(id) && !seen.has(id)) {
                ordered.push(id);
                seen.add(id);
            }
        }
    }
    // Voeg ontbrekende toe in manifest-volgorde — behalve Ethiopische boeken buiten de ethiopisch-volgorde
    for (const b of manifest.books) {
        if (!seen.has(b.id) && isBookVisibleInNavigation(b)) {
            ordered.push(b.id);
            seen.add(b.id);
        }
    }
    return ordered;
}

// Expose globally
if (typeof window !== 'undefined') {
    window.BookOrders = BookOrders;
    window.getBookOrderGroups = getBookOrderGroups;
    window.getFlatBookOrder = getFlatBookOrder;
    window.isBookVisibleInNavigation = isBookVisibleInNavigation;
    window.ETHIOPIC_GROUP_LABEL = ETHIOPIC_GROUP_LABEL;
    window.ETHIOPIC_BOOKS = ETHIOPIC_BOOKS;
}
