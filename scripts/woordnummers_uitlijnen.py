#!/usr/bin/env python3
"""Strong-nummers per woord uitlijnen waar nu één anker voor het hele vers staat.

Bij een deel van het NT (o.a. Hebreeën t/m Judas en Openbaring) koppelt
woordnummers het hele vers aan alle Griekse woorden; de lezer zet dan alle
nummers achter het laatste woord. Dit hulpmiddel vervangt zo'n versanker door
koppelingen per Nederlands woord(groep), op dezelfde manier als in Mattheüs.

  toon    python3 scripts/woordnummers_uitlijnen.py toon --boek hebreeen --hoofdstuk 1
          JSON per vers met een versanker: text2026 en de genummerde Griekse
          woorden (index, woord, strong, morfologie, glos).
  schrijf python3 scripts/woordnummers_uitlijnen.py schrijf --boek hebreeen --hoofdstuk 1 --bestand uitlijning.json
          uitlijning.json: {"<vers>": [{"tekst": "God", "voorkomen": 1, "bronindices": [5]}, ...]}
          Controleert per koppeling dat (tekst, voorkomen) in text2026 bestaat
          (zelfde woordgrenzen als js/woordnummers.js), dat de indices bestaan en
          dat geen Grieks woord twee keer gebruikt wordt. Bij een fout wordt niets
          geschreven. Schrijft data/<boek>/<h>.json (woordnummers) en
          data/woordnummers-inline/<boek>.json bij, in dezelfde opmaak.

De nieuwe koppelingen krijgen reviewstatus "automatisch_hoog_vertrouwen"
(niet door een mens nagekeken) en status "uitgelijnd".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LIJSTVELDEN = ("strongs", "lemma_strongs", "morfologie", "bronwoorden", "transliteraties", "glossen", "tvm")
# Het oorspronkelijke versanker wordt bij de eerste uitlijning bewaard, zodat
# een controleur de uitlijning later opnieuw kan schrijven.
ANKERS = DATA / "woordnummers-review" / "versankers"


def anker_van(boek: str, h: int, vers: dict):
    """Het versanker van dit vers: uit de data, of uit de bewaarde kopie."""
    if is_versanker(vers):
        return vers["woordnummers"][0]
    pad = ANKERS / f"{boek}-{h}.json"
    if pad.exists():
        return json.loads(pad.read_text(encoding="utf-8")).get(str(vers["number"]))
    return None


def is_versanker(vers: dict) -> bool:
    wn = vers.get("woordnummers") or []
    return (len(wn) == 1 and isinstance(wn[0], dict)
            and (wn[0].get("tekst") or "").strip() == (vers.get("text2026") or "").strip()
            and len(wn[0].get("strongs") or []) > 1)


def voorkomens(tekst: str, doel: str) -> int:
    patroon = re.compile(r"(^|[^\w])(" + re.escape(doel) + r")(?=$|[^\w])", re.U)
    n, pos = 0, 0
    while True:
        m = patroon.search(tekst, pos)
        if not m:
            return n
        n += 1
        pos = m.start(2) + len(m.group(2))


def laad(boek: str, h: int):
    pad = DATA / boek / f"{h}.json"
    return pad, json.loads(pad.read_text(encoding="utf-8"))


def bewaar(pad: Path, data) -> None:
    oud = pad.read_text(encoding="utf-8")
    kern = oud.rstrip("\n")
    origineel = json.loads(oud)
    vormen = [(2, None), (1, None), (None, None), (None, (",", ":")), (4, None)]
    for inspring, scheiding in vormen:
        if json.dumps(origineel, ensure_ascii=False, indent=inspring, separators=scheiding) == kern:
            break
    else:
        inspring, scheiding = 2, None
    pad.write_text(json.dumps(data, ensure_ascii=False, indent=inspring, separators=scheiding)
                   + oud[len(kern):], encoding="utf-8")


def toon(a) -> int:
    _, d = laad(a.boek, a.hoofdstuk)
    uit = []
    for v in d.get("verses", []):
        anker = anker_van(a.boek, a.hoofdstuk, v)
        if anker is None or (not a.herzien and not is_versanker(v)):
            continue
        glossen = anker.get("glossen") or []
        uit.append({
            "vers": v["number"],
            "text2026": v["text2026"],
            "grieks": [{"i": i, "woord": g.get("woord"), "strong": g.get("strongs"),
                        "morf": g.get("morfologie"), "glos": glossen[i] if i < len(glossen) else ""}
                       for i, g in enumerate(v.get("grondtekst") or [])],
        })
        if a.herzien and not is_versanker(v):
            uit[-1]["huidig"] = [{"tekst": k["tekst"], "voorkomen": k["voorkomen"],
                                  "bronindices": (k.get("herkomst") or {}).get("bronindices")}
                                 for k in v.get("woordnummers") or []]
    print(json.dumps(uit, ensure_ascii=False, indent=0))
    return 0


def schrijf(a) -> int:
    pad, d = laad(a.boek, a.hoofdstuk)
    uitlijning = json.loads(Path(a.bestand).read_text(encoding="utf-8"))
    fouten, nieuw = [], {}
    verzen = {str(v["number"]): v for v in d.get("verses", [])}
    for vn, koppelingen in uitlijning.items():
        v = verzen.get(str(vn))
        anker = anker_van(a.boek, a.hoofdstuk, v) if v is not None else None
        if anker is None:
            fouten.append(f"{vn}: geen vers met versanker (of bewaard anker)")
            continue
        n_grieks = len(v.get("grondtekst") or [])
        gebruikt = set()
        records = []
        for k in koppelingen:
            tekst, occ, idx = k.get("tekst", ""), int(k.get("voorkomen", 1) or 1), k.get("bronindices") or []
            if not tekst or not idx:
                fouten.append(f"{vn}: lege tekst of indices in {k}")
                continue
            if voorkomens(v["text2026"], tekst) < occ:
                fouten.append(f"{vn}: '{tekst}' #{occ} komt niet (zo vaak) voor in de tekst")
            for i in idx:
                if not isinstance(i, int) or i < 0 or i >= n_grieks:
                    fouten.append(f"{vn}: index {i} bestaat niet (0..{n_grieks - 1})")
                elif i in gebruikt:
                    fouten.append(f"{vn}: Grieks woord {i} twee keer gekoppeld")
                gebruikt.add(i)
            rec = {"tekst": tekst, "voorkomen": occ}
            for veld in LIJSTVELDEN:
                lijst = anker.get(veld)
                if isinstance(lijst, list) and len(lijst) == n_grieks:
                    rec[veld] = [lijst[i] for i in idx if isinstance(i, int) and 0 <= i < n_grieks]
            rec["status"] = "uitgelijnd"
            rec["confidence"] = 0.9
            rec["reviewstatus"] = "automatisch_hoog_vertrouwen"
            herkomst = dict(anker.get("herkomst") or {})
            herkomst["bronindices"] = idx
            rec["herkomst"] = herkomst
            records.append(rec)
        nieuw[str(vn)] = records
    if fouten:
        print("FOUT — niets geschreven:\n" + "\n".join(fouten[:80]))
        return 1
    ANKERS.mkdir(parents=True, exist_ok=True)
    ap = ANKERS / f"{a.boek}-{a.hoofdstuk}.json"
    bewaard = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else {}
    for vn in nieuw:
        if is_versanker(verzen[vn]):
            bewaard[vn] = verzen[vn]["woordnummers"][0]
    ap.write_text(json.dumps(bewaard, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    for vn, records in nieuw.items():
        verzen[vn]["woordnummers"] = records
    bewaar(pad, d)
    # data/woordnummers-inline/<boek>.json wordt apart bijgewerkt met 'sync'
    # (één schrijver per boek; parallelle uitlijners raken zo alleen hun eigen
    # hoofdstukbestand).
    print(f"OK: {len(nieuw)} verzen uitgelijnd ({sum(len(r) for r in nieuw.values())} koppelingen)")
    return 0


def sync(a) -> int:
    """Neem de uitgelijnde verzen uit de hoofdstukbestanden over in het inline-boekbestand."""
    ip = DATA / "woordnummers-inline" / f"{a.boek}.json"
    inline = json.loads(ip.read_text(encoding="utf-8"))
    n = 0
    for pad in sorted((DATA / a.boek).glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        if not pad.stem.isdigit():
            continue
        d = json.loads(pad.read_text(encoding="utf-8"))
        for v in d.get("verses", []):
            wn = v.get("woordnummers") or []
            if wn and all(isinstance(k, dict) and k.get("status") == "uitgelijnd" for k in wn):
                inline.setdefault("chapters", {}).setdefault(pad.stem, {})[str(v["number"])] = wn
                n += 1
    bewaar(ip, inline)
    print(f"{a.boek}: {n} uitgelijnde verzen in het inline-bestand")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="actie", required=True)
    sy = sub.add_parser("sync")
    sy.add_argument("--boek", required=True)
    for naam in ("toon", "schrijf"):
        s = sub.add_parser(naam)
        s.add_argument("--boek", required=True)
        s.add_argument("--hoofdstuk", type=int, required=True)
        if naam == "toon":
            s.add_argument("--herzien", action="store_true", help="ook al uitgelijnde verzen, met de huidige koppelingen")
        if naam == "schrijf":
            s.add_argument("--bestand", required=True)
    a = ap.parse_args()
    sys.exit({"toon": toon, "schrijf": schrijf, "sync": sync}[a.actie](a))
