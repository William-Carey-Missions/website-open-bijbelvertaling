#!/usr/bin/env python3
"""Bouw kleine, citeerbare hoofdstukbestanden zonder vergelijkingsteksten."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EDITION = "ov"
BASE = "https://openvertaling.nl"
NAME = "Open Vertaling"
STATUS = "nagekeken"
LICENSE = {"id": "CC0-1.0", "name": "CC0 1.0, publiek domein",
           "url": "https://creativecommons.org/publicdomain/zero/1.0/"}


def plain(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).split())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def source_books(root):
    from build_leespaginas import GROEPEN, platte_tekst
    metadata = json.loads((root / "data/books-index.json").read_text(encoding="utf-8"))
    by_id = {book["id"]: book for book in metadata["boeken"]}
    public = [book for _, ids in GROEPEN for book in ids.split()]
    if len(public) != 82 or len(set(public)) != 82:
        raise ValueError("De openbare collectie moet precies 82 verschillende boeken bevatten")
    result = []
    for book_id in public:
        book = by_id[book_id]
        chapters = []
        paths = sorted((root / "data" / book_id).glob("*.json"), key=lambda path: int(path.stem) if path.stem.isdigit() else -1)
        for path in paths:
            if not path.stem.isdigit():
                continue
            source = json.loads(path.read_text(encoding="utf-8"))
            verses = []
            for verse in source.get("verses", []):
                text = plain(platte_tekst(verse.get("text2026")))
                if not text:
                    continue
                notes = [{"marker": str(note.get("marker", "")),
                          "text": plain(platte_tekst(note["text2026"]))}
                         for note in verse.get("marginNotes", []) or [] if note.get("text2026")]
                verses.append({"verse": int(verse["number"]), "text": text, "notes": notes})
            chapters.append({"chapter": int(path.stem), "verses": verses})
        result.append({"id": book_id, "name": book["naam"], "chapters": chapters})
    return result


def build_catalog(root=ROOT, output=None, books=None):
    output = output or root
    books = source_books(root) if books is None else books
    edition = {"id": EDITION, "name": NAME, "language": "nl", "status": STATUS,
               "kind": "parafrase" if EDITION == "opw" else "herziening van de Statenvertaling"}
    catalog = {"schemaVersion": 1, "edition": edition, "license": LICENSE,
               "source": {"url": BASE + "/", "description": "Gepubliceerde tekst van deze editie; geen vergelijkingsteksten"},
               "citation": "Boek hoofdstuk:vers (" + NAME + (" (proef)" if EDITION == "opw" else "") + ")",
               "books": []}
    seen_books = set()
    for book in books:
        if book["id"] in seen_books:
            raise ValueError("Dubbel boek in catalogus")
        seen_books.add(book["id"])
        entry = {"id": book["id"], "name": book["name"], "url": f"{BASE}/bijbel/{book['id']}/", "chapters": []}
        seen_chapters = set()
        for chapter in book["chapters"]:
            number = chapter["chapter"]
            if number in seen_chapters or number < 1:
                raise ValueError("Dubbel of ongeldig hoofdstuk")
            seen_chapters.add(number)
            page = f"{BASE}/bijbel/{book['id']}/{number}.html"
            resource = f"{BASE}/data/llm/{book['id']}/{number}.json"
            verses = []
            seen_verses = set()
            for verse in chapter["verses"]:
                n = verse["verse"]
                if n in seen_verses or n < 1 or not verse["text"].strip():
                    raise ValueError("Dubbel, leeg of ongeldig vers")
                seen_verses.add(n)
                item = {"id": f"urn:{EDITION}:{book['id']}:{number}:{n}", "book": book["id"],
                        "chapter": number, "verse": n, "text": verse["text"],
                        "citation": f"{book['name']} {number}:{n} ({NAME}{' (proef)' if EDITION == 'opw' else ''})",
                        "url": page + (f"#vers-{n}" if EDITION == "opw" else f"#v{n}")}
                if EDITION == "ov":
                    item["notes"] = verse.get("notes", [])
                verses.append(item)
            if not verses:
                raise ValueError(f"Leeg hoofdstuk: {book['id']} {number}")
            chapter_data = {"schemaVersion": 1, "edition": edition, "license": LICENSE,
                            "book": book["id"], "bookName": book["name"], "chapter": number,
                            "url": page, "verses": verses}
            chapter_data["version"] = "sha256:" + digest(chapter_data)
            write_json(output / "data/llm" / book["id"] / f"{number}.json", chapter_data)
            entry["chapters"].append({"chapter": number, "url": page, "json": resource,
                                       "verseCount": len(verses), "version": chapter_data["version"]})
        if not entry["chapters"]:
            raise ValueError(f"Boek zonder hoofdstukken: {book['id']}")
        entry["chapterCount"] = len(entry["chapters"])
        catalog["books"].append(entry)
    catalog["bookCount"] = len(books)
    catalog["chapterCount"] = sum(book["chapterCount"] for book in catalog["books"])
    catalog["version"] = "sha256:" + digest(catalog)
    write_json(output / "data/llm/index.json", catalog)
    return catalog


def guide_section():
    anchor = "vers-16" if EDITION == "opw" else "v16"
    return f'''## Begin hier: vinden, lezen en citeren

1. Lees de [machineleesbare catalogus]({BASE}/data/llm/index.json). Die bevat precies de 82 openbare boeken, namen, echte hoofdstuknummers en downloadlinks per hoofdstuk.
2. Haal alleen het benodigde hoofdstuk op, bijvoorbeeld [Johannes 3 als JSON]({BASE}/data/llm/johannes/3.json). Dit is een kleine UTF-8-download zonder vergelijkingsteksten.
3. Gebruik `verses[].text` als tekst en `verses[].citation` met `verses[].url` als bronverwijzing. Voorbeeld: [Johannes 3:16 ({NAME}{' (proef)' if EDITION == 'opw' else ''})]({BASE}/bijbel/johannes/3.html#{anchor}).

Schema versie 1: de index heeft `edition`, `source`, `version`, `license` en `books[].chapters[]` met `chapter`, `json`, `url`, `verseCount`, `version`. Een hoofdstuk heeft `edition`, `license`, `version`, `book`, `bookName`, `chapter`, `url`, `verses`. Elk vers heeft `id`, `book`, `chapter`, `verse`, `text`, `citation`, `url`{' en `notes` (uitsluitend herziene OV-kanttekeningen)' if EDITION == 'ov' else ''}. Getallen zijn JSON-nummers. `id` is een vaste URN, bijvoorbeeld `urn:{EDITION}:johannes:3:16`; `version` is een inhoudshash, geen verzonnen publicatiedatum. Citeer de HTML-verslink; gebruik de JSON-link voor ophalen.

De licentie geldt voor de tekst van deze editie: {LICENSE['name']} ({LICENSE['url']}). Neem geen rechten voor afbeeldingen, woordenboeken, grondtekstdata of andere edities aan op basis van deze tekstlicentie. Ethiopische boeken staan niet in deze openbare collectie.

Houd de bronnen apart: [Open Vertaling](https://openvertaling.nl/llms.txt) is de nagekeken herziening van de Statenvertaling met herziene kanttekeningen; [Open Parafrase Weergave](https://open-parafrase-weergave.nl/llms.txt) is een parafrase in eenvoudig Nederlands met proef-/conceptstatus; [Open Gods Word](https://opengodsword.com/llms.txt) biedt wiki, achtergrond en broninformatie. Schrijf bij een citaat de werkelijke editie erbij.

'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--uit", type=Path)
    args = parser.parse_args()
    result = build_catalog(args.root, args.uit)
    print(f"LLM: {result['bookCount']} boeken, {result['chapterCount']} hoofdstukken, {result['version']}")
