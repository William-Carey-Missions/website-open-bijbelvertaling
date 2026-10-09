from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_changelog_heeft_geen_eigen_legacy_linkernavigatie():
    html = (ROOT / "changelog.html").read_text(encoding="utf-8")

    assert 'id="topnav"' in html
    assert 'class="doc-sidebar"' not in html
    assert 'class="doc-shell"' not in html
    assert "width:220px" not in html


def test_changelog_is_bereikbaar_via_de_documentatie_op_over_ov():
    # Sinds de splitsing (2026-10-08) heeft de OV geen wiki meer; de
    # documentatie hangt aan over-ov.html#documentatie.
    over_ov = (ROOT / "over-ov.html").read_text(encoding="utf-8")

    assert 'id="documentatie"' in over_ov
    assert 'href="changelog.html"' in over_ov
