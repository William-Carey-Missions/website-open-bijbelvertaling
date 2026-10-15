from pathlib import Path


HTML = (Path(__file__).parents[1] / "statistieken.html").read_text(encoding="utf-8")


def test_statistieken_toont_alleen_actuele_kerncijfers():
    required = (
        'data-stat="books_total"',
        'data-stat="chapters_verified"',
        'data-stat="verses_verified"',
        'data-stat="chapters_verified_pct"',
        'data-stat="ot_verses_verified_pct"',
        'data-stat="nt_verses_verified_pct"',
        'data-stat="ap_verses_verified_pct"',
        'js/stats-inject.js',
    )
    for fragment in required:
        assert fragment in HTML, f"Actueel kerncijfer ontbreekt: {fragment}"


def test_statistieken_bevat_geen_verouderde_of_irrelevante_secties():
    forbidden = (
        "Sprekers (speech-v2)",
        "Voortgang in de tijd",
        "Per boek",
        "Easton's",
        "Nave’s",
        "Nave's",
    )
    for fragment in forbidden:
        assert fragment not in HTML, f"Verouderde sectie staat nog op de pagina: {fragment}"
