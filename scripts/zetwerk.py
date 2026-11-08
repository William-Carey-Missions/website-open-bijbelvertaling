#!/usr/bin/env python3
"""Kleine zetmachine voor de boekuitgaven: letters vormen, regels breken, PDF schrijven.

De uitgave met kanttekeningen heeft bijbeltekst in twee kolommen en daaronder,
op dezelfde bladzijde, noten in drie kolommen over de volle breedte. Geen van de
gangbare zetprogramma's kan die noten per bladzijde over de volle breedte
verdelen. Daarom meten we alles zelf: wat hier gemeten wordt, is precies wat er
in de PDF komt, zodat de bladzijde-opbouw en de controle achteraf kloppen.

Dit bestand weet niets van de Bijbel; dat staat in build_kanttekeningen_pdf.py.
"""
import io
from pathlib import Path
import os
import re
import tempfile
import unicodedata
import zlib
from pathlib import Path

import pyphen
import uharfbuzz as hb
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

_HEBR = r'[\u0590-\u05FF\uFB1D-\uFB4F]+'
HEBREEUWS = re.compile(_HEBR + r'(?:[\s\u05BE]+' + _HEBR + r')*')
ONEINDIG = 10 ** 9


def maak_instantie(bron, assen, naam, map_=None):
    """Zet een variabel lettertype om naar een vaste snit; de PDF kent alleen vaste snitten."""
    map_ = Path(map_ or os.path.join(tempfile.gettempdir(), 'ov-zetwerk-fonts'))
    map_.mkdir(parents=True, exist_ok=True)
    doel = map_ / f'{naam}.ttf'
    if not doel.exists():
        font = instancer.instantiateVariableFont(TTFont(bron), assen, inplace=False)
        tijdelijk = doel.with_suffix(f'.{os.getpid()}.tmp')
        font.save(tijdelijk)
        os.replace(tijdelijk, doel)
    return doel


class Lettertype:
    """Eén vaste snit: vormt tekst met HarfBuzz en onthoudt welke glyphs gebruikt zijn."""

    teller = 0

    def __init__(self, pad, naam):
        Lettertype.teller += 1
        self.pdfnaam = f'F{Lettertype.teller}'
        self.naam = naam
        self.pad = str(pad)
        self.ttf = TTFont(self.pad, lazy=True)
        self.upem = self.ttf['head'].unitsPerEm
        self.cmap = self.ttf.getBestCmap()
        self.hmtx = self.ttf['hmtx']
        self.glyphnamen = self.ttf.getGlyphOrder()
        with open(self.pad, 'rb') as fh:
            self.hbfont = hb.Font(hb.Face(fh.read()))
        self.vormen = {}
        self.tekst_bij = {}
        os2 = self.ttf['OS/2']
        self.kaphoogte = getattr(os2, 'sCapHeight', 0) / self.upem or 0.67
        self.xhoogte = getattr(os2, 'sxHeight', 0) / self.upem or 0.47

    def heeft(self, ch):
        return ord(ch) in self.cmap

    def vorm(self, tekst, kenmerken=(), rtl=False):
        sleutel = (tekst, kenmerken, rtl)
        gevonden = self.vormen.get(sleutel)
        if gevonden is not None:
            return gevonden
        buf = hb.Buffer()
        buf.add_str(tekst)
        if rtl:
            buf.direction, buf.script, buf.language = 'rtl', 'hebr', 'he'
        else:
            buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, dict(kenmerken))
        infos, posities = buf.glyph_infos, buf.glyph_positions
        clusters = sorted({i.cluster for i in infos})
        einde = {c: (clusters[n + 1] if n + 1 < len(clusters) else len(tekst)) for n, c in enumerate(clusters)}
        gezien = set()
        uit = []
        for info, pos in zip(infos, posities):
            gid = info.codepoint
            if info.cluster not in gezien:
                gezien.add(info.cluster)
                self.tekst_bij.setdefault(gid, tekst[info.cluster:einde[info.cluster]])
            else:
                self.tekst_bij.setdefault(gid, '')
            uit.append((gid, pos.x_advance, pos.x_offset, pos.y_offset))
        uit = tuple(uit)
        self.vormen[sleutel] = uit
        return uit


class Stijl:
    __slots__ = ('letter', 'corps', 'hoog', 'kenmerken', 'spatie', 'afbreken', 'rtl', 'kleur', 'schaal', 'spatiebreedte')

    def __init__(self, letter, corps, hoog=0.0, kenmerken=(), spatie=0.0, afbreken=True, rtl=False, kleur=(0, 0, 0)):
        self.letter, self.corps, self.hoog = letter, corps, hoog
        self.kenmerken, self.spatie, self.afbreken, self.rtl = tuple(kenmerken), spatie, afbreken, rtl
        self.kleur = kleur
        self.schaal = corps / letter.upem
        self.spatiebreedte = letter.vorm(' ', self.kenmerken)[0][1] * self.schaal + spatie

    def maat(self, vorm):
        return sum(g[1] for g in vorm) * self.schaal + self.spatie * len(vorm)


class Regel:
    """Een gezette regel: stukken (stijl, vorm) en losse ruimtes (None, breedte)."""
    __slots__ = ('stukken', 'breedte', 'x', 'noten')

    def __init__(self, stukken, breedte, x=0.0, noten=()):
        self.stukken, self.breedte, self.x, self.noten = stukken, breedte, x, noten


class Zetter:
    """Breekt alinea's in regels volgens Knuth en Plass, met Nederlandse afbreking."""

    def __init__(self, terugval=()):
        self.pyphen = pyphen.Pyphen(lang='nl_NL', left=2, right=3)
        self.afbreekcache = {}
        self.terugval = terugval
        self.te_breed = 0
        self.onbekend = set()

    def _stukken(self, tekst, stijl):
        """Een woord dat de hoofdletter niet heeft, gaat in zijn geheel naar een terugval-letter."""
        if all(ord(c) in stijl.letter.cmap or unicodedata.combining(c) for c in tekst):
            return [(tekst, stijl)]
        for andere in self.terugval:
            if all(andere.heeft(c) or unicodedata.combining(c) or not c.isalpha() for c in tekst):
                return [(tekst, Stijl(andere, stijl.corps, stijl.hoog, afbreken=False, kleur=stijl.kleur))]
        self.onbekend.update(c for c in tekst if not any(a.heeft(c) for a in self.terugval))
        return [(tekst, stijl)]

    def _breekpunten(self, woord):
        gevonden = self.afbreekcache.get(woord)
        if gevonden is None:
            gevonden = tuple(self.pyphen.positions(woord)) if len(woord) >= 6 and woord.isalpha() else ()
            self.afbreekcache[woord] = gevonden
        return gevonden

    def _woord(self, delen, uit):
        """Eén woord (een of meer stijlen, bv. nootcijfer + woord) wordt dozen met afbreekpunten."""
        for tekst, stijl, noot in delen:
            if noot is not None:
                uit.append((0, 0.0, 0, 0, 0, False, ('noot', noot)))
            if not tekst:
                continue
            if stijl.rtl:
                vorm = stijl.letter.vorm(tekst, stijl.kenmerken, True)
                uit.append((0, stijl.maat(vorm), 0, 0, 0, False, (stijl, vorm)))
                continue
            for stuk, st in self._stukken(tekst, stijl):
                # Een streepje in het woord is een natuurlijk breekpunt.
                for n, deel in enumerate(re.split(r'(?<=[-–—])(?=\w)', stuk)):
                    if n:
                        uit.append((2, 0.0, 0, 0, 40, True, None))
                    punten = self._breekpunten(deel) if st.afbreken else ()
                    vorige = 0
                    for p in punten:
                        vorm = st.letter.vorm(deel[vorige:p], st.kenmerken)
                        uit.append((0, st.maat(vorm), 0, 0, 0, False, (st, vorm)))
                        streep = st.letter.vorm('-', st.kenmerken)
                        uit.append((2, st.maat(streep), 0, 0, 60, True, (st, streep)))
                        vorige = p
                    vorm = st.letter.vorm(deel[vorige:], st.kenmerken)
                    uit.append((0, st.maat(vorm), 0, 0, 0, False, (st, vorm)))

    def items(self, segmenten, inspring=0.0):
        """segmenten: (tekst, stijl) of (tekst, stijl, noot_id). Noot-id's blijven aan hun regel hangen."""
        uit = []
        if inspring:
            uit.append((0, inspring, 0, 0, 0, False, (None, inspring)))
        delen = []

        def sluit():
            if delen:
                self._woord(delen, uit)
                delen.clear()

        for seg in segmenten:
            tekst, stijl = seg[0], seg[1]
            noot = seg[2] if len(seg) > 2 else None
            if noot is not None and not tekst:
                delen.append(('', stijl, noot))
                continue
            for t, st in self._hebreeuws(tekst, stijl):
                if st.rtl:
                    delen.append((t, st, noot))
                    noot = None
                    continue
                for m, stuk in enumerate(re.split(r'( +)', t)):
                    if m % 2:
                        sluit()
                        s = stijl.spatiebreedte
                        uit.append((1, s, s * 0.55, s * 0.28, 0, False, stijl))
                    elif stuk:
                        delen.append((stuk, st, noot))
                        noot = None
            if noot is not None:
                delen.append(('', stijl, noot))
        sluit()
        return uit

    def _hebreeuws(self, tekst, stijl):
        if not HEBREEUWS.search(tekst):
            return [(tekst, stijl)]
        uit, pos = [], 0
        heb = self.terugval[0]
        for m in HEBREEUWS.finditer(tekst):
            if m.start() > pos:
                uit.append((tekst[pos:m.start()], stijl))
            uit.append((m.group(0), Stijl(heb, stijl.corps, stijl.hoog, afbreken=False, rtl=True, kleur=stijl.kleur)))
            pos = m.end()
        if pos < len(tekst):
            uit.append((tekst[pos:], stijl))
        return uit

    def breek(self, items, breedte, eerste=(), tolerantie=2.2):
        """Beste breekpunten van een alinea. eerste: afwijkende breedte van de eerste regels."""
        n = len(items)
        for tol in (tolerantie, 4.0, 12.0, 100.0):
            resultaat = self._knuth_plass(items, n, breedte, eerste, tol)
            if resultaat is not None:
                return resultaat
        self.te_breed += 1
        return self._eerste_past(items, n, breedte, eerste)

    @staticmethod
    def _knuth_plass(items, n, breedte, eerste, tol):
        W = Y = Z = 0.0
        # actief: [positie, regelnummer, W, Y, Z, demerits, vorige, klasse]
        actief = [[0, 0, 0.0, 0.0, 0.0, 0.0, None, 1]]
        vorige_doos = False
        lengte_eerste = len(eerste)
        for b in range(n + 1):
            if b == n:
                # Einde alinea: de laatste regel mag kort blijven.
                it = (2, 0.0, 0, 0, -ONEINDIG, False, None)
                wettig = True
                extra_rek = ONEINDIG
            else:
                it = items[b]
                extra_rek = 0
                if it[0] == 0:
                    W += it[1]
                    vorige_doos = True
                    continue
                if it[0] == 1:
                    wettig = vorige_doos
                else:
                    wettig = True
            if wettig:
                nieuw = {}
                pw = it[1] if it[0] == 2 else 0.0
                behoud = []
                for a in actief:
                    regel = a[1]
                    doel = eerste[regel] if regel < lengte_eerste else breedte
                    L = W - a[2] + pw
                    if L < doel:
                        rek = Y - a[3] + extra_rek
                        r = (doel - L) / rek if rek > 0 else ONEINDIG
                    elif L > doel:
                        krimp = Z - a[4]
                        r = (doel - L) / krimp if krimp > 0 else -ONEINDIG
                    else:
                        r = 0.0
                    if r >= -1 and it[4] > -ONEINDIG:
                        behoud.append(a)
                    if -1 <= r <= tol:
                        slecht = 100 * abs(r) ** 3
                        d = (1 + slecht + max(it[4], 0)) ** 2
                        if it[5] and a[0] and items[a[0]][5]:
                            d += 3000  # geen twee afbrekingen onder elkaar
                        klasse = 0 if r < -0.5 else 1 if r <= 0.5 else 2 if r <= 1 else 3
                        if abs(klasse - a[7]) > 1:
                            d += 2000
                        d += a[5]
                        sleutel = (regel + 1 if regel + 1 < lengte_eerste else -1, klasse)
                        best = nieuw.get(sleutel)
                        if best is None or d < best[0]:
                            nieuw[sleutel] = (d, a, klasse)
                actief = behoud
                if nieuw:
                    # Na een breekpunt vervallen spaties tot de volgende doos.
                    w2, y2, z2 = W, Y, Z
                    p = b
                    while p < n:
                        x = items[p]
                        if x[0] == 0:
                            break
                        if x[0] == 1:
                            w2 += x[1]
                            y2 += x[2]
                            z2 += x[3]
                        elif x[4] <= -ONEINDIG and p > b:
                            break
                        p += 1
                    for d, a, klasse in nieuw.values():
                        actief.append([b, a[1] + 1, w2, y2, z2, d, a, klasse])
                elif not actief:
                    return None
            if b < n and it[0] == 1:
                W += it[1]
                Y += it[2]
                Z += it[3]
            vorige_doos = False
        eindes = [a for a in actief if a[0] == n]
        if not eindes:
            return None
        beste = min(eindes, key=lambda a: a[5])
        punten = []
        while beste is not None and beste[6] is not None:
            punten.append(beste[0])
            beste = beste[6]
        punten.reverse()
        return punten

    @staticmethod
    def _eerste_past(items, n, breedte, eerste):
        punten, regel, w = [], 0, 0.0
        for b, it in enumerate(items):
            doel = eerste[regel] if regel < len(eerste) else breedte
            if it[0] == 0 and w + it[1] > doel and w > 0:
                punten.append(b)
                regel += 1
                w = 0.0
            if it[0] != 2:
                w += it[1]
        punten.append(n)
        return punten

    def zet(self, segmenten, breedte, inspring=0.0, eerste=(), verschuif=(), uitvullen=True):
        """Zet een alinea en geeft de regels. verschuif: x van de eerste regels (beginletter)."""
        items = self.items(segmenten, inspring)
        if not items:
            return []
        punten = self.breek(items, breedte, eerste)
        regels, begin = [], 0
        for r, b in enumerate(punten):
            laatste = r == len(punten) - 1
            doel = eerste[r] if r < len(eerste) else breedte
            regels.append(self._bouw_regel(items, begin, b, doel, not laatste and uitvullen,
                                            verschuif[r] if r < len(verschuif) else 0.0))
            begin = b
            while begin < len(items) and items[begin][0] != 0:
                begin += 1
            # Een afbreekstreep hoort bij de vorige regel; de volgende begint met de doos.
        return regels

    @staticmethod
    def _bouw_regel(items, begin, eind, doel, uitvullen, x):
        w = y = z = 0.0
        stuk = items[begin:eind]
        while stuk and stuk[-1][0] != 0:
            stuk.pop()
        for it in stuk:
            if it[0] == 0:
                w += it[1]
            elif it[0] == 1:
                w += it[1]
                y += it[2]
                z += it[3]
        streep = items[eind] if eind < len(items) and items[eind][0] == 2 and items[eind][6] else None
        if streep:
            w += streep[1]
        verhouding = 0.0
        if uitvullen:
            if w < doel and y > 0:
                verhouding = (doel - w) / y
            elif w > doel and z > 0:
                verhouding = max((doel - w) / z, -1.0)
        elif doel and w > doel and z > 0:
            # Een laatste regel die alleen past door de spaties in te knijpen.
            verhouding = max((doel - w) / z, -1.0)
        stukken, noten = [], []
        for it in stuk:
            if it[0] == 0:
                p = it[6]
                if p[0] == 'noot':
                    noten.append(p[1])
                elif p[0] is None:
                    stukken.append((None, it[1]))
                else:
                    stukken.append(p)
            elif it[0] == 1:
                breedte = it[1] + (it[2] * verhouding if verhouding >= 0 else it[3] * verhouding)
                stukken.append((it[6], breedte))
        if streep:
            stukken.append(streep[6])
        breedte = doel if uitvullen else min(w, doel) if doel else w
        return Regel(stukken, breedte, x, noten)

    def los(self, segmenten):
        """Eén onafgebroken regel, bv. een titel; breedte is de natuurlijke breedte."""
        items = self.items(segmenten)
        return self._bouw_regel(items, 0, len(items), 0, False, 0.0)


# ---------------------------------------------------------------- PDF

def _getal(x):
    return f'{x:.2f}'.rstrip('0').rstrip('.') or '0'


def teken_regel(regel, x, y, uit):
    """Schrijft de operatoren voor één regel; de echte spatie-glyph blijft staan voor zoeken en kopiëren."""
    delen = [f'BT 1 0 0 1 {_getal(x + regel.x)} {_getal(y)} Tm ']
    huidig = None
    tj = []

    def sluit_tj():
        if tj:
            delen.append('[' + ''.join(tj) + ']TJ ')
            tj.clear()

    def zet_stijl(st):
        nonlocal huidig
        if huidig is not st:
            sluit_tj()
            if huidig is None or huidig.letter is not st.letter or huidig.corps != st.corps:
                delen.append(f'/{st.letter.pdfnaam} {_getal(st.corps)} Tf ')
            if huidig is None or huidig.hoog != st.hoog:
                delen.append(f'{_getal(st.hoog)} Ts ')
            if huidig is None or huidig.kleur != st.kleur:
                delen.append(' '.join(_getal(c) for c in st.kleur) + ' rg ')
            huidig = st

    for st, inhoud in regel.stukken:
        if st is None:
            # Vaste ruimte zonder glyph (inspringing).
            if huidig is not None:
                tj.append(f'{-inhoud / huidig.corps * 1000:.1f}')
            else:
                delen[0] = f'BT 1 0 0 1 {_getal(x + regel.x + inhoud)} {_getal(y)} Tm '
            continue
        if isinstance(inhoud, float):
            # Spatie: de spatie-glyph met zo veel correctie dat de breedte klopt.
            zet_stijl(st)
            letter = st.letter
            vorm = letter.vorm(' ', st.kenmerken)[0]
            eigen = letter.hmtx[letter.glyphnamen[vorm[0]]][0] * st.schaal
            tj.append(f'<{vorm[0]:04X}>{(eigen - inhoud) / st.corps * 1000:.1f}')
            continue
        zet_stijl(st)
        letter = st.letter
        for gid, adv, xo, yo in inhoud:
            eigen = letter.hmtx[letter.glyphnamen[gid]][0]
            if xo or yo:
                sluit_tj()
                delen.append(f'[{-xo / letter.upem * 1000:.1f}]TJ {_getal(st.hoog + yo * st.schaal)} Ts ')
                delen.append(f'[<{gid:04X}>{(xo + eigen - adv) / letter.upem * 1000 - st.spatie / st.corps * 1000:.1f}]TJ {_getal(st.hoog)} Ts ')
                continue
            correctie = (eigen - adv) / letter.upem * 1000 - st.spatie / st.corps * 1000
            if abs(correctie) > 0.2:
                tj.append(f'<{gid:04X}>{correctie:.1f}')
            else:
                tj.append(f'<{gid:04X}>')
    sluit_tj()
    if huidig is not None and huidig.hoog:
        delen.append('0 Ts ')
    delen.append('ET\n')
    uit.append('q ' + ''.join(delen) + 'Q\n')


def lijn(x1, y1, x2, y2, dikte, uit):
    uit.append(f'{_getal(dikte)} w {_getal(x1)} {_getal(y1)} m {_getal(x2)} {_getal(y2)} l S\n')


class Pdf:
    def __init__(self, breedte, hoogte, titel, auteur='Open Vertaling', onderwerp=''):
        self.breedte, self.hoogte = breedte, hoogte
        self.titel, self.auteur, self.onderwerp = titel, auteur, onderwerp
        self.objecten = []
        self.paginas = []  # (inhoud, links)
        self.bladwijzers = []  # (titel, pagina-index, niveau)
        self.lettertypes = []
        self.afbeeldingen = {}

    def _nieuw(self, inhoud=None):
        self.objecten.append(inhoud)
        return len(self.objecten)

    def _stream(self, data, extra=''):
        z = zlib.compress(data, 9)
        return self._nieuw(f'<</Length {len(z)}/Filter/FlateDecode{extra}>>\nstream\n'.encode() + z + b'\nendstream')

    def pagina(self, inhoud, links=()):
        self.paginas.append((inhoud, list(links)))
        return len(self.paginas) - 1

    def afbeelding(self, pad, x, y, breedte, hoogte):
        """Plaats een volledige JPEG, zonder uitsnede of vervorming."""
        from PIL import Image
        sleutel = str(pad)
        if sleutel not in self.afbeeldingen:
            with Image.open(pad) as im:
                w, h = im.size
                if im.mode != 'RGB':
                    buffer = io.BytesIO()
                    im.convert('RGB').save(buffer, format='JPEG', quality=95)
                    data = buffer.getvalue()
                else:
                    data = Path(pad).read_bytes()
            naam = f'Im{len(self.afbeeldingen) + 1}'
            header = (f'<</Type/XObject/Subtype/Image/Width {w}/Height {h}'
                      f'/ColorSpace/DeviceRGB/BitsPerComponent 8/Filter/DCTDecode/Length {len(data)}>>\nstream\n').encode()
            obj = self._nieuw(header + data + b'\nendstream')
            self.afbeeldingen[sleutel] = (naam, obj)
        naam, _ = self.afbeeldingen[sleutel]
        return f'q {breedte:.3f} 0 0 {hoogte:.3f} {x:.3f} {y:.3f} cm /{naam} Do Q\n'

    def _lettertype(self, font):
        gebruikte = sorted(font.tekst_bij)
        opties = subset.Options()
        opties.retain_gids = True
        opties.hinting = False
        opties.layout_features = []
        opties.name_IDs = []
        opties.notdef_outline = True
        opties.drop_tables += ['GSUB', 'GPOS', 'GDEF', 'STAT', 'DSIG', 'MVAR', 'HVAR', 'avar', 'fvar', 'gvar']
        ttf = TTFont(font.pad)
        s = subset.Subsetter(opties)
        s.populate(gids=gebruikte)
        s.subset(ttf)
        buf = io.BytesIO()
        ttf.save(buf)
        data = buf.getvalue()
        bestand = self._stream(data, f'/Length1 {len(data)}')
        schaal = 1000 / font.upem
        post = font.ttf['post']
        head = font.ttf['head']
        hhea = font.ttf['hhea']
        naam = re.sub(r'[^A-Za-z0-9-]', '', font.naam)
        voorvoegsel = ''.join(chr(65 + (ord(c) + i) % 26) for i, c in enumerate((naam * 6)[:6]))
        basis = f'{voorvoegsel}+{naam}'
        beschrijving = self._nieuw((
            f'<</Type/FontDescriptor/FontName/{basis}/Flags 6'
            f'/FontBBox[{int(head.xMin * schaal)} {int(head.yMin * schaal)} {int(head.xMax * schaal)} {int(head.yMax * schaal)}]'
            f'/ItalicAngle {post.italicAngle}/Ascent {int(hhea.ascent * schaal)}/Descent {int(hhea.descent * schaal)}'
            f'/CapHeight {int(font.kaphoogte * 1000)}/StemV 80/FontFile2 {bestand} 0 R>>').encode())
        breedtes = ' '.join(f'{g}[{font.hmtx[font.glyphnamen[g]][0] * schaal:.1f}]' for g in gebruikte)
        cid = self._nieuw((
            f'<</Type/Font/Subtype/CIDFontType2/BaseFont/{basis}'
            f'/CIDSystemInfo<</Registry(Adobe)/Ordering(Identity)/Supplement 0>>'
            f'/FontDescriptor {beschrijving} 0 R/W[{breedtes}]/DW 1000/CIDToGIDMap/Identity>>').encode())
        tounicode = self._stream(self._tounicode(font).encode('ascii'))
        return self._nieuw((
            f'<</Type/Font/Subtype/Type0/BaseFont/{basis}/Encoding/Identity-H'
            f'/DescendantFonts[{cid} 0 R]/ToUnicode {tounicode} 0 R>>').encode())

    @staticmethod
    def _tounicode(font):
        regels = ['/CIDInit /ProcSet findresource begin 12 dict begin begincmap',
                  '/CIDSystemInfo <</Registry (Adobe)/Ordering (UCS)/Supplement 0>> def',
                  '/CMapName /Adobe-Identity-UCS def /CMapType 2 def',
                  '1 begincodespacerange <0000> <FFFF> endcodespacerange']
        # Glyphs zonder eigen teken (tweede deel van een cluster) krijgen een onzichtbaar teken,
        # anders verzint een PDF-lezer er bij kopiëren zelf iets bij.
        paren = [(g, t or chr(0x200B)) for g, t in sorted(font.tekst_bij.items())]
        for i in range(0, len(paren), 100):
            blok = paren[i:i + 100]
            regels.append(f'{len(blok)} beginbfchar')
            for g, t in blok:
                regels.append(f'<{g:04X}> <{t.encode("utf-16-be").hex().upper()}>')
            regels.append('endbfchar')
        regels += ['endcmap', 'CMapName currentdict /CMap defineresource pop end end']
        return '\n'.join(regels)

    def schrijf(self, pad, lettertypes):
        fontdict = ''.join(f'/{f.pdfnaam} {self._lettertype(f)} 0 R' for f in lettertypes if f.tekst_bij)
        beelden = ''.join(f'/{naam} {obj} 0 R' for naam, obj in self.afbeeldingen.values())
        bronnen = self._nieuw(f'<</Font<<{fontdict}>>/XObject<<{beelden}>>>>'.encode())
        paginaboom = self._nieuw(None)
        pagina_ids = []
        for inhoud, links in self.paginas:
            stream = self._stream(inhoud.encode('ascii'))
            annots = ''
            if links:
                onderdelen = []
                for rect, doel in links:
                    recttekst = ' '.join(_getal(v) for v in rect)
                    actie = (f'/A<</S/URI/URI {self._pdf_tekst(doel)}>>' if isinstance(doel, str)
                             else f'/Dest[@{doel}@ /Fit]')
                    onderdelen.append(self._nieuw(
                        f'<</Type/Annot/Subtype/Link/Border[0 0 0]/Rect[{recttekst}]{actie}>>'.encode()))
                annots = '/Annots[' + ' '.join(f'{o} 0 R' for o in onderdelen) + ']'
            pagina_ids.append(self._nieuw(
                f'<</Type/Page/Parent {paginaboom} 0 R/MediaBox[0 0 {_getal(self.breedte)} {_getal(self.hoogte)}]'
                f'/Contents {stream} 0 R/Resources {bronnen} 0 R{annots}>>'.encode()))
        # Verwijzingen naar pagina's kunnen pas na het nummeren worden ingevuld.
        for i, obj in enumerate(self.objecten):
            if obj and b'/Subtype/Link' in obj[:60]:
                self.objecten[i] = re.sub(rb'@(\d+)@', lambda m: f'{pagina_ids[int(m.group(1))]} 0 R'.encode(), obj)
        self.objecten[paginaboom - 1] = (
            f'<</Type/Pages/Count {len(pagina_ids)}/Kids[' + ' '.join(f'{p} 0 R' for p in pagina_ids) + ']>>').encode()
        catalogus = f'<</Type/Catalog/Pages {paginaboom} 0 R/Lang(nl-NL)/ViewerPreferences<</DisplayDocTitle true>>'
        wijzers = self._bladwijzers(pagina_ids)
        if wijzers:
            catalogus += f'/Outlines {wijzers} 0 R/PageMode/UseOutlines'
        catalogus_id = self._nieuw((catalogus + '>>').encode())
        info = self._nieuw(
            f'<</Title {self._pdf_tekst(self.titel)}/Author {self._pdf_tekst(self.auteur)}'
            f'/Subject {self._pdf_tekst(self.onderwerp)}/Producer (scripts/zetwerk.py)>>'.encode())
        tijdelijk = str(pad) + '.tmp'
        with open(tijdelijk, 'wb') as fh:
            fh.write(b'%PDF-1.6\n%\xe2\xe3\xcf\xd3\n')
            posities = []
            for n, obj in enumerate(self.objecten, 1):
                posities.append(fh.tell())
                fh.write(f'{n} 0 obj\n'.encode() + obj + b'\nendobj\n')
            xref = fh.tell()
            fh.write(f'xref\n0 {len(posities) + 1}\n0000000000 65535 f \n'.encode())
            for p in posities:
                fh.write(f'{p:010d} 00000 n \n'.encode())
            fh.write(f'trailer\n<</Size {len(posities) + 1}/Root {catalogus_id} 0 R/Info {info} 0 R>>\nstartxref\n{xref}\n%%EOF\n'.encode())
        os.replace(tijdelijk, pad)

    @staticmethod
    def _pdf_tekst(tekst):
        return '<FEFF' + tekst.encode('utf-16-be').hex().upper() + '>'

    def _bladwijzers(self, pagina_ids):
        if not self.bladwijzers:
            return None
        wortel = self._nieuw(None)
        knopen = [{'titel': t, 'pagina': p, 'niveau': n, 'kinderen': []} for t, p, n in self.bladwijzers]
        boom = {'kinderen': [], 'niveau': -1}
        stapel = [boom]
        for k in knopen:
            while stapel[-1]['niveau'] >= k['niveau']:
                stapel.pop()
            stapel[-1]['kinderen'].append(k)
            stapel.append(k)
        for k in knopen:
            k['id'] = self._nieuw(None)

        def vul(ouder_id, kinderen):
            for i, k in enumerate(kinderen):
                d = f'<</Title {self._pdf_tekst(k["titel"])}/Parent {ouder_id} 0 R/Dest[{pagina_ids[k["pagina"]]} 0 R /Fit]'
                if i:
                    d += f'/Prev {kinderen[i - 1]["id"]} 0 R'
                if i + 1 < len(kinderen):
                    d += f'/Next {kinderen[i + 1]["id"]} 0 R'
                if k['kinderen']:
                    d += f'/First {k["kinderen"][0]["id"]} 0 R/Last {k["kinderen"][-1]["id"]} 0 R/Count -{len(k["kinderen"])}'
                self.objecten[k['id'] - 1] = (d + '>>').encode()
                vul(k['id'], k['kinderen'])

        vul(wortel, boom['kinderen'])
        kids = boom['kinderen']
        self.objecten[wortel - 1] = (
            f'<</Type/Outlines/First {kids[0]["id"]} 0 R/Last {kids[-1]["id"]} 0 R/Count {len(kids)}>>').encode()
        return wortel
