const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const root = resolve(__dirname, '..');
const lees = pad => readFileSync(resolve(root, pad), 'utf8');

function opties() {
    const context = vm.createContext({ window: {} });
    for (const file of ['js/optie-maten.js', 'js/opties.js']) {
        vm.runInContext(lees(file), context);
    }
    const current = context.window.Opties;
    current.state = { ...current.DEFAULTS };
    return current;
}

/* embed.js draait buiten de lezer en heeft een eigen naamvervanging; de bestanden
   komen hier van schijf in plaats van via het netwerk. */
function insluiten() {
    const fetch = async url => {
        const pad = String(url).replace(/^https?:\/\/[^/]+/, '').replace(/^\//, '');
        try {
            const tekst = lees(pad);
            return { ok: true, json: async () => JSON.parse(tekst) };
        } catch (e) {
            return { ok: false, json: async () => null };
        }
    };
    const document = {
        currentScript: null, readyState: 'complete', head: { appendChild() {} },
        getElementById: () => null, createElement: () => ({}), querySelectorAll: () => [],
        addEventListener() {},
    };
    const window = { document, fetch, location: { hostname: 'localhost' },
        localStorage: { getItem: () => null } };
    const context = vm.createContext({ window, document, fetch, location: window.location,
        localStorage: window.localStorage });
    vm.runInContext(lees('embed.js'), context);
    return context.window.OSV;
}

function drukversie() {
    const document = { addEventListener() {} };
    const context = vm.createContext({ window: {}, document });
    vm.runInContext(lees('js/drukversie.js'), context);
    return context.window.Druk;
}

test('de keuze Yehováh vervangt JAHWEH in de Open Vertaling', () => {
    const current = opties();
    current.state.godsnaam = 'yehovah';
    assert.equal(current.transformOV('En JAHWEH zei tot Mozes', 'OT'), 'En Yehováh zei tot Mozes');
    assert.equal(current.transformOV('God JAHWEH maakte de mens', 'OT'), 'God Yehováh maakte de mens');
});

test('de keuze Yehováh blijft van HTML-attributen af', () => {
    const current = opties();
    current.state.godsnaam = 'yehovah';
    assert.equal(
        current.transformOV('<span title="JAHWEH">JAHWEH</span> is mijn Herder', 'OT'),
        '<span title="JAHWEH">Yehováh</span> is mijn Herder'
    );
});

test('de keuze Yehováh vervangt HEERE in de Open Parafrase, maar niet Heere', () => {
    const current = opties();
    current.state.godsnaamOPV = 'yehovah';
    assert.equal(
        current.transformOPV('De HEERE God maakte de mens, en de Heere zag het'),
        'Yehováh God maakte de mens, en de Heere zag het'
    );
    assert.equal(current.transformOPV('het woord van de HEERE'), 'het woord van Yehováh');
});

test('de lezer biedt Yehováh aan bij de Open Vertaling en bij de Open Parafrase', () => {
    const html = lees('index.html');
    assert.match(html, /<input type="radio" name="opt-godsnaam" data-optie="godsnaam" value="yehovah"> Yehováh \/ God Yehováh<\/label>/);
    assert.match(html, /<input type="radio" name="opt-godsnaamOPV" data-optie="godsnaamOPV" value="yehovah"> Yehováh<\/label>/);
});

test('een ingesloten citaat volgt de keuze yehovah', async () => {
    const uitkomst = await insluiten().cite('psalmen 23:1', { godsnaam: 'yehovah', link: false });
    assert.match(uitkomst.plain, /Yehováh is mijn Herder/);
    assert.doesNotMatch(uitkomst.plain, /JAHWEH/);
    assert.match(uitkomst.html, /Yehováh is mijn Herder/);
});

test('de insluitpagina biedt de keuze yehovah aan en noemt haar in de uitleg', () => {
    const html = lees('insluiten.html');
    assert.match(html, /<option value="yehovah">Yehováh<\/option>/);
    assert.match(html, /ov \/ klassiek \/ jehovah \/ yehovah \/ jhwh/);
});

test('de drukversie biedt Yehováh aan als Godsnaam', () => {
    const godsnaam = drukversie().LEESOPTIES.find(optie => optie[0] === 'godsnaam');
    // De lijst komt uit een andere vm-context; kopiëren maakt haar vergelijkbaar.
    assert.deepEqual(
        [...godsnaam[2]].map(keuze => keuze[0]),
        ['ov', 'klassiek', 'jehovah', 'yehovah', 'jhwh', 'yhwh']
    );
    assert.equal(godsnaam[2].find(keuze => keuze[0] === 'yehovah')[1], 'Yehováh');
});

test('de uitlegpagina noemt Yehováh bij de keuzes voor de Godsnaam', () => {
    assert.match(lees('over-ov.html'), /Godsnaam &mdash; 5 opties:<\/strong>[^<]*Yehováh/);
});
