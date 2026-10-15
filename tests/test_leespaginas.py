"""Gewone leespagina's en llms-full.txt: de Bijbeltekst zonder JavaScript vindbaar."""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"


@pytest.fixture(scope="module")
def gebouwd(tmp_path_factory):
    uit = tmp_path_factory.mktemp("leespaginas")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_leespaginas.py"), "--uit", str(uit)],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    return uit


def vers(boek, hoofdstuk, nummer):
    data = json.loads((ROOT / "data" / boek / f"{hoofdstuk}.json").read_text(encoding="utf-8"))
    return next(v for v in data["verses"] if v["number"] == nummer)


def json_ld(pagina):
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', pagina, re.S).group(1))


def test_elk_hoofdstuk_van_alle_82_boeken_krijgt_een_pagina(gebouwd):
    boeken = json.loads((ROOT / "data" / "books-index.json").read_text(encoding="utf-8"))["boeken"]
    for boek in boeken:
        eerste = boek["eerste_hoofdstuk"]
        for nummer in range(eerste, eerste + boek["hoofdstukken"]):
            assert (gebouwd / "bijbel" / boek["id"] / f"{nummer}.html").exists(), (boek["id"], nummer)
        assert (gebouwd / "bijbel" / boek["id"] / "index.html").exists()
    assert len(list((gebouwd / "bijbel").glob("*/[0-9]*.html"))) == 1370


def test_hoofdstukpagina_bevat_de_ov_tekst_en_niet_de_vergelijkingsteksten(gebouwd):
    pagina = (gebouwd / "bijbel" / "johannes" / "3.html").read_text(encoding="utf-8")
    zestien = vers("johannes", 3, 16)
    assert html.escape(zestien["text2026"], quote=True) in pagina
    for veld in ("hsv", "nbg51"):
        if zestien.get(veld):
            assert zestien[veld] not in pagina
    assert '<link rel="canonical" href="https://openvertaling.nl/bijbel/johannes/3.html">' in pagina
    assert 'href="index.html#johannes/3"' in pagina
    ld = json_ld(pagina)
    assert ld["@type"] == "Chapter" and ld["license"] == CC0 and ld["name"] == "Johannes 3"


def test_navigatie_loopt_over_boekgrenzen_en_esther_apocrief_begint_bij_10(gebouwd):
    maleachi = (gebouwd / "bijbel" / "maleachi" / "4.html").read_text(encoding="utf-8")
    assert 'href="bijbel/mattheus/1.html" rel="next"' in maleachi
    esther = (gebouwd / "bijbel" / "estherapocrief" / "index.html").read_text(encoding="utf-8")
    assert 'href="bijbel/estherapocrief/10.html"' in esther
    assert not (gebouwd / "bijbel" / "estherapocrief" / "1.html").exists()


def test_opschrift_verschijnt_zonder_punthaken(gebouwd):
    pagina = (gebouwd / "bijbel" / "jezussirach" / "51.html").read_text(encoding="utf-8")
    assert "&lt;&lt;" not in pagina and '<span class="lp-opschrift">' in pagina


def test_overzicht_noemt_alle_boeken(gebouwd):
    overzicht = (gebouwd / "bijbel" / "index.html").read_text(encoding="utf-8")
    boeken = json.loads((ROOT / "data" / "books-index.json").read_text(encoding="utf-8"))["boeken"]
    for boek in boeken:
        assert f'href="bijbel/{boek["id"]}/"' in overzicht, boek["id"]
    assert "37.235 verzen" in overzicht


def test_llms_full_bevat_de_hele_tekst_met_licentie(gebouwd):
    tekst = (gebouwd / "llms-full.txt").read_text(encoding="utf-8")
    assert CC0 in tekst
    assert len(re.findall(r"^### ", tekst, re.M)) == 1370
    assert f"16 {vers('johannes', 3, 16)['text2026']}" in tekst
    assert "### Henoch 1" not in tekst and "### Esther (apocrief) 10" in tekst


def test_sitemap_bevat_de_leespaginas():
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://openvertaling.nl/bijbel/</loc>" in sitemap
    assert "<loc>https://openvertaling.nl/bijbel/johannes/3.html</loc>" in sitemap
    assert "<loc>https://openvertaling.nl/bijbel/henoch/</loc>" not in sitemap
    assert len(re.findall(r"<loc>https://openvertaling\.nl/bijbel/[^/]+/\d+\.html</loc>", sitemap)) == 1370


def test_serviceworker_haalt_mapadressen_vers_op():
    # /bijbel/genesis/ is een pagina; cache-first zou hem tot de volgende versie laten hangen.
    script = """
const fs = require('fs');
let handler;
const stale = { ok: true, body: 'stale', clone() { return this; } };
const fresh = { ok: true, body: 'fresh', clone() { return this; } };
global.self = { addEventListener: (name, fn) => { if (name === 'fetch') handler = fn; },
                location: { origin: 'https://example.test' }, clients: { claim: async () => {} } };
global.caches = { open: async () => ({ put: async () => {}, match: async () => stale }), keys: async () => [] };
global.fetch = async () => fresh;
eval(fs.readFileSync('sw.js', 'utf8'));
handler({
  request: { method: 'GET', url: 'https://example.test/bijbel/genesis/', headers: { has: () => false } },
  respondWith: promise => promise.then(response => process.stdout.write(response.body)),
});
"""
    uitkomst = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
    assert uitkomst.stdout == "fresh"


def test_uitrol_bouwt_de_leespaginas_en_git_bewaart_ze_niet():
    workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    bouwstap = next(regel for regel in workflow.splitlines() if "build_command:" in regel)
    assert "scripts/build_leespaginas.py" in bouwstap
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/bijbel/" in gitignore and "/llms-full.txt" in gitignore
