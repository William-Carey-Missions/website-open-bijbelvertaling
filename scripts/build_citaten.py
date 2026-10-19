#!/usr/bin/env python3
"""Bouw lichte citaatbestanden voor embed.js uit de hoofdstukdata.

Een bewijstekst op een naslagpagina heeft van een hoofdstuk alleen het
versnummer en de tekst van de Open Vertaling nodig. Het volledige
hoofdstukbestand draagt daarnaast de grondtekst, de kanttekeningen, de tekst
van 1637 en 1888 en de woordnummers, en weegt daardoor een half tot een hele
megabyte; de tekst zelf is daar ongeveer drie procent van. Dit script schrijft
per hoofdstuk alleen wat embed.js nodig heeft:

- data/citaat/boeken.js                      naam en testament per boek
- data/citaat/<boek>/<hoofdstuk>.js          versnummer, opgemaakte en platte tekst
- data/citaat/<boek>/<hoofdstuk>.woorden.js  de woordnummers, alleen voor Strong

Het zijn scriptbestanden en geen JSON, omdat een <script> ook vanaf een andere
site geladen mag worden. Open Gods Woord en andere sites die embed.js insluiten
halen hun tekst zo rechtstreeks van openvertaling.nl, zonder dat de server
daarvoor CORS hoeft toe te staan.

De uitvoer staat niet in git; de uitrol bouwt hem opnieuw uit de data.
Draai vanuit de repo-root:  python scripts/build_citaten.py
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lees_json(pad):
    return json.loads(pad.read_text(encoding="utf-8"))


def script(sleutel, data):
    """Een aanroep van OSV._ontvang met de data als JavaScript-letterwaarde.

    JSON is geldig JavaScript, op twee tekens na die in oudere browsers een
    tekenreeks afbreken; die gaan als escape mee. "</" wordt "<\\/", zodat het
    bestand ook binnen een inline-script niets afsluit.
    """
    tekst = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    tekst = tekst.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("</", "<\\/")
    return f"OSV._ontvang({json.dumps(sleutel)},{tekst});\n"


def versregel(vers):
    """Versnummer, opgemaakte en platte tekst — met dezelfde terugval als embed.js."""
    nummer = vers.get("number", vers.get("nummer"))
    html = vers.get("text2026_html") or vers.get("html") or vers.get("text2026") or vers.get("tekst") or ""
    plat = vers.get("text2026") or vers.get("tekst") or ""
    return [nummer, html, plat]


def schrijf(pad, inhoud):
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(inhoud, encoding="utf-8", newline="\n")
    return len(inhoud.encode("utf-8"))


def bouw(data_map, uit_map, alleen=None):
    """Schrijf de citaatbestanden; geeft (hoofdstukken, bytes bron, bytes uit).

    Met `alleen` (een verzameling boek-id's) komen alleen die boeken mee; de
    boekenlijst blijft compleet.
    """
    boeken = lees_json(data_map / "books.json")["books"]
    schrijf(uit_map / "boeken.js", script("boeken", {
        boek["id"]: {"naam": boek["nameDutch"], "testament": boek["testament"]} for boek in boeken
    }))

    hoofdstukken = bron_bytes = uit_bytes = 0
    for boek in boeken:
        map_ = data_map / boek["id"]
        if (alleen is not None and boek["id"] not in alleen) or not map_.is_dir():
            continue
        for pad in sorted(map_.glob("*.json"), key=lambda p: (len(p.stem), p.stem)):
            if not pad.stem.isdigit():
                continue
            verzen = lees_json(pad)
            verzen = verzen.get("verses") or verzen.get("verzen") or []
            woorden = {str(vers.get("number", vers.get("nummer"))): vers["woordnummers"]
                       for vers in verzen if vers.get("woordnummers")}
            sleutel = f"{boek['id']}/{pad.stem}"
            uit_bytes += schrijf(uit_map / boek["id"] / f"{pad.stem}.js", script(sleutel, {
                "verzen": [versregel(vers) for vers in verzen],
                # embed.js vraagt het woordnummerbestand alleen op als het er is:
                # een ontbrekend bestand geeft bij de server een HTML-pagina terug.
                "woorden": bool(woorden),
            }))
            if woorden:
                schrijf(uit_map / boek["id"] / f"{pad.stem}.woorden.js", script(f"{sleutel}#woorden", woorden))
            bron_bytes += pad.stat().st_size
            hoofdstukken += 1
    return hoofdstukken, bron_bytes, uit_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="map met books.json en de hoofdstukken")
    parser.add_argument("--uit", type=Path, default=ROOT / "data" / "citaat", help="map voor de citaatbestanden")
    args = parser.parse_args()

    hoofdstukken, bron, uit = bouw(args.data, args.uit)
    if not hoofdstukken:
        sys.exit(f"Geen hoofdstukken gevonden in {args.data}")
    print(f"{hoofdstukken} hoofdstukken: {bron / 1e6:.0f} MB hoofdstukdata, "
          f"{uit / 1e6:.1f} MB citaattekst ({uit / bron:.1%}) in {args.uit}")


if __name__ == "__main__":
    main()
