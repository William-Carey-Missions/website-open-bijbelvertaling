#!/usr/bin/env python3
"""Verwerk de Google-opmerkingen bij Jubileeën.

Jubileeën is uit het Ge'ez vertaald en heeft dus geen tekst uit 1888. De
principes gelden hier voor de vertaling zelf; een woorddiff is er niet.

1. Oude naamvallen en woorden. Alle 69 tweede naamvallen met "des" (N3),
   "Gods" (V402), "wiens" (N18, V312) en "neder" (V354) in het boek.
2. "wakers" wordt "wachters" (V1642), op verzoek, ook in Henoch.
3. Twee vertaalpunten: in 10:21 stond "maten" waar het Ge'ez "bakstenen"
   heeft, en in 3:17-18 mist de Ge'ez-tekst die hier gevolgd wordt een stuk
   dat de editie van Charles wel heeft. Het eerste is verbeterd; het tweede
   krijgt een voetnoot, want de vertaling volgt het Ge'ez en niet Charles.
4. De opdracht van de engel in 2:1 is als citaat gemarkeerd.

De verzen die gesplitst moesten worden (11:3 tot en met 15:11) zijn eerder
gesplitst; dat staat alleen in de reviewlijst.

Draaien vanuit de repo-root:  python scripts/apply_google_review_jubileeen.py
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_hulp import registreer_principes, schrijf_reviewlijst, verwerk_correcties  # noqa: E402
from sweep_principe import gebalanceerd, kaal, lees, schrijf  # noqa: E402

BOEK = "jubileeen"
NAAM = "Jubileeën"

# --- 1. naamvallen en oude woorden -----------------------------------------

# Volgorde telt: de langere vorm eerst.
DES = [
    ("en des toorns", "en van de gramschap"),  # 36:10, naast "van de toorn"
    ("stonden op des nachts", "stonden 's nachts op"),
    ("des aangezichts", "van het aangezicht"),
    ("des vuurs", "van het vuur"),
    ("des hemels", "van de hemel"),
    ("des oordeels", "van het oordeel"),
    ("des verderfs", "van het verderf"),
    ("des harten", "van het hart"),
    ("des nachts", "'s nachts"),
    ("des velds", "van het veld"),
    ("des morgens", "'s morgens"),
    ("des avonds", "'s avonds"),
    ("des Eeds", "van de Eed"),
    ("des Gezichts", "van het Gezicht"),
    ("des jaars", "van het jaar"),
    ("des persoons", "van de persoon"),
    ("des levens", "van het leven"),
    ("des doods", "van de dood"),
    ("des konings", "van de koning"),
]

VASTE_CORRECTIES = {
    (1, 2): [("de berg Gods", "de berg van God", "V402"),
             ("de heerlijkheid Gods", "de heerlijkheid van God", "V402")],
    (1, 3): [("de heerlijkheid Gods", "de heerlijkheid van God", "V402")],
    (2, 1): [("het woord Gods", "het woord van God", "V402")],
    (3, 1): [("het woord Gods", "het woord van God", "V402")],
    (4, 12): [("de naam Gods", "de naam van God", "V402")],
    (18, 9): [("een vrees Gods is", "godvrezend is", "MR-JUB-002")],
    (18, 11): [("een vrees Gods bent", "godvrezend bent", "MR-JUB-002")],
    (7, 1): [("wiens naam Lubar is", "waarvan de naam Lubar is", "N18")],
    (15, 14): [("wiens voorhuidsvlees", "van wie het voorhuidsvlees", "V312")],
    (15, 26): [("wiens voorhuidsvlees", "van wie het voorhuidsvlees", "V312")],
    (7, 13): [("en het mishaagde hem dat", "en het beviel hem niet dat", "MR-JUB-001")],
    (10, 21): [("De volle muur was dertien maten in haar breedte",
                "Er waren dertien hele bakstenen in haar breedte", "MR-JUB-003")],
}

WAKERS_BOEKEN = (("jubileeen", NAAM), ("henoch", "Henoch"))


def verzen_van(boek):
    for pad in sorted((ROOT / "data" / boek).glob("*.json"), key=lambda p: int(p.stem)):
        for vers in json.loads(io.open(pad, encoding="utf-8").read())["verses"]:
            yield int(pad.stem), vers["number"], vers["text2026"]


def correcties_voor_jubileeen():
    per_vers = {sleutel: list(paren) for sleutel, paren in VASTE_CORRECTIES.items()}
    for hoofdstuk, nummer, tekst in verzen_van(BOEK):
        # Vaste correcties eerst, zodat de patronen hieronder de bijgewerkte
        # tekst zien en elkaar niet in de weg zitten.
        for oud, nieuw, _ in per_vers.get((hoofdstuk, nummer), []):
            tekst = tekst.replace(oud, nieuw)
        extra = []
        for oud, nieuw in DES:
            if oud in tekst:
                extra.append((oud, nieuw, "N3"))
                tekst = tekst.replace(oud, nieuw)
        if re.search(r"\bneder", tekst):
            extra.append(("neder", "neer", "V354"))
            tekst = tekst.replace("neder", "neer")
        if "wakers" in tekst:
            extra.append(("wakers", "wachters", "V1642"))
        if extra:
            per_vers.setdefault((hoofdstuk, nummer), []).extend(extra)
    return per_vers


def correcties_voor_henoch():
    return {(hoofdstuk, nummer): [("wakers", "wachters", "V1642")]
            for hoofdstuk, nummer, tekst in verzen_van("henoch") if "wakers" in tekst}


NIEUWE_PRINCIPES = [
    {
        "id": "MR-JUB-001", "categorie": "Menselijke review",
        "oud": "het mishaagde hem", "nieuw": "het beviel hem niet",
        "toelichting": "Beoordeeld in de review van Jubileeën; niet zonder "
                       "herbeoordeling buiten dit bereik toepassen.",
        "regex": "", "voorbeeld": "jubileeen 7:13",
        "bereik": {BOEK: ["7:13"]}, "bron": "menselijke-review",
    },
    {
        "id": "MR-JUB-002", "categorie": "Menselijke review",
        "oud": "een vrees Gods zijn", "nieuw": "godvrezend zijn",
        "toelichting": "'Een vrees Gods' is hier een persoon die God vreest, geen "
                       "eigenschap van God. Beoordeeld in de review van Jubileeën.",
        "regex": "", "voorbeeld": "jubileeen 18:11",
        "bereik": {BOEK: ["18:9", "18:11"]}, "bron": "menselijke-review",
    },
    {
        "id": "MR-JUB-003", "categorie": "Menselijke review",
        "oud": "dertien maten", "nieuw": "dertien hele bakstenen",
        "toelichting": "Vertaalcorrectie: het Ge'ez heeft ግንፋል, 'baksteen', hetzelfde "
                       "woord als in 10:20. Beoordeeld in de review van Jubileeën.",
        "regex": "", "voorbeeld": "jubileeen 10:21",
        "bereik": {BOEK: ["10:21"]}, "bron": "menselijke-review",
    },
]


def wachters_principe(bereik):
    return {
        "id": "V1642", "categorie": "Verouderde woorden",
        "oud": "wakers", "nieuw": "wachters",
        "toelichting": "De hemelse wezens die in Henoch en Jubileeën over de mensen "
                       "waken (Ge'ez ትጉሃን). Op verzoek van de eigenaar 'wachters', de "
                       "gangbare Nederlandse benaming. Geldt voor de vertaling uit het "
                       "Ge'ez; in de parafrase van Henoch staat nog 'wakers'.",
        "regex": r"\bwakers\b", "voorbeeld": "jubileeen 4:22",
        "bereik": bereik,
    }


# --- 2. citaat en voetnoten -------------------------------------------------

ENGEL = '<span class="angel-speaks"><i>'
SLUIT = "</i></span>"

VOETNOTEN = {
    (3, 17): ("nauwkeurig.",
              "De Ge'ez-tekst die deze vertaling volgt (editie Ran, Beta maṣāḥǝft) gaat "
              "hier van de zeven jaren meteen over op het antwoord van de vrouw. De editie "
              "van Charles heeft daartussen dat de slang in de tweede maand, op de "
              "zeventiende dag, naar de vrouw kwam en vroeg of God geboden had niet te "
              "eten van alle bomen van de hof. In haar antwoord (3:18) volgt bij Charles "
              "na 'Eet' nog dat God van de boom in het midden van de hof gezegd heeft dat "
              "zij daarvan niet mogen eten en hem niet mogen aanraken, opdat zij niet "
              "sterven. Vergelijk Genesis 3:1-3."),
    (10, 21): ("bakstenen",
               "Ge'ez ግንፋል is 'baksteen', hetzelfde woord als in 10:20. Tot 2026 stond "
               "hier 'dertien maten'."),
}


def markeer_engel(vers):
    """2:1: de opdracht van de engel aan Mozes, na 'zeggende:'."""
    html = vers["text2026_html"]
    if ENGEL in html:
        return False
    aankondiging = "zeggende: "
    i = html.index(aankondiging) + len(aankondiging)
    nieuw = html[:i] + ENGEL + html[i:] + SLUIT
    if kaal(nieuw) != kaal(vers["text2026"]) or not gebalanceerd(nieuw):
        raise ValueError("Jubileeën 2:1: citaat niet veilig te markeren")
    vers["text2026_html"] = nieuw
    return True


def zet_voetnoot(vers, anker, tekst):
    html = vers["text2026_html"]
    noten = vers.setdefault("marginNotes", [])
    if any(noot.get("text2026") == tekst for noot in noten):
        return False
    marker = "abcdefghij"[len(noten)]
    positie = html.index(anker) + len(anker)
    vers["text2026_html"] = (html[:positie] + '<sup class="note-marker" data-note="%s">%s</sup>'
                             % (marker, marker) + html[positie:])
    noten.append({"marker": marker, "type": "explanatory", "text1637": "", "text2026": tekst})
    if kaal(vers["text2026_html"]) != kaal(vers["text2026"]):
        raise ValueError("voetnoot verandert de leestekst")
    return True


def werk_hoofdstuk_bij(hoofdstuk, handeling):
    pad = ROOT / "data" / BOEK / ("%d.json" % hoofdstuk)
    data, vorm = lees(str(pad))
    verzen = {item["number"]: item for item in data["verses"]}
    if handeling(verzen):
        schrijf(str(pad), data, vorm)
        return 1
    return 0


def lees_tekst(pad):
    with io.open(pad, encoding="utf-8", newline="") as bestand:
        return bestand.read()


def schrijf_tekst(pad, tekst):
    """Schrijf zonder dat Windows de regeleinden omzet."""
    with io.open(pad, "w", encoding="utf-8", newline="") as bestand:
        bestand.write(tekst)


def werk_staging_bij():
    """De vertaling in ethiopische-boeken/vertaling volgt dezelfde verbetering."""
    map_ = ROOT / "ethiopische-boeken" / "vertaling" / BOEK
    tien = map_ / "10.md"
    tekst = lees_tekst(tien)
    tekst = tekst.replace("De volle muur was dertien maten in haar breedte",
                          "Er waren dertien hele bakstenen in haar breedte")
    noot = "- vers 21: " + VOETNOTEN[(10, 21)][1]
    if noot not in tekst:
        tekst = tekst.rstrip("\n") + ("\n" if "## Voetnoten" in tekst else "\n\n## Voetnoten\n") + noot + "\n"
    schrijf_tekst(tien, tekst)
    drie = map_ / "3.md"
    tekst = lees_tekst(drie)
    noot = "- vers 17-18: " + VOETNOTEN[(3, 17)][1]
    if noot not in tekst:
        tekst = tekst.rstrip("\n") + ("\n" if "## Voetnoten" in tekst else "\n\n## Voetnoten\n") + noot + "\n"
    schrijf_tekst(drie, tekst)


def werk_woordenlijst_bij():
    pad = ROOT / ".claude" / "skills" / "geez-vertalen" / "woordenlijst.md"
    if not pad.exists():
        return False
    tekst = lees_tekst(pad)
    oud = '| ትጉሃን | de wakers | lett. "de wakenden"; hemelse wezens (1:5) |'
    nieuw = ('| ትጉሃን | de wachters | lett. "de wakenden"; hemelse wezens (1:5); tot 2026 '
             '"de wakers" |')
    if oud not in tekst:
        return False
    schrijf_tekst(pad, tekst.replace(oud, nieuw))
    return True


# --- 3. reviewlijst ---------------------------------------------------------

SPLITS = "Gesplitst; in heel Jubileeën zijn 49 samengevoegde verzen gesplitst, met behoud van de citaatopmaak."

BESLUITEN = [
    ("1:3", "[Principe] Heerlijkheid van God", "principe", "verwerkt",
     "'de heerlijkheid Gods' is nu 'de heerlijkheid van God'; zo ook elders in "
     "Jubileeën (1:2, 2:1, 3:1, 4:12), en 'een vrees Gods' is 'godvrezend' (18:9, 18:11)."),
    ("1:27", "[Oude woorden vervangen] [Principe] [Oude woorden vervangen] Des aangezichts",
     "principe", "verwerkt",
     "'de engel des aangezichts' is nu 'de engel van het aangezicht'. Alle 69 tweede "
     "naamvallen met 'des' in Jubileeën zijn vervangen, zoals 'de tafelen van de hemel' "
     "en 'de dag van het oordeel' (principe N3)."),
    ("2:1", "[Citatie]  Hele hoofdstuk", "citatieopmaak", "verwerkt",
     "De opdracht van de engel aan Mozes in 2:1 is nu als citaat gemarkeerd. De rest van "
     "het hoofdstuk is, zoals het hele boek, het verslag dat de engel aan Mozes doet; "
     "als dat als citaat werd opgemaakt, stond vrijwel heel Jubileeën in een citaat. "
     "Gods woorden in 2:19-20 waren al gemarkeerd."),
    ("3:18", "Mis je niet een tekst hirr?", "vertaling", "verwerkt",
     "Ja. De Ge'ez-tekst die deze vertaling volgt mist hier dat de slang de vrouw "
     "nadert en haar een vraag stelt, en de tweede helft van haar antwoord; de editie "
     "van Charles heeft die wel. Dat staat nu in een kanttekening bij 3:17. De tekst zelf "
     "is niet aangevuld, omdat de vertaling de Ge'ez-grondtekst volgt."),
    ("4:22", "[Principe] Wachters ipv wakers", "principe", "verwerkt",
     "'wakers' is nu 'wachters', in Jubileeën en in Henoch (principe V1642). De vaste "
     "term in de woordenlijst voor het vertalen uit het Ge'ez is mee aangepast. De "
     "Open Parafrase Weergave van Henoch gebruikt nog 'wakers'."),
    ("5:3", "[Oude woorden vervangen] Verordening", "tekst_eenduidig", "afgedekt",
     "Staat als 'ordening'."),
    ("7:1", "Wiens - van wie de naam", "tekst_eenduidig", "verwerkt",
     "Nu 'waarvan de naam Lubar is', omdat het om een berg gaat. Ook in 15:14 en 15:26 "
     "staat geen 'wiens' meer."),
    ("7:13", "[Oude woorden vervangen] Mishaagde", "tekst_eenduidig", "verwerkt",
     "'het mishaagde hem' is nu 'het beviel hem niet'."),
    ("10:21", "Bereken de ‘maat", "vertaling", "verwerkt",
     "Er stond 'dertien maten', maar het Ge'ez heeft 'bakstenen', zoals in 10:20. Nu: "
     "'Er waren dertien hele bakstenen in haar breedte'. Een aantal bakstenen is niet "
     "om te rekenen."),
    ("10:21", "Bereken de hoogte", "eenheden", "afgedekt",
     "De leesoptie voor maten rekent de hoogte om: 'vijfduizend vierhonderddrieëndertig "
     "el (ongeveer 2,4 km)'."),
    ("10:26", "[Oude woorden vervangen] Neder", "tekst_eenduidig", "verwerkt",
     "'neder' is nu 'neer', overal in Jubileeën (principe V354)."),
    ("11:3", "Vs 4 splitsen", "versindeling", "verwerkt", SPLITS),
    ("11:9", "Vers splitsen", "versindeling", "verwerkt", SPLITS),
    ("11:19", "Splits vers", "versindeling", "verwerkt", SPLITS),
    ("11:23", "Splits vers , checkheel jubilieen", "versindeling", "verwerkt", SPLITS),
    ("12:29", "Splits", "versindeling", "verwerkt", SPLITS),
    ("15:11", "Verzen splitten , alles nalopen", "versindeling", "verwerkt",
     SPLITS + " De citaatopmaak van 15:11 staat weer goed."),
]


def main():
    jubileeen = correcties_voor_jubileeen()
    henoch = correcties_voor_henoch()
    wachters = {boek: ["%d:%d" % sleutel for sleutel in sorted(correcties)
                       if any(p == "V1642" for _, _, p in correcties[sleutel])]
                for boek, correcties in ((BOEK, jubileeen), ("henoch", henoch))}
    registreer_principes("MR-JUB-", NIEUWE_PRINCIPES)
    registreer_principes("V1642", [wachters_principe({b: r for b, r in wachters.items() if r})],
                         gebruikt=["N3", "N18", "V312", "V354", "V402", "V1642",
                                   "MR-JUB-001", "MR-JUB-002", "MR-JUB-003"])
    tekst = verwerk_correcties(BOEK, NAAM, jubileeen)
    tekst += verwerk_correcties("henoch", "Henoch", henoch)

    over = [("%d:%d" % (h, n), m.group(0)) for h, n, t in verzen_van(BOEK)
            for m in re.finditer(r"\bdes\b|\bneder|\bGods\b|\bwiens\b|\bwakers\b", t)]
    if over:
        raise ValueError("nog over in Jubileeën: %s" % over)

    opmaak = werk_hoofdstuk_bij(2, lambda verzen: markeer_engel(verzen[1]))
    for (hoofdstuk, nummer), (anker, noot) in VOETNOTEN.items():
        opmaak += werk_hoofdstuk_bij(hoofdstuk, lambda verzen, n=nummer, a=anker, t=noot:
                                     zet_voetnoot(verzen[n], a, t))
    werk_staging_bij()
    woordenlijst = werk_woordenlijst_bij()
    lijst = schrijf_reviewlijst(BOEK, NAAM, BESLUITEN)
    print("%d verzen tekst, %d hoofdstukken opmaak of voetnoot, woordenlijst %s, %d "
          "meldingen in de reviewlijst." % (tekst, opmaak, "bijgewerkt" if woordenlijst
                                             else "ongewijzigd", lijst))


if __name__ == "__main__":
    main()
