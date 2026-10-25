// De Godsnaam-keuze YHWH: de vier medeklinkers in Latijnse letters, naast יהוה.
// Hetzelfde testbestand staat in de drie sites; het toetst alleen wat er in de
// betreffende repo bestaat (de Open Parafrase heeft bijvoorbeeld geen embed.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { existsSync, readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const root = resolve(__dirname, '..');
const lees = pad => readFileSync(resolve(root, pad), 'utf8');
const heeft = pad => existsSync(resolve(root, pad));

function opties() {
    const context = vm.createContext({ window: {} });
    for (const file of ['js/optie-maten.js', 'js/opties.js']) {
        if (heeft(file)) vm.runInContext(lees(file), context);
    }
    const current = context.window.Opties || vm.runInContext('Opties', context);
    current.state = { ...current.DEFAULTS };
    return current;
}

/* embed.js draait buiten de lezer; de bestanden komen hier van schijf. */
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

test('de keuze YHWH vervangt JAHWEH in de Open Vertaling', () => {
    const current = opties();
    current.state.godsnaam = 'yhwh';
    assert.equal(current.transformOV('En JAHWEH zei tot Mozes', 'OT'), 'En YHWH zei tot Mozes');
    assert.equal(current.transformOV('God JAHWEH maakte de mens', 'OT'), 'God YHWH maakte de mens');
    assert.equal(
        current.transformOV('<span title="JAHWEH">JAHWEH</span> is mijn Herder', 'OT'),
        '<span title="JAHWEH">YHWH</span> is mijn Herder'
    );
});

test('de keuze YHWH vervangt HEERE in de Open Parafrase, maar niet Heere', () => {
    const current = opties();
    current.state.godsnaamOPV = 'yhwh';
    assert.equal(
        current.transformOPV('De HEERE God maakte de mens, en de Heere zag het'),
        'YHWH God maakte de mens, en de Heere zag het'
    );
    assert.equal(current.transformOPV('het woord van de HEERE'), 'het woord van YHWH');
});

test('een ingesloten citaat volgt de keuze yhwh', { skip: !heeft('embed.js') && 'geen embed.js' }, async () => {
    const uitkomst = await insluiten().cite('genesis 2:7', { godsnaam: 'yhwh', link: false });
    assert.match(uitkomst.plain, /God YHWH had de mens gevormd/);
    assert.doesNotMatch(uitkomst.plain, /JAHWEH/);
});

test('het optiepaneel biedt YHWH aan', { skip: !/value="jhwh"/.test(heeft('index.html') ? lees('index.html') : '') && 'geen Godsnaam-keuze in de lezer' }, () => {
    const html = lees('index.html');
    if (/data-optie="godsnaam" value="jhwh"/.test(html)) {
        assert.match(html, /<input type="radio" name="opt-godsnaam" data-optie="godsnaam" value="yhwh"> YHWH \/ God YHWH<\/label>/);
    }
    if (/data-optie="godsnaamOPV" value="jhwh"/.test(html)) {
        assert.match(html, /<input type="radio" name="opt-godsnaamOPV" data-optie="godsnaamOPV" value="yhwh"> YHWH<\/label>/);
    }
});

test('de insluitpagina noemt YHWH', { skip: !heeft('insluiten.html') && 'geen insluitpagina' }, () => {
    const html = lees('insluiten.html');
    assert.match(html, /<option value="yhwh">YHWH<\/option>/);
    assert.match(html, /ov \/ klassiek \/ jehovah \/ yehovah \/ jhwh \/ yhwh/);
});

test('de drukversie biedt YHWH aan', { skip: !heeft('js/drukversie.js') && 'geen drukversie' }, () => {
    const context = vm.createContext({ window: {}, document: { addEventListener() {} } });
    vm.runInContext(lees('js/drukversie.js'), context);
    const godsnaam = context.window.Druk.LEESOPTIES.find(optie => optie[0] === 'godsnaam');
    assert.equal(godsnaam[2].find(keuze => keuze[0] === 'yhwh')[1], 'YHWH');
});

test('YHWH is de standaard voor beide leesedities', () => {
    const current = opties();
    assert.equal(current.DEFAULTS.godsnaam, 'yhwh');
    assert.equal(current.DEFAULTS.godsnaamOPV, 'yhwh');
    assert.equal(current.transformOV('God JAHWEH sprak tot JAHWEH', 'OT'), 'God YHWH sprak tot YHWH');
    assert.equal(current.transformOPV('De HEERE God sprak, de Heere hoorde'), 'YHWH God sprak, de Heere hoorde');
});

test('een bewaarde Godsnaam-keuze blijft behouden', () => {
    const current = opties();
    current.state.godsnaam = 'jehovah';
    current.state.godsnaamOPV = 'heere';
    if (current.enforceReaderOptions) current.enforceReaderOptions();
    assert.equal(current.state.godsnaam, 'jehovah');
    assert.equal(current.transformOV('God JAHWEH sprak', 'OT'), 'God Jehovah sprak');
    assert.equal(current.transformOPV('de HEERE sprak'), 'de HEERE sprak');
});

test('een ingesloten citaat gebruikt standaard YHWH', { skip: !heeft('embed.js') && 'geen embed.js' }, async () => {
    const uitkomst = await insluiten().cite('genesis 2:7', { link: false });
    assert.match(uitkomst.plain, /God YHWH had de mens gevormd/);
});