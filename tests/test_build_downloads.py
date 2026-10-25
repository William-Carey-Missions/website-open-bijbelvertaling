"""Build and inspect actual release artifacts from a small isolated corpus."""
import json
import re
import zipfile
import xml.etree.ElementTree as ET
import pytest
from scripts import build_downloads as builder


@pytest.fixture()
def release(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "genesis").mkdir(parents=True)
    (data / "books.json").write_text(json.dumps({"books": [{
        "id": "genesis", "nameDutch": "Genesis", "totalChapters": 2,
    }]}))
    for chapter in (1, 2):
        (data / f"genesis/{chapter}.json").write_text(json.dumps({
            "number": chapter, "verses": [{"number": 1, "text2026": f"Hoofdstuk {chapter}.",
                "text2026_html": f"<span>Hoofdstuk {chapter}.</span><sup>1</sup>"}],
        }))
    (data / "verified-chapters.json").write_text(json.dumps({"genesis": [1]}))
    (data / "stats.json").write_text(json.dumps({"version": "test", "date": "test"}))
    monkeypatch.setattr(builder, "ROOT", str(tmp_path))
    monkeypatch.setattr(builder, "DATA", str(data))
    monkeypatch.setattr(builder, "UIT", str(tmp_path / "downloads"))
    assert builder.main() == 0
    return tmp_path / "downloads"


def test_epub_contains_all_published_chapters_and_valid_xml(release):
    with zipfile.ZipFile(release / builder.EPUB_NAAM) as epub:
        first = epub.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        assert epub.read("mimetype").decode() == "application/epub+zip"
        for name in epub.namelist():
            if name.endswith((".xhtml", ".opf", ".xml")):
                ET.fromstring(epub.read(name))
        text = epub.read("OEBPS/genesis.xhtml").decode()
        assert set(re.findall(r'<h2 id="h(\d+)">', text)) == {"1", "2"}
        assert "<sup" not in text
        assert "Hoofdstuk 2." in text
        assert "CC0" in epub.read("OEBPS/colofon.xhtml").decode()
        nav = epub.read("OEBPS/nav.xhtml").decode()
        for href in re.findall(r'href="([^"#]+)', nav):
            assert "OEBPS/" + href in epub.namelist()
        manifest = epub.read("OEBPS/content.opf").decode()
        hrefs = set(re.findall(r'<item[^>]+href="([^"]+)"', manifest))
        for name in epub.namelist():
            if name.startswith("OEBPS/") and name.endswith(".xhtml"):
                assert name[len("OEBPS/"):] in hrefs


def test_release_index_and_unfiltered_source_zip(release):
    index = json.loads((release / "index.json").read_text())
    assert len(index["uitgaven"]) == 2
    for item in index["uitgaven"]:
        assert (release / item["bestand"]).stat().st_size == item["bytes"]
        assert item["omschrijving"].strip()
    with zipfile.ZipFile(release / builder.ZIP_NAAM) as archive:
        assert {"data/books.json", "data/genesis/1.json", "data/genesis/2.json"} <= set(archive.namelist())


def test_interrupted_build_preserves_previous_release_and_removes_partial_output(tmp_path):
    target = tmp_path / "archive.zip"
    target.write_bytes(b"previous release")
    with pytest.raises(RuntimeError):
        with builder.atomic_output(str(target)) as temporary:
            from pathlib import Path
            Path(temporary).write_bytes(b"incomplete")
            raise RuntimeError("interrupted build")
    assert target.read_bytes() == b"previous release"
    assert not (tmp_path / "archive.zip.tmp").exists()


def test_pdf_and_markdown_urls_point_to_existing_artifacts(release):
    root = release.parent
    (release / builder.PDF_NAAM).write_bytes(b"%PDF-1.4\n")
    (root / "markdown").mkdir()
    (root / "markdown/ov-volledig.md").write_text("# Open Vertaling\n")
    assert builder.main() == 0
    index = json.loads((release / "index.json").read_text())
    formats = {item['url']: item for item in index['uitgaven'] if 'url' in item}
    assert set(formats) == {'/downloads/' + builder.PDF_NAAM, '/markdown/ov-volledig.md'}
    for url, item in formats.items():
        assert (root / url.lstrip('/')).stat().st_size == item['bytes']
    assert 'Zonder kanttekeningen' in formats['/downloads/' + builder.PDF_NAAM]['omschrijving']
