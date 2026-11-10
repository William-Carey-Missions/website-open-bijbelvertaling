"""De mobiele weergave: de tekst staat voorop en niets drijft eroverheen."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lees(pad):
    return (ROOT / pad).read_text(encoding="utf-8")


def test_statistiekknop_drijft_op_de_telefoon_niet_over_de_tekst():
    bron = lees("js/analytics.js")
    assert "@media(max-width:768px),(pointer:coarse){#analytics-settings{position:static" in bron


def test_zustersites_zijn_op_de_telefoon_goed_te_raken():
    assert ".ka-fam-links a::after" in lees("js/topnav.js")


def test_onderbalk_laat_de_tekst_niet_door_de_knoppen_lopen():
    css = lees("css/style.css")
    assert "background: linear-gradient(to top, var(--bg-page) calc(100% - 6px), transparent);" in css
    assert "body { padding-bottom: calc(98px + env(safe-area-inset-bottom, 0px)); }" in css
    # De voortgangsbalk ligt binnen de balk, op de paginakleur, niet over de laatste regel.
    assert "#mobile-footer-nav .mfn-scrubber { top: 6px; }" in css


def test_voortgangsbalk_is_op_de_telefoon_te_raken():
    assert "@media (pointer: coarse) { .mfn-scrubber { top: -12px; height: 20px;" in lees("css/style.css")
