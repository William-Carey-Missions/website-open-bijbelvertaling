from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_topnav_loads_global_options_host_without_reader_redirect():
    # De wiki-shell (die de opties naar zijn frame doorgaf) bestaat sinds de
    # splitsing niet meer op de OV; elke pagina laadt de host via de topnav.
    topnav = read("js/topnav.js")

    assert 'js/global-options-host.js' in topnav
    assert 'index.html?opties=1' not in topnav


def test_reader_has_no_floating_or_mobile_options_opener():
    html = read("index.html")
    topnav = read("js/topnav.js")

    assert 'id="sidebar-right-open"' not in html
    assert 'id="mobile-opties-btn"' not in html
    assert 'id="topnav-weergave"' in topnav
    assert 'id="topnav-mobile-weergave"' in topnav


def test_options_headers_use_shared_navigation_palette():
    css = read("css/style.css")
    assert ".options-category > summary" in css
    assert "background: var(--navy)" in css
    assert ".options-section-heading" in css
