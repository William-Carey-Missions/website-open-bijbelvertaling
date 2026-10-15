"""Regressietests voor de naam en payoff in linkvoorbeelden en appmetadata."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYOFF = "Een herziening van de Statenvertaling"


def test_homepage_linkmetadata_gebruikt_open_vertaling_en_de_vaste_payoff():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert f"<title>Open Vertaling — {PAYOFF}</title>" in html
    assert f'<meta property="og:title" content="Open Vertaling — {PAYOFF}">' in html
    assert f'<meta name="twitter:title" content="Open Vertaling — {PAYOFF}">' in html
    assert PAYOFF in html
    assert "Open Statenvertaling" not in html


def test_installatiemetadata_gebruikt_dezelfde_projectnaam_en_payoff():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "Open Vertaling"
    assert manifest["description"].startswith(PAYOFF)
