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

def test_perikoop_heeft_witregel_erboven_en_geen_witregel_eronder():
    fonts=basis.lettertypes();st=basis.stijlen(fonts)
    items=[]
    basis.zet_hoofdstuk(basis.Zetter(terugval=(fonts['hebr'],fonts['grieks'])),st,'genesis',
        {'number':1,'verses':[{'number':1,'text2026':'In het begin.'}]},{(1,1):'De schepping'},items,[],{'verzen':0,'noten':0})
    wit=[i for i,it in enumerate(items) if it.gat and not it.breek and it.h==basis.TEKST_REGEL]
    assert len(wit)==1
    kop=wit[0]+1
    assert items[kop].regel is not None and not items[kop].breek
    assert items[kop+1].regel is not None and not items[kop+1].gat

def test_a3_proef_heeft_de_juiste_platen_en_geen_verlies(tmp_path):
    subprocess.run([sys.executable,str(ROOT/'scripts/build_eenband_pdf.py'),'--proef','genesis:2-3','--uit',str(tmp_path)],check=True,capture_output=True)
    info=json.loads((tmp_path/'eenband-uitgave.json').read_text())
    assert info['formaat']=='A3' and info['afbeelding_ids']==[7,8,9]
    assert info['godsnaam']=='HEERE'
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
    assert 1<=len(beeldpaginas)<=3  # Beelden maken deel uit van de doorlopende tekstkolommen.
    for pagina in beeldpaginas:
        tekst=subprocess.check_output(['pdftotext','-f',str(pagina),'-l',str(pagina),str(pdf),'-'],text=True)
        assert 'GENESIS' in tekst
        assert 'HEERE' in tekst
        assert 'Gospelimages' not in tekst
        assert 'Niet commercieel' not in tekst
        assert len(tekst)>2000


def test_meerdere_werken_bij_hetzelfde_vers_blijven_in_de_tekst(tmp_path):
    subprocess.run([sys.executable,str(ROOT/'scripts/build_eenband_pdf.py'),'--proef','lukas:15','--uit',str(tmp_path)],check=True,capture_output=True)
    info=json.loads((tmp_path/'eenband-uitgave.json').read_text())
    assert info['verzen']==32 and info['afbeeldingen']==6
    assert info['controle']['noot_te_laat']==0 and not info['afwijkingen']
    pdf=tmp_path/info['bestand']
    lijst=subprocess.check_output(['pdfimages','-list',str(pdf)],text=True)
    for regel in lijst.splitlines()[2:]:
        if not regel.strip():continue
        velden=regel.split()
        assert int(velden[4])/float(velden[13])*72<543  # maximaal halve A3-zetspiegel
    tekst=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True)
    assert 'LUKAS XV' in tekst


def test_yhwh_behoudt_html_en_zet_klassieke_naamvormen_om():
    from godsnaam import yhwh, heere
    assert yhwh('JAHWEH sprak. De HEERE zei: het woord des HEEREN.')=='YHWH sprak. YHWH zei: het woord van YHWH.'
    assert yhwh('De JAHWEH sprak.')=='YHWH sprak.'
    assert yhwh('<span title="HEERE">JAHWEH</span>')=='<span title="HEERE">YHWH</span>'
    assert heere('JAHWEH sprak.')=='De HEERE sprak.'


def test_didache_pdf_heeft_yhwh_en_eigen_bestanden(tmp_path):
    subprocess.run([sys.executable,str(ROOT/'scripts/build_eenband_pdf.py'),'--godsnaam','YHWH','--proef','genesis:2-3','--uit',str(tmp_path)],check=True,capture_output=True)
    info=json.loads((tmp_path/'eenband-uitgave-yhwh.json').read_text())
    assert info['godsnaam']=='YHWH' and info['bestand'].endswith('-yhwh.pdf')
    assert info['verzen']==49 and info['afbeeldingen']==3
    assert info['controle']['noot_te_laat']==0 and not info['afwijkingen']
    assert not (tmp_path/'eenband-uitgave.json').exists()
    tekst=subprocess.check_output(['pdftotext',str(tmp_path/info['bestand']),'-'],text=True)
    assert 'YHWH' in tekst
    assert not re.search(r'\b(?:HEERE|HEEREN|JAHWEH)\b',tekst)
    assert not re.search(r'\b[Dd]e YHWH\b',tekst)
