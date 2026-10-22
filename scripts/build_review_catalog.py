#!/usr/bin/env python3
"""Build the revision-bound catalog consumed by the collaboration API.

The catalog describes reviewable data; it never contains reviewer identities.
Those identities and immutable decisions live in the server-side audit store.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from review_content import canonical_hash, text_review_payload, text_revision, location_review_payload
from review_components import component_metadata
OUTPUT = ROOT / "data" / "review-catalog.json"


def build_catalog(root: Path = ROOT) -> dict:
    data = root / "data"
    books = json.loads((data / "books.json").read_text(encoding="utf-8"))["books"]
    historical_subjects = []
    component_history = json.loads((root / 'migrations/review-components-v1.json').read_text())
    if component_history['schemaVersion'] != 1:
        raise ValueError('Unknown component migration version')
    historical_components = {(i['type'], i['id'], i['revision']): i['metadata']['components']
                             for i in component_history['subjects']}
    for filename in ("review-history-v1.json", "review-history-v2.json"):
        history = json.loads((root / "migrations" / filename).read_text(encoding="utf-8"))
        if history["schemaVersion"] != 1:
            raise ValueError("onbekende historische migratieversie")
        historical_subjects.extend(history["subjects"])
    for item in historical_subjects:
        item['metadata'] = {'components': historical_components[(item['type'], item['id'], item['revision'])]}
    # De kaart en de plaatsen staan sinds de splitsing op Open Gods Woord.
    # Daar bestaat dit bestand en komen de plaatsen in de catalogus; op de
    # OV-site ontbreekt het en bevat de catalogus alleen tekstonderwerpen.
    geography_path = data / "geografie-runtime.geojson"
    geography = (json.loads(geography_path.read_text(encoding="utf-8"))
                 if geography_path.exists() else None)

    book_ids = [book["id"] for book in books]
    if len(book_ids) != len(set(book_ids)):
        raise ValueError("books.json bevat dubbele boek-id's")

    subjects = []
    for book in books:
        book_id = book["id"]
        included = book.get("chaptersIncluded")
        if not isinstance(included, list) or len(included) != len(set(included)):
            raise ValueError(f"ongeldige hoofdstuklijst voor {book_id}")
        for chapter_number in included:
            path = data / book_id / f"{chapter_number}.json"
            chapter = json.loads(path.read_text(encoding="utf-8"))
            source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            subject = {
                "type": "text-chapter",
                "id": f"{book_id}/{chapter_number}",
                "revision": text_revision(chapter),
                "label": f"{book['nameDutch']} {chapter_number}",
                "href": f"index.html#{book_id}/{chapter_number}",
                "source": f"data/{book_id}/{chapter_number}.json",
                "metadata": {
                    "sourceHash": source_hash,
                    "book": book_id,
                    "chapter": chapter_number,
                    "verses": len(chapter.get("verses", [])),
                    "components": component_metadata('text-chapter', text_review_payload(chapter)),
                },
            }
            subjects.append(subject)
            for verse in text_review_payload(chapter)["verses"]:
                subjects.append({
                    "type": "text-verse",
                    "id": f"{book_id}/{chapter_number}/{verse['number']}",
                    "revision": canonical_hash(verse),
                    "label": f"{book['nameDutch']} {chapter_number}:{verse['number']}",
                    "href": f"index.html#{book_id}/{chapter_number}/{verse['number']}",
                    "source": f"data/{book_id}/{chapter_number}.json",
                    "metadata": {"sourceHash": source_hash,
                                 "components": component_metadata('text-verse', verse)},
                })

    if geography is not None:
        features = geography.get("features")
        geography_hash = hashlib.sha256(geography_path.read_bytes()).hexdigest()
        if not isinstance(features, list):
            raise ValueError("geografie-runtime.geojson moet features bevatten")
        for feature in features:
            if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
                raise ValueError("ieder geografisch punt moet properties hebben")
            properties = feature["properties"]
            subject_id = properties.get("id")
            if not subject_id:
                raise ValueError("Geografisch punt zonder stabiele id")
            subject = {
                "type": "location",
                "id": subject_id,
                "revision": canonical_hash(location_review_payload(feature)),
                "label": properties.get("naam") or subject_id,
                "href": f"plaats.html?plaats={subject_id}",
                "source": "data/geografie-runtime.geojson",
                "metadata": {
                    "sourceHash": geography_hash,
                    "components": component_metadata('location', location_review_payload(feature)),
                    "certainty": properties.get("zekerheid", "onzeker"),
                    "sourceDataset": (properties.get("bron") or {}).get("dataset"),
                },
            }
            subjects.append(subject)

    subject_keys = [(item["type"], item["id"]) for item in subjects]
    if len(subject_keys) != len(set(subject_keys)):
        raise ValueError("reviewcatalogus bevat dubbele onderwerp-id's")
    subjects.sort(key=lambda item: (item["type"], item["label"].casefold(), item["id"]))
    catalog = {
        "schemaVersion": 3,
        "componentHistory": component_history['subjects'],
        "historicalSubjects": historical_subjects,
        "subjectTypes": {
            "text-chapter": "Bijbelhoofdstuk",
            "text-verse": "Bijbelvers",
            "location": "Geografische locatie",
        },
        "subjects": subjects,
    }
    catalog["catalogRevision"] = canonical_hash(catalog)
    return catalog


def main() -> None:
    catalog = build_catalog()
    OUTPUT.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        f"{OUTPUT.relative_to(ROOT)}: {len(catalog['subjects'])} reviewonderwerpen"
    )


if __name__ == "__main__":
    main()
