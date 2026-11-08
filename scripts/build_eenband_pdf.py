#!/usr/bin/env python3
"""Eén complete A3-uitgave met kanttekeningen en alle vastgelegde Gospelimages-werken."""
import argparse
import datetime
import json
import re
import unicodedata
from pathlib import Path
from PIL import Image
import build_kanttekeningen_pdf as basis
from zetwerk import teken_regel

ROOT = Path(__file__).resolve().parents[1]
BESTAND = 'gods-woord-kanttekeningen-geillustreerd-a3.pdf'

def sleutel(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFD', s.lower()).encode('ascii','ignore').decode())

def catalogus():
    manifest = json.loads((ROOT/'data/gospelimages.json').read_text())
    namen = json.loads((ROOT/'data/books-index.json').read_text())['boeken']
    ids = {sleutel(b['naam']):b['id'] for b in namen}
    ids.update({'psalm':'psalmen','2timothieus':'2timotheus'})
    mapping = {}
    for werk in manifest['afbeeldingen']:
        match = re.match(r'^(.*?)\s+(\d+):',werk['verwijzing'])
        if not match or sleutel(match[1]) not in ids:
            raise ValueError(f"Onbekende Bijbelplaats: {werk['verwijzing']}")
        boek, hoofdstuk = ids[sleutel(match[1])], int(match[2])
        if not (ROOT/werk['bestand']).is_file():raise FileNotFoundError(werk['bestand'])
        mapping.setdefault((boek,hoofdstuk),[]).append(werk)
    return manifest,mapping

def configureer():
    basis.BREEDTE,basis.HOOGTE = 841.89,1190.55 # A3: één ISO-stap boven A4.
    basis.BINNEN,basis.BUITEN = 64.0,54.0
    basis.BOVEN,basis.ONDER = 64.0,46.0
    basis.ZETBREEDTE = basis.BREEDTE-basis.BINNEN-basis.BUITEN
    basis.ZETHOOGTE = basis.HOOGTE-basis.BOVEN-basis.ONDER
    basis.KOLOM2=(basis.ZETBREEDTE-basis.KOLOMWIT2)/2
    basis.KOLOM3=(basis.ZETBREEDTE-2*basis.KOLOMWIT3)/3
    basis.TEKST_KORPS,basis.TEKST_REGEL=11.5,14.2
    basis.NOOT_KORPS,basis.NOOT_REGEL=8.5,10.2
    basis.INTRO_KORPS,basis.INTRO_REGEL=10.5,13.0
    basis.DELEN[0]={'titel':'De gehele Bijbel met kanttekeningen en illustraties',
      'testament':'Het Oude en Nieuwe Testament, met de apocriefe boeken',
      'groepen':[('Het Oude Testament',[b for d in (1,2) for _,groep in basis.DELEN[d]['groepen'] for b in groep])]+basis.DELEN[3]['groepen']}
    basis.UITVOERNAAM=BESTAND

def bouw(uit, proef=None):
    manifest,mapping=catalogus()
    configureer()
    def eerste_vers(werk):
        return int(re.search(r':(\d+)',werk['verwijzing']).group(1))
    ankers={}
    for (boek,hoofdstuk),werken in mapping.items():
        data=json.loads((ROOT/f'data/{boek}/{hoofdstuk}.json').read_text())
        vrij={int(v['number']) for v in data['verses'] if str(v['number']).isdigit()}
        for werk in sorted(werken,key=eerste_vers):
            gewenst=eerste_vers(werk)
            # Verspreid werken bij hetzelfde vers over aangrenzende verzen, zodat
            # ieder beeld met tekst meegaat en er geen losse beeldpagina ontstaat.
            vers=min(vrij,key=lambda v:(abs(v-gewenst),v<gewenst))
            vrij.remove(vers)
            ankers[(boek,hoofdstuk,vers)]=werk
    oorspronkelijke_titelpagina = basis.titelpagina
    def titelpagina(b, deel):
        # Vergroot de hele zwarte boekband evenredig met het papierformaat.
        breedte, hoogte = basis.BREEDTE, basis.HOOGTE
        basis.BREEDTE, basis.HOOGTE = 595.28, 841.89
        try:
            oorspronkelijke_titelpagina(b, deel)
        finally:
            basis.BREEDTE, basis.HOOGTE = breedte, hoogte
        inhoud, links = b.pdf.paginas[-1]
        b.pdf.paginas[-1] = (f'q {breedte/595.28:.6f} 0 0 {hoogte/841.89:.6f} 0 0 cm\n' + inhoud + 'Q\n', links)
    basis.titelpagina = titelpagina
    origineel=basis.Boekbouwer
    class Geillustreerd(origineel):
        def voeg_illustraties(self,boek,hoofdstuk,vers,items):
            werk=ankers.get((boek,hoofdstuk,vers))
            if werk:
                with Image.open(ROOT/werk['bestand']) as im:w,h=im.size
                titel=self.zetter.zet([(werk['titel']+' · '+werk['verwijzing'],self.st['fm_c'])],basis.KOLOM2,uitvullen=False)
                kophoogte=len(titel)*13+10
                factor=min(basis.KOLOM2/w,(basis.ZETHOOGTE/2-kophoogte-12)/h)
                bw,bh=w*factor,h*factor
                items.append(basis.Item(kophoogte+bh+12,breek=False,hst=hoofdstuk,
                    extra=('beeld',werk,titel,bw,bh,kophoogte)))
        def teken_illustratie(self,it,x,y,uit,pagina):
            _,werk,titel,bw,bh,kophoogte=it.extra
            for nr,r in enumerate(titel):
                teken_regel(r,x+(basis.KOLOM2-r.breedte)/2,y-12-nr*13,uit)
            bx=x+(basis.KOLOM2-bw)/2
            by=y-kophoogte-bh
            uit.append(self.pdf.afbeelding(ROOT/werk['bestand'],bx,by,bw,bh))
            self.pagina_links.append(((bx,by,bx+bw,by+bh),werk['bron']))
            self.pdf.bladwijzers.append((werk['titel']+' — '+werk['verwijzing'],pagina-1,1))
            geplaatst.append(werk['id'])
    geplaatst=[]
    basis.Boekbouwer=Geillustreerd
    afkortingen=basis.afkortingen
    def voorwerk(b):
        afkortingen(b)
        basis.alinea_bladzijden(b,['§§Over deze geïllustreerde uitgave',
          'Deze complete uitgave bevat de Bijbeltekst en herziene kanttekeningen in één band op A3 (297 × 420 mm). De Godsnaam wordt weergegeven als HEERE. De Bijbeltekst staat in twee kolommen en de kanttekeningen in drie kolommen onderaan dezelfde pagina.',
          f"Alle {len(manifest['afbeeldingen'])} werken uit de op 8 november 2026 vastgelegde openbare Gospelimages-catalogus van Jan van ’t Hoff zijn ongewijzigd opgenomen. De schilderijen en tekeningen staan tussen de verzen in de doorlopende tekstkolommen, bij de Bijbelplaats waarnaar de kunstenaar verwijst. Ze beslaan maximaal een halve pagina. De kanttekeningen sluiten direct aan op de Bijbeltekst.",
          'De tekst en herziene kanttekeningen zijn CC0 / publiek domein. Dit geldt niet voor de afbeeldingen. © Jan van ’t Hoff / Gospelimages. De afbeeldingen mogen uitsluitend worden gebruikt met naamsvermelding, niet commercieel en zonder afgeleide werken. Deze voorwaarden blijven gelden bij verspreiding van deze geïllustreerde PDF. De naamsvermelding en gebruiksvoorwaarden staan hier centraal voor alle afbeeldingen. Iedere afbeelding bevat een klikbare verwijzing naar de afzonderlijke bron bij Gospelimages.',
          'Broncatalogus en gebruiksvoorwaarden: https://www.gospelimages.nl/schilderijen. Voor commercieel gebruik van de afbeeldingen is afzonderlijke toestemming van de rechthebbende nodig.'])
    basis.afkortingen=voorwerk
    vandaag=datetime.date.today()
    datum=f'{vandaag.day} november {vandaag.year}' if vandaag.month==11 else vandaag.isoformat()
    verslag=basis.bouw_deel(0,uit,datum,proef)
    verwacht=[w['id'] for k,werken in mapping.items() if not proef or (k[0]==proef[0] and k[1] in proef[1]) for w in werken]
    if sorted(geplaatst)!=sorted(verwacht):raise ValueError('Niet alle verwachte afbeeldingen opgenomen')
    verslag.update({'formaat':'A3','breedte_mm':297,'hoogte_mm':420,'afbeeldingen':len(geplaatst),'illustraties_in_tekst':True,'opmaak_versie':'inline-20261108','afbeelding_ids':geplaatst,
                    'afbeeldingen_licentie':'Naamsvermelding; niet commercieel; geen afgeleide werken',
                    'bron_afbeeldingen':'https://www.gospelimages.nl/schilderijen'})
    (uit/'eenband-uitgave.json').write_text(json.dumps(verslag,ensure_ascii=False,indent=2)+'\n')
    return verslag

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--uit',type=Path,default=ROOT/'downloads')
    p.add_argument('--proef',help='Bijvoorbeeld genesis:2-3')
    a=p.parse_args();proef=None
    if a.proef:
        boek,bereik=a.proef.split(':');delen=bereik.split('-');proef=(boek,set(range(int(delen[0]),int(delen[-1])+1)))
    print(json.dumps(bouw(a.uit,proef),ensure_ascii=False),flush=True)
