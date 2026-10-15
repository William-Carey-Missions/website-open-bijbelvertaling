"""De voorlezing hoort bij de Open Vertaling.

De opnames lezen de tekst van de Open Vertaling voor. Staat er in de lezer een
andere teksteditie, zoals de Open Parafrase Weergave, dan mag de speler die
opname niet aanbieden.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

HARNAS = r"""
const fs = require('fs');
const vm = require('vm');
const pad = process.argv[process.argv.length - 1];
const ctx = {
    localStorage: { getItem: () => null, setItem: () => {} },
    OV_ASSETS: { url: (bestand) => bestand },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(pad, 'utf8'), ctx);
const [boek, hoofdstukken] = Object.entries(ctx.AUDIO_AVAILABLE).find(([, lijst]) => lijst.length);
const hoofdstuk = hoofdstukken[0];
const uitkomst = { zonderEditielaag: ctx.OV_AUDIO.available(boek, hoofdstuk) };
for (const editie of ['nl-ov', 'nl-opv', 'en-webbe']) {
    ctx.TekstEditie = { code: () => editie };
    uitkomst[editie] = ctx.OV_AUDIO.available(boek, hoofdstuk);
}
console.log(JSON.stringify(uitkomst));
"""


def test_opname_alleen_bij_de_open_vertaling():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is niet beschikbaar")
    uit = subprocess.run(
        [node, "-e", HARNAS, str(ROOT / "js" / "audio-available.js")],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    uitkomst = json.loads(uit.stdout)
    assert uitkomst["zonderEditielaag"] is True
    assert uitkomst["nl-ov"] is True
    assert uitkomst["nl-opv"] is False
    assert uitkomst["en-webbe"] is False


def test_hoofdstuk_zonder_tekst_in_de_editie_stopt_de_voorlezing():
    app = (ROOT / "js" / "chapter-renderer.js").read_text(encoding="utf-8")
    tak = re.search(r"if \(chapter\._unavailable\) \{(.*?)\n        \}", app, re.S)
    assert tak, "de tak voor een hoofdstuk zonder tekst in de editie is niet gevonden"
    assert "App._updateAudioPlayer(bookId, chapterNum);" in tak.group(1)
