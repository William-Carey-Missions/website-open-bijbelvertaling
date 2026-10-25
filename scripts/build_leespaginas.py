#!/usr/bin/env python3
"""Bouw gewone leespagina's en llms-full.txt uit de hoofdstukdata.

De leesweergave (index.html#boek/hoofdstuk) is een JavaScript-toepassing met
hash-adressen. Zoekmachines en AI-crawlers zien daarin geen Bijbeltekst. Dit
script schrijft de tekst van de Open Vertaling daarom ook als gewone HTML:

- bijbel/index.html                  82 boeken
- bijbel/<boek>/index.html           inhoud van een boek
- bijbel/<boek>/<hoofdstuk>.html     de tekst van een hoofdstuk
- llms-full.txt                      de hele tekst als platte tekst

De uitvoer staat niet in git; de uitrol bouwt hem opnieuw uit de data.
Draai vanuit de repo-root:  python scripts/build_leespaginas.py
"""
import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://openvertaling.nl"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"

GROEPEN = [
    ("Oude Testament", "genesis exodus leviticus numeri deuteronomium jozua richteren ruth 1samuel 2samuel "
     "1koningen 2koningen 1kronieken 2kronieken ezra nehemia esther job psalmen spreuken prediker hooglied "
     "jesaja jeremia klaagliederen ezechiel daniel hosea joel amos obadja jona micha nahum habakuk zefanja "
     "haggai zacharia maleachi"),
    ("Nieuwe Testament", "mattheus markus lukas johannes handelingen romeinen 1korinthiers 2korinthiers galaten "
     "efeziers filippenzen kolossenzen 1tessalonicensen 2tessalonicensen 1timotheus 2timotheus titus filemon "
     "hebreeen jakobus 1petrus 2petrus 1johannes 2johannes 3johannes judas openbaring"),
    ("Apocriefe en deuterocanonieke boeken", "3ezra 4ezra tobit judith boekderwijsheid jezussirach baruch "
     "estherapocrief gebedvanazaria gezangindevuuroven susanna belenddedraak gebedvanmanasse 1makkabeeen "
     "2makkabeeen 3makkabeeen"),
]

STIJL = """
.lp { max-width: 760px; margin: 0 auto; padding: 24px 16px 56px; }
.lp-kruimel { font-size: 13px; color: var(--text-muted, #888); margin: 0 0 14px; }
.lp-kruimel a { color: var(--teal, #76978a); text-decoration: none; }
.lp h1 { font-family: var(--font-serif); color: var(--navy, #142e42); margin: 0 0 8px; }
.lp-lead { color: var(--text-secondary, #555); margin: 0 0 18px; }
.lp-inhoud { font-style: italic; color: var(--text-secondary, #555); border-left: 3px solid var(--gold, #cba449); padding: 4px 12px; margin: 0 0 20px; }
.lp-inleiding { color: var(--text-secondary, #555); line-height: 1.6; }
.lp-tekst { font-family: var(--font-serif); font-size: 19px; line-height: 1.65; color: var(--text-primary, #333); }
.lp-tekst p { margin: 0 0 6px; }
.lp-tekst sup { color: var(--gold, #cba449); font-family: var(--font-body); font-size: 11px; font-weight: 600; margin-right: 3px; }
.lp-opschrift { display: block; font-size: 16px; color: var(--text-secondary, #555); }
.lp-verder { display: flex; justify-content: space-between; gap: 12px; margin: 28px 0 8px; font-size: 14px; }
.lp-verder a, .lp-app a, .lp-lijst a { color: var(--teal, #76978a); }
.lp-app { background: var(--bg-surface, #fff); border: 1px solid var(--border-soft, #e8e4dc); border-radius: 8px; padding: 10px 14px; font-size: 14px; margin: 0 0 22px; }
.lp-lijst { display: flex; flex-wrap: wrap; gap: 6px 14px; padding: 0; list-style: none; }
.lp-hoofdstukken { display: grid; grid-template-columns: repeat(auto-fill, minmax(44px, 1fr)); gap: 6px; padding: 0; list-style: none; }
.lp-hoofdstukken a { display: block; text-align: center; padding: 6px 0; border: 1px solid var(--border-soft, #e8e4dc); border-radius: 6px; text-decoration: none; color: var(--navy, #142e42); background: var(--bg-surface, #fff); }
.lp h2 { font-family: var(--font-serif); color: var(--navy, #142e42); margin: 26px 0 8px; }
.lp-voet { margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--border-soft, #e8e4dc); font-size: 13px; color: var(--text-muted, #888); }
.lp-voet a { color: var(--teal, #76978a); }
:root[data-theme="donker"] .lp h1, :root[data-theme="donker"] .lp h2, :root[data-theme="donker"] .lp-hoofdstukken a { color: var(--text-primary); }
"""


def esc(tekst):
    return html.escape(str(tekst or ""), quote=True)


# Godsnaam HEERE, zoals de leesweergave hem standaard toont (js/opties.js, 'klassiek').
# De volgorde telt: samenstellingen eerst, daarna voorzetsel en aanroep, dan de rest.
GODSNAAM = [
    (re.compile(r"\bGod JAHWEH\b"), "de HEERE God"),
    (re.compile(r"\bJAHWEH van de legermachten\b"), "de HEERE der heirscharen"),
    (re.compile(r"\b(op|van|aan|voor|tot|door|in|met|bij|over|onder|naast|achter|jegens|uit|na|sinds) JAHWEH\b",
                re.I), r"\1 de HEERE"),
    (re.compile(r"\b([Oo]) JAHWEH\b"), r"\1 HEERE"),
    (re.compile(r"\bJAHWEH!"), "HEERE!"),
    (re.compile(r"(^|[.!?]\s+)JAHWEH\b"), r"\1De HEERE"),
    (re.compile(r"\bJAHWEH\b"), "de HEERE"),
    (re.compile(r"\bde de HEERE\b"), "de HEERE"),
    (re.compile(r"\bDe de HEERE\b"), "De HEERE"),
]


def godsnaam(tekst):
    for patroon, vervanging in GODSNAAM:
        tekst = patroon.sub(vervanging, tekst)
    return tekst


def verstekst(tekst):
    """Platte versdata naar HTML; <<opschrift>> (bv. Jezus Sirach 51:1) wordt een opschrift."""
    veilig = esc(" ".join(godsnaam(str(tekst or "")).split()))
    return re.sub(r"&lt;&lt;(.+?)&gt;&gt;\s*", r'<span class="lp-opschrift">\1</span>', veilig)


def platte_tekst(tekst):
    tekst = " ".join(godsnaam(str(tekst or "")).split())
    return re.sub(r"<<(.+?)>>\s*", r"\1. ", tekst)


def lees_json(pad):
    with open(pad, encoding="utf-8") as bestand:
        return json.load(bestand)


def pagina(titel, omschrijving, pad, inhoud, json_ld, extra_head=""):
    url = f"{BASE}/{pad}"
    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<script src="/js/theme.js"></script>
<base href="/">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titel)}</title>
<meta name="description" content="{esc(omschrijving)}">
<meta name="robots" content="index, follow, max-snippet:-1">
<link rel="canonical" href="{url}">
<link rel="license" href="{CC0}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Open Vertaling">
<meta property="og:locale" content="nl_NL">
<meta property="og:title" content="{esc(titel)}">
<meta property="og:description" content="{esc(omschrijving)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}/icons/icon-512.png">
<link rel="describedby" href="/llms.txt" type="text/markdown">
{extra_head}<link rel="stylesheet" href="css/fonts.css">
<link rel="stylesheet" href="css/style.css">
<link rel="stylesheet" href="css/ontwerp.css?v=0.60.0">
<link rel="stylesheet" href="css/publication.css?v=0.60.0">
<style>{STIJL}</style>
<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
</head>
<body>
<nav id="topnav"></nav>
<script src="js/topnav.js"></script>
<main class="lp">
{inhoud}
<footer class="lp-voet">De tekst van de Open Vertaling is vrij van rechten (<a href="{CC0}" rel="license">CC0 1.0</a>, publiek domein): vrij te citeren, te kopiëren en te hergebruiken, zonder toestemming. De tekst en kanttekeningen zijn nagekeken.</footer>
</main>
</body>
</html>
"""


def boek_ld(boek):
    return {
        "@type": "Book",
        "name": f"{boek['naam']} — Open Vertaling",
        "url": f"{BASE}/bijbel/{boek['id']}/",
        "inLanguage": "nl-NL",
        "license": CC0,
        "isPartOf": {"@id": f"{BASE}/#book"},
    }


def hoofdstukpagina(boek, nummer, data, vorige, volgende):
    titel = f"{boek['naam']} {nummer}"
    pad = f"bijbel/{boek['id']}/{nummer}.html"
    verzen = [v for v in data.get("verses", []) if str(v.get("text2026") or "").strip()]
    eerste = platte_tekst(verzen[0]["text2026"]) if verzen else ""
    omschrijving = f"{titel} in de Open Vertaling, vrij van rechten (CC0). {eerste}"
    if len(omschrijving) > 200:
        omschrijving = omschrijving[:197].rsplit(" ", 1)[0] + "…"
    intro = (data.get("chapterIntro") or {}).get("text2026") if isinstance(data.get("chapterIntro"), dict) else None
    regels = [
        f'<p class="lp-kruimel"><a href="bijbel/">Bijbel</a> › <a href="bijbel/{boek["id"]}/">{esc(boek["naam"])}</a></p>',
        f"<h1>{esc(titel)}</h1>",
        f'<p class="lp-app"><a href="index.html#{boek["id"]}/{nummer}">Lees {esc(titel)} in de leesweergave</a>, '
        "met grondtekst, Strong-nummers, kanttekeningen en de verschillen met de Statenvertaling.</p>",
    ]
    if intro:
        regels.append(f'<p class="lp-inhoud">{verstekst(intro)}</p>')
    regels.append('<div class="lp-tekst">')
    for vers in verzen:
        regels.append(f'<p id="v{vers["number"]}"><sup>{vers["number"]}</sup>{verstekst(vers["text2026"])}</p>')
    regels.append("</div>")
    links = []
    if vorige:
        links.append(f'<a href="bijbel/{vorige[0]["id"]}/{vorige[1]}.html" rel="prev">‹ {esc(vorige[0]["naam"])} {vorige[1]}</a>')
    else:
        links.append("<span></span>")
    if volgende:
        links.append(f'<a href="bijbel/{volgende[0]["id"]}/{volgende[1]}.html" rel="next">{esc(volgende[0]["naam"])} {volgende[1]} ›</a>')
    regels.append(f'<nav class="lp-verder" aria-label="Hoofdstukken">{"".join(links)}</nav>')
    ld = {
        "@context": "https://schema.org",
        "@type": "Chapter",
        "name": titel,
        "position": nummer,
        "url": f"{BASE}/{pad}",
        "inLanguage": "nl-NL",
        "license": CC0,
        "isAccessibleForFree": True,
        "isPartOf": boek_ld(boek),
    }
    extra = f'<link rel="alternate" type="application/json" href="{BASE}/data/{boek["id"]}/{nummer}.json">\n'
    return pad, pagina(f"{titel} — Open Vertaling", omschrijving, pad, "\n".join(regels), ld, extra)


def boekpagina(boek, nummers, boekdata):
    pad = f"bijbel/{boek['id']}/"
    intro = ((boekdata or {}).get("bookIntro") or {}).get("text2026")
    regels = [
        '<p class="lp-kruimel"><a href="bijbel/">Bijbel</a></p>',
        f"<h1>{esc(boek['naam'])}</h1>",
        f'<p class="lp-lead">{esc(boek["testament"])} · {len(nummers)} '
        f'{"hoofdstuk" if len(nummers) == 1 else "hoofdstukken"} · vrij van rechten (CC0)</p>',
    ]
    regels.append('<ul class="lp-hoofdstukken">' + "".join(
        f'<li><a href="bijbel/{boek["id"]}/{n}.html" aria-label="{esc(boek["naam"])} {n}">{n}</a></li>' for n in nummers
    ) + "</ul>")
    if intro:
        regels.append(f'<h2>Inleiding</h2>\n<p class="lp-inleiding">{verstekst(intro)}</p>')
    ld = {"@context": "https://schema.org", **boek_ld(boek)}
    omschrijving = (f"{boek['naam']} in de Open Vertaling, een herziening van de Statenvertaling in hedendaags "
                    f"Nederlands. Alle {len(nummers)} hoofdstukken, vrij van rechten (CC0).")
    return pad + "index.html", pagina(f"{boek['naam']} — Open Vertaling", omschrijving, pad, "\n".join(regels), ld)


def overzicht(groepen, aantallen):
    verzen = f'{aantallen["verzen"]:,}'.replace(",", ".")
    regels = [
        "<h1>De Bijbel in de Open Vertaling</h1>",
        f'<p class="lp-lead">Alle {aantallen["boeken"]} boeken, {aantallen["hoofdstukken"]} hoofdstukken en '
        f"{verzen} verzen: het Oude en het Nieuwe Testament, de apocriefe en deuterocanonieke "
        "boeken. Een herziening van de Statenvertaling in hedendaags Nederlands, "
        "vrij van rechten (CC0).</p>",
        '<p class="lp-app"><a href="index.html">Lees de Open Vertaling</a>, haal de hele '
        'tekst als <a href="llms-full.txt">platte tekst</a> '
        'of via de <a href="downloads.html">downloads</a>.</p>',
    ]
    for groep, boeken in groepen:
        regels.append(f"<h2>{esc(groep)}</h2>")
        regels.append('<ul class="lp-lijst">' + "".join(
            f'<li><a href="bijbel/{b["id"]}/">{esc(b["naam"])}</a></li>' for b, _ in boeken
        ) + "</ul>")
    ld = {
        "@context": "https://schema.org",
        "@type": "Book",
        "@id": f"{BASE}/#book",
        "name": "Open Vertaling",
        "url": f"{BASE}/bijbel/",
        "inLanguage": "nl-NL",
        "license": CC0,
        "isBasedOn": "Statenvertaling (1637/1888)",
        "isAccessibleForFree": True,
    }
    omschrijving = ("De volledige Bijbel in de Open Vertaling: 82 boeken, inclusief de apocriefe, "
                    "in hedendaags Nederlands en vrij van rechten (CC0).")
    return "bijbel/index.html", pagina("De Bijbel — Open Vertaling", omschrijving, "bijbel/", "\n".join(regels), ld)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uit", type=Path, default=ROOT, help="map waarin bijbel/ en llms-full.txt komen")
    doel = parser.parse_args().uit
    index = lees_json(ROOT / "data" / "books-index.json")
    per_id = {boek["id"]: boek for boek in index["boeken"]}
    volgorde = [(groep, ids.split()) for groep, ids in GROEPEN]
    bekend = [boek_id for _, ids in volgorde for boek_id in ids]
    if sorted(bekend) != sorted(per_id):
        sys.exit(f"Boekvolgorde wijkt af van data/books-index.json: {sorted(set(bekend) ^ set(per_id))}")

    groepen = []
    for groep, ids in volgorde:
        boeken = []
        for boek_id in ids:
            map_ = ROOT / "data" / boek_id
            nummers = sorted(int(p.stem) for p in map_.glob("*.json") if p.stem.isdigit())
            boeken.append((per_id[boek_id], nummers))
        groepen.append((groep, boeken))
    reeks = [(boek, n) for _, boeken in groepen for boek, nummers in boeken for n in nummers]
    positie = {(boek["id"], n): plek for plek, (boek, n) in enumerate(reeks)}

    uit = doel / "bijbel"
    geschreven = 0
    verzen_totaal = 0
    tekst = [
        "# Open Vertaling — de volledige Bijbel in hedendaags Nederlands",
        "",
        "> De volledige tekst van de Open Vertaling (openvertaling.nl): een herziening van de Statenvertaling "
        "(1637/1888) in hedendaags Nederlands. 82 boeken: het Oude Testament, het Nieuwe Testament, de "
        "apocriefe/deuterocanonieke boeken.",
        "",
        f"Licentie: CC0 1.0, publiek domein ({CC0}). Vrij te citeren, te kopiëren, te bewerken en te hergebruiken, "
        "ook commercieel en door AI-taalmodellen, zonder toestemming en zonder verplichte bronvermelding.",
        f"Bron: {BASE} · per hoofdstuk: {BASE}/bijbel/{{boek-id}}/{{hoofdstuk}}.html en "
        f"{BASE}/data/{{boek-id}}/{{hoofdstuk}}.json · gebouwd op {datetime.date.today().isoformat()}.",
        "De tekst en kanttekeningen zijn nagekeken.",
        "",
    ]
    for groep, boeken in groepen:
        tekst += [f"# {groep}", ""]
        for boek, nummers in boeken:
            boekdata = None
            boekbestand = ROOT / "data" / f"{boek['id']}.json"
            if boekbestand.exists():
                boekdata = lees_json(boekbestand)
            pad, inhoud = boekpagina(boek, nummers, boekdata)
            (uit / boek["id"]).mkdir(parents=True, exist_ok=True)
            (uit / pad.split("/", 1)[1]).write_text(inhoud, encoding="utf-8", newline="\n")
            tekst += [f"## {boek['naam']}", ""]
            for n in nummers:
                data = lees_json(ROOT / "data" / boek["id"] / f"{n}.json")
                plek = positie[(boek["id"], n)]
                vorige = reeks[plek - 1] if plek > 0 else None
                volgende = reeks[plek + 1] if plek + 1 < len(reeks) else None
                pad, inhoud = hoofdstukpagina(boek, n, data, vorige, volgende)
                (uit / pad.split("/", 1)[1]).write_text(inhoud, encoding="utf-8", newline="\n")
                geschreven += 1
                tekst += [f"### {boek['naam']} {n}", ""]
                for vers in data.get("verses", []):
                    if str(vers.get("text2026") or "").strip():
                        tekst.append(f"{vers['number']} {platte_tekst(vers['text2026'])}")
                        verzen_totaal += 1
                tekst.append("")

    aantallen = {"boeken": len(per_id), "hoofdstukken": geschreven, "verzen": verzen_totaal}
    pad, inhoud = overzicht(groepen, aantallen)
    (uit / "index.html").write_text(inhoud, encoding="utf-8", newline="\n")
    (doel / "llms-full.txt").write_text("\n".join(tekst) + "\n", encoding="utf-8", newline="\n")
    print(f"Leespagina's: {geschreven} hoofdstukken in {len(per_id)} boeken, {verzen_totaal} verzen; "
          f"llms-full.txt {(doel / 'llms-full.txt').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
