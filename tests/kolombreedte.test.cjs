// De breedte van tekst en kanttekeningen is met slepen in te stellen.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const lees = pad => readFileSync(resolve(__dirname, '..', pad), 'utf8');

function module() {
    const document = { addEventListener() {}, readyState: 'loading' };
    const context = vm.createContext({ window: { document }, document });
    vm.runInContext(lees('js/kolombreedte.js'), context);
    return context.window.KolomBreedte;
}

test('het aandeel van de kanttekeningen volgt de plek van de greep', () => {
    const k = module();
    // Rij van 100 tot 1100: een greep op 700 laat 400 van de 1000 pixels aan de noten.
    assert.equal(k.aandeelUit(700, 100, 1100), 0.4);
});

test('het aandeel blijft tussen een vijfde en drie vijfde', () => {
    const k = module();
    assert.equal(k.aandeelUit(1090, 100, 1100), 0.2);
    assert.equal(k.aandeelUit(150, 100, 1100), 0.6);
    assert.equal(k.begrens(Number.NaN), k.STANDAARD);
});

test('de kolommen lezen hun breedte uit een variabele', () => {
    const css = lees('css/publication.css');
    assert.match(css, /grid-template-columns:2rem minmax\(0,var\(--kt-tekst,1\.7fr\)\) minmax\(0,var\(--kt-noten,1fr\)\)/);
    assert.match(css, /\.kt-greep \{/);
});

test('de lezer laadt de module', () => {
    assert.match(lees('index.html'), /<script src="js\/kolombreedte\.js\?v=1"><\/script>/);
});

test('geen lookbehind: die breekt de lezer op iPadOS 15', () => {
    assert.doesNotMatch(lees('js/kolombreedte.js'), /\(\?<[=!]/);
});
