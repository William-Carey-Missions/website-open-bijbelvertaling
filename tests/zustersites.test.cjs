// De strook met zustersites staat letterlijk gelijk in de drie sites (Open
// Vertaling, Open Gods Woord, Open Parafrase Weergave). Hetzelfde testbestand
// staat in alle drie; het toetst het blok in js/topnav.js van deze repo.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');

const bron = readFileSync(resolve(__dirname, '..', 'js', 'topnav.js'), 'utf8');
const BEGIN = '    /* === Zustersites: gelijk in de drie sites';
const EINDE = '    /* === einde zustersites';

function blok() {
    const a = bron.indexOf(BEGIN);
    const b = bron.indexOf(EINDE);
    assert.ok(a >= 0 && b > a, 'het gedeelde blok staat in js/topnav.js');
    return bron.slice(a, b);
}

function strook(huidig) {
    const head = { kinderen: [], appendChild(el) { this.kinderen.push(el); } };
    const document = {
        head,
        getElementById: id => head.kinderen.find(el => el.id === id) || null,
        createElement: () => ({ setAttribute(k, v) { this[k] = v; } }),
    };
    const context = vm.createContext({ document, window: {} });
    vm.runInContext(blok() + '\n;globalThis.uitkomst = familiestrook(' + JSON.stringify(huidig) + ');', context);
    return { el: context.uitkomst, stijl: head.kinderen };
}

test('de eigen site roept de strook aan met zijn eigen sleutel', () => {
    const aanroepen = bron.match(/familiestrook\('(ov|ogw|opv)'\)/g) || [];
    assert.equal(aanroepen.length, 1);
    assert.match(bron, /nav\.insertAdjacentElement\('beforebegin', familiestrook\('(ov|ogw|opv)'\)\)/);
});

test('de drie sites staan in dezelfde volgorde, de eigen site gemarkeerd', () => {
    for (const [huidig, naam] of [['ov', 'Open Vertaling'], ['ogw', 'Open Gods Woord'], ['opv', 'Open Parafrase Weergave']]) {
        const { el, stijl } = strook(huidig);
        assert.equal(el.id, 'ka-fam');
        assert.equal(el['aria-label'], 'Zustersites van de kleine ark');
        const namen = [...el.innerHTML.matchAll(/<a [^>]*>([^<]+)<\/a>/g)].map(m => m[1]);
        assert.deepEqual(namen, ['Open Vertaling', 'Open Gods Woord', 'Open Parafrase Weergave']);
        assert.match(el.innerHTML, new RegExp('<a href="index.html" aria-current="page">' + naam + '</a>'));
        assert.equal((el.innerHTML.match(/aria-current/g) || []).length, 1);
        assert.equal(stijl.length, 1, 'de opmaak komt één keer mee');
        assert.match(stijl[0].textContent, /\.ka-fam \{/);
    }
});

test('de oude eigen strook van de Open Parafrase is weg', () => {
    assert.doesNotMatch(bron, /opv-zus/);
});
