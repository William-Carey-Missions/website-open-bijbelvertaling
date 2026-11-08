"""Controleer de complete geïllustreerde uitgave op brondekking en proefbouw."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
pytest.importorskip('uharfbuzz')
import build_kanttekeningen_pdf as basis
import build_eenband_pdf as eenband

def test_alle_gecatalogiseerde_werken_zijn_gemapt_en_ongewijzigd():
    manifest,mapping=eenband.catalogus()
    werken=manifest['afbeeldingen']
    assert len(werken)==126
    assert sorted(w['id'] for groep in mapping.values() for w in groep)==sorted(w['id'] for w in werken)
    for w in werken:
        assert hashlib.sha256((ROOT/w['bestand']).read_bytes()).hexdigest()==w['sha256']
        assert w['voorwaarden']==['Naamsvermelding','Niet commercieel','Geen afgeleide werken']

def test_alineas_behouden_alle_woorden():
    tekst=('Dit is de eerste volledige zin. Dit is een tweede volledige zin. '*18).strip()
    alineas=basis.inleiding_alineas(tekst)
    assert len(alineas)>1
    assert ' '.join(alineas)==tekst
    assert basis.inleiding_alineas('Eerste alinea.\n\nTweede alinea.')==['Eerste alinea.','Tweede alinea.']

def test_perikoop_heeft_een_volledige_witregel():
    fonts=basis.lettertypes();st=basis.stijlen(fonts)
    items=[]
    basis.zet_hoofdstuk(basis.Zetter(terugval=(fonts['hebr'],fonts['grieks'])),st,'genesis',
        {'number':1,'verses':[{'number':1,'text2026':'In het begin.'}]},{(1,1):'De schepping'},items,[],{'verzen':0,'noten':0})
    assert any(it.gat and not it.breek and it.h==basis.TEKST_REGEL for it in items)

def test_a3_proef_heeft_de_juiste_platen_en_geen_verlies(tmp_path):
    subprocess.run([sys.executable,str(ROOT/'scripts/build_eenband_pdf.py'),'--proef','genesis:2-3','--uit',str(tmp_path)],check=True,capture_output=True)
    info=json.loads((tmp_path/'eenband-uitgave.json').read_text())
    assert info['formaat']=='A3' and info['afbeelding_ids']==[7,8,9]
    assert info['verzen']==49 and info['afbeeldingen']==3
    assert info['controle']['noot_te_laat']==0
    assert not info['afwijkingen'] and not info['onbekende_tekens']
    content=(tmp_path/info['bestand']).read_bytes()
    assert b'/MediaBox[0 0 841.89 1190.55]' in content
    assert content.count(b'/Subtype/Image')==3
    assert content.count(b'/S/URI')==3

    # Iedere plaat deelt de pagina met echte hoofdstuktekst en kanttekeningen.
    assert info['illustraties_in_tekst'] is True
    pdf=tmp_path/info['bestand']
    lijst=subprocess.check_output(['pdfimages','-list',str(pdf)],text=True)
    beeldpaginas={int(regel.split()[0]) for regel in lijst.splitlines()[2:] if regel.strip()}
    assert len(beeldpaginas)==3  # Ook elk werk bij Genesis 3 krijgt een halve pagina.
    for pagina in beeldpaginas:
        tekst=subprocess.check_output(['pdftotext','-f',str(pagina),'-l',str(pagina),str(pdf),'-'],text=True)
        assert 'GENESIS' in tekst
        assert 'HEERE' in tekst
        assert 'Gospelimages' in tekst
        assert len(tekst)>2000
