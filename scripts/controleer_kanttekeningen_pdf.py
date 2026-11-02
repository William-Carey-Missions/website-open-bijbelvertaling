#!/usr/bin/env python3
"""Controleert de gebouwde PDF's met kanttekeningen op bladzijdeniveau.

Leest de PDF terug zoals een lezer hem ziet en controleert:
  - elk merkteken in de tekst heeft zijn kanttekening op dezelfde bladzijde;
  - niets valt buiten de bladspiegel en tekst en noten overlappen niet;
  - alle lettertypes zijn ingesloten;
  - de inhoudsopgave wijst naar de bladzijde waar het boek begint;
  - elk vers staat er, in de juiste volgorde;
  - het aantal verzen en kanttekeningen klopt met data/.

Vereist PyMuPDF (alleen voor deze controle): python -m pip install pymupdf
Gebruik: python scripts/controleer_kanttekeningen_pdf.py [map-met-pdfs]
"""
import json
import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_kanttekeningen_pdf import (BREEDTE, BUITEN, DATA, DELEN, HOOGTE, NOOT_KORPS, ONDER, TEKST_KORPS,
                                      TITELS, UITVOER, UITVOERNAAM, godsnaam)

MERK_KORPS = 5.7


def spans(pagina):
    for blok in pagina.get_text('dict')['blocks']:
        for regel in blok.get('lines', []):
            yield regel, regel['spans']


def verwacht(deel):
    verzen = noten = 0
    for _, boeken in DELEN[deel]['groepen']:
        for boek in boeken:
            for p in (DATA / boek).glob('*.json'):
                if not p.stem.isdigit():
                    continue
                with open(p, encoding='utf-8') as fh:
                    for v in json.load(fh)['verses']:
                        verzen += 1
                        noten += sum(1 for n in v.get('marginNotes') or [] if n.get('text2026') and n.get('marker'))
    return verzen, noten


def kaal(tekst):
    return re.sub(r'[^0-9a-zà-ÿ]', '', tekst.lower())


def controleer_volgorde(doc, deel, fouten):
    """Elk vers staat in de PDF, woord voor woord en in de juiste volgorde."""
    tekst = kaal(''.join(s['text'] for pagina in doc for _, stukken in spans(pagina) for s in stukken
                         if round(s['size'], 1) == round(TEKST_KORPS, 1)))
    pos = 0
    for _, boeken in DELEN[deel]['groepen']:
        for boek in boeken:
            nummers = sorted(int(p.stem) for p in (DATA / boek).glob('*.json') if p.stem.isdigit())
            for n in nummers:
                with open(DATA / boek / f'{n}.json', encoding='utf-8') as fh:
                    verzen = json.load(fh)['verses']
                for v in verzen[1:]:  # vers 1 begint met een grote beginletter in een eigen corps
                    bron = kaal(godsnaam(v.get('text2026') or ''))
                    gevonden = tekst.find(bron, pos)
                    if gevonden < 0:
                        fouten.append(f'{boek} {n}:{v["number"]} niet gevonden of buiten volgorde')
                        continue
                    pos = gevonden + len(bron)


def controleer_inhoud(doc, verslag, fouten):
    """De inhoudsopgave wijst naar de bladzijde waar de titel van het boek staat."""
    for boek, regel in zip((b for _, g in DELEN[verslag['deel']]['groepen'] for b in g), verslag['boeken']):
        groot = TITELS[boek][2].upper()
        if groot not in doc[regel['pagina'] - 1].get_text():
            fouten.append(f'inhoud: {regel["naam"]} staat niet op bladzijde {regel["pagina"]}')


def controleer_pagina(pagina, nummer, fouten):
    merken_tekst, noot_start, y_tekst, y_noot = [], [], 0.0, HOOGTE
    for regel, stukken in spans(pagina):
        x0, y0, x1, y1 = regel['bbox']
        if not stukken or not any(s['text'].strip() for s in stukken):
            continue
        if x0 < BUITEN - 1.5 or x1 > BREEDTE - BUITEN + 1.5 or y1 > HOOGTE - ONDER + 4:
            fouten.append(f'blz. {nummer}: regel buiten de bladspiegel: {stukken[0]["text"][:40]!r}')
        for s in stukken:
            korps = round(s['size'], 1)
            if korps == MERK_KORPS:
                merken_tekst.extend(m for m in re.split(r'[\s ]+', s['text'].strip()) if m)
                y_tekst = max(y_tekst, regel['bbox'][3])
            elif korps == round(TEKST_KORPS, 1):
                y_tekst = max(y_tekst, regel['bbox'][3])
            elif korps == round(NOOT_KORPS, 1):
                y_noot = min(y_noot, regel['bbox'][1])
        # Het begin van een noot: nummer of "– letter" aan het begin van een ingesprongen regel.
        eerste = stukken[0]
        if round(eerste['size'], 1) == round(NOOT_KORPS, 1):
            tekst = ''.join(s['text'] for s in stukken)
            m = re.match(r'^(?:– )?([^\s]+)\s', tekst)
            if m:
                noot_start.append(m.group(1))
    if y_noot < HOOGTE and y_tekst > y_noot + 1.5:
        fouten.append(f'blz. {nummer}: tekst en noten overlappen ({y_tekst:.1f} > {y_noot:.1f})')
    op_blad = set(noot_start)
    zonder = [m for m in merken_tekst if m not in op_blad]
    return merken_tekst, zonder


def controleer_pdf(pad, deel, verslag):
    fouten, zonder_noot, merken = [], [], 0
    with fitz.open(pad) as doc:
        for i, pagina in enumerate(doc):
            for f in pagina.get_fonts(full=False):
                if f[1] not in ('ttf', 'cff', 'otf') or '+' not in f[3]:
                    fouten.append(f'blz. {i + 1}: lettertype niet ingesloten: {f[3]}')
            m, zonder = controleer_pagina(pagina, i + 1, fouten)
            merken += len(m)
            zonder_noot += [(i + 1, x) for x in zonder]
        controleer_volgorde(doc, deel, fouten)
        controleer_inhoud(doc, verslag, fouten)
        toc = doc.get_toc()
        for niveau, titel, blad in toc:
            if niveau == 1 and blad > 8 and titel[0:1].isalpha():
                if not doc[blad - 1].get_text().strip():
                    fouten.append(f'bladwijzer {titel}: lege bladzijde {blad}')
        paginas = len(doc)
    return {'pagina': paginas, 'merken': merken, 'zonder_noot': zonder_noot, 'fouten': fouten}


def main():
    map_ = Path(sys.argv[1]) if len(sys.argv) > 1 else UITVOER
    verslag = json.loads((map_ / 'kanttekeningen-uitgave.json').read_text(encoding='utf-8'))
    code = 0
    for v in verslag['delen']:
        deel = v['deel']
        uitslag = controleer_pdf(map_ / UITVOERNAAM.format(deel), deel, v)
        verzen, noten = verwacht(deel)
        print(f'deel {deel}: {uitslag["pagina"]} blz., {v["bytes"] / 1048576:.1f} MB, '
              f'{v["verzen"]}/{verzen} verzen, {v["noten"]}/{noten} kanttekeningen, {uitslag["merken"]} merktekens, '
              f'noot-te-laat {v["controle"]["noot_te_laat"]}, gesplitst {v["controle"]["noot_gesplitst"]}, '
              f'zonder noot op blad {len(uitslag["zonder_noot"])}, afwijkingen {len(v["afwijkingen"])}, '
              f'te brede alinea\'s {v["te_brede_alineas"]}, fouten {len(uitslag["fouten"])}')
        for f in uitslag['fouten'][:15]:
            print('  ', f)
        print('   zonder noot:', uitslag['zonder_noot'][:15])
        if uitslag['fouten'] or uitslag['zonder_noot'] or v['verzen'] != verzen or v['noten'] != noten:
            code = 1
    return code


if __name__ == '__main__':
    sys.exit(main())
