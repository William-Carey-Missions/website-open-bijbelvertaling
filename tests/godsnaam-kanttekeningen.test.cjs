// Kanttekeningen en inleidingen volgen dezelfde Godsnaam-keuze als de Bijbeltekst.
// Zonder deze omzetting stond in de noten "JAHWEH" terwijl de tekst "HEERE" toont.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const lees = pad => readFileSync(resolve(__dirname, '..', pad), 'utf8');

function opties() {
    const context = vm.createContext({ window: {} });
    for (const file of ['js/optie-maten.js', 'js/opties.js']) {
        try { vm.runInContext(lees(file), context); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    }
    const current = context.window.Opties || vm.runInContext('Opties', context);
    current.state = { ...current.DEFAULTS };
    return current;
}

test('een kanttekening met JAHWEH volgt de standaardweergave van de site', () => {
    const current = opties();
    const uit = current.transformOV('Versta, de tabernakel, waarin God kwam om met JAHWEH te spreken.');
    assert.doesNotMatch(uit, /JAHWEH/);
});

test('de kanttekeningkolom zet de godsnaam om', () => {
    assert.match(lees('js/chapter-renderer.js'), /tekst\.innerHTML = ChapterRenderer\.godsnaam\(/);
    assert.match(lees('js/chapter-renderer.js'), /kanttekeningCel\(verse, bookId, chapterNum, book\.testament\)/);
});

test('het notenvenster zet de godsnaam om', () => {
    assert.match(lees('js/editor.js'), /ChapterRenderer\.godsnaam\(References\.linkify\(note\.text2026/);
});

test('boek- en hoofdstukinleiding zetten de godsnaam om', () => {
    const bron = lees('js/chapter-renderer.js');
    assert.match(bron, /ChapterRenderer\.godsnaam\(book\.bookIntro\.text2026/);
    assert.match(bron, /ChapterRenderer\.godsnaam\(chapter\.chapterIntro\.text2026/);
});

test('de kanttekeningen op de startpagina zetten de godsnaam om', () => {
    assert.match(lees('js/startscherm.js'), /Opties\.transformOV\(References\.linkify\(bron, 'johannes', 1\), 'NT'\)/);
});
