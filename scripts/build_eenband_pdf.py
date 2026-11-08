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
    groepen={}
    for plaats,werken in mapping.items():
        werken=sorted(werken,key=eerste_vers)
        stap=2 if len(werken)>2 else 1
        groepen[plaats]=[werken[i:i+stap] for i in range(0,len(werken),stap)]
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
        def __init__(self,*args):
            super().__init__(*args)
            self.werken=[]
        def markeer_illustraties(self,boek,hoofdstuk,naam,vers,positie):
            self.werken.extend((positie,g,naam,hoofdstuk) for g in groepen.get((boek,hoofdstuk),[]) if eerste_vers(g[0])==vers)
        def vul(self,items,noten,kopfunctie,*args,**kwargs):
            self.gewichten=[0.0]
            for it in items:
                self.gewichten.append(self.gewichten[-1]+it.h/2+sum(len(noten[n]) for n in it.noten)*basis.NOOT_REGEL/3)
            self.grenzen=[i+1 for i,it in enumerate(items) if it.breek]
            result=super().vul(items,noten,lambda h,v:kopfunctie(h,v and not self.beeld_op_pagina),*args,**kwargs)
            if self.werken:
                raise ValueError('Afbeeldingen over na het zetten van het boek')
            return result
        def bereid_pagina(self,items,noten,i,boven,voorop):
            self.beeld_op_pagina=False
            if not self.werken:
                return boven,voorop,len(items),[]
            positie,werken,naam,hoofdstuk=self.werken[0]
            afstand=self.gewichten[positie]-self.gewichten[i]
            resterend=self.gewichten[-1]-self.gewichten[i]
            toon=not voorop and i<len(items) and (afstand<=basis.ZETHOOGTE/2 or resterend<=basis.ZETHOOGTE/2*(len(self.werken)+0.5))
            if toon:
                self.werken.pop(0)
                self.beeld_op_pagina=True
                pagina=len(self.pdf.paginas)
                x0=self.linkerrand(pagina+1)
                hoogte=basis.ZETHOOGTE/2
                top=basis.HOOGTE-basis.BOVEN
                content,links=[],[]
                tussen=18.0
                vakbreedte=(basis.ZETBREEDTE-tussen*(len(werken)-1))/len(werken)
                kopruimte=54 if len(werken)>1 else 28
                maten=[]
                for werk in werken:
                    with Image.open(ROOT/werk['bestand']) as im:w,h=im.size
                    factor=min(vakbreedte/w,(hoogte-kopruimte-18)/h)
                    maten.append((w*factor,h*factor))
                # Reserveer alleen de echte beeldhoogte, maximaal een halve pagina.
                hoogte=kopruimte+max(bh for _,bh in maten)+18
                for nr,werk in enumerate(werken):
                    plaat=ROOT/werk['bestand']
                    bw,bh=maten[nr]
                    vx=x0+nr*(vakbreedte+tussen)
                    x=vx+(vakbreedte-bw)/2
                    y=top-kopruimte-bh
                    content.append(self.pdf.afbeelding(plaat,x,y,bw,bh))
                    titel=self.zetter.zet([(werk['titel']+' · '+werk['verwijzing'],self.st['fm_c'])],vakbreedte,uitvullen=False)
                    for regel,r in enumerate(titel):
                        teken_regel(r,vx+(vakbreedte-r.breedte)/2,top-15-regel*13,content)
                    self.pdf.bladwijzers.append((werk['titel']+' — '+werk['verwijzing'],pagina,1))
                    geplaatst.append(werk['id'])
                    links.append(((x,y,x+bw,y+bh),werk['bron']))
                boven,voorop=hoogte,content
            else:
                links=[]
            # Bewaar voldoende tekst voor komende beelden, ook aan het boekeinde.
            grens=len(items)
            if self.werken:
                reserve=min(resterend/(len(self.werken)+1),basis.ZETHOOGTE*0.375)*len(self.werken)
                kandidaten=[g for g in self.grenzen if g>i and self.gewichten[g]<=self.gewichten[-1]-reserve]
                grens=kandidaten[-1] if kandidaten else next(g for g in self.grenzen if g>i)
            return boven,voorop,grens,links
    geplaatst=[]
    basis.Boekbouwer=Geillustreerd
    afkortingen=basis.afkortingen
    def voorwerk(b):
        afkortingen(b)
        basis.alinea_bladzijden(b,['§§Over deze geïllustreerde uitgave',
          'Deze complete uitgave bevat de Bijbeltekst en herziene kanttekeningen in één band op A3 (297 × 420 mm). De Godsnaam wordt weergegeven als HEERE. De Bijbeltekst staat in twee kolommen en de kanttekeningen in drie kolommen onderaan dezelfde pagina.',
          f"Alle {len(manifest['afbeeldingen'])} werken uit de op 8 november 2026 vastgelegde openbare Gospelimages-catalogus van Jan van ’t Hoff zijn ongewijzigd opgenomen. De schilderijen en tekeningen staan bij het bijbehorende hoofdstuk, in de bovenste helft van dezelfde pagina als de Bijbeltekst en kanttekeningen. Afbeeldingen staan tussen de doorlopende Bijbeltekst en beslaan maximaal een halve pagina. Bij hoofdstukken met veel werken kunnen twee afbeeldingen naast elkaar staan. De kanttekeningen sluiten direct aan op de Bijbeltekst.",
          'De tekst en herziene kanttekeningen zijn CC0 / publiek domein. Dit geldt niet voor de afbeeldingen. © Jan van ’t Hoff / Gospelimages. De afbeeldingen mogen uitsluitend worden gebruikt met naamsvermelding, niet commercieel en zonder afgeleide werken. Deze voorwaarden blijven gelden bij verspreiding van deze geïllustreerde PDF. De naamsvermelding en gebruiksvoorwaarden staan hier centraal voor alle afbeeldingen. Iedere afbeelding bevat een klikbare verwijzing naar de afzonderlijke bron bij Gospelimages.',
          'Broncatalogus en gebruiksvoorwaarden: https://www.gospelimages.nl/schilderijen. Voor commercieel gebruik van de afbeeldingen is afzonderlijke toestemming van de rechthebbende nodig.'])
    basis.afkortingen=voorwerk
    vandaag=datetime.date.today()
    datum=f'{vandaag.day} november {vandaag.year}' if vandaag.month==11 else vandaag.isoformat()
    verslag=basis.bouw_deel(0,uit,datum,proef)
    verwacht=[w['id'] for k,werken in mapping.items() if not proef or (k[0]==proef[0] and k[1] in proef[1]) for w in werken]
    if sorted(geplaatst)!=sorted(verwacht):raise ValueError('Niet alle verwachte afbeeldingen opgenomen')
    verslag.update({'formaat':'A3','breedte_mm':297,'hoogte_mm':420,'afbeeldingen':len(geplaatst),'illustraties_in_tekst':True,'opmaak_versie':'doorlopend-20261108','afbeelding_ids':geplaatst,
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
