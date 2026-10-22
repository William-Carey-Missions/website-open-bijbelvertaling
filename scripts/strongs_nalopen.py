#!/usr/bin/env python3
"""Strong-nummers nalopen: per grondtekstwoord zien bij welk Nederlands woord
het nummer staat, en verzen opnieuw koppelen.

  toon     python3 scripts/strongs_nalopen.py toon --boek genesis --hoofdstukken 1-3 [--glossen glossen.json]
           python3 scripts/strongs_nalopen.py toon --refs koppelingen.json   (alleen die verzen)
           Per vers: text2026 en per grondtekstwoord  i woord strong (glos) =«tekst»#voorkomen.
           =∅ betekent: niet afzonderlijk weergegeven (geen knop in de tekst).
           Meldingen: NIET GEVONDEN (de lezer kan het woord niet vinden en toont
           de nummers niet), en CLUSTER (meerdere nummers achter een woordgroep).
  schrijf  python3 scripts/strongs_nalopen.py schrijf --bestand koppelingen.json
           koppelingen.json: {"genesis/1/1": [{"tekst": "begin", "voorkomen": 1, "i": [0]}, ...]}
           Een onvertaald woord (zoals אֵת) mag een anker krijgen:
           {"anker": "hemel", "voorkomen": 1, "plaats": "voor", "i": [3]}; de lezer
           zet het nummer dan vóór (of met "na": achter) dat woord.
           Vervangt de woordnummers van ieder genoemd vers volledig. "i" zijn de
           grondtekst-indices uit 'toon'. Grondtekstwoorden die nergens genoemd
           worden, krijgen een koppeling zonder tekst (niet afzonderlijk
           weergegeven). Controle vooraf: (tekst, voorkomen) bestaat in text2026
           met dezelfde woordgrenzen als js/woordnummers.js, indices bestaan en
           ieder grondtekstwoord komt hooguit één keer voor. Bij één fout in een
           vers blijft dat vers ongewijzigd; de andere verzen worden geschreven.
           Elke wijziging komt in reviews/strongs/<boek>.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = ROOT / "reviews" / "strongs"
ZICHTBAAR = {"handmatig_gecontroleerd", "automatisch_hoog_vertrouwen"}


def bereik(tekst: str) -> range:
    a, _, b = tekst.partition("-")
    return range(int(a), int(b or a) + 1)


def laad(boek: str, h: int):
    pad = DATA / boek / f"{h}.json"
    return pad, json.loads(pad.read_text(encoding="utf-8"))


def bewaar(pad: Path, data) -> None:
    """Schrijf in dezelfde opmaak als het bestand al had."""
    oud = pad.read_text(encoding="utf-8")
    kern = oud.rstrip("\n")
    origineel = json.loads(oud)
    for inspring, scheiding in [(2, None), (1, None), (None, None), (None, (",", ":")), (4, None)]:
        if json.dumps(origineel, ensure_ascii=False, indent=inspring, separators=scheiding) == kern:
            break
    else:
        inspring, scheiding = 2, None
    pad.write_text(json.dumps(data, ensure_ascii=False, indent=inspring, separators=scheiding)
                   + oud[len(kern):], encoding="utf-8")


def platte_tekst(vers: dict) -> str:
    """De tekst zoals de lezer hem doorzoekt (zonder voetnootmarkeringen)."""
    html = vers.get("text2026_html") or vers.get("text2026") or ""
    html = re.sub(r"<(sup|button|script|style)\b.*?</\1>", "", html, flags=re.S)
    tekst = re.sub(r"<[^>]+>", "", html)
    return (tekst.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))


def plekken(tekst: str, doel: str) -> list[int]:
    """Beginposities van doel, hoofdletterongevoelig, met woordgrenzen als in de lezer."""
    if not doel:
        return []
    patroon = re.compile(r"(^|[^\w])(" + re.escape(doel) + r")(?=$|[^\w])", re.I)
    uit, pos = [], 0
    while True:
        m = patroon.search(tekst, pos)
        if not m:
            return uit
        uit.append(m.start(2))
        pos = m.start(2) + len(m.group(2))


def norm(woord: str) -> str:
    woord = unicodedata.normalize("NFD", woord or "")
    return "".join(c for c in woord if not unicodedata.combining(c) and c not in "/־׀").lower()


def indices(vers: dict) -> list:
    """Per koppeling de grondtekst-indices. In het OT verwijzen de opgeslagen
    bronindices naar de volgorde van de brondataset, niet naar 'grondtekst';
    dan zoeken we het woord op Strong-nummer en grondvorm."""
    gt = vers.get("grondtekst") or []
    gs = [(g.get("strongs"), norm(g.get("woord"))) if isinstance(g, dict) else (None, "") for g in gt]
    wn = vers.get("woordnummers") or []
    gebruikt, uit, later = set(), [], []
    for j, m in enumerate(wn):
        h = m.get("herkomst") or {}
        idx = h.get("grondindices", h.get("bronindices")) or []
        st = m.get("strongs") or []
        if (idx and len(idx) == len(st) and not set(idx) & gebruikt
                and all(isinstance(i, int) and 0 <= i < len(gs) and gs[i][0] == s for i, s in zip(idx, st))):
            uit.append(list(idx))
            gebruikt |= set(idx)
        else:
            uit.append(None)
            later.append(j)
    for j in later:
        m = wn[j]
        st, bw = m.get("strongs") or [], m.get("bronwoorden") or []
        res = []
        for k, s in enumerate(st):
            w = norm(bw[k]) if k < len(bw) else ""
            kand = [i for i, (g, _) in enumerate(gs) if g == s and i not in gebruikt and i not in res]
            exact = [i for i in kand if gs[i][1] == w]
            if not (exact or kand):
                res = None
                break
            res.append((exact or kand)[0])
        if res:
            gebruikt |= set(res)
        uit[j] = res or []
    return uit


def laad_glossen(pad: str | None) -> dict:
    pad = pad or os.environ.get("STRONGS_GLOSSEN")
    if pad and Path(pad).exists():
        return json.loads(Path(pad).read_text(encoding="utf-8"))
    return {}


def vers_weergave(boek: str, h: int, vers: dict, glossen: dict) -> str:
    tekst = platte_tekst(vers)
    gt = vers.get("grondtekst") or []
    wn = vers.get("woordnummers") or []
    idx = indices(vers)
    aan = {}
    meldingen = []
    for m, ii in zip(wn, idx):
        t = m.get("tekst") or m.get("anker") or ""
        occ = max(1, int(m.get("voorkomen") or 1))
        zichtbaar = not m.get("reviewstatus") or m["reviewstatus"] in ZICHTBAAR
        label = f"«{t}»#{occ}" if t else "∅"
        if not m.get("tekst") and t:
            # onvertaald woord: de lezer zet het nummer vóór (of na) dit ankerwoord
            label = f"{'vóór' if m.get('plaats') == 'voor' else 'na'} «{t}»#{occ}"
        if t and not zichtbaar:
            label += "(verborgen)"
        for i in ii:
            aan[i] = label
        if t and zichtbaar and len(plekken(tekst, t)) < occ:
            meldingen.append(f"NIET GEVONDEN «{t}»#{occ} i={ii}")
        if t and len([i for i in ii if (gt[i].get('strongs') if i < len(gt) and isinstance(gt[i], dict) else None)]) >= 3:
            meldingen.append(f"CLUSTER «{t}» i={ii}")
    regels = [f"{boek}/{h}/{vers['number']} | {tekst}"]
    delen = []
    for i, g in enumerate(gt):
        if not isinstance(g, dict):
            continue
        s = g.get("strongs") or ""
        glos = glossen.get(s, "") if s else ""
        doel = aan.get(i, "—" if s else "")
        delen.append(f"{i} {g.get('woord', '')} {s}{f' ({glos})' if glos else ''} ={doel}")
    regels.append("   " + " | ".join(delen))
    for m in meldingen:
        regels.append("   ! " + m)
    if gt and not wn:
        regels.append("   ! GEEN KOPPELINGEN")
    return "\n".join(regels)


def toon(a) -> int:
    glossen = laad_glossen(a.glossen)
    if a.refs:
        # alleen de verzen uit een koppelingenbestand (ter controle na 'schrijf')
        refs = list(json.loads(Path(a.refs).read_text(encoding="utf-8")))
        hoofdstukken = {}
        for ref in refs:
            boek, h, vn = ref.split("/")
            hoofdstukken.setdefault((boek, int(h)), set()).add(vn)
    else:
        if not (a.boek and a.hoofdstukken):
            print("geef --boek en --hoofdstukken, of --refs")
            return 2
        hoofdstukken = {(a.boek, h): None for h in bereik(a.hoofdstukken)}
    for (boek, h), verzen in hoofdstukken.items():
        if not (DATA / boek / f"{h}.json").exists():
            continue
        _, d = laad(boek, h)
        for v in d.get("verses", []):
            if verzen is not None and str(v.get("number")) not in verzen:
                continue
            if v.get("grondtekst") or v.get("woordnummers"):
                print(vers_weergave(boek, h, v, glossen))
    return 0


def token_record(g: dict) -> dict:
    return {
        "strongs": g.get("strongs"),
        "lemma_strongs": g.get("lemma_strongs"),
        "morfologie": g.get("morfologie") or g.get("morph"),
        "bronwoorden": g.get("woord") or "",
        "transliteraties": g.get("transliteratie") or "",
        "glossen": g.get("gloss") or g.get("betekenis") or "",
        "tvm": g.get("tvm"),
    }


def bouw(vers: dict, koppelingen: list, fouten: list, ref: str) -> list | None:
    tekst = platte_tekst(vers)
    gt = vers.get("grondtekst") or []
    oud = vers.get("woordnummers") or []
    basis = next((dict(m.get("herkomst") or {}) for m in oud if m.get("herkomst")), {})
    for sleutel in ("bronindices", "grondindices"):
        basis.pop(sleutel, None)
    # bronindex per grondtekstwoord, waar de oude data die kende
    oud_bron = {}
    for m, ii in zip(oud, indices(vers)):
        bron = (m.get("herkomst") or {}).get("bronindices") or []
        if len(bron) == len(ii):
            oud_bron.update(zip(ii, bron))
    gebruikt, nieuw, ok = set(), [], True
    for k in koppelingen:
        t = (k.get("tekst") or "").strip()
        anker = "" if t else (k.get("anker") or "").strip()
        plaats = k.get("plaats") or "voor"
        occ = int(k.get("voorkomen") or 1)
        ii = k.get("i") or []
        if not ii:
            fouten.append(f"{ref}: koppeling zonder indices {k}")
            ok = False
            continue
        if anker and plaats not in ("voor", "na"):
            fouten.append(f"{ref}: plaats moet 'voor' of 'na' zijn: {k}")
            ok = False
        doel = t or anker
        if doel and len(plekken(tekst, doel)) < occ:
            fouten.append(f"{ref}: «{doel}»#{occ} komt niet (zo vaak) voor in de tekst")
            ok = False
        for i in ii:
            if not isinstance(i, int) or not 0 <= i < len(gt) or not isinstance(gt[i], dict):
                fouten.append(f"{ref}: index {i} bestaat niet (0..{len(gt) - 1})")
                ok = False
            elif i in gebruikt:
                fouten.append(f"{ref}: grondtekstwoord {i} twee keer gekoppeld")
                ok = False
            gebruikt.add(i)
        if ok:
            nieuw.append((t, occ, ii, anker, plaats))
    if not ok:
        return None
    for i, g in enumerate(gt):
        if isinstance(g, dict) and g.get("strongs") and i not in gebruikt:
            nieuw.append(("", 1, [i], "", ""))
    records = []
    for t, occ, ii, anker, plaats in sorted(nieuw, key=lambda x: min(x[2])):
        tokens = [token_record(gt[i]) for i in ii]
        rec = {"tekst": t, "voorkomen": occ}
        if anker:
            rec["anker"], rec["plaats"] = anker, plaats
        for veld in ("strongs", "lemma_strongs", "morfologie", "bronwoorden", "transliteraties", "glossen", "tvm"):
            waarden = [tk[veld] for tk in tokens]
            if veld in ("lemma_strongs", "morfologie", "tvm") and not any(waarden):
                continue
            rec[veld] = waarden
        rec["status"] = "uitgelijnd" if t else "niet_afzonderlijk_weergegeven"
        rec["confidence"] = 0.9
        rec["reviewstatus"] = "automatisch_hoog_vertrouwen"
        herkomst = dict(basis)
        herkomst["grondindices"] = list(ii)
        herkomst["bronindices"] = [oud_bron.get(i, i) for i in ii]
        rec["herkomst"] = herkomst
        records.append(rec)
    return records


def kort(records: list, gt: list) -> list:
    return [[r.get("tekst") or (f"{r.get('plaats', 'voor')}:{r['anker']}" if r.get("anker") else ""),
             r.get("voorkomen"), r.get("strongs")] for r in records]


def schrijf(a) -> int:
    invoer = json.loads(Path(a.bestand).read_text(encoding="utf-8"))
    fouten, cache, log = [], {}, {}
    geschreven = 0
    for ref, koppelingen in invoer.items():
        try:
            boek, h, vn = ref.split("/")
            sleutel = (boek, int(h))
        except ValueError:
            fouten.append(f"{ref}: verwacht boek/hoofdstuk/vers")
            continue
        if sleutel not in cache:
            try:
                cache[sleutel] = laad(*sleutel)
            except FileNotFoundError:
                fouten.append(f"{ref}: hoofdstuk bestaat niet")
                continue
        _, d = cache[sleutel]
        vers = next((v for v in d.get("verses", []) if str(v.get("number")) == vn), None)
        if vers is None:
            fouten.append(f"{ref}: vers bestaat niet")
            continue
        records = bouw(vers, koppelingen, fouten, ref)
        if records is None:
            continue
        log.setdefault(boek, []).append({"ref": ref, "oud": kort(vers.get("woordnummers") or [], []),
                                         "nieuw": kort(records, []), "reden": a.reden})
        vers["woordnummers"] = records
        geschreven += 1
    for pad, d in cache.values():
        bewaar(pad, d)
    LOG.mkdir(parents=True, exist_ok=True)
    for boek, regels in log.items():
        # één write per boek, zodat parallelle schrijvers geen regels door elkaar halen
        with (LOG / f"{boek}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regels))
    if fouten:
        print("NIET GESCHREVEN (rest wel):\n" + "\n".join(fouten[:100]))
    print(f"{geschreven} verzen opnieuw gekoppeld")
    return 1 if fouten else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="actie", required=True)
    t = sub.add_parser("toon")
    t.add_argument("--boek")
    t.add_argument("--hoofdstukken")
    t.add_argument("--refs", help="koppelingenbestand: toon alleen die verzen")
    t.add_argument("--glossen")
    s = sub.add_parser("schrijf")
    s.add_argument("--bestand", required=True)
    s.add_argument("--reden", default="nalopen")
    a = ap.parse_args()
    sys.exit(toon(a) if a.actie == "toon" else schrijf(a))
