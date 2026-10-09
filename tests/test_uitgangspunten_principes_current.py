from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_uitgangspunten_beschrijft_de_actuele_werkwijze():
    html = read("uitgangspunten.html")

    assert "data/&lt;boek&gt;/&lt;hoofdstuk&gt;.json" in html
    assert "data/verified-chapters.json" in html
    assert "menselijke controle" in html
    assert "phraseDiff" in html
    assert "data/wijzigingsprincipes.json" in html
    assert 'href="principes.html"' in html
    assert 'href="bronnen.html"' in html


def test_uitgangspunten_bevat_geen_verouderde_techniek_of_oude_standaarden():
    html = read("uitgangspunten.html")

    for stale in (
        "v0.18.4",
        "data/&lt;boek&gt;.json",
        "/hertaal-kanttekeningen",
        "apply_uitgangspunten_all.py",
        "apply_speech_v2.py",
        "GET /api/paintings",
        "Spreuken 8:",
        "HEERE</strong> de standaard",
    ):
        assert stale not in html


def test_documentatiepagina_s_staan_op_zichzelf_met_de_bovenbalk():
    # Sinds de splitsing geen wiki-shell meer: de bovenbalk (Documentatie)
    # is de navigatie, er wordt niet meer doorgestuurd.
    for name in ("uitgangspunten.html", "principes.html"):
        html = read(name)
        assert "doc-sidebar" not in html
        assert "doc-shell" not in html
        assert "wiki.html" not in html
        assert 'id="topnav"' in html


def test_principes_legt_status_en_herkomst_van_de_lijst_uit():
    html = read("principes.html")
    js = read("js/principes.js")

    assert "data/wijzigingsprincipes.json" in html
    assert "data/principes-data.json" in html
    assert "menselijk nagekeken" in html
    assert "uitzonderingen" in html
    assert "v0.18.4" not in html
    assert "tussen SV1888 en de Open Vertaling" in js
    assert "tussen SV1888 en de OSV" not in js
    assert "const totalPrincipes = principesData.length" in js
