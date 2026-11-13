"""De leestekst gebruikt de hele breedte van de pagina, met en zonder kanttekeningen."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_met_kanttekeningen_geen_grens_van_1280_pixels():
    css = (ROOT / "css" / "publication.css").read_text(encoding="utf-8")
    assert "#verses-container { max-width:1280px" not in css
    assert "body.kt-popup-mode #content.reading-mode #verses-container { max-width:none !important; }" in css


def test_zonder_kanttekeningen_geen_grens_van_900_pixels():
    css = (ROOT / "css" / "ontwerp.css").read_text(encoding="utf-8")
    assert "max-width: 900px;" not in css
