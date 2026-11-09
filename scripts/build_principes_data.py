#!/usr/bin/env python3
"""Bouwt data/principes-data.json voor de principes-overzichtspagina.

principes.html toont per principe hoe vaak het is toegepast en waar. Die
gegevens zitten verspreid over ruim 1.100 hoofdstukbestanden in het veld
`phraseDiff`; ze bij het openen van de pagina verzamelen zou betekenen dat de
bezoeker de hele Bijbel binnenhaalt. Vandaar dit vooraf berekende bestand.

Dat het vooraf berekend is, is ook de valkuil: het loopt achter zodra er een
sweep is gedraaid, en dan lijken principes op de site minder vindplaatsen te
hebben dan ze werkelijk raken. **Draai dit script na elke tekstwijziging.**

De vindplaatsen worden per principe afgekapt (zie MAX_VERZEN). De telling in
`counts` blijft wel volledig, dus de pagina kan "745 plaatsen, eerste 300
getoond" laten zien zonder het bestand te laten opzwellen.

Sleutels zijn kort gehouden omdat ze honderdduizenden keren voorkomen:
  b = boek-id, n = boeknaam, c = hoofdstuk, v = vers, o = oud, x = nieuw

Gebruik:
    python scripts/build_principes_data.py
"""
import collections
import json
import os
import sys

WORTEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_VERZEN = 300


def boeknamen():
    """Boek-id naar Nederlandse naam, uit data/books.json."""
    with open(os.path.join(WORTEL, "data", "books.json"), encoding="utf-8") as fh:
        boeken = json.load(fh)
    if isinstance(boeken, dict):
        boeken = boeken.get("books") or next(iter(boeken.values()))
    return {b["id"]: b.get("nameDutch") or b.get("name") or b["id"] for b in boeken}


def main():
    data = os.path.join(WORTEL, "data")
    namen = boeknamen()
    counts = collections.Counter()
    verzen = collections.defaultdict(list)

    def revision_entries(obj, boek, hst=None, vers=None, marker=None):
        for r in obj.get("herzieningen", []):
            pid = r["principe"]
            counts[pid] += 1
            if len(verzen[pid]) < MAX_VERZEN:
                verzen[pid].append({"b":boek,"n":namen.get(boek,boek),"c":hst,"v":vers,
                    "o":r["old"],"x":r["new"],"k":r["soort"],"m":marker,
                    "r":r["reden"],"q":r["bronpassage"],"s":r["bronveld"],"t":r["datum"],"id":r["id"],"f":r.get("veld","text2026"),"e":r.get("editie")})

    for boek in sorted(os.listdir(data)):
        map_ = os.path.join(data, boek)
        if not os.path.isdir(map_) or not os.path.exists(os.path.join(map_, "1.json")):
            continue
        manifest = os.path.join(data, boek + ".json")
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as fh:
                revision_entries(json.load(fh).get("bookIntro") or {}, boek)
        bestanden = [f for f in os.listdir(map_) if f.endswith(".json")]
        # op hoofdstuknummer, niet alfabetisch: anders komt 10 voor 2
        bestanden.sort(key=lambda f: int(f[:-5]) if f[:-5].isdigit() else 0)
        for fn in bestanden:
            with open(os.path.join(map_, fn), encoding="utf-8") as fh:
                d = json.load(fh)
            hst = d.get("number")
            for v in d.get("verses", []):
                revision_entries(v, boek, hst, v.get("number"))
                for note in v.get("marginNotes") or []:
                    if isinstance(note, dict):
                        revision_entries(note, boek, hst, v.get("number"), note.get("marker"))
                for p in v.get("phraseDiff") or []:
                    pid = p.get("principe")
                    if not pid:
                        continue
                    for one_id in pid if isinstance(pid, list) else [pid]:
                        counts[one_id] += 1
                        if len(verzen[one_id]) < MAX_VERZEN:
                            verzen[one_id].append({
                                "b": boek,
                                "n": namen.get(boek, boek),
                                "c": hst,
                                "v": v.get("number"),
                                "o": p.get("old", ""),
                                "x": p.get("new", ""),
                            })

    edition = os.path.join(data, "vertalingen", "nl-opv")
    if os.path.isdir(edition):
        for boek in sorted(os.listdir(edition)):
            folder = os.path.join(edition, boek)
            if not os.path.isdir(folder): continue
            for fn in sorted(os.listdir(folder)):
                if not fn.endswith(".json") or not fn[:-5].isdigit(): continue
                with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                    chapter = json.load(fh)
                for verse in chapter.get("verzen", []):
                    revision_entries(verse, boek, chapter["hoofdstuk"], verse["nummer"])

    uit = {"counts": dict(counts), "verses": {k: v for k, v in verzen.items()}}
    pad = os.path.join(data, "principes-data.json")
    with open(pad, "w", encoding="utf-8", newline="") as fh:
        json.dump(uit, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")

    afgekapt = sum(1 for pid in verzen if counts[pid] > MAX_VERZEN)
    print(f"{len(counts)} principes, {sum(counts.values())} toepassingen")
    print(f"  {afgekapt} principes hebben meer dan {MAX_VERZEN} vindplaatsen; "
          f"daarvan is de lijst afgekapt, de telling niet")
    print(f"  geschreven naar {os.path.relpath(pad, WORTEL)} "
          f"({os.path.getsize(pad) // 1024} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
