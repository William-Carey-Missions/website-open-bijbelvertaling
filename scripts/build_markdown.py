#!/usr/bin/env python3
"""Bouw de Bijbeltekst met kanttekeningen als Markdown, plus de achtergrondpagina.

Uitvoer (niet in git; de uitrol bouwt hem opnieuw uit de data):

- markdown/index.md                  overzicht van alle bestanden
- markdown/ov/<boek>.md              Open Vertaling met herziene kanttekeningen (CC0)
- markdown/sv1888/<boek>.md          Statenvertaling, editie 1888, met kanttekeningen (publiek domein)
- markdown/sv1637/<boek>.md          Statenvertaling 1637 in oorspronkelijke spelling (publiek domein)
- markdown/<editie>-volledig.md      de hele editie in één bestand
- markdown/wijzigingsprincipes.md    de vaste vervangingen van SV1888 naar OV
- achtergrond.html                   achtergrond.md als gewone HTML-pagina

Andere vergelijkingsteksten in de hoofdstukdata zijn auteursrechtelijk beschermd
en komen hier niet in: het script leest alleen de velden hieronder.

Draai vanuit de repo-root:  python scripts/build_markdown.py
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_leespaginas import BASE, CC0, GROEPEN, esc, godsnaam, lees_json, pagina  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PD = "https://creativecommons.org/publicdomain/mark/1.0/"

EDITIES = {
    "ov": {
        "naam": "Open Vertaling", "kort": "OV",
        "tekst": "text2026_html", "plat": "text2026", "noot": "text2026", "inleiding": "text2026",
        "godsnaam": True,
        "licentie": f"CC0 1.0, publiek domein ({CC0})",
        "uitleg": "De Open Vertaling: de Statenvertaling (editie 1888) herzien naar hedendaags Nederlands, "
                  "met de kanttekeningen eveneens herzien.",
    },
    "sv1888": {
        "naam": "Statenvertaling (editie 1888)", "kort": "SV 1888",
        "tekst": "textSV1888_html", "plat": "textSV1888", "noot": "textSV1888", "inleiding": None,
        "godsnaam": False,
        "licentie": f"publiek domein ({PD})",
        "uitleg": "De Statenvertaling in de spelling van de editie van 1888, de basis van de Open Vertaling. "
                  "Bij verwijzende kanttekeningen is de tekst van de aangehaalde verzen toegevoegd.",
    },
    "sv1637": {
        "naam": "Statenvertaling 1637", "kort": "SV 1637",
        "tekst": "text1637_html", "plat": "text1637", "noot": "text1637", "inleiding": "text1637",
        "godsnaam": False,
        "licentie": f"publiek domein ({PD})",
        "uitleg": "De oorspronkelijke Statenvertaling van 1637 in de spelling van toen, met de kanttekeningen "
                  "van de Statenvertalers.",
    },
}

MARKER = re.compile(r'<sup class="note-marker" data-note="([^"]*)">[^<]*</sup>')
LOS_MARKER = re.compile(r"\[([a-z]|\d+)\]\s*")


def schoon(tekst, met_godsnaam):
    """HTML en witruimte eruit; bij de OV dezelfde Godsnaam als op de site.

    Geen strip(): de spaties aan de randen staan tussen tekst en kanttekeningmarker."""
    tekst = html.unescape(re.sub(r"<[^>]+>", "", str(tekst or "")))
    if met_godsnaam:
        tekst = godsnaam(tekst)
    return re.sub(r"\s+", " ", re.sub(r"<<(.+?)>>\s*", r"\1. ", tekst))


def md(tekst):
    """Tekens die Markdown anders leest, letterlijk houden."""
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", tekst)


def noot_id(hoofdstuk, vers, marker):
    # Enkele markers in de data bevatten tekens als "[" (bv. "33[13"); die mogen niet in een voetnoot-id.
    return f"{hoofdstuk}-{vers}-" + re.sub(r"[^\w]", "_", marker)


def vers_md(vers, hoofdstuk, editie, cfg):
    """Eén vers als Markdown-regel, met voetnootverwijzingen op de plek van de markers."""
    noten = {}
    for noot in vers.get("marginNotes") or []:
        inhoud = schoon(noot.get(cfg["noot"]), cfg["godsnaam"])
        if inhoud and noot.get("marker"):
            noten[str(noot["marker"])] = (noot.get("type"), inhoud)

    bron = vers.get(cfg["tekst"]) or ""
    gebruikt = []
    if bron:
        delen, laatste = [], 0
        for treffer in MARKER.finditer(bron):
            delen.append(md(schoon(bron[laatste:treffer.start()], cfg["godsnaam"])))
            marker = treffer.group(1)
            if marker in noten and marker not in gebruikt:
                gebruikt.append(marker)
                delen.append(f"[^{noot_id(hoofdstuk, vers['number'], marker)}]")
            laatste = treffer.end()
        delen.append(md(schoon(bron[laatste:], cfg["godsnaam"])))
        regel = "".join(delen)
    else:
        regel = md(schoon(LOS_MARKER.sub("", vers.get(cfg["plat"]) or ""), cfg["godsnaam"]))
    regel = re.sub(r"\s+", " ", regel).strip()
    if not regel:
        return None, []
    # Noten zonder marker in de tekst komen achter het vers.
    rest = [m for m in noten if m not in gebruikt]
    regel += "".join(f"[^{noot_id(hoofdstuk, vers['number'], m)}]" for m in rest)
    voetnoten = []
    for marker in gebruikt + rest:
        soort, inhoud = noten[marker]
        label = "Verwijzing" if soort == "crossref" else "Kanttekening"
        voetnoten.append(f"[^{noot_id(hoofdstuk, vers['number'], marker)}]: {label} {md(marker)}: {md(inhoud)}")
    return f"**{vers['number']}** {regel}", voetnoten


def boek_md(boek, nummers, editie, cfg):
    regels = [
        f"# {boek['naam']} — {cfg['naam']}",
        "",
        f"> {cfg['uitleg']} Licentie: {cfg['licentie']}.",
        f"> Bron: {BASE}/bijbel/{boek['id']}/ · andere edities en boeken: {BASE}/markdown/",
        "",
    ]
    verzen = noten = 0
    for n in nummers:
        data = lees_json(ROOT / "data" / boek["id"] / f"{n}.json")
        hoofdstuk_regels, voetnoten = [], []
        for vers in data.get("verses", []):
            regel, eigen = vers_md(vers, n, editie, cfg)
            if regel and editie == "ov":
                regel += f" [bron]({BASE}/bijbel/{boek['id']}/{n}.html#v{vers['number']})"
            if regel:
                hoofdstuk_regels += [regel, ""]
                voetnoten += eigen
                verzen += 1
        if not hoofdstuk_regels:
            continue
        regels += [f"## {boek['naam']} {n}", ""]
        if editie == "ov":
            regels += [f"[Hoofdstuk als JSON]({BASE}/data/llm/{boek['id']}/{n}.json)", ""]
        inleiding = data.get("chapterIntro")
        if cfg["inleiding"] and isinstance(inleiding, dict) and inleiding.get(cfg["inleiding"]):
            regels += [f"*{md(schoon(inleiding[cfg['inleiding']], cfg['godsnaam']))}*", ""]
        regels += hoofdstuk_regels
        if voetnoten:
            regels += voetnoten + [""]
            noten += len(voetnoten)
    return "\n".join(regels).rstrip() + "\n", verzen, noten


def principes_md():
    principes = lees_json(ROOT / "data" / "wijzigingsprincipes.json")["principes"]
    regels = [
        "# Wijzigingsprincipes van de Open Vertaling",
        "",
        "> Vaste vervangingen waarmee de Statenvertaling (editie 1888) naar de Open Vertaling is herzien. "
        "Elk principe werkt één keer, vanuit de tekst van 1888; wat een principe heeft opgeleverd, wordt niet "
        f"door een ander principe opnieuw veranderd. Licentie: CC0 1.0 ({CC0}).",
        "",
        f"Aantal principes: {len(principes)}. Per vers is te zien welk principe een wijziging heeft gemaakt: "
        f"de hoofdstukdata ({BASE}/data/{{boek}}/{{hoofdstuk}}.json) noemt het principe bij elke gewijzigde woordgroep.",
        "",
    ]
    per_categorie = {}
    for principe in principes:
        per_categorie.setdefault(principe.get("categorie") or "Overig", []).append(principe)
    for categorie, lijst in sorted(per_categorie.items(), key=lambda kv: -len(kv[1])):
        regels += [f"## {categorie} ({len(lijst)})", "", "| Code | SV1888 | Open Vertaling | Toelichting |", "|---|---|---|---|"]
        for p in lijst:
            cel = [md(" ".join(str(p.get(k) or "").split())).replace("|", "\\|") for k in ("id", "oud", "nieuw", "toelichting")]
            regels.append("| " + " | ".join(cel) + " |")
        regels.append("")
    return "\n".join(regels)


def regel_md(tekst):
    """Inline Markdown (links, vet, cursief) naar HTML voor de achtergrondpagina."""
    veilig = esc(tekst)
    veilig = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', veilig)
    veilig = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", veilig)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", veilig)


def markdown_naar_html(tekst):
    """Genoeg Markdown voor achtergrond.md: koppen, alinea's, lijsten en citaten."""
    uit, alinea, lijst = [], [], None

    def sluit():
        nonlocal lijst
        if alinea:
            uit.append(f"<p>{regel_md(' '.join(alinea))}</p>")
            alinea.clear()
        if lijst:
            uit.append(f"</{lijst}>")
            lijst = None

    for ruw in tekst.splitlines():
        regel = ruw.strip()
        kop = re.match(r"(#{1,3}) (.+)", regel)
        punt = re.match(r"(?:[-*]|(\d+)\.) (.+)", regel)
        if not regel:
            sluit()
        elif kop:
            sluit()
            niveau = len(kop.group(1))
            uit.append(f"<h{niveau}>{regel_md(kop.group(2))}</h{niveau}>")
        elif punt:
            if alinea:
                uit.append(f"<p>{regel_md(' '.join(alinea))}</p>")
                alinea.clear()
            soort = "ol" if punt.group(1) else "ul"
            if lijst != soort:
                if lijst:
                    uit.append(f"</{lijst}>")
                uit.append(f"<{soort}>")
                lijst = soort
            uit.append(f"<li>{regel_md(punt.group(2))}</li>")
        elif regel.startswith(">"):
            sluit()
            uit.append(f'<p class="lp-inhoud">{regel_md(regel.lstrip("> "))}</p>')
        else:
            alinea.append(regel)
    sluit()
    return "\n".join(uit)


def achtergrond_html():
    bron = (ROOT / "achtergrond.md").read_text(encoding="utf-8")
    titel = re.search(r"^# (.+)$", bron, re.M).group(1)
    omschrijving = ("Achtergrond van de Open Vertaling: waarom een vrije herziening van de Statenvertaling, "
                    "hoe de tekst en de kanttekeningen zijn herzien, de wijzigingsprincipes, de controle door "
                    "mensen, de licentie en hergebruik.")
    ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": titel, "url": f"{BASE}/achtergrond.html",
          "inLanguage": "nl", "license": CC0, "isPartOf": {"@type": "WebSite", "name": "Open Vertaling", "url": f"{BASE}/"}}
    inhoud = (f'<article class="lp-achtergrond">\n{markdown_naar_html(bron)}\n</article>\n'
              '<p class="lp-app">Deze pagina staat ook als <a href="achtergrond.md">Markdown</a>.</p>')
    extra = ('<link rel="alternate" type="text/markdown" href="/achtergrond.md">\n'
             '<style>.lp-achtergrond p, .lp-achtergrond li { line-height: 1.75; margin: 0 0 14px; }\n'
             '.lp-achtergrond ul, .lp-achtergrond ol { padding-left: 22px; margin: 0 0 14px; }\n'
             '.lp-achtergrond h3 { margin: 22px 0 8px; } .lp-achtergrond a { color: var(--teal, #76978a); }</style>\n')
    return pagina(titel, omschrijving, "achtergrond.html", inhoud, ld, extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uit", type=Path, default=ROOT, help="map waarin markdown/ en achtergrond.html komen")
    parser.add_argument("--boeken", nargs="*", help="alleen deze boek-id's (voor tests)")
    args = parser.parse_args()
    doel = args.uit
    per_id = {boek["id"]: boek for boek in lees_json(ROOT / "data" / "books-index.json")["boeken"]}
    groepen = [(groep, [per_id[i] for i in ids.split() if not args.boeken or i in args.boeken])
               for groep, ids in GROEPEN]

    uit = doel / "markdown"
    totaal = {}
    for editie, cfg in EDITIES.items():
        (uit / editie).mkdir(parents=True, exist_ok=True)
        volledig = [f"# {cfg['naam']} — volledige tekst met kanttekeningen", "",
                    f"> {cfg['uitleg']} Licentie: {cfg['licentie']}. Bron: {BASE}/markdown/", ""]
        tellers = {"boeken": 0, "verzen": 0, "noten": 0}
        for groep, boeken in groepen:
            for boek in boeken:
                nummers = sorted(int(p.stem) for p in (ROOT / "data" / boek["id"]).glob("*.json") if p.stem.isdigit())
                tekst, verzen, noten = boek_md(boek, nummers, editie, cfg)
                if not verzen:
                    continue
                (uit / editie / f"{boek['id']}.md").write_text(tekst, encoding="utf-8", newline="\n")
                # Voetnoot-id's beginnen met het hoofdstuk; in één bestand komt het boek ervoor.
                romp = tekst.split("\n", 5)[5]
                romp = re.sub(r"\[\^(\d+-\d+-[^\]]+)\]", lambda t, b=boek["id"]: f"[^{b}-{t.group(1)}]", romp)
                volledig += [f"## {boek['naam']}", "", re.sub(r"^## ", "### ", romp, flags=re.M)]
                tellers["boeken"] += 1
                tellers["verzen"] += verzen
                tellers["noten"] += noten
        (uit / f"{editie}-volledig.md").write_text("\n".join(volledig), encoding="utf-8", newline="\n")
        totaal[editie] = tellers

    (uit / "wijzigingsprincipes.md").write_text(principes_md(), encoding="utf-8", newline="\n")
    (uit / "index.md").write_text(index_md(groepen, totaal), encoding="utf-8", newline="\n")
    (doel / "achtergrond.html").write_text(achtergrond_html(), encoding="utf-8", newline="\n")
    for editie, t in totaal.items():
        print(f"Markdown {editie}: {t['boeken']} boeken, {t['verzen']} verzen, {t['noten']} kanttekeningen")


def index_md(groepen, totaal):
    regels = [
        "# Open Vertaling — Bijbeltekst en kanttekeningen in Markdown",
        "",
        "> Alle edities van openvertaling.nl als Markdown: de Open Vertaling (CC0) en de Statenvertaling in de "
        "edities 1888 en 1637 (publiek domein), elk met de kanttekeningen als voetnoten. Vrij te gebruiken, "
        "ook voor zoekmachines en AI-taalmodellen.",
        "",
        f"Achtergrond: {BASE}/achtergrond.md · Wijzigingsprincipes: {BASE}/markdown/wijzigingsprincipes.md · "
        f"Overzicht voor AI: {BASE}/llms.txt",
        "",
        "Opbouw van een boekbestand: per hoofdstuk een kop `## Boek N`, per vers een regel die begint met het "
        "versnummer in vet, en daarna de kanttekeningen van dat hoofdstuk als voetnoten `[^hoofdstuk-vers-marker]`. "
        "Letters (a, b, …) zijn verwijzingen naar andere Bijbelplaatsen; cijfers zijn uitleggende kanttekeningen.",
        "",
        "## Edities",
        "",
    ]
    from build_llm_catalog import guide_section
    regels.insert(6, guide_section())
    for editie, cfg in EDITIES.items():
        t = totaal[editie]
        regels.append(f"- [{cfg['naam']} — volledig]({BASE}/markdown/{editie}-volledig.md): {t['boeken']} boeken, "
                      f"{t['verzen']} verzen, {t['noten']} kanttekeningen. Licentie: {cfg['licentie']}.")
    regels.append("")
    for groep, boeken in groepen:
        regels += [f"## {groep}", ""]
        for boek in boeken:
            links = " · ".join(f"[{cfg['kort']}]({BASE}/markdown/{editie}/{boek['id']}.md)"
                               for editie, cfg in EDITIES.items())
            regels.append(f"- {boek['naam']}: {links}")
        regels.append("")
    return "\n".join(regels)


if __name__ == "__main__":
    main()
