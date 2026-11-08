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
        def heeft_illustraties(self,boek,hoofdstuk):
            return (boek,hoofdstuk) in mapping
        def plaats_illustraties(self,boek,hoofdstuk,naam):
            for werk in mapping[(boek,hoofdstuk)]:
                plaat = ROOT/werk['bestand']
                with Image.open(plaat) as im:w,h=im.size
                breedte=basis.ZETBREEDTE
                maxhoogte=basis.ZETHOOGTE-135
                factor=min(breedte/w,maxhoogte/h)
                bw,bh=w*factor,h*factor
                x=(basis.BREEDTE-bw)/2
                y=basis.ONDER+95+(maxhoogte-bh)/2
                content=[]
                self.koptekst(content,len(self.pdf.paginas)+1,f'{naam.upper()} {hoofdstuk}')
                def center(text,style,y):
                    r=self.zetter.los([(text,style)])
                    teken_regel(r,(basis.BREEDTE-r.breedte)/2,y,content)
                center(werk['titel'],self.st['boek_boven'],basis.HOOGTE-basis.BOVEN-30)
                center(werk['verwijzing'],self.st['fm_c'],basis.HOOGTE-basis.BOVEN-56)
                content.append(self.pdf.afbeelding(plaat,x,y,bw,bh))
                center('© Jan van ’t Hoff · Gospelimages',self.st['fm'],basis.ONDER+67)
                center('Naamsvermelding · Niet commercieel · Geen afgeleide werken',self.st['fm_klein'],basis.ONDER+49)
                center(werk['bron'],self.st['fm_klein'],basis.ONDER+31)
                self.pdf.bladwijzers.append((werk['titel']+' — '+werk['verwijzing'],len(self.pdf.paginas),1))
                self.pdf.pagina(''.join(content), [((basis.BINNEN, basis.ONDER+24, basis.BREEDTE-basis.BUITEN, basis.ONDER+44),werk['bron'])])
                geplaatst.append(werk['id'])
    geplaatst=[]
    basis.Boekbouwer=Geillustreerd
    afkortingen=basis.afkortingen
    def voorwerk(b):
        afkortingen(b)
        basis.alinea_bladzijden(b,['§§Over deze geïllustreerde uitgave',
          'Deze complete uitgave bevat de Bijbeltekst en herziene kanttekeningen in één band op A3 (297 × 420 mm). De Godsnaam wordt weergegeven als HEERE. De Bijbeltekst staat in twee kolommen en de kanttekeningen in drie kolommen onderaan dezelfde pagina.',
          f"Alle {len(manifest['afbeeldingen'])} werken uit de op 8 november 2026 vastgelegde openbare Gospelimages-catalogus van Jan van ’t Hoff zijn ongewijzigd opgenomen. De schilderijen en tekeningen volgen het hoofdstuk waarnaar de kunstenaar verwijst. Verschillende werken bij dezelfde Bijbelplaats zijn ieder afzonderlijk opgenomen.",
          'De tekst en herziene kanttekeningen zijn CC0 / publiek domein. Dit geldt niet voor de afbeeldingen. © Jan van ’t Hoff / Gospelimages. De afbeeldingen mogen uitsluitend worden gebruikt met naamsvermelding, niet commercieel en zonder afgeleide werken. Deze voorwaarden blijven gelden bij verspreiding van deze geïllustreerde PDF. De afzonderlijke bron staat onder ieder werk.',
          'Broncatalogus en gebruiksvoorwaarden: https://www.gospelimages.nl/schilderijen. Voor commercieel gebruik van de afbeeldingen is afzonderlijke toestemming van de rechthebbende nodig.'])
    basis.afkortingen=voorwerk
    vandaag=datetime.date.today()
    datum=f'{vandaag.day} november {vandaag.year}' if vandaag.month==11 else vandaag.isoformat()
    verslag=basis.bouw_deel(0,uit,datum,proef)
    verwacht=[w['id'] for k,werken in mapping.items() if not proef or (k[0]==proef[0] and k[1] in proef[1]) for w in werken]
    if sorted(geplaatst)!=sorted(verwacht):raise ValueError('Niet alle verwachte afbeeldingen opgenomen')
    verslag.update({'formaat':'A3','breedte_mm':297,'hoogte_mm':420,'afbeeldingen':len(geplaatst),'afbeelding_ids':geplaatst,
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
