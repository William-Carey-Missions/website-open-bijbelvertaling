#!/usr/bin/env python3
"""Maakt de omslagen en het voorbeeld voor kanttekeningen.html (images/kanttekeningen/).

Eenmalig werk: de beelden veranderen niet met de tekst en staan daarom in git.
Vereist PyMuPDF en Pillow, die de uitrol niet nodig heeft.
Gebruik: python scripts/build_kanttekeningen_omslagen.py map-met-gebouwde-pdfs
"""
import io
import sys
from pathlib import Path

import fitz
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_kanttekeningen_pdf import DELEN, UITVOERNAAM, lettertypes, romeins
from zetwerk import Pdf, Stijl, Zetter, lijn, teken_regel

UIT = Path(__file__).resolve().parents[1] / 'images' / 'kanttekeningen'
BREEDTE, HOOGTE = 400.0, 600.0
NAVY = '0.078 0.18 0.259'
GOUD = '0.796 0.643 0.286'
WIT = '0.98 0.97 0.94'
OMSCHRIJVING = {1: ['Genesis', 'tot en met', 'Esther'], 2: ['Job', 'tot en met', 'Maleachi'],
                3: ['Mattheüs', 'tot en met', 'Openbaring', 'met de apocriefe boeken']}


def omslag(deel, fonts, pad):
    zetter = Zetter(terugval=(fonts['hebr'], fonts['grieks']))
    groot = Stijl(fonts['kop'], 62, spatie=0.2, afbreken=False)
    klein = Stijl(fonts['kop'], 13, spatie=1.6, afbreken=False)
    deelkop = Stijl(fonts['kop'], 20, spatie=1.5, afbreken=False)
    tekst = Stijl(fonts['tekst'], 15, kenmerken=(('onum', True),), afbreken=False)
    cursief = Stijl(fonts['tekst_c'], 15, kenmerken=(('onum', True),), afbreken=False)
    uit = [f'{NAVY} rg 0 0 {BREEDTE} {HOOGTE} re f\n', f'{GOUD} RG\n']
    for inzet, dikte in ((18, 1.2), (23, 0.4)):
        uit.append(f'{dikte} w {inzet} {inzet} {BREEDTE - 2 * inzet} {HOOGTE - 2 * inzet} re S\n')

    def regel(t, stijl, y, kleur=WIT):
        r = zetter.los([(t, stijl)])
        uit.append(f'{kleur} rg\n')
        teken_regel(r, (BREEDTE - r.breedte) / 2, y, uit)

    regel('DE BIJBEL', klein, 505, GOUD)
    regel('Open', groot, 438)
    regel('Vertaling', groot, 376)
    lijn(BREEDTE / 2 - 34, 344, BREEDTE / 2 + 34, 344, 0.8, uit)
    regel('met kanttekeningen', cursief, 316)
    regel(f'DEEL {romeins(deel)}', deelkop, 220, GOUD)
    y = 188
    for t in OMSCHRIJVING[deel]:
        regel(t, cursief if t.startswith(('tot', 'met')) else tekst, y)
        y -= 21
    pdf = Pdf(BREEDTE, HOOGTE, 'Omslag')
    pdf.pagina(''.join(uit))
    tijdelijk = pad.with_suffix('.pdf')
    pdf.schrijf(tijdelijk, list(fonts.values()))
    with fitz.open(tijdelijk) as doc:
        png = doc[0].get_pixmap(dpi=108).tobytes('png')
    tijdelijk.unlink()
    Image.open(io.BytesIO(png)).convert('RGB').save(pad, 'WEBP', quality=88, method=6)


def voorbeeld(map_pdf, pad):
    """De opening van Genesis 1, zodat een bezoeker de zetting ziet voordat hij downloadt."""
    with fitz.open(map_pdf / UITVOERNAAM.format(1)) as d:
        w, h = d[0].rect.width, d[0].rect.height
        doel = fitz.open()
        blad = doel.new_page(width=w * 2 + 8, height=h)
        blad.draw_rect(blad.rect, fill=(0.86, 0.85, 0.81), color=None)
        blad.show_pdf_page(fitz.Rect(0, 0, w, h), d, 9)
        blad.show_pdf_page(fitz.Rect(w + 8, 0, 2 * w + 8, h), d, 10)
        png = blad.get_pixmap(dpi=100).tobytes('png')
    Image.open(io.BytesIO(png)).convert('RGB').save(pad, 'WEBP', quality=78, method=6)


def main():
    UIT.mkdir(parents=True, exist_ok=True)
    fonts = lettertypes()
    for deel in DELEN:
        omslag(deel, fonts, UIT / f'deel-{deel}.webp')
    voorbeeld(Path(sys.argv[1]), UIT / 'voorbeeld-genesis-1.webp')


if __name__ == '__main__':
    main()
