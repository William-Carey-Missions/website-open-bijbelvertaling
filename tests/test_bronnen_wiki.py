"""Bronnen is een gewone documentatiepagina van de OV (zonder wiki)."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_bronnen_staat_in_de_documentatie_en_opent_zelfstandig():
    over_ov = read("over-ov.html")
    bronnen = read("bronnen.html")

    assert 'href="bronnen.html"' in over_ov
    # Geen lokale wiki-link meer; alleen nog de link naar Open Gods Woord.
    assert not re.search(r'\shref="wiki\.html', over_ov)
    # Geen doorsturen meer naar een wiki-shell: de pagina staat op zichzelf.
    assert "location.replace" not in bronnen
    assert 'id="topnav"' in bronnen


def test_bronnenlijst_beschrijft_ook_de_huidige_vertalingen_en_geografiebron():
    bronnen = read("bronnen.html")

    for naam in (
        "Louis Segond 1910",
        "World English Bible British Edition",
        "Arabic Van Dyck",
        "Reina-Valera 1909",
        "OpenBible.info Bible Geocoding Data",
    ):
        assert naam in bronnen

    assert "CC0 / publiek domein" in bronnen
    assert "niet-commercieel" not in bronnen.lower()


def test_machineleesbare_bestanden_openen_niet_binnen_het_wikiframe():
    bronnen = read("bronnen.html")
    bestandslinks = re.findall(
        r"<a\b[^>]*href=[\"'](?!https?://|mailto:|#)([^\"']+\.(?:json|txt))[\"'][^>]*>",
        bronnen,
    )

    assert bestandslinks
    for href in bestandslinks:
        tag = re.search(
            rf"<a\b[^>]*href=[\"']{re.escape(href)}[\"'][^>]*>", bronnen
        ).group(0)
        assert 'target="_blank"' in tag
