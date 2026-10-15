"""De citaatopmaak in de leeseditie van de Open Parafrase Weergave.

De opmaak wordt uit de sprekersdata van de parafrase gebouwd
(scripts/opv_leeseditie.py). Die mag de tekst zelf niet veranderen, en moet
dezelfde conventie volgen als de Open Vertaling: de aankondiging buiten de span.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from opv_leeseditie import klasse, vers_html  # noqa: E402

EDITIE = ROOT / "data" / "vertalingen" / "nl-opv"
SPAN_OPEN = re.compile(r'<span class="(god-speaks|direct-speech|angel-speaks|devil-speaks)"><i>')


def _kaal(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def _verzen():
    for pad in sorted(EDITIE.glob("*/*.json")):
        for vers in json.loads(pad.read_text(encoding="utf-8"))["verzen"]:
            yield f"{pad.parent.name} {pad.stem}:{vers['nummer']}", vers


def _genest_goed(h):
    stapel = []
    for m in re.finditer(r"</?(?:span|i)\b[^>]*>", h):
        tag = m.group(0)
        if tag.startswith("</"):
            if not stapel or stapel.pop() != tag[2:-1]:
                return False
        else:
            stapel.append(re.match(r"<(\w+)", tag).group(1))
    return not stapel


def test_opmaak_laat_de_tekst_ongemoeid_en_is_welgevormd():
    fouten = []
    met_opmaak = 0
    for ref, vers in _verzen():
        h = vers.get("html")
        if h is None:
            continue
        met_opmaak += 1
        if _kaal(h) != vers["tekst"]:
            fouten.append(f"{ref}: tekst veranderd")
        if not _genest_goed(h):
            fouten.append(f"{ref}: opmaak niet goed genest")
        if re.search(r"<i>\s|\s</i>", h):
            fouten.append(f"{ref}: witruimte binnen de span")
    assert met_opmaak > 5000, met_opmaak
    assert not fouten, fouten[:20]


def test_aankondiging_blijft_buiten_de_span():
    h = next(v["html"] for ref, v in _verzen() if ref == "genesis 3:9")
    assert h.startswith("De HEERE God riep Adam en vroeg: <span"), h
    # de slang citeert God: een span binnen een span
    h = next(v["html"] for ref, v in _verzen() if ref == "genesis 3:1")
    assert len(SPAN_OPEN.findall(h)) == 2, h
    assert '<span class="direct-speech"><i>Heeft God echt gezegd: <span class="god-speaks">' in h, h


def test_sprekerstype_bepaalt_de_klasse():
    assert klasse({"id": "god", "type": "god"}) == "god-speaks"
    assert klasse({"id": "jezus", "type": "god"}) == "god-speaks"
    assert klasse({"id": "gabriel", "type": "angel"}) == "angel-speaks"
    assert klasse({"id": "heilige-geest", "type": "spirit"}) == "god-speaks"
    assert klasse({"id": "duivel", "type": "spirit"}) == "devil-speaks"
    assert klasse({"id": "mozes", "type": "human"}) == "direct-speech"
    assert klasse({"id": "volk", "type": "group"}) == "direct-speech"


def test_kruisende_citaten_worden_geweigerd():
    vers = {
        "tekst": "a b c",
        "segmenten": [{"id": "s1", "tekst": "a "}, {"id": "s2", "tekst": "b "}, {"id": "s3", "tekst": "c"}],
        "citaten": [
            {"id": "q1", "startSegment": "s1", "endSegment": "s2", "spreker": {"id": "x", "type": "human"}},
            {"id": "q2", "startSegment": "s2", "endSegment": "s3", "spreker": {"id": "y", "type": "human"}},
        ],
    }
    try:
        vers_html(vers)
    except ValueError as fout:
        assert "kruist" in str(fout)
    else:
        raise AssertionError("kruisende citaten zijn niet geweigerd")
