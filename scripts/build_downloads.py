#!/usr/bin/env python3
"""Bouwt de downloadbestanden voor de site.

Levert in downloads/:
  open-vertaling-brondata.zip    de complete data-map, ongefilterd
  open-vertaling-nagekeken.epub  alleen nagekeken hoofdstukken, verstekst
  index.json                     naam, omvang en datum per uitgave

Draait tijdens de deploy, na export_review_status.py en build_stats.py,
zodat de uitgaven altijd gelijk lopen met de tekst en er geen binaire
bestanden in git komen.

Gebruik:  python scripts/build_downloads.py [--datum "4 augustus 2026"]
"""
import json, os, re, sys, zipfile, html, datetime
from contextlib import contextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UIT = os.path.join(ROOT, "downloads")
SITE = "https://openvertaling.nl"

ZIP_NAAM = "open-vertaling-brondata.zip"
EPUB_NAAM = "open-vertaling-nagekeken.epub"


@contextmanager
def atomic_output(path):
    """A live release URL must never serve a partly written archive or index."""
    temporary = path + ".tmp"
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def lees(pad, standaard=None):
    try:
        with open(pad, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return standaard


def nagekeken_hoofdstukken(verified, boek_id, totaal):
    """Welke hoofdstukken van dit boek zijn nagekeken? Lege lijst = geen."""
    return sorted(verified.get(boek_id, []))


def verstekst(vers):
    """Platte, EPUB-veilige tekst van een vers.

    text2026_html bevat site-eigen opmaak (kanttekening-markers, Strong's,
    geo-markering). Die hoort niet in een leesuitgave, dus we strippen alles
    en houden de kale zin over.
    """
    ruw = vers.get("text2026_html") or vers.get("text2026") or vers.get("textHerzien") or ""
    ruw = re.sub(r"<sup[^>]*>.*?</sup>", "", ruw)      # kanttekening-markers
    ruw = re.sub(r"<[^>]+>", "", ruw)                   # overige opmaak
    ruw = ruw.replace("God JAHWEH", "de HEERE God")
    ruw = re.sub(r"\bJAHWEH\b", "de HEERE", ruw)
    ruw = re.sub(r"\bde de HEERE\b", "de HEERE", ruw)
    return re.sub(r"\s+", " ", ruw).strip()


# ---------------------------------------------------------------- brondata
def bouw_zip():
    pad = os.path.join(UIT, ZIP_NAAM)
    with atomic_output(pad) as temporary, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for wortel, _dirs, bestanden in os.walk(DATA):
            for f in sorted(bestanden):
                vol = os.path.join(wortel, f)
                z.write(vol, os.path.relpath(vol, ROOT))
    return pad


# -------------------------------------------------------------------- epub
def xml(s):
    return html.escape(s, quote=True)


def bouw_epub(boeken, verified, stats):
    pad = os.path.join(UIT, EPUB_NAAM)
    versie = stats.get("version", "")
    datum = stats.get("date", "")

    hoofdstukken = []          # (boek, [(nr, [verzen])])
    n_boeken = n_hfdst = n_verzen = 0

    for boek in boeken:
        bid, naam = boek["id"], boek["nameDutch"]
        nrs = nagekeken_hoofdstukken(verified, bid, boek.get("totalChapters", 0))
        if not nrs:
            continue
        inhoud = []
        for nr in nrs:
            doc = lees(os.path.join(DATA, bid, f"{nr}.json"))
            if not doc:
                continue
            verzen = [(v.get("number"), verstekst(v)) for v in doc.get("verses") or []]
            verzen = [(n, t) for n, t in verzen if t]
            if verzen:
                inhoud.append((nr, verzen))
                n_verzen += len(verzen)
        if inhoud:
            hoofdstukken.append((boek, inhoud))
            n_boeken += 1
            n_hfdst += len(inhoud)

    # --- documenten opbouwen
    docs = []                  # (bestandsnaam, xhtml)
    for boek, inhoud in hoofdstukken:
        volledig = nagekeken_hoofdstukken(verified, boek["id"], boek.get("totalChapters", 0))
        deels = len(volledig) < boek.get("totalChapters", 0)
        delen = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<!DOCTYPE html>',
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="nl" lang="nl"><head>',
            f'<title>{xml(boek["nameDutch"])}</title>',
            '<link rel="stylesheet" type="text/css" href="stijl.css"/>',
            '</head><body>',
            f'<h1>{xml(boek["nameDutch"])}</h1>',
        ]
        if deels:
            reeks = ", ".join(str(n) for n in volledig[:3]) + ("…" if len(volledig) > 3 else "")
            delen.append(f'<p class="deels">Van dit boek zijn alleen de nagekeken '
                         f'hoofdstukken opgenomen ({reeks}).</p>')
        for nr, verzen in inhoud:
            delen.append(f'<h2 id="h{nr}">{xml(boek["nameDutch"])} {nr}</h2>')
            for vnr, tekst in verzen:
                delen.append(f'<p class="v"><span class="n">{vnr}</span> {xml(tekst)}</p>')
        delen.append("</body></html>")
        docs.append((f'{boek["id"]}.xhtml', "\n".join(delen)))

    colofon = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="nl" lang="nl"><head>
<title>Colofon</title><link rel="stylesheet" type="text/css" href="stijl.css"/>
</head><body>
<h1>Open Vertaling</h1>
<p>Een vrije, leesbare herziening van de Statenvertaling (1637/1888) in
hedendaags Nederlands.</p>
<h2>Wat er in deze uitgave staat</h2>
<p>Alleen hoofdstukken die vers voor vers zijn nagekeken. De vertaling is nog
in bewerking; deze uitgave groeit mee naarmate er meer wordt nagekeken. Van
boeken die nog niet af zijn, zijn alleen de nagekeken hoofdstukken opgenomen.</p>
<p>Deze uitgave bevat {n_boeken} boeken, {n_hfdst} hoofdstukken en {n_verzen} verzen.</p>
<h2>Versie</h2>
<p>{xml(versie)} — {xml(datum)}</p>
<h2>Rechten</h2>
<p>CC0 / publiek domein. U mag deze tekst vrij gebruiken, kopiëren, bewerken
en verspreiden, voor elk doel, zonder toestemming of bronvermelding.</p>
<h2>Herkomst</h2>
<p>De volledige tekst, met grondtekst, kanttekeningen en verantwoording, staat
op <a href="{SITE}/">{SITE}</a>.</p>
</body></html>"""

    nav_items = "\n".join(
        f'<li><a href="{b["id"]}.xhtml">{xml(b["nameDutch"])}</a><ol>' +
        "".join(f'<li><a href="{b["id"]}.xhtml#h{nr}">{nr}</a></li>' for nr, _ in inh) +
        "</ol></li>"
        for b, inh in hoofdstukken)
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="nl" lang="nl"><head><title>Inhoud</title></head><body>
<nav epub:type="toc" id="toc"><h1>Inhoud</h1><ol>
<li><a href="colofon.xhtml">Colofon</a></li>
{nav_items}
</ol></nav></body></html>"""

    manifest = "\n".join(
        f'<item id="{b["id"]}" href="{b["id"]}.xhtml" media-type="application/xhtml+xml"/>'
        for b, _ in hoofdstukken)
    spine = "\n".join(f'<itemref idref="{b["id"]}"/>' for b, _ in hoofdstukken)
    ident = f"urn:openvertaling:nagekeken:{versie or 'onbekend'}"
    vandaag = datetime.date.today().isoformat()

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{xml(ident)}</dc:identifier>
<dc:title>Open Vertaling — nagekeken tekst</dc:title>
<dc:language>nl</dc:language>
<dc:creator>Open Vertaling — de kleine ark</dc:creator>
<dc:rights>CC0 / publiek domein</dc:rights>
<dc:date>{vandaag}</dc:date>
<meta property="dcterms:modified">{vandaag}T00:00:00Z</meta>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="colofon" href="colofon.xhtml" media-type="application/xhtml+xml"/>
<item id="stijl" href="stijl.css" media-type="text/css"/>
{manifest}
</manifest>
<spine>
<itemref idref="colofon"/>
{spine}
</spine>
</package>"""

    stijl = """body { font-family: serif; line-height: 1.6; margin: 1em; }
h1 { font-size: 1.5em; margin: 1em 0 0.5em; }
h2 { font-size: 1.15em; margin: 1.2em 0 0.4em; }
p.v { margin: 0 0 0.35em; text-indent: 0; }
span.n { font-size: 0.7em; vertical-align: super; color: #777; margin-right: 0.3em; }
p.deels { font-style: italic; color: #666; font-size: 0.9em; }
"""

    with atomic_output(pad) as temporary, zipfile.ZipFile(temporary, "w") as z:
        # mimetype moet als eerste en ongecomprimeerd
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0" encoding="utf-8"?>\n'
                   '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>',
                   zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/colofon.xhtml", colofon, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/stijl.css", stijl, zipfile.ZIP_DEFLATED)
        for naam, inhoud in docs:
            z.writestr(f"OEBPS/{naam}", inhoud, zipfile.ZIP_DEFLATED)

    return pad, {"boeken": n_boeken, "hoofdstukken": n_hfdst, "verzen": n_verzen}


# -------------------------------------------------------------------- main
def main():
    os.makedirs(UIT, exist_ok=True)
    with open(os.path.join(DATA, "verified-chapters.json"), encoding="utf-8") as fh:
        verified = json.load(fh)
    boeken = (lees(os.path.join(DATA, "books.json"), {}) or {}).get("books", [])
    stats = lees(os.path.join(DATA, "stats.json"), {}) or {}
    zippad = bouw_zip()
    vandaag = datetime.date.today().isoformat()

    index = {
        "versie": stats.get("version", ""),
        "gebouwd": vandaag,
        "uitgaven": [
            {
                "naam": "Brondata (ZIP)",
                "bestand": ZIP_NAAM,
                "omschrijving": ("De complete data-map zoals de site die gebruikt: alle boeken en "
                                 "hoofdstukken als JSON, met kanttekeningen, grondtekst en "
                                 "Strong's-nummers. Ongefilterd, dus inclusief nog niet nagekeken tekst."),
                "bytes": os.path.getsize(zippad),
                "datum": vandaag,
            },
        ],
    }
    if any(verified.values()):
        epubpad, telling = bouw_epub(boeken, verified, stats)
        index["uitgaven"].insert(0, {
            "naam": "Geverifieerde tekst (EPUB)",
            "bestand": EPUB_NAAM,
            "omschrijving": (
                f"Leesuitgave: {telling['boeken']} boeken, {telling['hoofdstukken']} hoofdstukken "
                f"en {telling['verzen']} verzen. Accountgebonden hoofdstukverificaties op {vandaag}."
            ),
            "bytes": os.path.getsize(epubpad),
            "datum": vandaag,
        })
    with atomic_output(os.path.join(UIT, "index.json")) as temporary, open(temporary, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    if not any(verified.values()):
        # Trek eerst de link in; verwijder daarna uitsluitend de oude gegenereerde EPUB.
        previous_epub = os.path.join(UIT, EPUB_NAAM)
        if os.path.exists(previous_epub):
            os.unlink(previous_epub)

    for u in index["uitgaven"]:
        print(f"  {u['bestand']:<34} {u['bytes']/1024/1024:>7.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
