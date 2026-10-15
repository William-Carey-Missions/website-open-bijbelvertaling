#!/usr/bin/env python3
"""Zet de Open Parafrase Weergave om naar de leeseditie op de site.

De parafrase wordt gemaakt in `data/edities/opv/chapters/<boek>/<hs>.json`, met
per vers de segmenten, de sprekers en de begripskoppelingen. De lezer op de site
leest edities uit `data/vertalingen/<code>/<boek>/<hs>.json`, in een net iets
ander formaat: `js/teksteditie.js` gebruikt daarvan `kop` en `verzen`, en per
vers `nummer`, `tekst`, `html` en optioneel `segmenten`.

De citaten gaan mee als opmaak in `html`, met dezelfde klassen als de Open
Vertaling (god-speaks, direct-speech, angel-speaks, devil-speaks). Een citaat
loopt van zijn begin- tot zijn eindsegment; de aankondiging staat in het
segment ervóór en blijft dus buiten de span. Een citaat binnen een citaat wordt
een span binnen een span, net als in de OV. De redactionele laag - blokken met
reviewstatus, begrippen, aangesprokenen - blijft in de eerste vorm staan.

Gebruik:
    python scripts/opv_leeseditie.py [data/edities/opv/chapters]
"""
import html as htmllib
import json
import re
import shutil
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
CODE = "nl-opv"

# Het sprekerstype bepaalt de klasse. Geesten verschillen: de Heilige Geest
# spreekt als God, de duivel en de onreine geesten krijgen hun eigen kleur.
KLASSE_PER_TYPE = {"god": "god-speaks", "angel": "angel-speaks"}
GODDELIJKE_GEESTEN = {"heilige-geest"}


def klasse(spreker):
    soort = spreker.get("type")
    if soort == "spirit":
        return "god-speaks" if spreker.get("id") in GODDELIJKE_GEESTEN else "devil-speaks"
    return KLASSE_PER_TYPE.get(soort, "direct-speech")


def vers_html(vers):
    """De verstekst met de citaten als geneste spans.

    Faalt hard als citaten elkaar kruisen of een segment onbekend is: dan is de
    bron fout, en een leeseditie die daar stilletjes omheen werkt verbergt dat.
    """
    segmenten = vers.get("segmenten") or []
    if not segmenten:
        return htmllib.escape(vers["tekst"], quote=False)
    positie = {s["id"]: i for i, s in enumerate(segmenten)}
    openen = {i: [] for i in range(len(segmenten))}
    sluiten = {i: 0 for i in range(len(segmenten))}
    citaten = []
    for c in vers.get("citaten") or []:
        a, b = positie[c["startSegment"]], positie[c["endSegment"]]
        if b < a:
            raise ValueError(f"{c['id']}: eindsegment vóór beginsegment")
        citaten.append((a, b, c))
    # buitenste eerst: vroegste begin, en bij gelijk begin het laatste einde
    citaten.sort(key=lambda t: (t[0], -t[1]))
    stapel = []
    for a, b, c in citaten:
        while stapel and stapel[-1] < a:
            stapel.pop()
        if stapel and b > stapel[-1]:
            raise ValueError(f"{c['id']}: kruist een ander citaat")
        stapel.append(b)
        openen[a].append(klasse(c["spreker"]))
        sluiten[b] += 1

    delen = []
    for i, s in enumerate(segmenten):
        for k in openen[i]:
            delen.append(f'<span class="{k}"><i>')
        delen.append(htmllib.escape(s["tekst"], quote=False))
        delen.append("</i></span>" * sluiten[i])
    uit = "".join(delen)
    # Witruimte hoort buiten de span: "zei: <span>…</span> Toen" en niet
    # "zei:<span> …</span>Toen". Herhalen tot het stabiel is, voor geneste spans.
    vorige = None
    while vorige != uit:
        vorige = uit
        uit = re.sub(r'(\s+)(</i></span>)', r'\2\1', uit)
        uit = re.sub(r'(<span class="[a-z-]+"><i>)(\s+)', r'\2\1', uit)
    return uit


def main():
    bron = Path(sys.argv[1]) if len(sys.argv) > 1 else WORTEL / "data" / "edities" / "opv" / "chapters"
    doel = WORTEL / "data" / "vertalingen" / CODE
    if doel.exists():
        shutil.rmtree(doel)
    boeken = []
    hoofdstukken = 0
    verzen = 0
    citaten = 0
    for boekmap in sorted(bron.iterdir()):
        if not boekmap.is_dir():
            continue
        boek = boekmap.name
        nummers = sorted(int(p.stem) for p in boekmap.glob("*.json") if p.stem.isdigit())
        if not nummers:
            continue
        boeken.append(boek)
        (doel / boek).mkdir(parents=True, exist_ok=True)
        for nr in nummers:
            doc = json.loads((boekmap / f"{nr}.json").read_text(encoding="utf-8"))
            lijst = []
            for vers in doc.get("verzen", []):
                item = {
                    "nummer": vers["nummer"],
                    "tekst": vers["tekst"],
                    "segmenten": [
                        {"id": s["id"], "tekst": s["tekst"]}
                        for s in vers.get("segmenten", [])
                    ],
                }
                if vers.get("citaten"):
                    item["html"] = vers_html(vers)
                    citaten += len(vers["citaten"])
                lijst.append(item)
            uit = {
                "editie": CODE,
                "boek": boek,
                "hoofdstuk": doc["hoofdstuk"],
                "kop": doc.get("kop", ""),
                "blokken": [
                    {"type": "kop", "niveau": "s1", "tekst": blok["kop"], "vers": blok["vanaf"]}
                    for blok in doc.get("blokken", [])
                ],
                "verzen": lijst,
            }
            (doel / boek / f"{nr}.json").write_text(
                json.dumps(uit, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8")
            hoofdstukken += 1
            verzen += len(lijst)

    manifest_pad = WORTEL / "data" / "vertalingen" / "manifest.json"
    manifest = json.loads(manifest_pad.read_text(encoding="utf-8"))
    manifest["edities"] = [e for e in manifest["edities"] if e["code"] != CODE]
    manifest["edities"].insert(0, {
        "code": CODE,
        "naam": "Open Parafrase Weergave",
        "taal": "nl",
        "richting": "ltr",
        "rechten": "publiek domein",
        "bron": "data/edities/opv",
        "boeken": boeken,
    })
    manifest_pad.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")
    print(f"{len(boeken)} boeken, {hoofdstukken} hoofdstukken, {verzen} verzen, {citaten} citaten")
    print("boeken:", ", ".join(boeken))


if __name__ == "__main__":
    main()
