#!/usr/bin/env python3
"""Kanttekeningen nalezen: tonen, corrigeren en elke wijziging vastleggen.

  toon     python3 scripts/kanttekeningen_nalezen.py toon --boek ruth --hoofdstukken 1-2
           JSON-lijst met per verklarende kanttekening: id (boek/hst/vers/marker),
           text1637, textSV1888 (zonder de aangehaalde Bijbelverzen) en text2026.
  schrijf  python3 scripts/kanttekeningen_nalezen.py schrijf --bestand bevindingen.json
           bevindingen.json: {"correcties": [{"id", "oud", "nieuw", "reden", "soort"}],
                              "twijfel":    [{"id", "voorstel", "reden", "soort"}]}
           Een correctie wordt alleen toegepast als "oud" exact gelijk is aan de
           huidige text2026 (zo overschrijft niemand een ander). Alleen text2026
           van de kanttekening verandert. Alles komt in
           reviews/kanttekeningen/<boek>.jsonl (gecorrigeerd én twijfel).

Toegestane soorten correctie (veilig): sweepschade, ontbrekend-woord,
leesteken, afwijking-1888, spelfout. Al het andere is twijfel.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = ROOT / "reviews" / "kanttekeningen"
VEILIG = {"sweepschade", "ontbrekend-woord", "leesteken", "afwijking-1888", "spelfout"}
# In textSV1888 staan na de kanttekening soms de aangehaalde verzen voluit
# ("Genesis 1:1: In den beginne …"). Die horen niet bij de kanttekening zelf.
AANHALING = re.compile(r"\s(?:[1-4] )?[A-ZÀ-Ý][a-zà-ÿë]+(?: [a-zà-ÿ]+)? \d+:\d+ ?: ")


def bereik(tekst: str) -> range:
    if "-" in tekst:
        a, b = tekst.split("-")
        return range(int(a), int(b) + 1)
    return range(int(tekst), int(tekst) + 1)


def kern_1888(tekst: str, eigen: str) -> str:
    """textSV1888 zonder aangehaalde verzen, tenzij die ook in text2026 staan."""
    if not tekst:
        return ""
    m = AANHALING.search(tekst)
    if m and not AANHALING.search(eigen or ""):
        return tekst[:m.start()].strip()
    return tekst


def laad(boek: str, hst: int):
    pad = DATA / boek / f"{hst}.json"
    return pad, json.loads(pad.read_text(encoding="utf-8"))


def bewaar(pad: Path, data) -> None:
    """Schrijf in exact dezelfde opmaak als het bestand al had (inspringing,
    slotregel), zodat de diff alleen de gewijzigde kanttekening toont."""
    oud = pad.read_text(encoding="utf-8")
    kern = oud.rstrip("\n")
    for inspring in (2, 1, None, 4):
        if json.dumps(json.loads(oud), ensure_ascii=False, indent=inspring) == kern:
            break
    else:
        inspring = 2
    pad.write_text(json.dumps(data, ensure_ascii=False, indent=inspring) + oud[len(kern):], encoding="utf-8")


def toon(a) -> int:
    uit = []
    for hst in bereik(a.hoofdstukken):
        pad, data = laad(a.boek, hst)
        for vers in data.get("verses", []):
            for m in vers.get("marginNotes") or []:
                if not isinstance(m, dict) or m.get("type") != "explanatory" or not m.get("text2026"):
                    continue
                uit.append({
                    "id": f"{a.boek}/{hst}/{vers['number']}/{m['marker']}",
                    "text1637": m.get("text1637", ""),
                    "textSV1888": kern_1888(m.get("textSV1888", ""), m["text2026"]),
                    "text2026": m["text2026"],
                })
    print(json.dumps(uit, ensure_ascii=False, indent=0))
    return 0


def schrijf(a) -> int:
    bevindingen = json.loads(Path(a.bestand).read_text(encoding="utf-8"))
    per_boek = {}
    fouten, toegepast = [], 0
    cache = {}
    for c in bevindingen.get("correcties", []):
        boek, hst, vers, marker = c["id"].split("/")
        if c.get("soort") not in VEILIG:
            fouten.append(f"{c['id']}: soort {c.get('soort')!r} is geen veilige correctie; zet hem bij twijfel")
            continue
        sleutel = (boek, int(hst))
        if sleutel not in cache:
            cache[sleutel] = laad(boek, int(hst))
        pad, data = cache[sleutel]
        noot = next((m for v in data["verses"] if str(v["number"]) == vers
                     for m in (v.get("marginNotes") or []) if isinstance(m, dict) and m.get("marker") == marker), None)
        if noot is None:
            fouten.append(f"{c['id']}: kanttekening niet gevonden")
            continue
        if noot["text2026"] != c["oud"]:
            fouten.append(f"{c['id']}: 'oud' komt niet exact overeen met de huidige text2026")
            continue
        if not c["nieuw"].strip() or c["nieuw"] == c["oud"]:
            fouten.append(f"{c['id']}: 'nieuw' is leeg of gelijk aan 'oud'")
            continue
        noot["text2026"] = c["nieuw"]
        toegepast += 1
        per_boek.setdefault(boek, []).append({"actie": "gecorrigeerd", **c})
    for t in bevindingen.get("twijfel", []):
        per_boek.setdefault(t["id"].split("/")[0], []).append({"actie": "twijfel", **t})
    if fouten:
        print("NIET TOEGEPAST:\n" + "\n".join(fouten))
    for (boek, hst), (pad, data) in cache.items():
        bewaar(pad, data)
    LOG.mkdir(parents=True, exist_ok=True)
    for boek, regels in per_boek.items():
        with (LOG / f"{boek}.jsonl").open("a", encoding="utf-8") as fh:
            for r in regels:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{toegepast} correcties toegepast, {len(bevindingen.get('twijfel', []))} twijfelgevallen vastgelegd")
    return 1 if fouten else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="actie", required=True)
    t = sub.add_parser("toon"); t.add_argument("--boek", required=True); t.add_argument("--hoofdstukken", required=True)
    s = sub.add_parser("schrijf"); s.add_argument("--bestand", required=True)
    a = ap.parse_args()
    sys.exit(toon(a) if a.actie == "toon" else schrijf(a))
