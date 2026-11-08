"""Volledige leesuitgave als PDF: omslag op pagina 1, daarna de uitgave-informatie."""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

fitz = pytest.importorskip('fitz')
pytest.importorskip('reportlab')
import build_downloads  # noqa: E402
import build_pdf  # noqa: E402
from build_leespaginas import GROEPEN  # noqa: E402


def test_omslag_en_uitgave_informatie(tmp_path, monkeypatch):
    shutil.copytree(ROOT / 'fonts', tmp_path / 'fonts')
    ids = ' '.join(groep for _, groep in GROEPEN).split()
    books = [{'id': i, 'nameDutch': i.capitalize(), 'testament': 'OT', 'totalChapters': 1} for i in ids]
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data/books.json').write_text(json.dumps({'books': books}), encoding='utf-8')
    (tmp_path / 'data/stats.json').write_text(json.dumps({'version': 'v9.9.9'}), encoding='utf-8')
    for i in ids:
        (tmp_path / 'data' / i).mkdir()
        (tmp_path / 'data' / i / '1.json').write_text(json.dumps(
            {'verses': [{'number': 1, 'text2026': 'In het begin schiep God de hemel en de aarde.'}]}), encoding='utf-8')
    monkeypatch.setattr(build_pdf, 'ROOT', tmp_path)
    monkeypatch.setattr(build_downloads, 'DATA', str(tmp_path / 'data'))

    uit = tmp_path / 'volledig.pdf'
    assert build_pdf.build(uit) == {'boeken': 82, 'hoofdstukken': 82, 'verzen': 82}

    with fitz.open(uit) as pdf:
        omslag = pdf[0].get_text()
        # Spatiëring tussen kapitalen komt bij tekstextractie terug als losse spaties.
        zonder_spaties = omslag.replace(' ', '')
        for regel in ('OPEN VERTALING', 'Gods Woord', 'DE GEHELE HEILIGE SCHRIFT', 'Volledige leesuitgave',
                      'met de apocriefe boeken', 'openvertaling.nl'):
            assert regel.replace(' ', '') in zonder_spaties
        # Het omslag is een donker vlak over de hele pagina, zonder paginanummer.
        pixel = pdf[0].get_pixmap(dpi=20).pixel(2, 2)
        assert max(pixel) < 60
        assert omslag.strip().splitlines()[-1] == 'openvertaling.nl'
        over = pdf[1].get_text()
        assert 'Over deze uitgave' in over
        assert '82 boeken · 82 hoofdstukken · 82 verzen' in over and 'Uitgave v9.9.9' in over
        assert pdf.metadata['title'] == 'Open Vertaling - volledige leesuitgave'
