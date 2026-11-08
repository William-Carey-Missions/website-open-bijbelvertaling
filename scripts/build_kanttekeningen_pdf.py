#!/usr/bin/env python3
"""Bouw de Open Vertaling met kanttekeningen als PDF, in drie delen.

  deel 1  Genesis t/m Esther
  deel 2  Job t/m Maleachi
  deel 3  Mattheüs t/m Openbaring, met de apocriefe boeken aan het eind

Bijbeltekst in twee kolommen, daaronder op dezelfde bladzijde de kanttekeningen
in drie kolommen. De tekst komt uit data/ (text2026), de Godsnaam zoals de site
hem standaard toont (HEERE).

Installatie: python -m pip install -r requirements-pdf.txt
Gebruik:     python scripts/build_kanttekeningen_pdf.py [--deel 1] [--uit map]
             python scripts/build_kanttekeningen_pdf.py --proef genesis:1-3
"""
import argparse
from html.parser import HTMLParser
import bisect
import datetime
import difflib
import html as htmllib
import json
import math
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zetwerk import Lettertype, Pdf, Regel, Stijl, Zetter, lijn, maak_instantie, teken_regel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
BRONFONTS = ROOT / 'scripts' / 'druk-fonts'
UITVOER = ROOT / 'downloads'
UITVOERNAAM = 'open-vertaling-kanttekeningen-deel-{}.pdf'

# ---------------------------------------------------------------- bladspiegel (punten, A4)
BREEDTE, HOOGTE = 595.28, 841.89
BINNEN, BUITEN = 56.0, 44.0
BOVEN, ONDER = 58.0, 40.0
ZETBREEDTE = BREEDTE - BINNEN - BUITEN
ZETHOOGTE = HOOGTE - BOVEN - ONDER
KOLOMWIT2, KOLOMWIT3 = 17.0, 12.0
KOLOM2 = (ZETBREEDTE - KOLOMWIT2) / 2
KOLOM3 = (ZETBREEDTE - 2 * KOLOMWIT3) / 3
TEKST_KORPS, TEKST_REGEL = 10.2, 12.5
NOOT_KORPS, NOOT_REGEL = 7.5, 8.9
INTRO_KORPS, INTRO_REGEL = 9.2, 11.3
HST_KORPS, HST_REGEL = 8.0, 9.6
GAT_TEKST_NOTEN = 9.0
LIJNDIKTE = 0.35

DELEN = {
    1: {
        'titel': 'Genesis tot en met Esther',
        'testament': 'bevattende de boeken van het Oude Testament\nvan Genesis tot en met Esther',
        'groepen': [('', ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium', 'jozua', 'richteren', 'ruth',
                          '1samuel', '2samuel', '1koningen', '2koningen', '1kronieken', '2kronieken', 'ezra',
                          'nehemia', 'esther'])],
    },
    2: {
        'titel': 'Job tot en met Maleachi',
        'testament': 'bevattende de boeken van het Oude Testament\nvan Job tot en met Maleachi',
        'groepen': [('', ['job', 'psalmen', 'spreuken', 'prediker', 'hooglied', 'jesaja', 'jeremia', 'klaagliederen',
                          'ezechiel', 'daniel', 'hosea', 'joel', 'amos', 'obadja', 'jona', 'micha', 'nahum',
                          'habakuk', 'zefanja', 'haggai', 'zacharia', 'maleachi'])],
    },
    3: {
        'titel': 'Mattheüs tot en met Openbaring, met de apocriefe boeken',
        'testament': 'bevattende de boeken van het Nieuwe Testament\nen de apocriefe boeken',
        'groepen': [('Het Nieuwe Testament', ['mattheus', 'markus', 'lukas', 'johannes', 'handelingen', 'romeinen',
                                              '1korinthiers', '2korinthiers', 'galaten', 'efeziers', 'filippenzen',
                                              'kolossenzen', '1tessalonicensen', '2tessalonicensen', '1timotheus',
                                              '2timotheus', 'titus', 'filemon', 'hebreeen', 'jakobus', '1petrus',
                                              '2petrus', '1johannes', '2johannes', '3johannes', 'judas', 'openbaring']),
                    ('De apocriefe boeken', ['3ezra', '4ezra', 'tobit', 'judith', 'boekderwijsheid', 'jezussirach',
                                             'baruch', 'estherapocrief', 'gebedvanazaria', 'gezangindevuuroven',
                                             'susanna', 'belenddedraak', 'gebedvanmanasse', '1makkabeeen',
                                             '2makkabeeen', '3makkabeeen'])],
    },
}

# Boektitels: (bovenregel, tussenregel, grote regel).
TITELS = {
    'genesis': ('Het eerste boek van Mozes,', 'genaamd', 'Genesis'),
    'exodus': ('Het tweede boek van Mozes,', 'genaamd', 'Exodus'),
    'leviticus': ('Het derde boek van Mozes,', 'genaamd', 'Leviticus'),
    'numeri': ('Het vierde boek van Mozes,', 'genaamd', 'Numeri'),
    'deuteronomium': ('Het vijfde boek van Mozes,', 'genaamd', 'Deuteronomium'),
    'jozua': ('Het boek', '', 'Jozua'),
    'richteren': ('Het boek van de', '', 'Richteren'),
    'ruth': ('Het boek', '', 'Ruth'),
    '1samuel': ('Het eerste boek van', '', 'Samuël'),
    '2samuel': ('Het tweede boek van', '', 'Samuël'),
    '1koningen': ('Het eerste boek van de', '', 'Koningen'),
    '2koningen': ('Het tweede boek van de', '', 'Koningen'),
    '1kronieken': ('Het eerste boek van de', '', 'Kronieken'),
    '2kronieken': ('Het tweede boek van de', '', 'Kronieken'),
    'ezra': ('Het boek', '', 'Ezra'),
    'nehemia': ('Het boek', '', 'Nehemia'),
    'esther': ('Het boek', '', 'Esther'),
    'job': ('Het boek', '', 'Job'),
    'psalmen': ('Het boek van de', '', 'Psalmen'),
    'spreuken': ('De spreuken van', '', 'Salomo'),
    'prediker': ('Het boek van de', '', 'Prediker'),
    'hooglied': ('Het hooglied van', '', 'Salomo'),
    'jesaja': ('De profeet', '', 'Jesaja'),
    'jeremia': ('De profeet', '', 'Jeremia'),
    'klaagliederen': ('De klaagliederen van', '', 'Jeremia'),
    'ezechiel': ('De profeet', '', 'Ezechiël'),
    'daniel': ('De profeet', '', 'Daniël'),
    'hosea': ('De profeet', '', 'Hosea'),
    'joel': ('De profeet', '', 'Joël'),
    'amos': ('De profeet', '', 'Amos'),
    'obadja': ('De profeet', '', 'Obadja'),
    'jona': ('De profeet', '', 'Jona'),
    'micha': ('De profeet', '', 'Micha'),
    'nahum': ('De profeet', '', 'Nahum'),
    'habakuk': ('De profeet', '', 'Habakuk'),
    'zefanja': ('De profeet', '', 'Zefanja'),
    'haggai': ('De profeet', '', 'Haggaï'),
    'zacharia': ('De profeet', '', 'Zacharia'),
    'maleachi': ('De profeet', '', 'Maleachi'),
    'mattheus': ('Het evangelie', 'volgens', 'Mattheüs'),
    'markus': ('Het evangelie', 'volgens', 'Markus'),
    'lukas': ('Het evangelie', 'volgens', 'Lukas'),
    'johannes': ('Het evangelie', 'volgens', 'Johannes'),
    'handelingen': ('De handelingen', 'van de', 'Apostelen'),
    'romeinen': ('De brief van de apostel Paulus', 'aan de', 'Romeinen'),
    '1korinthiers': ('De eerste brief van de apostel Paulus', 'aan de', 'Korinthiërs'),
    '2korinthiers': ('De tweede brief van de apostel Paulus', 'aan de', 'Korinthiërs'),
    'galaten': ('De brief van de apostel Paulus', 'aan de', 'Galaten'),
    'efeziers': ('De brief van de apostel Paulus', 'aan de', 'Efeziërs'),
    'filippenzen': ('De brief van de apostel Paulus', 'aan de', 'Filippenzen'),
    'kolossenzen': ('De brief van de apostel Paulus', 'aan de', 'Kolossenzen'),
    '1tessalonicensen': ('De eerste brief van de apostel Paulus', 'aan de', 'Tessalonicensen'),
    '2tessalonicensen': ('De tweede brief van de apostel Paulus', 'aan de', 'Tessalonicensen'),
    '1timotheus': ('De eerste brief van de apostel Paulus', 'aan', 'Timotheüs'),
    '2timotheus': ('De tweede brief van de apostel Paulus', 'aan', 'Timotheüs'),
    'titus': ('De brief van de apostel Paulus', 'aan', 'Titus'),
    'filemon': ('De brief van de apostel Paulus', 'aan', 'Filemon'),
    'hebreeen': ('De brief', 'aan de', 'Hebreeën'),
    'jakobus': ('De algemene brief van', '', 'Jakobus'),
    '1petrus': ('De eerste algemene brief van', '', 'Petrus'),
    '2petrus': ('De tweede algemene brief van', '', 'Petrus'),
    '1johannes': ('De eerste algemene brief van', '', 'Johannes'),
    '2johannes': ('De tweede brief van', '', 'Johannes'),
    '3johannes': ('De derde brief van', '', 'Johannes'),
    'judas': ('De algemene brief van', '', 'Judas'),
    'openbaring': ('De openbaring van', '', 'Johannes'),
    '3ezra': ('Het derde boek van', '', 'Ezra'),
    '4ezra': ('Het vierde boek van', '', 'Ezra'),
    'tobit': ('Het boek', '', 'Tobit'),
    'judith': ('Het boek', '', 'Judith'),
    'boekderwijsheid': ('Het boek', 'der', 'Wijsheid'),
    'jezussirach': ('De wijsheid van', '', 'Jezus Sirach'),
    'baruch': ('Het boek van', '', 'Baruch'),
    'estherapocrief': ('De toevoegingen aan het boek', '', 'Esther'),
    'gebedvanazaria': ('Het gebed van', '', 'Azarja'),
    'gezangindevuuroven': ('Het gezang', 'in de', 'Vuuroven'),
    'susanna': ('De geschiedenis van', '', 'Susanna'),
    'belenddedraak': ('De geschiedenis van', '', 'Bel en de draak'),
    'gebedvanmanasse': ('Het gebed van', '', 'Manasse'),
    '1makkabeeen': ('Het eerste boek van de', '', 'Makkabeeën'),
    '2makkabeeen': ('Het tweede boek van de', '', 'Makkabeeën'),
    '3makkabeeen': ('Het derde boek van de', '', 'Makkabeeën'),
}

# De bijbelplaatsen voor de bladzijde over het lezen van de Schrift (OV-tekst uit data/).
SCHRIFTLEZING = [
    ('deuteronomium', 31, [12]), ('jozua', 1, [8]), ('psalmen', 1, [2]), ('psalmen', 119, [105]),
    ('johannes', 5, [39]), ('handelingen', 17, [11]), ('romeinen', 15, [4]),
    ('2timotheus', 3, [15, 16, 17]), ('openbaring', 1, [3]),
]

AFKORTINGEN = [('aant.', 'aantekening, aantekeningen'), ('Chald.', 'Chaldeeuws'), ('d.i.', 'dat is'), ('Gr.', 'Grieks'),
               ('Hebr.', 'Hebreeuws'), ('hst.', 'hoofdstuk, hoofdstukken'), ('nl.', 'namelijk'), ('t.w.', 'te weten'),
               ('vgl.', 'vergelijk'), ('vs.', 'vers, verzen')]

VERANTWOORDING = [
    'De Open Vertaling is een vrije herziening van de Statenvertaling in hedendaags Nederlands. De tekst blijft zo dicht '
    'mogelijk bij de Statenvertaling; alleen wat een lezer van nu niet meer begrijpt is aangepast: naamvallen, '
    'werkwoordsvormen, verouderde woorden en de spelling. Woorden die in de Bijbeltaal thuishoren, zoals uitspansel en '
    'gevogelte, zijn blijven staan. Uitgangspunt is de editie van de Statenvertaling uit 1888.',
    'De Statenvertalers gaven hun vertaling kanttekeningen mee: toelichtingen bij woorden en zinnen en verwijzingen naar '
    'andere bijbelplaatsen. Ook die zijn in de Open Vertaling herzien, op dezelfde manier als de bijbeltekst. Deze '
    'uitgave zet ze weer op de plaats waarvoor ze bedoeld zijn: op dezelfde bladzijde als de tekst waarbij ze horen.',
    'Vervangingen zijn gedaan volgens vastgelegde wijzigingsprincipes. AI is daarbij als hulpmiddel gebruikt; de '
    'uitgangspunten en de redactionele keuzes zijn door mensen bepaald. De volledige lijst met principes staat op '
    'openvertaling.nl.',
    '§Over deze uitgave',
    'De bijbeltekst staat in twee kolommen, de kanttekeningen daaronder in drie. Een cijfer in de tekst verwijst naar een '
    'uitleggende kanttekening, een letter naar een verwijzing naar andere bijbelplaatsen; beide staan vlak vóór het woord '
    'waarop ze slaan en lopen per hoofdstuk door. Een schuingedrukt woord aan het begin van een kanttekening is het woord '
    'of de woordgroep uit de tekst die wordt besproken.',
    'Godscitaten die in de brontekst zijn gemarkeerd, staan rood en cursief.',
    'De Godsnaam staat in deze uitgave als HEERE, gelijk aan de standaardweergave op openvertaling.nl.',
    'In de digitale kanttekeningen is bij een verwijzing vaak de volledige tekst van de bijbelplaats ingevoegd. Hier staat '
    'alleen de verwijzing, zodat de bladzijde overzichtelijk blijft; veelvoorkomende woorden zijn afgekort volgens de lijst '
    'op de volgende bladzijden.',
    'De apocriefe boeken staan, zoals in de oude Statenbijbels, apart achter de andere boeken. De Statenvertalers namen ze '
    'op met de waarschuwing dat ze niet tot de canon van de Heilige Schrift behoren. In deze uitgave staan bij die boeken '
    'geen kanttekeningen.',
    'De tekst is vrij van rechten (CC0 1.0): iedereen mag hem citeren, kopiëren, drukken, bewerken en hergebruiken, zonder '
    'toestemming te vragen. Deze PDF wordt opnieuw opgebouwd uit de tekst op openvertaling.nl.',
]

BOEKNAAM_VARIANTEN = (
    'Genesis Exodus Leviticus Numeri Deuteronomium Jozua Richteren Ruth Samuël Koningen Kronieken Ezra Nehemia Esther '
    'Job Psalmen Psalm Spreuken Prediker Hooglied Jesaja Jeremia Klaagliederen Ezechiël Daniël Hosea Joël Amos Obadja '
    'Jona Micha Nahum Habakuk Zefanja Haggaï Zacharia Maleachi Mattheüs Markus Lukas Johannes Handelingen Romeinen '
    'Korinthiërs Korintiërs Galaten Efeziërs Filippenzen Kolossenzen Kolossensen Thessalonicenzen Thessalonicensen '
    'Timotheüs Titus Filemon Hebreeën Jakobus Petrus Judas Openbaring Tobit Judith Wijsheid Sirach Baruch Susanna').split()
INGEVOEGD_VERS = re.compile(
    r'(?:(?<=[\s.;,:)\]])|^)((?:[123] )?(?:' + '|'.join(BOEKNAAM_VARIANTEN) + r')\s+\d+\s?:\s?\d+)\s?:\s+\S')
GEEN_LEMMA = re.compile(
    r'^(hebr|hebreeuws|grieks|gr\b|chald|of\b|anders|dat\b|dit\b|dan\b|die\b|zie\b|vgl|vergelijk|verg\b|versta|namelijk|nl\b|'
    r'te weten|t\.w|d\.i|let\b|want\b|men\b|hier\b|maar\b|en\b|zo\b|als\b|ook\b|niet\b|hij\b|zij\b|wij\b|ik\b|het is|'
    r'sommigen|anderen|enige|de zin|de betekenis|de mening|noot\b)', re.I)
BOEKAFKORTING = r'(?:Kor|Kon|Sam|Kron|Tim|Thess|Tess|Petr?|Joh|Mak|Ezra|Makk)\b'


def romeins(n):
    uit = ''
    for waarde, teken in ((100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= waarde:
            uit += teken
            n -= waarde
    return uit


def godsnaam(tekst):
    """Gelijk aan de klassieke standaardinstelling van openvertaling.nl."""
    from godsnaam import heere
    return heere(tekst)


def spaties(tekst):
    tekst = re.sub(r'\s+', ' ', tekst).strip()
    tekst = re.sub(r' ([,;:.!?)\]])', r'\1', tekst)
    return tekst


def schoon_noot(tekst, marker, verstekst):
    """Geeft (lemma, tekst): zonder ingevoegde versteksten, dubbel cijfer en met afkortingen."""
    t = tekst.strip()
    gevonden = re.match(r'^(\d+)\s+(?!' + BOEKAFKORTING + ')', t)
    if gevonden and gevonden.group(1) == str(marker):
        t = t[gevonden.end():]
    m = INGEVOEGD_VERS.search(t)
    if m:
        kop = t[:m.start()].rstrip(' ,;')
        t = kop if kop else m.group(1)
    t = spaties(godsnaam(t))
    lemma = ''
    m = re.match(r'^([^.:;!?]{1,80}):\s+(?=\S)', t)
    if m and not GEEN_LEMMA.match(m.group(1)):
        # Alleen een echte aanhaling: het merendeel van de woorden staat ook in het vers.
        woorden = re.findall(r'\w+', m.group(1).lower())
        in_vers = set(re.findall(r'\w+', verstekst.lower()))
        if woorden and sum(w in in_vers for w in woorden) / len(woorden) >= 0.6:
            lemma = m.group(1)
            t = t[m.end():]
    return lemma, afkort(t)


def afkort(t):
    """Vaste afkortingen uit de lijst in het voorwerk; alleen waar de vorm ondubbelzinnig is."""
    t = re.sub(r'\bHebreeuws(?:e tekst)?\s?[,:]\s', 'Hebr.: ', t)
    t = re.sub(r'\bHebr\.?\s?[,:]\s', 'Hebr.: ', t)
    t = re.sub(r'\bHebr\.\s(?=[a-zëï])', 'Hebr.: ', t)
    t = re.sub(r'\bHebreeuws\b', 'Hebr.', t)
    t = re.sub(r'\bGrieks\s?[,:]\s', 'Gr.: ', t)
    t = re.sub(r'\bGrieks\b', 'Gr.', t)
    t = re.sub(r'\bChaldeeuws\s?[,:]\s', 'Chald.: ', t)
    t = re.sub(r'\bChaldeeuws\b', 'Chald.', t)
    t = re.sub(r'\bOf,\s', 'Of: ', t)
    t = re.sub(r'\bAnders,\s', 'Anders: ', t)
    t = re.sub(r'\bDat is,\s', 'D.i. ', t)
    t = re.sub(r'\bdat is,\s', 'd.i. ', t)
    t = re.sub(r'\bNamelijk,?\s', 'Nl. ', t)
    t = re.sub(r'\bnamelijk,?\s', 'nl. ', t)
    t = re.sub(r'^Te weten,?\s', 'T.w. ', t)
    t = re.sub(r'(?<=[.;] )Te weten,?\s', 'T.w. ', t)
    t = re.sub(r'\bte weten,\s', 't.w. ', t)
    t = re.sub(r'\bVergelijk\s', 'Vgl. ', t)
    t = re.sub(r'\bvergelijk\s', 'vgl. ', t)
    t = re.sub(r'\b(?:vers|verzen)\s(?=\d)', 'vs. ', t)
    t = re.sub(r'\b(?:Vers|Verzen)\s(?=\d)', 'Vs. ', t)
    t = re.sub(r'\bhfdst\.?\s(?=\d)', 'hst. ', t)
    t = re.sub(r'\bhoofdstuk(?:ken)?\s(?=\d)', 'hst. ', t)
    t = re.sub(r'\baantekeningen?\b', 'aant.', t)
    return t.replace('..', '.').replace('.,', ',') if '..' in t or 'aant.,' in t else t


def noot_segmenten(lemma, tekst, marker, soort, st):
    """De kanttekening als gezette stukken: nummer, cursief lemma, cursieve lezing na 'Hebr.:' of 'Of:'."""
    if soort == 'crossref':
        segs = [('– ', st['noot']), (f'{marker} ', st['noot_c'])]
    else:
        segs = [(f'{marker} ', st['noot'])]
    if lemma:
        segs.append((f'{lemma}: ', st['noot_c']))
    m = re.match(r'^((?:Hebr|Gr|Chald)\.:|Of:|Anders:) ([^.;]{1,70})([.;]|$)(.*)$', tekst, re.S)
    if m:
        segs += [(m.group(1) + ' ', st['noot']), (m.group(2), st['noot_c']), (m.group(3) + m.group(4), st['noot'])]
    else:
        segs.append((tekst, st['noot']))
    return segs


def vers_woorden(vers):
    """Woorden van het vers met de nootmerktekens vóór het woord waarop ze slaan.

    In de data staat een merkteken achter het vorige woord (`de<sup>3</sup> hemel`);
    op papier staat het voor het woord zelf (`de ³hemel`).
    """
    bron = godsnaam(vers.get('text2026_html') or vers.get('text2026') or '')
    class WoordenParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.woorden, self.wachtend, self.stapel = [], [], []
            self.huidig = None
            self.sup = 0

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'sup':
                self.sup += 1
                merk = attrs.get('data-note')
                if merk is not None:
                    if self.huidig is not None and not re.search(r'\w', self.huidig['tekst']):
                        self.huidig['voor'].append(merk)
                    else:
                        self.wachtend.append(merk)
            if tag not in ('br', 'hr', 'img', 'wbr'):
                self.stapel.append((tag, 'god-speaks' in attrs.get('class', '').split()))

        def handle_endtag(self, tag):
            if tag == 'sup':
                self.sup = max(0, self.sup - 1)
            for i in range(len(self.stapel) - 1, -1, -1):
                if self.stapel[i][0] == tag:
                    del self.stapel[i:]
                    break

        def handle_data(self, data):
            if self.sup:
                return
            god = any(markering for _, markering in self.stapel)
            for stuk in re.findall(r'\s+|\S+', data.replace(chr(0xA0), ' ')):
                if stuk.isspace():
                    self.huidig = None
                    continue
                if self.huidig is None:
                    self.huidig = {'voor': self.wachtend, 'tekst': '', 'delen': []}
                    self.wachtend = []
                    self.woorden.append(self.huidig)
                self.huidig['tekst'] += stuk
                self.huidig['delen'].append((stuk, god))

    parser = WoordenParser()
    parser.feed(bron)
    parser.close()
    if parser.wachtend and parser.woorden:
        parser.woorden[-1]['voor'] += parser.wachtend
    return parser.woorden



def hang_noten_aan(vers, woorden, plat):
    """Koppelt elke kanttekening aan een merkteken; zonder merkteken zoeken we de plek op."""
    aanwezig = {m for w in woorden for m in w['voor']}
    noten = [n for n in vers.get('marginNotes') or [] if n.get('text2026') and n.get('marker')]
    for noot in noten:
        marker = str(noot['marker'])
        if marker in aanwezig or not woorden:
            continue
        doel = zoek_plek(noot, marker, vers, woorden, plat)
        woorden[doel]['voor'].append(marker)
        aanwezig.add(marker)
    per_merk = {}
    for noot in noten:
        per_merk.setdefault(str(noot['marker']), []).append(noot)
    for w in woorden:
        w['voor'] = [m for m in w['voor'] if m in per_merk]
    return per_merk


def zoek_plek(noot, marker, vers, woorden, plat):
    """Eerst op het besproken woord, dan op de plaats in de oudere tekst, anders achteraan."""
    t = re.sub(r'^\d+\s+', '', noot['text2026'])
    m = re.match(r'^([^.:;!?]{1,80}):\s', t)
    if m and not GEEN_LEMMA.match(m.group(1)):
        eerste = re.findall(r"[\w']+", godsnaam(m.group(1)).lower())
        if eerste:
            kandidaten = [re.sub(r'\W', '', w['tekst'].lower()) for w in woorden]
            for i in range(len(kandidaten)):
                if kandidaten[i:i + len(eerste)] == eerste:
                    return i
            for woord in eerste:
                if len(woord) > 2 and woord in kandidaten:
                    return kandidaten.index(woord)
    for sleutel in ('textSV1888_html', 'text1637_html'):
        oud = vers.get(sleutel) or ''
        m = re.search(r'data-note="' + re.escape(marker) + '"', oud)
        if m:
            voor = len(re.sub(r'<[^>]+>', ' ', oud[:m.start()]).split())
            totaal = max(1, len(re.sub(r'<[^>]+>', ' ', oud).split()))
            return min(len(woorden) - 1, round(voor / totaal * len(woorden)))
    return len(woorden) - 1


# ---------------------------------------------------------------- lettertypes

def lettertypes():
    bron = BRONFONTS / 'SourceSerif4[opsz,wght].ttf'
    bron_c = BRONFONTS / 'SourceSerif4-Italic[opsz,wght].ttf'
    bron_h = BRONFONTS / 'NotoSerifHebrew[wdth,wght].ttf'
    bron_g = BRONFONTS / 'EBGaramond[wght].ttf'
    f = {
        'tekst': Lettertype(maak_instantie(bron, {'opsz': 11, 'wght': 400}, 'SourceSerif4-Text'), 'SourceSerif4-Text'),
        'tekst_c': Lettertype(maak_instantie(bron_c, {'opsz': 11, 'wght': 400}, 'SourceSerif4-TextItalic'), 'SourceSerif4-TextItalic'),
        'noot': Lettertype(maak_instantie(bron, {'opsz': 8, 'wght': 400}, 'SourceSerif4-Caption'), 'SourceSerif4-Caption'),
        'noot_c': Lettertype(maak_instantie(bron_c, {'opsz': 8, 'wght': 400}, 'SourceSerif4-CaptionItalic'), 'SourceSerif4-CaptionItalic'),
        'kop': Lettertype(maak_instantie(bron, {'opsz': 28, 'wght': 500}, 'SourceSerif4-Subhead'), 'SourceSerif4-Subhead'),
        'hebr': Lettertype(maak_instantie(bron_h, {'wdth': 100, 'wght': 400}, 'NotoSerifHebrew'), 'NotoSerifHebrew'),
        'grieks': Lettertype(maak_instantie(bron_g, {'wght': 500}, 'EBGaramond-Medium'), 'EBGaramond-Medium'),
    }
    return f


def stijlen(f):
    oud = (('onum', True), )
    return {
        'tekst': Stijl(f['tekst'], TEKST_KORPS, kenmerken=oud),
        'godscitaat': Stijl(f['tekst_c'], TEKST_KORPS, kenmerken=oud, kleur=(0.65, 0.08, 0.10)),
        'tekst_kk': Stijl(f['tekst'], TEKST_KORPS, kenmerken=(('smcp', True), ('onum', True)), spatie=0.25, afbreken=False),
        'nr': Stijl(f['tekst'], TEKST_KORPS, kenmerken=oud, afbreken=False),
        'merk': Stijl(f['noot'], 5.7, hoog=3.7, afbreken=False),
        'begin': Stijl(f['kop'], 2 * TEKST_REGEL / 0.66 * 0.70, afbreken=False),
        'intro': Stijl(f['tekst'], INTRO_KORPS, kenmerken=oud),
        'intro_begin': Stijl(f['kop'], 2 * INTRO_REGEL / 0.66 * 0.70, afbreken=False),
        'intro_kk': Stijl(f['tekst'], INTRO_KORPS, kenmerken=(('smcp', True), ('onum', True)), spatie=0.2, afbreken=False),
        'hst_kop': Stijl(f['kop'], 9.4, spatie=0.9, afbreken=False),
        'hst': Stijl(f['noot'], HST_KORPS, kenmerken=oud),
        'tussenkop': Stijl(f['tekst_c'], TEKST_KORPS, kenmerken=oud),
        'noot': Stijl(f['noot'], NOOT_KORPS, kenmerken=oud),
        'noot_c': Stijl(f['noot_c'], NOOT_KORPS, kenmerken=oud),
        'boek_boven': Stijl(f['kop'], 17, spatie=0.8, afbreken=False),
        'boek_tussen': Stijl(f['kop'], 11, spatie=0.7, afbreken=False),
        'boek_groot': Stijl(f['kop'], 31, spatie=0.4, afbreken=False),
        'inhoud_kop': Stijl(f['kop'], 9.6, spatie=0.9, afbreken=False),
        'kop_bl': Stijl(f['kop'], 8.4, spatie=0.7, afbreken=False),
        'bladnr': Stijl(f['tekst'], 10, kenmerken=oud, afbreken=False),
        't_groot': Stijl(f['kop'], 54, spatie=1.0, afbreken=False),
        't_mid': Stijl(f['kop'], 25, spatie=0.8, afbreken=False),
        't_klein': Stijl(f['kop'], 15, spatie=0.5, afbreken=False),
        't_tekst': Stijl(f['tekst'], 11.5, kenmerken=oud, afbreken=False),
        't_cursief': Stijl(f['tekst_c'], 11.5, kenmerken=oud, afbreken=False),
        'fm_kop': Stijl(f['kop'], 15, spatie=0.7, afbreken=False),
        'fm': Stijl(f['tekst'], 10.2, kenmerken=oud),
        'fm_c': Stijl(f['tekst_c'], 10.2, kenmerken=oud),
        'fm_klein': Stijl(f['tekst'], 9.2, kenmerken=oud),
    }


# ---------------------------------------------------------------- bouwstenen

class Item:
    """Eén regel of witruimte in de kolommen van de bijbeltekst."""
    __slots__ = ('h', 'regel', 'breek', 'noten', 'hst', 'gat', 'x', 'extra')

    def __init__(self, h, regel=None, breek=True, noten=(), hst=None, gat=False, x=0.0, extra=None):
        self.h, self.regel, self.breek, self.noten = h, regel, breek, noten
        self.hst, self.gat, self.x, self.extra = hst, gat, x, extra


def laad_boek(boek):
    with open(DATA / f'{boek}.json', encoding='utf-8') as fh:
        meta = json.load(fh)
    nummers = sorted(int(p.stem) for p in (DATA / boek).glob('*.json') if p.stem.isdigit())
    hoofdstukken = []
    for n in nummers:
        with open(DATA / boek / f'{n}.json', encoding='utf-8') as fh:
            hoofdstukken.append(json.load(fh))
    return meta, hoofdstukken


def zet_hoofdstuk(zetter, st, boek, hoofdstuk, perikopen, items, noten, stats):
    """Voegt de kop, inleiding en verzen van één hoofdstuk toe aan de kolomstroom."""
    nummer = int(hoofdstuk['number'])
    psalm = boek == 'psalmen'
    koptekst = f'PSALM {nummer}' if psalm else f'HOOFDSTUK {romeins(nummer)}'
    if items:
        items.append(Item(13.0, gat=True, breek=False, hst=nummer))
    kop = zetter.los([(koptekst, st['hst_kop'])])
    items.append(Item(14.0, kop, breek=False, hst=nummer, x=(KOLOM2 - kop.breedte) / 2, extra=('hst', nummer)))
    items.append(Item(3.0, gat=True, breek=False, hst=nummer))

    intro = (hoofdstuk.get('chapterIntro') or {}).get('text2026')
    if intro:
        regels = zetter.zet([(re.sub(r'\bvers\s(?=\d)', 'vs. ', spaties(godsnaam(intro))), st['hst'])], KOLOM2)
        for i, r in enumerate(regels):
            mag = 2 <= i + 1 <= len(regels) - 2
            items.append(Item(HST_REGEL, r, breek=mag, hst=nummer))
        items.append(Item(4.0, gat=True, breek=False, hst=nummer))

    for vers in hoofdstuk['verses']:
        versnummer = int(vers['number']) if str(vers['number']).isdigit() else vers['number']
        kop_tekst = perikopen.get((nummer, versnummer))
        if kop_tekst:
            k = zetter.zet([(godsnaam(kop_tekst), st['tussenkop'])], KOLOM2, uitvullen=False)
            for r in k:
                items.append(Item(TEKST_REGEL + 1.0, r, breek=False, hst=nummer, x=(KOLOM2 - r.breedte) / 2))
            items.append(Item(TEKST_REGEL, gat=True, breek=False, hst=nummer))
        woorden = vers_woorden(vers)
        plat = ' '.join(w['tekst'] for w in woorden)
        per_merk = hang_noten_aan(vers, woorden, plat)
        eerste_vers = vers is hoofdstuk['verses'][0]

        segs = []
        dropcap = None
        if eerste_vers and woorden and not any(god for _, god in woorden[0]['delen']) and re.match(r'^[^\W\d_]', woorden[0]['tekst']):
            eerste = woorden[0]
            letter = eerste['tekst'][0].upper()
            dropcap = zetter.los([(letter, st['begin'])])
            segs += merktekens(eerste['voor'], per_merk, st)
            rest = eerste['tekst'][1:]
            if rest:
                # Rest van het eerste woord in kleinkapitalen, zoals bij een oude Bijbel.
                segs.append((rest.lower(), st['tekst_kk']))
            segs.append((' ', st['tekst']))
            woorden = woorden[1:]
        else:
            segs.append((f'{versnummer}' + chr(0xA0), st['nr']))
        for i, w in enumerate(woorden):
            segs += merktekens(w['voor'], per_merk, st)
            for tekst, god in w['delen']:
                segs.append((tekst, st['godscitaat'] if god else st['tekst']))
            if i + 1 < len(woorden):
                segs.append((' ', st['tekst']))

        if dropcap:
            d = dropcap.breedte + 1.5
            regels = zetter.zet(segs, KOLOM2, eerste=(KOLOM2 - d, KOLOM2 - d), verschuif=(d, d))
        else:
            regels = zetter.zet(segs, KOLOM2, inspring=8.0)
        n = len(regels)
        gezet = set()
        for i, r in enumerate(regels):
            mag = (i + 1 >= 2 and n - i - 1 >= 2) or i + 1 == n
            lijst = []
            for merk in r.noten:
                lijst += per_merk.get(merk, [])
            ids = []
            for noot in lijst:
                if id(noot) in gezet:
                    continue  # een merkteken dat twee keer in het vers staat
                gezet.add(id(noot))
                ids.append(len(noten))
                noten.append(maak_noot(zetter, st, noot, vers, plat, nummer))
                stats['noten'] += 1
            r.noten = ()
            extra = None
            if dropcap and i == 1:
                extra = ('begin', dropcap)
            items.append(Item(TEKST_REGEL, r, breek=mag, noten=ids, hst=nummer, extra=extra))
        if dropcap and n == 1:
            items[-1].breek = False
            items.append(Item(TEKST_REGEL, Regel([], 0), breek=True, hst=nummer, extra=('begin', dropcap)))
        stats['verzen'] += 1


def merktekens(merken, per_merk, st):
    segs = []
    for j, merk in enumerate(merken):
        tussen = ' ' if j else ''
        segs.append((tussen + merk, st['merk'], merk))
    return segs


def maak_noot(zetter, st, noot, vers, plat, hoofdstuk):
    lemma, tekst = schoon_noot(noot['text2026'], noot['marker'], plat)
    segs = noot_segmenten(lemma, tekst, noot['marker'], noot.get('type'), st)
    return zetter.zet(segs, KOLOM3, inspring=6.0)


class Boekbouwer:
    """Vult bladzijden: bijbeltekst bovenaan in twee kolommen, kanttekeningen onderaan in drie."""

    def __init__(self, pdf, st, zetter):
        self.pdf, self.st, self.zetter = pdf, st, zetter
        self.controle = {'noot_te_laat': 0, 'noot_gesplitst': 0}
        self.afwijkingen = []

    # coördinaten
    def linkerrand(self, pagina):
        """Oneven bladzijden liggen rechts; de binnenmarge zit dan links."""
        return BINNEN if pagina % 2 == 1 else BUITEN

    def koptekst(self, uit, pagina, tekst):
        x = self.linkerrand(pagina)
        y = HOOGTE - 36.0
        nr = self.zetter.los([(str(pagina), self.st['bladnr'])])
        if pagina % 2 == 1:
            teken_regel(nr, x + ZETBREEDTE - nr.breedte, y, uit)
        else:
            teken_regel(nr, x, y, uit)
        if tekst:
            kop = self.zetter.los([(tekst, self.st['kop_bl'])])
            teken_regel(kop, x + (ZETBREEDTE - kop.breedte) / 2, y, uit)

    def kolomverdeling(self, som, items, i, k):
        """Kleinste kolomhoogte voor items[i:k] in twee kolommen. Geeft (hoogte, splitsing)."""
        totaal = som[k] - som[i]
        if k - i == 1:
            return totaal, k
        doel = som[i] + totaal / 2
        s = bisect.bisect_left(som, doel, i + 1, k + 1)
        beste = None
        for kandidaat in range(max(i + 1, s - 14), min(k, s + 14) + 1):
            if kandidaat < k and not items[kandidaat - 1].breek:
                continue
            eerste, tweede = som[kandidaat] - som[i], som[k] - som[kandidaat]
            h = max(eerste, tweede)
            # Bij gelijke hoogte: de eerste kolom krijgt het meest.
            if beste is None or h < beste[0] - 1e-6:
                beste = (h, kandidaat)
        return beste if beste else (totaal, k)

    def vul(self, items, noten, kopfunctie, bovenruimte=0.0, voorop=None):
        """Zet de hele stroom op bladzijden. Geeft het nummer van de laatste bladzijde."""
        som = [0.0]
        for it in items:
            som.append(som[-1] + it.h)
        # Aantal notenregels per item, cumulatief.
        notensom = [0]
        for it in items:
            notensom.append(notensom[-1] + sum(len(noten[n]) for n in it.noten))
        i, n = 0, len(items)
        overloop = []  # notenregels die nog moeten
        boven = bovenruimte
        while i < n or overloop:
            beschikbaar = ZETHOOGTE - boven
            carry = len(overloop)
            beste_k, beste_h, beste_s = i, 0.0, i
            k = i + 1
            kandidaten_over = None
            while k <= n:
                h, s = self.kolomverdeling(som, items, i, k)
                if h > beschikbaar:
                    break
                if k == n or items[k - 1].breek:
                    nodig = carry + notensom[k] - notensom[i]
                    ruimte = beschikbaar - h - (GAT_TEKST_NOTEN if nodig else 0)
                    rijen = int(ruimte // NOOT_REGEL) if ruimte > 0 else 0
                    if nodig <= rijen * 3:
                        beste_k, beste_h, beste_s = k, h, s
                    else:
                        # Past alleen als de laatste noot mag doorlopen; onthoud voor als het nodig is.
                        laatste = self._laatste_noot(items, i, k, noten)
                        minimum = nodig - max(0, laatste - 3) if laatste else nodig
                        if minimum <= rijen * 3:
                            kandidaten_over = (k, h, s)
                k += 1

            vulling = self._vulling(beste_h, carry + notensom[beste_k] - notensom[i], beschikbaar)
            if (beste_k == i or (vulling < 0.86 and beste_k < n)) and kandidaten_over and kandidaten_over[0] > beste_k:
                beste_k, beste_h, beste_s = kandidaten_over
            if beste_k == i and carry == 0 and i < n:
                # Noodgreep: een regel met meer noten dan op een bladzijde past.
                k = i + 1
                while k < n and not items[k - 1].breek:
                    k += 1
                beste_k = k
                beste_h, beste_s = self.kolomverdeling(som, items, i, k)
                self.afwijkingen.append(f'noodgreep op bladzijde {len(self.pdf.paginas) + 1}')

            # Notenregels voor deze bladzijde.
            nieuw = []
            for it in items[i:beste_k]:
                for nid in it.noten:
                    nieuw.append((nid, noten[nid]))
            ruimte = beschikbaar - beste_h - GAT_TEKST_NOTEN
            rijen = max(0, int(ruimte // NOOT_REGEL))
            capaciteit = rijen * 3
            regels, overloop = overloop[:capaciteit], overloop[capaciteit:]
            for nid, nregels in nieuw:
                for rn, r in enumerate(nregels):
                    if len(regels) < capaciteit:
                        regels.append(r)
                    else:
                        if rn == 0:
                            self.controle['noot_te_laat'] += 1
                        overloop.append(r)
            if overloop:
                self.controle['noot_gesplitst'] += 1

            pagina = len(self.pdf.paginas) + 1
            self._teken_pagina(pagina, items, i, beste_s, beste_k, beste_h, regels, boven, kopfunctie,
                               voorop, n, overloop)
            voorop = None
            i = beste_k
            boven = 0.0
        return len(self.pdf.paginas)

    @staticmethod
    def _laatste_noot(items, i, k, noten):
        for it in reversed(items[i:k]):
            if it.noten:
                return len(noten[it.noten[-1]])
        return 0

    @staticmethod
    def _vulling(h, notenregels, beschikbaar):
        rijen = math.ceil(notenregels / 3)
        return (h + (GAT_TEKST_NOTEN if notenregels else 0) + rijen * NOOT_REGEL) / beschikbaar

    def _teken_pagina(self, pagina, items, i, s, k, h, notenregels, boven, kopfunctie, voorop, n, overloop):
        uit = ['0 0 0 RG 0 0 0 rg\n']
        x0 = self.linkerrand(pagina)
        y_boven = HOOGTE - BOVEN - boven
        hoofdstukken = [it.hst for it in items[i:k] if it.hst is not None]
        self.koptekst(uit, pagina, kopfunctie(hoofdstukken, voorop is not None))
        if voorop:
            uit.extend(voorop)
        self._teken_kolom(items, i, s, x0, y_boven, uit, pagina)
        self._teken_kolom(items, s, k, x0 + KOLOM2 + KOLOMWIT2, y_boven, uit, pagina)
        if s < k and i < s:
            xr = x0 + KOLOM2 + KOLOMWIT2 / 2
            lijn(xr, y_boven - 1, xr, y_boven - h + 1.5, LIJNDIKTE, uit)
        if notenregels:
            rijen = math.ceil(len(notenregels) / 3)
            # Onderaan de bladzijde, zodat de bladspiegel gelijk blijft; op een laatste, korte
            # bladzijde van een boek sluiten ze direct op de tekst aan.
            y_top = ONDER + rijen * NOOT_REGEL
            einde_boek = k == n and not overloop
            if einde_boek:
                y_top = y_boven - h - GAT_TEKST_NOTEN
            kolommen = [notenregels[c * rijen:(c + 1) * rijen] for c in range(3)]
            for c, kol in enumerate(kolommen):
                x = x0 + c * (KOLOM3 + KOLOMWIT3)
                y = y_top - NOOT_REGEL * 0.76
                for r in kol:
                    teken_regel(r, x, y, uit)
                    y -= NOOT_REGEL
                if c < 2 and kolommen[c + 1]:
                    xr = x + KOLOM3 + KOLOMWIT3 / 2
                    lijn(xr, y_top - 0.5, xr, y_top - rijen * NOOT_REGEL + 0.5, LIJNDIKTE, uit)
        self.pdf.pagina(''.join(uit))

    def _teken_kolom(self, items, i, k, x, y_top, uit, pagina):
        y = y_top
        eerste = True
        for it in items[i:k]:
            if it.gat and eerste:
                continue
            eerste = False
            if it.regel is not None:
                basis = y - it.h * 0.77
                teken_regel(it.regel, x + it.x, basis, uit)
                if it.extra:
                    if it.extra[0] == 'hst':
                        self.bladwijzer_hoofdstuk(it.extra[1], pagina - 1)
                    elif it.extra[0] == 'begin':
                        teken_regel(it.extra[1], x, basis, uit)
            y -= it.h
        return y

    def bladwijzer_hoofdstuk(self, nummer, pagina_index):
        self.hoofdstuk_op.append((nummer, pagina_index))


def is_kopie_van_hoofdstuk(intro, hoofdstukken):
    """Bij de apocriefe boeken is de boekinleiding de samenvatting van hoofdstuk 1 nog eens."""
    eerste = ((hoofdstukken[0].get('chapterIntro') or {}).get('text2026') or '') if hoofdstukken else ''
    return bool(eerste) and difflib.SequenceMatcher(None, intro, eerste, autojunk=False).quick_ratio() > 0.8 and         difflib.SequenceMatcher(None, intro, eerste, autojunk=False).ratio() > 0.6


def lees_perikopen():
    with open(DATA / 'pericopen.json', encoding='utf-8') as fh:
        ruw = json.load(fh)
    return {boek: {(p['c'], p['v']): p['t'] for p in lijst} for boek, lijst in ruw.items()}


def inleiding_alineas(tekst):
    """Maak leesbare alinea's op zinsgrenzen, zonder de woorden te wijzigen."""
    expliciet = [spaties(x) for x in re.split(r'\n\s*\n|</p>\s*<p[^>]*>', tekst) if spaties(x)]
    if len(expliciet) > 1:
        return expliciet
    zinnen = re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ])', spaties(tekst))
    alineas, lopend = [], ''
    for zin in zinnen:
        lopend = (lopend + ' ' + zin).strip()
        if len(lopend) >= 430:
            alineas.append(lopend)
            lopend = ''
    if lopend:
        if alineas and len(lopend) < 150:
            alineas[-1] += ' ' + lopend
        else:
            alineas.append(lopend)
    return alineas


def zet_boek(b, boek, namen, perikopen, stats, hoofdstukfilter=None, recto=True):
    """Zet één boek: titel, inhoud van het boek over de volle breedte, daarna de kolommen."""
    pdf, st, zetter = b.pdf, b.st, b.zetter
    meta, hoofdstukken = laad_boek(boek)
    if hoofdstukfilter:
        hoofdstukken = [h for h in hoofdstukken if int(h['number']) in hoofdstukfilter]

    if recto and len(pdf.paginas) % 2 == 1:
        pdf.pagina('')
    pagina_start = len(pdf.paginas) + 1
    boven_t, tussen_t, groot_t = TITELS[boek]
    naam = namen[boek]
    pdf.bladwijzers.append((naam, pagina_start - 1, 0))

    # Volle breedte: de titel en de inhoud van het boek.
    bovenaan, y = [], HOOGTE - BOVEN - 12.0
    x0 = b.linkerrand(pagina_start)

    def gecentreerd(tekst, stijl, stap, x=x0):
        nonlocal y
        r = zetter.los([(tekst, stijl)])
        y -= stap
        teken_regel(r, x + (ZETBREEDTE - r.breedte) / 2, y, bovenaan)

    gecentreerd(boven_t.upper(), st['boek_boven'], 16)
    if tussen_t:
        gecentreerd(tussen_t.upper(), st['boek_tussen'], 22)
    gecentreerd(groot_t.upper(), st['boek_groot'], 40)
    y -= 26

    intro = ((meta.get('bookIntro') or {}).get('text2026') or '').strip()
    if intro and is_kopie_van_hoofdstuk(intro, hoofdstukken):
        intro = ''
    extra_paginas = []
    if intro:
        gecentreerd('INHOUD VAN DIT BOEK', st['inhoud_kop'], 12)
        y -= 9
        alineas = inleiding_alineas(godsnaam(intro))
        intro = alineas[0]
        beginletter = zetter.los([(intro[0].upper(), st['intro_begin'])])
        d = beginletter.breedte + 2.5
        eerste_woord, rest = (intro[1:].split(' ', 1) + [''])[:2]
        regels = zetter.zet([(eerste_woord.lower(), st['intro_kk']), (' ' + rest, st['intro'])], ZETBREEDTE,
                            eerste=(ZETBREEDTE - d, ZETBREEDTE - d), verschuif=(d, d))
        for alinea in alineas[1:]:
            regels.append(None)
            regels.extend(zetter.zet([(alinea, st['intro'])], ZETBREEDTE, inspring=8.0))
        for nr, r in enumerate(regels):
            if r is None:
                y -= INTRO_REGEL * 0.7
                continue
            if y - INTRO_REGEL < ONDER:
                extra_paginas.append(bovenaan)
                bovenaan = []
                y = HOOGTE - BOVEN
                x0 = b.linkerrand(pagina_start + len(extra_paginas))
            y -= INTRO_REGEL
            teken_regel(r, x0, y, bovenaan)
            if nr == 1:
                teken_regel(beginletter, x0, y, bovenaan)
        y -= 14

    # Pagina's met alleen inleiding.
    for p, inhoud in enumerate(extra_paginas):
        uit = ['0 0 0 RG 0 0 0 rg\n']
        pag = len(pdf.paginas) + 1
        b.koptekst(uit, pag, '' if p == 0 else naam.upper())
        uit.extend(inhoud)
        pdf.pagina(''.join(uit))

    # Te weinig ruimte over: de kolommen beginnen op de volgende bladzijde.
    bovenruimte = HOOGTE - BOVEN - y
    voorop = bovenaan
    if ZETHOOGTE - bovenruimte < 110:
        uit = ['0 0 0 RG 0 0 0 rg\n']
        b.koptekst(uit, len(pdf.paginas) + 1, '' if not extra_paginas else naam.upper())
        uit.extend(bovenaan)
        pdf.pagina(''.join(uit))
        bovenruimte, voorop = 0.0, None

    # Tekst en kanttekeningen zetten.
    items, noten = [], []
    per = perikopen.get(boek, {})
    def kopregel(hst, heeft_voorop):
        if heeft_voorop and not extra_paginas:
            return ''
        if not hst:
            return naam.upper()
        lo, hi = min(hst), max(hst)
        if boek == 'psalmen':
            return f'PSALM {lo}' if lo == hi else f'PSALM {lo}–{hi}'
        if len(hoofdstukken) == 1 and meta.get('chapters') and len(meta['chapters']) == 1:
            return naam.upper()
        return f'{naam.upper()} {romeins(lo)}' if lo == hi else f'{naam.upper()} {romeins(lo)}–{romeins(hi)}'

    b.hoofdstuk_op = []
    for h in hoofdstukken:
        geillustreerd = getattr(b, 'heeft_illustraties', lambda *args: False)(boek, int(h['number']))
        if geillustreerd and items:
            b.vul(items, noten, kopregel, bovenruimte, voorop)
            items, noten = [], []
            bovenruimte, voorop = 0.0, None
        zet_hoofdstuk(zetter, st, boek, h, per, items, noten, stats)
        if geillustreerd:
            b.vul_geillustreerd(boek, int(h['number']), naam, items, noten, kopregel, voorop)
            items, noten = [], []
            bovenruimte, voorop = 0.0, None
    if items:
        b.vul(items, noten, kopregel, bovenruimte, voorop)
    seen = set()
    for nummer, p in b.hoofdstuk_op:
        if nummer not in seen:
            seen.add(nummer)
            label = f'Psalm {nummer}' if boek == 'psalmen' else f'Hoofdstuk {nummer}'
            pdf.bladwijzers.append((label, p, 1))
    return pagina_start


# ---------------------------------------------------------------- voorwerk

def titelpagina(b, deel):
    """Rustig titelblad, optisch gecentreerd op de pagina, voor alle drie delen."""
    from copy import copy
    st = {naam: copy(stijl) for naam, stijl in b.st.items()}
    licht = (0.94, 0.91, 0.83)
    for stijl in st.values():
        stijl.kleur = licht
    zetter, pdf = b.zetter, b.pdf
    uit = [f'q 0.025 0.025 0.025 rg 0 0 {BREEDTE} {HOOGTE} re f Q\n']
    # Een vectorpatroon als blinddruk: zacht gebogen bladeren in een ruitrooster.
    uit.append(f'q 38 38 {BREEDTE - 76} {HOOGTE - 76} re W n '
               '0.075 0.070 0.057 RG 0.45 w\n')
    for cy in range(46, int(HOOGTE), 78):
        for cx in range(24, int(BREEDTE) + 78, 78):
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                uit.append(f'{cx} {cy} m '
                           f'{cx + dx * 23} {cy + dy * 2} '
                           f'{cx + dx * 28} {cy + dy * 19} '
                           f'{cx + dx * 31} {cy + dy * 31} c '
                           f'{cx + dx * 10} {cy + dy * 28} '
                           f'{cx + dx * 2} {cy + dy * 16} '
                           f'{cx} {cy} c S\n')
    uit.append('Q\n')
    # Dubbele goudlijn met kleine hoekruiten, ruim binnen de snijrand.
    uit.append(f'q 0.68 0.55 0.32 RG 0.68 0.55 0.32 rg '
               f'1.1 w 25 25 {BREEDTE - 50} {HOOGTE - 50} re S '
               f'0.35 w 33 33 {BREEDTE - 66} {HOOGTE - 66} re S\n')
    for x, y in ((33, 33), (BREEDTE - 33, 33),
                 (33, HOOGTE - 33), (BREEDTE - 33, HOOGTE - 33)):
        uit.append(f'{x} {y + 5} m {x + 5} {y} l '
                   f'{x} {y - 5} l {x - 5} {y} l h f\n')
    uit.append('Q\n')
    midden = BREEDTE / 2
    kop = st['t_groot'].letter
    klein = Stijl(kop, 13, spatie=1.8, afbreken=False, kleur=licht)
    titel = Stijl(kop, 60, spatie=0.6, afbreken=False, kleur=licht)
    ondertitel = Stijl(kop, 18, spatie=1.0, afbreken=False, kleur=licht)

    st['t_tekst'] = Stijl(st['t_tekst'].letter, 14.5, kleur=licht, afbreken=False)
    st['t_cursief'] = Stijl(st['t_cursief'].letter, 15, kleur=licht, afbreken=False)

    def regel(tekst, stijl, y):
        r = zetter.los([(tekst, stijl)])
        teken_regel(r, midden - r.breedte / 2, y, uit)

    def ornament(y):
        # Subtiele gouden haarlijnen en een kleine ruit op de zwarte omslag.
        uit.append(f'q 0.68 0.55 0.32 RG 0.68 0.55 0.32 rg 0.45 w '
                   f'{midden - 82} {y} m {midden - 12} {y} l S '
                   f'{midden + 12} {y} m {midden + 82} {y} l S '
                   f'{midden} {y + 3} m {midden + 3} {y} l '
                   f'{midden} {y - 3} l {midden - 3} {y} l h f Q\n')

    regel('OPEN VERTALING', klein, HOOGTE - 100)
    regel('Gods Woord', titel, HOOGTE - 228)
    regel('DE GEHELE HEILIGE SCHRIFT', ondertitel, HOOGTE - 266)
    ornament(HOOGTE - 301)
    regel('Met de herziene kanttekeningen', st['t_cursief'], HOOGTE - 341)
    regel('Een vrije herziening van de Statenvertaling', st['t_tekst'], HOOGTE - 389)
    regel('in hedendaags Nederlands', st['t_tekst'], HOOGTE - 413)

    regel('ÉÉN COMPLETE UITGAVE' if deel == 0 else f'DEEL {romeins(deel)}', klein, 263)
    # Deel III heeft een lange titel; geef de apocriefe boeken een eigen regel.
    titelregels = DELEN[deel]['titel'].replace(', met de ', '\nmet de ').split('\n')
    for i, tekst in enumerate(titelregels):
        regel(tekst, st['t_tekst'], 233 - i * 24)
    ornament(178)
    regel('openvertaling.nl', st['t_tekst'], 80)
    pdf.pagina(''.join(uit))


def colofon(b, deel, datum):
    st, zetter, pdf = b.st, b.zetter, b.pdf
    uit = ['0 0 0 RG 0 0 0 rg\n']
    x0, y = BUITEN, ONDER + 150
    teksten = [
        f'Open Vertaling met kanttekeningen: {DELEN[deel]["titel"]}.' if deel == 0 else f'Open Vertaling met kanttekeningen, deel {romeins(deel)}: {DELEN[deel]["titel"]}.',
        f'Deze PDF is opgebouwd op {datum} uit de tekst van openvertaling.nl.',
        '',
        'De tekst van de Open Vertaling en de herziene kanttekeningen vallen onder CC0 1.0 (publiek domein). '
        'U mag ze vrij gebruiken, kopiëren, drukken, bewerken en verspreiden, voor elk doel, zonder toestemming '
        'en zonder bronvermelding.',
        '',
        'Gezet in Source Serif 4, met Noto Serif Hebrew en EB Garamond voor het Hebreeuws en Grieks (SIL Open Font License).',
    ]
    for t in teksten:
        if not t:
            y -= 8
            continue
        for r in zetter.zet([(t, st['fm_klein'])], ZETBREEDTE * 0.72, uitvullen=False):
            y -= 12
            teken_regel(r, x0, y, uit)
    pdf.pagina(''.join(uit))


def alinea_bladzijden(b, koppen_teksten):
    """Doorlopende alinea's over de volle breedte, op zo veel bladzijden als nodig."""
    st, zetter, pdf = b.st, b.zetter, b.pdf
    uit, y = None, 0.0

    def nieuwe():
        nonlocal uit, y
        if uit is not None:
            pdf.pagina(''.join(uit))
        uit = ['0 0 0 RG 0 0 0 rg\n']
        b.koptekst(uit, len(pdf.paginas) + 1, '')
        y = HOOGTE - BOVEN - 6

    nieuwe()
    breedte = ZETBREEDTE * 0.86
    for t in koppen_teksten:
        x0 = b.linkerrand(len(pdf.paginas) + 1) + (ZETBREEDTE - breedte) / 2
        if t.startswith('§§'):
            r = zetter.los([(t[2:].upper(), st['fm_kop'])])
            y -= 20
            teken_regel(r, b.linkerrand(len(pdf.paginas) + 1) + (ZETBREEDTE - r.breedte) / 2, y, uit)
            y -= 30
            continue
        if t.startswith('§'):
            y -= 14
            r = zetter.los([(t[1:], st['fm_c'])])
            y -= 13
            teken_regel(r, x0, y, uit)
            y -= 7
            continue
        for r in zetter.zet([(t, st['fm'])], breedte):
            if y - 13.2 < ONDER:
                nieuwe()
                x0 = b.linkerrand(len(pdf.paginas) + 1) + (ZETBREEDTE - breedte) / 2
            y -= 13.2
            teken_regel(r, x0, y, uit)
        y -= 7
    pdf.pagina(''.join(uit))


def schriftlezing(b, namen):
    st, zetter, pdf = b.st, b.zetter, b.pdf
    uit = ['0 0 0 RG 0 0 0 rg\n']
    b.koptekst(uit, len(pdf.paginas) + 1, '')
    x0 = b.linkerrand(len(pdf.paginas) + 1)
    y = HOOGTE - BOVEN - 26
    r = zetter.los([('OVER HET LEZEN VAN DE SCHRIFT', st['fm_kop'])])
    teken_regel(r, x0 + (ZETBREEDTE - r.breedte) / 2, y, uit)
    y -= 46
    for boek, hst, verzen in SCHRIFTLEZING:
        with open(DATA / boek / f'{hst}.json', encoding='utf-8') as fh:
            data = json.load(fh)
        teksten = [re.sub(r'^[\u0590-\u05FF]+ \w+\. ', '', v['text2026']) for v in data['verses'] if v['number'] in verzen]
        plaats = f'{namen[boek]} {hst}:{verzen[0]}' + (f'-{verzen[-1]}' if len(verzen) > 1 else '')
        r = zetter.los([(plaats, st['t_tekst'])])
        teken_regel(r, x0 + (ZETBREEDTE - r.breedte) / 2, y, uit)
        y -= 14
        for r in zetter.zet([(godsnaam(spaties(' '.join(teksten))), st['fm_c'])], ZETBREEDTE * 0.86, uitvullen=False):
            teken_regel(r, x0 + (ZETBREEDTE - r.breedte) / 2, y, uit)
            y -= 13.2
        y -= 16
    pdf.pagina(''.join(uit))


def afkortingen(b):
    st, zetter, pdf = b.st, b.zetter, b.pdf
    uit = ['0 0 0 RG 0 0 0 rg\n']
    b.koptekst(uit, len(pdf.paginas) + 1, '')
    x0 = b.linkerrand(len(pdf.paginas) + 1) + 60
    y = ONDER + 25 + len(AFKORTINGEN) * 15
    r = zetter.los([('VERKLARING VAN ENIGE AFKORTINGEN', st['inhoud_kop'])])
    teken_regel(r, b.linkerrand(len(pdf.paginas) + 1) + (ZETBREEDTE - r.breedte) / 2, y + 30, uit)
    for kort, lang in AFKORTINGEN:
        teken_regel(zetter.los([(kort, st['fm'])]), x0, y, uit)
        teken_regel(zetter.los([(lang, st['fm'])]), x0 + 80, y, uit)
        y -= 15
    pdf.pagina(''.join(uit))


def inhoudsopgave(b, deel, inhoud, pagina_index):
    """Vervangt de lege bladzijde 3 zodra de paginanummers bekend zijn."""
    st, zetter, pdf = b.st, b.zetter, b.pdf
    uit = ['0 0 0 RG 0 0 0 rg\n']
    x0 = b.linkerrand(pagina_index + 1)
    y = HOOGTE - BOVEN - 16
    r = zetter.los([('INHOUD', st['fm_kop'])])
    teken_regel(r, x0 + (ZETBREEDTE - r.breedte) / 2, y, uit)
    y -= 40
    links = []
    regels = sum(1 + len(g[1]) for g in inhoud)
    per_kolom = math.ceil(regels / 2) if regels > 26 else regels
    breedte = (ZETBREEDTE - 26) / 2 if regels > 26 else ZETBREEDTE * 0.62
    x_kolom = x0 if regels > 26 else x0 + (ZETBREEDTE - breedte) / 2
    punt = st['fm'].letter.vorm('.', st['fm'].kenmerken)
    puntbreedte = st['fm'].maat(punt) + 2.4
    y_start, teller = y, 0
    for groep, boeken in inhoud:
        if groep:
            if teller:
                y -= 7
            r = zetter.los([(groep, st['fm_c'])])
            teken_regel(r, x_kolom, y, uit)
            y -= 15
            teller += 1
        for naam, pagina in boeken:
            if regels > 26 and teller >= per_kolom and x_kolom == x0:
                x_kolom, y = x0 + breedte + 26, y_start
            links_r = zetter.los([(naam, st['fm'])])
            rechts = zetter.los([(str(pagina), st['fm'])])
            teken_regel(links_r, x_kolom, y, uit)
            teken_regel(rechts, x_kolom + breedte - rechts.breedte, y, uit)
            ruimte = breedte - links_r.breedte - rechts.breedte - 10
            aantal = max(0, int(ruimte // puntbreedte))
            if aantal:
                punten = Regel([(Stijl(st['fm'].letter, st['fm'].corps, kenmerken=st['fm'].kenmerken, spatie=2.4),
                                 punt * aantal)], aantal * puntbreedte)
                teken_regel(punten, x_kolom + breedte - rechts.breedte - 5 - aantal * puntbreedte, y, uit)
            links.append(((x_kolom, y - 2, x_kolom + breedte, y + 9), pagina - 1))
            y -= 15
            teller += 1
    pdf.paginas[pagina_index] = (''.join(uit), links)


# ---------------------------------------------------------------- bouwen

def bouw_deel(deel, uit_map, datum, proef=None):
    fonts = lettertypes()
    st = stijlen(fonts)
    zetter = Zetter(terugval=(fonts['hebr'], fonts['grieks']))
    titel = f'Gods Woord — {DELEN[deel]["titel"]}' if deel == 0 else f'Open Vertaling met kanttekeningen, deel {romeins(deel)}: {DELEN[deel]["titel"]}'
    pdf = Pdf(BREEDTE, HOOGTE, titel, onderwerp='De Bijbel in de Open Vertaling met herziene kanttekeningen')
    b = Boekbouwer(pdf, st, zetter)
    stats = {'verzen': 0, 'noten': 0}
    with open(DATA / 'books-index.json', encoding='utf-8') as fh:
        namen = {x['id']: x['naam'] for x in json.load(fh)['boeken']}
    perikopen = lees_perikopen()

    titelpagina(b, deel)
    colofon(b, deel, datum)
    pdf.pagina('')  # plek voor de inhoudsopgave, bladzijde 3
    pdf.pagina('')
    pdf.bladwijzers.append(('Inhoud', 2, 0))
    pdf.bladwijzers.append(('Verantwoording', len(pdf.paginas), 0))
    alinea_bladzijden(b, ['§§Verantwoording'] + VERANTWOORDING)
    if len(pdf.paginas) % 2 == 1:
        pdf.pagina('')
    pdf.bladwijzers.append(('Over het lezen van de Schrift', len(pdf.paginas), 0))
    schriftlezing(b, namen)
    afkortingen(b)

    inhoud = []
    for groep, boeken in DELEN[deel]['groepen']:
        regels = []
        if groep and proef is None and boeken and boeken[0] == '3ezra':
            if len(pdf.paginas) % 2 == 1:
                pdf.pagina('')
            apocriefen_voorblad(b)
            pdf.bladwijzers.append(('De apocriefe boeken', len(pdf.paginas) - 1, 0))
        for boek in boeken:
            if proef and boek != proef[0]:
                continue
            pagina = zet_boek(b, boek, namen, perikopen, stats, proef[1] if proef else None)
            regels.append((namen[boek], pagina))
        inhoud.append((groep, regels))
    inhoudsopgave(b, deel, inhoud, 2)

    uit_map.mkdir(parents=True, exist_ok=True)
    pad = uit_map / UITVOERNAAM.format(deel)
    pdf.schrijf(pad, list(fonts.values()) + [])
    verslag = {'deel': deel, 'titel': DELEN[deel]['titel'], 'bestand': pad.name, 'paginas': len(pdf.paginas),
               'bytes': pad.stat().st_size, 'verzen': stats['verzen'], 'noten': stats['noten'],
               'boeken': [{'naam': n, 'pagina': p} for _, r in inhoud for n, p in r],
               'controle': b.controle, 'afwijkingen': b.afwijkingen, 'te_brede_alineas': zetter.te_breed,
               'onbekende_tekens': sorted(zetter.onbekend)}
    return verslag


def apocriefen_voorblad(b):
    st, zetter, pdf = b.st, b.zetter, b.pdf
    uit = ['0 0 0 RG 0 0 0 rg\n']
    x0 = b.linkerrand(len(pdf.paginas) + 1)
    y = HOOGTE - 280
    r = zetter.los([('DE APOCRIEFE BOEKEN', st['t_mid'])])
    teken_regel(r, x0 + (ZETBREEDTE - r.breedte) / 2, y, uit)
    y -= 40
    tekst = ('De Statenvertalers namen deze boeken op in een apart deel, met de waarschuwing dat zij niet tot de canon '
             'van de Heilige Schrift behoren. Bij deze boeken staan in deze uitgave geen kanttekeningen.')
    for r in zetter.zet([(tekst, st['t_cursief'])], ZETBREEDTE * 0.7, uitvullen=False):
        teken_regel(r, x0 + (ZETBREEDTE - r.breedte) / 2, y, uit)
        y -= 15
    pdf.pagina(''.join(uit))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deel', type=int, choices=[1, 2, 3], help='alleen dit deel')
    p.add_argument('--uit', type=Path, default=UITVOER)
    p.add_argument('--proef', help='alleen een boek en hoofdstukken, bv. genesis:1-3')
    p.add_argument('--datum', default=None)
    a = p.parse_args()
    maanden = ('januari februari maart april mei juni juli augustus september oktober november december').split()
    d = datetime.date.today()
    datum = a.datum or f'{d.day} {maanden[d.month - 1]} {d.year}'
    if a.proef:
        boek, _, bereik = a.proef.partition(':')
        lo, _, hi = bereik.partition('-')
        nummers = range(int(lo), int(hi or lo) + 1)
        deel = next(n for n, x in DELEN.items() for _, bs in x['groepen'] if boek in bs)
        print(json.dumps(bouw_deel(deel, a.uit, datum, (boek, set(nummers))), ensure_ascii=False, indent=1))
        return
    delen = [a.deel] if a.deel else [1, 2, 3]
    lettertypes()  # alvast de snitten maken, dan hoeven de processen niet te wachten
    with ProcessPoolExecutor(max_workers=len(delen)) as pool:
        verslagen = list(pool.map(bouw_deel, delen, [a.uit] * len(delen), [datum] * len(delen)))
    (a.uit / 'kanttekeningen-uitgave.json').write_text(
        json.dumps({'datum': datum, 'delen': verslagen}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(verslagen, ensure_ascii=False)[:2000])


if __name__ == '__main__':
    main()
