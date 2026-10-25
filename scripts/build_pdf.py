#!/usr/bin/env python3
"""Bouw de volledige OV-leesuitgave als PDF, zonder kanttekeningen.

Installatie: python -m pip install -r requirements-pdf.txt
Uitvoer is afgeleid van data/ en wordt bij iedere publicatie opnieuw gebouwd.
"""
import argparse
import datetime
import html
import io
import json
import re
from pathlib import Path

from fontTools.ttLib import TTFont as SourceFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from build_downloads import gepubliceerde_hoofdstukken, verstekst, atomic_output
from build_leespaginas import GROEPEN

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'downloads/open-vertaling-volledig.pdf'


def fonts():
    """Gebruik dezelfde vrij beschikbare letter als de website, ingebed in de PDF."""
    glyphs = None
    for name, filename in [('OV', 'eb-garamond-400.woff2'), ('OVBold', 'eb-garamond-600.woff2'), ('Hebrew', 'noto-serif-hebrew.woff2')]:
        source = SourceFont(ROOT / 'fonts' / filename)
        glyphs = set(source.getBestCmap()) if glyphs is None else glyphs | set(source.getBestCmap())
        source.flavor = None
        buffer = io.BytesIO()
        source.save(buffer)
        buffer.seek(0)
        pdfmetrics.registerFont(TTFont(name, buffer))
    pdfmetrics.registerFontFamily('OV', normal='OV', bold='OVBold')
    return glyphs


class Heading(Paragraph):
    def __init__(self, text, style, key, level):
        super().__init__(html.escape(text), style)
        self.key, self.level, self.title = key, level, text

    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, self.level, False)
        self.canv.current_heading = self.title
        super().draw()


def build(output=OUTPUT):
    glyphs = fonts()
    books = json.loads((ROOT / 'data/books.json').read_text(encoding='utf-8'))['books']
    order = {bid: i for i, bid in enumerate(' '.join(ids for _, ids in GROEPEN).split())}
    books.sort(key=lambda book: order.get(book['id'], len(order)))
    stats = json.loads((ROOT / 'data/stats.json').read_text(encoding='utf-8'))
    selected = []
    counts = dict(boeken=0, hoofdstukken=0, verzen=0)
    missing = set()
    for book in books:
        chapters = []
        numbers = gepubliceerde_hoofdstukken(book)
        if not book.get('ethiopic') and book.get('testament') != 'ET':
            expected = sorted(book.get('chaptersIncluded') or range(1, book.get('totalChapters', 0) + 1))
            if numbers != expected:
                raise ValueError(f"Ontbrekende hoofdstukken in {book['id']}")
        for nr in numbers:
            source = json.loads((ROOT / 'data' / book['id'] / f'{nr}.json').read_text(encoding='utf-8'))
            verses = [(v['number'], html.unescape(verstekst(v))) for v in source['verses']]
            if not verses or any(not text for _, text in verses):
                raise ValueError(f"Leeg vers in {book['id']} {nr}")
            for _, text in verses:
                missing.update(ord(c) for c in text if not c.isspace() and ord(c) not in glyphs)
            chapters.append((nr, verses))
            counts['verzen'] += len(verses)
        if chapters:
            selected.append((book, chapters))
            counts['hoofdstukken'] += len(chapters)
    counts['boeken'] = len(selected)
    if missing:
        raise ValueError('Ontbrekende lettertekens: ' + ', '.join(f'U+{n:04X}' for n in sorted(missing)))
    if counts['boeken'] != 82:
        raise ValueError(f"Verwacht 82 openbare boeken, gevonden {counts['boeken']}")

    ink = colors.HexColor('#143247')
    body = ParagraphStyle('body', fontName='OV', fontSize=11, leading=14.5, spaceAfter=3)
    title = ParagraphStyle('title', parent=body, fontName='OVBold', fontSize=34, leading=39, textColor=ink, spaceAfter=20)
    bookstyle = ParagraphStyle('book', parent=body, fontName='OVBold', fontSize=26, leading=32, textColor=ink, spaceAfter=24, keepWithNext=True)
    chapterstyle = ParagraphStyle('chapter', parent=body, fontName='OVBold', fontSize=16, leading=22, spaceBefore=14, spaceAfter=8, keepWithNext=True)
    small = ParagraphStyle('small', parent=body, fontSize=10, leading=14, spaceAfter=10)
    contents = ParagraphStyle('contents', parent=small, spaceAfter=2, leading=14)
    date = datetime.date.today().isoformat()
    version = str(stats.get('version', ''))
    story = [Spacer(1, 70), Paragraph('Open Vertaling', title), Paragraph('Volledige leesuitgave', bookstyle),
             Paragraph('Een herziening van de Statenvertaling in hedendaags Nederlands.', body), Spacer(1, 24),
             Paragraph(f"{counts['boeken']} boeken · {counts['hoofdstukken']} hoofdstukken · {counts['verzen']} verzen", small),
             Paragraph(f'Uitgave {html.escape(version)} · {date}', small),
             Paragraph('Zonder kanttekeningen en afbeeldingen.', small), PageBreak(),
             Paragraph('Over deze uitgave', bookstyle),
             Paragraph('Deze PDF bevat alle beschikbare hoofdstukken van de 82 openbare boeken van de Open Vertaling, inclusief de apocriefe boeken. De Godsnaam wordt weergegeven als HEERE. Voor kanttekeningen is de volledige Markdown-uitgave beschikbaar op openvertaling.nl/markdown/ov-volledig.md.', body),
             Spacer(1, 12), Paragraph('CC0 / publiek domein', chapterstyle),
             Paragraph('De OV-tekst mag vrij worden gebruikt, gekopieerd, bewerkt en verspreid, voor elk doel. Bronvermelding is niet verplicht. Deze PDF bevat geen extern beeldmateriaal.', body),
             Paragraph('Voorgestelde bronvermelding: Open Vertaling (OV), boek hoofdstuk:vers, uitgave '+html.escape(version)+', '+date+', https://openvertaling.nl.', small),
             Paragraph('Bron: <link href="https://openvertaling.nl" color="#143247">openvertaling.nl</link>. Licentie: <link href="https://creativecommons.org/publicdomain/zero/1.0/" color="#143247">CC0 1.0</link>. De inhoudsopgave en de bladwijzers van de PDF openen de boeken en hoofdstukken.', small), PageBreak(),
             Paragraph('Inhoud', bookstyle)]
    for book, chapters in selected:
        key = book['id']
        story.append(Paragraph(f'<link href="#{key}" color="#143247">{html.escape(book["nameDutch"])} <font color="#777777">({len(chapters)} hoofdstukken)</font></link>', contents))
    for book, chapters in selected:
        story.extend([PageBreak(), Heading(book['nameDutch'], bookstyle, book['id'], 0)])
        for nr, verses in chapters:
            story.append(Heading(f"{book['nameDutch']} {nr}", chapterstyle, f"{book['id']}-{nr}", 1))
            for number, text in verses:
                safe = re.sub(r'([\u0590-\u05ff]+)', r'<font name="Hebrew">\1</font>', html.escape(text))
                story.append(Paragraph(f'<super><font size="8">{number}</font></super> {safe}', body))

    def footer(canvas, doc):
        canvas.setTitle('Open Vertaling - volledige leesuitgave')
        canvas.setAuthor('Open Vertaling')
        canvas.setSubject(f'CC0 / publiek domein; {date}; {counts["boeken"]} boeken; zonder kanttekeningen')
        canvas.setCreator('Open Vertaling')
        canvas.setFont('OV', 9)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawCentredString(A5[0]/2, 25, str(doc.page))
        if doc.page > 2:
            canvas.drawString(38, A5[1]-25, 'Open Vertaling')

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with atomic_output(str(output)) as temporary:
        doc = SimpleDocTemplate(temporary, pagesize=A5, leftMargin=38, rightMargin=38, topMargin=42, bottomMargin=42, pageCompression=1)
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(json.dumps({'bestand': str(output), **counts}, ensure_ascii=False))
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    build(parser.parse_args().output)
