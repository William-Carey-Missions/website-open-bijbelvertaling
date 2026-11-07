"""De uitgave met kanttekeningen: notenopschoning, merktekens en de bladzijdeopbouw."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
pytest.importorskip('uharfbuzz')
pytest.importorskip('pyphen')

import build_kanttekeningen_pdf as bouw  # noqa: E402


def test_ingevoegde_verstekst_verdwijnt_en_de_verwijzing_blijft():
    _, tekst = bouw.schoon_noot('Zie Joh. 5:39 ; 2 Tim. 3:15 . Johannes 5:39 : Onderzoekt de Schriften.', '18', '')
    assert tekst == 'Zie Joh. 5:39; 2 Tim. 3:15.'


def test_noot_met_alleen_een_verstekst_houdt_de_plaats():
    _, tekst = bouw.schoon_noot('Psalmen 48:1 : Een lied, een psalm.', '3', '')
    assert tekst == 'Psalmen 48:1'


def test_dubbel_cijfer_gaat_weg_maar_een_boeknummer_niet():
    assert bouw.schoon_noot('46 Waarom zo: Dat is, haast.', '46', 'waarom zo')[0] == 'Waarom zo'
    assert bouw.schoon_noot('1 Kor. 1:22.', '1', '')[1] == '1 Kor. 1:22.'


def test_lemma_moet_uit_het_vers_komen():
    vers = 'En het land was woest'
    assert bouw.schoon_noot('het land: Dat is, de aarde.', '1', vers) == ('het land', 'D.i. de aarde.')
    assert bouw.schoon_noot('Scheppen betekent in dit hoofdstuk: iets maken.', '2', vers)[0] == ''
    assert bouw.schoon_noot('Dat wil zeggen: het land.', '3', vers)[0] == ''


def test_godsnaam_is_de_standaard_van_de_site():
    assert bouw.godsnaam('de God JAHWEH') == 'de God YHWH'
    opties = (ROOT / 'js' / 'opties.js').read_text(encoding='utf-8')
    assert re.search(r"godsnaam:\s*'yhwh'", opties)


def test_merkteken_staat_voor_het_woord_waarop_het_slaat():
    sup = '<sup class="note-marker" data-note="{0}">{0}</sup>'
    vers = {'text2026_html': 'In' + sup.format(1) + sup.format('a') + ' het begin' + sup.format(2) + ' schiep God.'}
    woorden = bouw.vers_woorden(vers)
    assert [(w['voor'], w['tekst']) for w in woorden] == [
        ([], 'In'), (['1', 'a'], 'het'), ([], 'begin'), (['2'], 'schiep'), ([], 'God.')]


def test_merkteken_aan_het_eind_komt_voor_het_laatste_woord():
    sup = '<sup class="note-marker" data-note="7">7</sup>'
    woorden = bouw.vers_woorden({'text2026_html': 'Hij kwam thuis.' + sup})
    assert woorden[-1]['voor'] == ['7']
    assert woorden[-1]['tekst'] == 'thuis.'


def test_noot_zonder_merkteken_krijgt_een_plek_bij_het_besproken_woord():
    vers = {'text2026_html': 'Roep luide over Jakob', 'marginNotes': [
        {'marker': '17', 'type': 'explanatory', 'text2026': '17 over Jakob: Of, zingt.'}]}
    woorden = bouw.vers_woorden(vers)
    per_merk = bouw.hang_noten_aan(vers, woorden, 'Roep luide over Jakob')
    assert woorden[2]['voor'] == ['17'] and '17' in per_merk


def test_alle_boeken_staan_in_precies_een_deel_en_de_ethiopische_niet():
    boeken = [b for d in bouw.DELEN.values() for _, groep in d['groepen'] for b in groep]
    index = json.loads((ROOT / 'data' / 'books-index.json').read_text(encoding='utf-8'))['boeken']
    assert sorted(boeken) == sorted(b['id'] for b in index)
    assert set(boeken) == set(bouw.TITELS)
    assert not {'henoch', 'jubileeen', '1meqabyan', '2meqabyan', '3meqabyan', '4baruch'} & set(boeken)


def test_proef_van_een_klein_boek(tmp_path):
    verslag = bouw.bouw_deel(2, tmp_path, '2 november 2026', ('obadja', {1}))
    assert verslag['verzen'] == 21
    assert verslag['controle']['noot_te_laat'] == 0
    assert verslag['te_brede_alineas'] == 0 and not verslag['onbekende_tekens']
    data = (tmp_path / bouw.UITVOERNAAM.format(2)).read_bytes()
    assert data.startswith(b'%PDF-') and b'/FontFile2' in data


def test_pagina_wijst_naar_de_drie_delen_zonder_lookbehind():
    html = (ROOT / 'kanttekeningen.html').read_text(encoding='utf-8')
    for deel in bouw.DELEN:
        assert bouw.UITVOERNAAM.format(deel) in html
        assert f'images/kanttekeningen/deel-{deel}.webp' in html
        assert (ROOT / 'images' / 'kanttekeningen' / f'deel-{deel}.webp').is_file()
    assert '(?<' not in html
    for naam in json.loads((ROOT / 'data' / 'books-index.json').read_text(encoding='utf-8'))['boeken']:
        assert naam['naam'] in html


def test_godscitaten_behouden_geneste_opmaak_en_nootmarkeringen():
    woorden = bouw.vers_woorden({'text2026_html': 'God zei: <span class="god-speaks"><i>Er <sup data-note="1">1</sup>zij <b>licht</b>!</i></span> En het was licht.'})
    assert ' '.join(w['tekst'] for w in woorden) == 'God zei: Er zij licht! En het was licht.'
    assert [w['tekst'] for w in woorden if any(god for _, god in w['delen'])] == ['Er', 'zij', 'licht!']
    assert woorden[3]['voor'] == ['1']


def test_citaatgrens_binnen_woord_blijft_behouden():
    woorden = bouw.vers_woorden({'text2026_html': '<span class="god-speaks">Licht</span>! Gewoon.'})
    assert woorden[0]['delen'] == [('Licht', True), ('!', False)]
    assert woorden[1]['delen'] == [('Gewoon.', False)]


def test_pdf_wisselt_rood_en_zwart_en_gebruikt_cursief():
    fonts = bouw.lettertypes()
    st = bouw.stijlen(fonts)
    assert st['godscitaat'].letter is fonts['tekst_c']
    regel = bouw.Zetter().los([('Licht', st['godscitaat']), (' gewoon', st['tekst'])])
    uit = []
    bouw.teken_regel(regel, 50, 50, uit)
    assert '0.65 0.08 0.1 rg' in ''.join(uit)
    assert '0 0 0 rg' in ''.join(uit)
