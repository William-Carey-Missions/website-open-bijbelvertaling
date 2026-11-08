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
        def vul_geillustreerd(self,boek,hoofdstuk,naam,items,noten,kopregel,voorop):
            # Boekinleiding apart; daarna beeld en hoofdstuktekst op dezelfde pagina.
            if voorop:
                content=['0 0 0 RG 0 0 0 rg\n']
                self.koptekst(content,len(self.pdf.paginas)+1,'')
                content.extend(voorop)
                self.pdf.pagina(''.join(content))
            werken=mapping[(boek,hoofdstuk)]
            # Verdeel de tekst op geldige regelovergangen: elk werk krijgt een eigen
            # halve pagina met tekst en noten, ook bij hoofdstukken met meerdere werken.
            grenzen=[i+1 for i,it in enumerate(items) if it.breek]
            som=[0.0]
            for it in items:
                som.append(som[-1]+it.h/2+sum(len(noten[n]) for n in it.noten)*basis.NOOT_REGEL/3)
            begin=0
            for nr,werk in enumerate(werken):
                resterend=len(werken)-nr
                if resterend==1:
                    einde=len(items)
                else:
                    kandidaten=[g for g in grenzen if g>begin and len([b for b in grenzen if b>g])>=resterend-1]
                    doel=som[begin]+(som[-1]-som[begin])/resterend
                    einde=min(kandidaten,key=lambda g:abs(som[g]-doel))
                pagina=len(self.pdf.paginas)
                x0=self.linkerrand(pagina+1)
                hoogte=basis.ZETHOOGTE/2
                top=basis.HOOGTE-basis.BOVEN
                plaat=ROOT/werk['bestand']
                with Image.open(plaat) as im:w,h=im.size
                factor=min(basis.ZETBREEDTE/w,(hoogte-105)/h)
                bw,bh=w*factor,h*factor
                x=x0+(basis.ZETBREEDTE-bw)/2
                y=top-34-(hoogte-105)+(hoogte-105-bh)/2
                content=[self.pdf.afbeelding(plaat,x,y,bw,bh)]
                def center(text,style,y):
                    r=self.zetter.los([(text,style)])
                    teken_regel(r,x0+(basis.ZETBREEDTE-r.breedte)/2,y,content)
                center(werk['titel']+' · '+werk['verwijzing'],self.st['fm_c'],top-15)
                center('© Jan van ’t Hoff · Gospelimages',self.st['fm_klein'],top-hoogte+57)
                center('Naamsvermelding · Niet commercieel · Geen afgeleide werken',self.st['fm_klein'],top-hoogte+43)
                center(werk['bron'],self.st['fm_klein'],top-hoogte+29)
                self.pdf.bladwijzers.append((werk['titel']+' — '+werk['verwijzing'],pagina,1))
                self.vul(items[begin:einde],noten,lambda h, _: kopregel(h,False),hoogte,content)
                inhoud,links=self.pdf.paginas[pagina]
                self.pdf.paginas[pagina]=(inhoud,links+[((x0,top-hoogte+15,x0+basis.ZETBREEDTE,top-hoogte+38),werk['bron'])])
                geplaatst.append(werk['id'])
                begin=einde
    geplaatst=[]
    basis.Boekbouwer=Geillustreerd
    afkortingen=basis.afkortingen
    def voorwerk(b):
        afkortingen(b)
        basis.alinea_bladzijden(b,['§§Over deze geïllustreerde uitgave',
          'Deze complete uitgave bevat de Bijbeltekst en herziene kanttekeningen in één band op A3 (297 × 420 mm). De Godsnaam wordt weergegeven als HEERE. De Bijbeltekst staat in twee kolommen en de kanttekeningen in drie kolommen onderaan dezelfde pagina.',
          f"Alle {len(manifest['afbeeldingen'])} werken uit de op 8 november 2026 vastgelegde openbare Gospelimages-catalogus van Jan van ’t Hoff zijn ongewijzigd opgenomen. De schilderijen en tekeningen staan bij het bijbehorende hoofdstuk, in de bovenste helft van dezelfde pagina als de Bijbeltekst en kanttekeningen. Elk werk krijgt een halve pagina beeld met daaronder een gedeelte van de hoofdstuktekst en de bijbehorende kanttekeningen.",
          'De tekst en herziene kanttekeningen zijn CC0 / publiek domein. Dit geldt niet voor de afbeeldingen. © Jan van ’t Hoff / Gospelimages. De afbeeldingen mogen uitsluitend worden gebruikt met naamsvermelding, niet commercieel en zonder afgeleide werken. Deze voorwaarden blijven gelden bij verspreiding van deze geïllustreerde PDF. De afzonderlijke bron staat onder ieder werk.',
          'Broncatalogus en gebruiksvoorwaarden: https://www.gospelimages.nl/schilderijen. Voor commercieel gebruik van de afbeeldingen is afzonderlijke toestemming van de rechthebbende nodig.'])
    basis.afkortingen=voorwerk
    vandaag=datetime.date.today()
    datum=f'{vandaag.day} november {vandaag.year}' if vandaag.month==11 else vandaag.isoformat()
    verslag=basis.bouw_deel(0,uit,datum,proef)
    verwacht=[w['id'] for k,werken in mapping.items() if not proef or (k[0]==proef[0] and k[1] in proef[1]) for w in werken]
    if sorted(geplaatst)!=sorted(verwacht):raise ValueError('Niet alle verwachte afbeeldingen opgenomen')
    verslag.update({'formaat':'A3','breedte_mm':297,'hoogte_mm':420,'afbeeldingen':len(geplaatst),'illustraties_in_tekst':True,'afbeelding_ids':geplaatst,
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
