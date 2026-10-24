"""Markdown-uitgaven met kanttekeningen en de achtergrondpagina (scripts/build_markdown.py)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_leespaginas import godsnaam  # noqa: E402


@pytest.fixture(scope="module")
def gebouwd(tmp_path_factory):
    uit = tmp_path_factory.mktemp("markdown")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_markdown.py"), "--uit", str(uit),
                    "--boeken", "johannes", "psalmen"], cwd=ROOT, check=True, capture_output=True, text=True)
    return uit


def verzen(boek, hoofdstuk):
    return json.loads((ROOT / "data" / boek / f"{hoofdstuk}.json").read_text(encoding="utf-8"))["verses"]


def test_drie_edities_per_boek_en_een_overzicht(gebouwd):
    for editie in ("ov", "sv1888", "sv1637"):
        assert (gebouwd / "markdown" / editie / "johannes.md").exists()
        assert (gebouwd / "markdown" / f"{editie}-volledig.md").exists()
    index = (gebouwd / "markdown" / "index.md").read_text(encoding="utf-8")
    assert "https://openvertaling.nl/markdown/sv1637/johannes.md" in index
    assert (gebouwd / "markdown" / "wijzigingsprincipes.md").exists()


def test_kanttekeningen_staan_als_voetnoot_op_de_plek_van_de_marker(gebouwd):
    tekst = (gebouwd / "markdown" / "ov" / "johannes.md").read_text(encoding="utf-8")
    assert "**1** [^1-1-a] In[^1-1-1] het begin was[^1-1-2] het Woord" in tekst
    noot = next(n for n in verzen("johannes", 1)[0]["marginNotes"] if n["marker"] == "1")
    assert f"[^1-1-1]: Kanttekening 1: {noot['text2026']}" in tekst
    assert "[^1-1-a]: Verwijzing a: " in tekst
    # Iedere verwijzing heeft precies één voetnoot.
    zonder_definities = re.sub(r"^\[\^[^\]]+\]:", "", tekst, flags=re.M)
    verwijzingen = set(re.findall(r"\[\^([^\]]+)\]", zonder_definities))
    definities = set(re.findall(r"^\[\^([^\]]+)\]:", tekst, re.M))
    assert verwijzingen == definities


def test_volledig_bestand_maakt_voetnoten_uniek_per_boek(gebouwd):
    tekst = (gebouwd / "markdown" / "ov-volledig.md").read_text(encoding="utf-8")
    definities = re.findall(r"^\[\^([^\]]+)\]:", tekst, re.M)
    assert "johannes-1-1-a" in definities and "psalmen-3-2-1" in definities
    assert len(definities) == len(set(definities))


def test_beschermde_vergelijkingsteksten_komen_er_niet_in(gebouwd):
    alles = "\n".join(p.read_text(encoding="utf-8") for p in (gebouwd / "markdown").rglob("*.md"))
    for vers in verzen("johannes", 3) + verzen("psalmen", 23):
        for veld in ("hsv", "nbg51"):
            beschermd = vers.get(veld) or ""
            # Soms is een zin woordelijk gelijk aan de (vrije) Statenvertaling; dat is geen lek.
            vrij = " ".join(str(vers.get(v) or "") for v in ("text2026", "textSV1888", "text1637"))
            if len(beschermd) > 30 and beschermd not in vrij:
                assert beschermd not in alles, (vers["number"], veld)
    assert "build_markdown" in (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")


def test_godsnaam_zoals_de_leesweergave():
    assert godsnaam("O JAHWEH! hoe") == "O HEERE! hoe"
    assert godsnaam("Toen zei God JAHWEH") == "Toen zei de HEERE God"
    assert godsnaam("Dit zegt JAHWEH van de legermachten.") == "Dit zegt de HEERE der heirscharen."
    assert godsnaam("Want JAHWEH is goed. JAHWEH zij geloofd") == "Want de HEERE is goed. De HEERE zij geloofd"
    assert godsnaam("vertrouw op JAHWEH") == "vertrouw op de HEERE"


def test_ov_en_1888_in_eigen_spelling(gebouwd):
    ov = (gebouwd / "markdown" / "ov" / "psalmen.md").read_text(encoding="utf-8")
    assert "JAHWEH" not in ov and "**2** O HEERE! hoe zijn mijn tegenstanders" in ov
    sv1888 = (gebouwd / "markdown" / "sv1888" / "johannes.md").read_text(encoding="utf-8")
    assert "In[^1-1-1] den beginne was" in sv1888
    sv1637 = (gebouwd / "markdown" / "sv1637" / "johannes.md").read_text(encoding="utf-8")
    assert "INDEN [^1-1-1] beginne was" in sv1637


def test_achtergrondpagina_uit_markdown(gebouwd):
    pagina = (gebouwd / "achtergrond.html").read_text(encoding="utf-8")
    assert "<title>Achtergrond van de Open Vertaling</title>" in pagina
    assert '<link rel="canonical" href="https://openvertaling.nl/achtergrond.html">' in pagina
    assert "<h2>Wat is de Open Vertaling?</h2>" in pagina
    assert '<a href="https://openvertaling.nl/markdown/wijzigingsprincipes.md">' in pagina
    assert "<li><strong>naamvallen</strong>:" in pagina
