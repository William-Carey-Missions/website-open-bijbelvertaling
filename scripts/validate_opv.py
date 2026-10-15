#!/usr/bin/env python3
"""Valideer het corpuscontract van de Open Parafrase Weergave."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any


REVIEW_STATUS_SEQUENCE = (
    "concept",
    "bron_gecontroleerd",
    "taal_gecontroleerd",
    "definitief",
)
ALLOWED_REVIEW_STATUSES = set(REVIEW_STATUS_SEQUENCE)
ALLOWED_SPEAKER_TYPES = {
    "god",
    "human",
    "angel",
    "spirit",
    "animal",
    "group",
    "narrator",
    "unknown",
}
REQUIRED_REGISTRY_FIELDS = {
    "code",
    "naam",
    "taal",
    "richting",
    "dataRoot",
    "boeken",
    "hoofdstukken",
    "gepubliceerdeHoofdstukken",
    "status",
}
REQUIRED_EDITION_FIELDS = {
    "editie",
    "naam",
    "taal",
    "richting",
    "status",
    "versie",
    "doelgroep",
    "bronnenbeleid",
    "redactioneleStatussen",
    "gepubliceerdeHoofdstukken",
    "boeken",
}
OPV_DATA_ROOT = "data/edities/opv/chapters"
HTML_RE = re.compile(r"<\s*/?\s*[A-Za-z!][^>]*>")
SEMANTIC_ID_RE = re.compile(r"^[a-z0-9]+(?:\.[a-z0-9]+)+$")
BOOK_CODE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
JSON_PATH_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
UNSAFE_PATH_CHARACTER_RE = re.compile(r'[\x00-\x1f\x7f-\x9f<>:"|?*]')


def _escape_control_characters(value: Any) -> str:
    text = str(value)
    return "".join(
        f"\\u{ord(character):04x}"
        if ord(character) < 0x20
        or 0x7F <= ord(character) <= 0x9F
        or character in ("\u2028", "\u2029")
        else character
        for character in text
    )


def _json_path_key(json_path: str, key: Any) -> str:
    key_text = str(key)
    if JSON_PATH_IDENTIFIER_RE.fullmatch(key_text):
        return f"{json_path}.{key_text}"
    return f"{json_path}[{json.dumps(key_text, ensure_ascii=True)}]"


def _error(code: str, filename: str, json_path: str) -> str:
    return " ".join(
        _escape_control_characters(part) for part in (code, filename, json_path)
    )


def _is_json_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_schema_one(value: Any) -> bool:
    return _is_json_integer(value) and value == 1


def _safe_relative_path(
    repo_root: Path,
    raw_path: Any,
    *,
    require_data: bool = True,
    require_json: bool = False,
) -> Path | None:
    if (
        not isinstance(raw_path, str)
        or not raw_path
        or "\\" in raw_path
        or UNSAFE_PATH_CHARACTER_RE.search(raw_path) is not None
    ):
        return None
    try:
        pure = PurePosixPath(raw_path)
        if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
            return None
        if any(part.endswith((" ", ".")) for part in pure.parts):
            return None
        if require_data and (not pure.parts or pure.parts[0] != "data"):
            return None
        if require_json and pure.suffix != ".json":
            return None
        candidate = (repo_root / Path(*pure.parts)).resolve()
        candidate.relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _load_json(repo_root: Path, filename: str, errors: list[str]) -> Any | None:
    path = _safe_relative_path(repo_root, filename, require_json=True)
    if path is None:
        errors.append(_error("MANIFEST_PATH_UNSAFE", str(filename), "$"))
        return None
    try:
        is_file = path.is_file()
    except (OSError, ValueError):
        is_file = False
    if not is_file:
        errors.append(_error("FILE_MISSING", filename, "$"))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(_error("JSON_INVALID", filename, "$"))
        return None


def _walk(value: Any, json_path: str = "$") -> Iterable[tuple[str, Any]]:
    yield json_path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, _json_path_key(json_path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{json_path}[{index}]")


def _validate_text_integrity(value: Any, filename: str) -> list[str]:
    errors: list[str] = []
    for json_path, child in _walk(value):
        if not isinstance(child, str):
            continue
        if unicodedata.normalize("NFC", child) != child:
            errors.append(_error("UNICODE_NOT_NFC", filename, json_path))
        if "\ufffd" in child:
            errors.append(_error("UNICODE_REPLACEMENT", filename, json_path))
        if HTML_RE.search(child):
            errors.append(_error("TEXT_HTML", filename, json_path))
    return errors


def _validate_no_strong_fields(value: Any, filename: str) -> list[str]:
    errors: list[str] = []

    def visit(child: Any, json_path: str) -> None:
        if isinstance(child, dict):
            for key, nested in child.items():
                key_path = _json_path_key(json_path, key)
                if "strong" in str(key).casefold():
                    errors.append(_error("STRONG_FIELD_FORBIDDEN", filename, key_path))
                visit(nested, key_path)
        elif isinstance(child, list):
            for index, nested in enumerate(child):
                visit(nested, f"{json_path}[{index}]")

    visit(value, "$")
    return errors


def _safe_repo_file(repo_root: Path, raw_path: Any) -> Path | None:
    return _safe_relative_path(repo_root, raw_path, require_json=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _book_chapters_from_edition_manifest(manifest: Any) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    if not isinstance(manifest, dict) or not isinstance(manifest.get("boeken"), list):
        return result
    for book in manifest["boeken"]:
        if not isinstance(book, dict):
            continue
        code = book.get("code")
        chapters = book.get("hoofdstukken")
        if (
            isinstance(code, str)
            and BOOK_CODE_RE.fullmatch(code)
            and isinstance(chapters, list)
            and all(_is_json_integer(chapter) and chapter > 0 for chapter in chapters)
        ):
            result[code] = chapters
    return result


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_chapter_numbers(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_is_json_integer(chapter) and chapter > 0 for chapter in value)
        and len(value) == len(set(value))
        and value == sorted(value)
    )


def _published_chapter_map(
    value: Any,
    planned: dict[str, list[int]],
    filename: str,
    json_path: str,
    errors: list[str],
) -> dict[str, list[int]]:
    """Valideer de werkelijk aanwezige subset van de geplande hoofdstukken."""

    if not isinstance(value, dict):
        errors.append(_error("PUBLISHED_CHAPTERS_INVALID", filename, json_path))
        return {}

    result: dict[str, list[int]] = {}
    safe_books: set[str] = set()
    for book, chapters in value.items():
        if not isinstance(book, str) or BOOK_CODE_RE.fullmatch(book) is None:
            errors.append(_error("MANIFEST_PATH_UNSAFE", filename, json_path))
            continue
        safe_books.add(book)
        book_path = _json_path_key(json_path, book)
        if book not in planned:
            errors.append(_error("PUBLISHED_BOOK_UNKNOWN", filename, book_path))
            continue
        valid = (
            isinstance(chapters, list)
            and all(_is_json_integer(chapter) and chapter > 0 for chapter in chapters)
            and len(chapters) == len(set(chapters))
            and chapters == sorted(chapters)
        )
        if not valid:
            errors.append(_error("PUBLISHED_CHAPTERS_INVALID", filename, book_path))
            continue
        result[book] = chapters
        if not set(chapters).issubset(planned[book]):
            errors.append(_error("PUBLISHED_CHAPTER_OUTSIDE_PLAN", filename, book_path))

    if safe_books != set(planned):
        errors.append(_error("PUBLISHED_BOOKS_MISMATCH", filename, json_path))
    return result


def validate_manifest(
    repo_root: Path,
    registry: Any | None = None,
    edition_manifest: Any | None = None,
) -> list[str]:
    """Valideer het centrale register en het OPV-manifest."""

    errors: list[str] = []
    registry_file = "data/edities/manifest.json"
    edition_file = "data/edities/opv/manifest.json"
    if registry is None:
        registry = _load_json(repo_root, registry_file, errors)
    if edition_manifest is None:
        edition_manifest = _load_json(repo_root, edition_file, errors)
    if registry is None or edition_manifest is None:
        return errors

    errors.extend(_validate_text_integrity(registry, registry_file))
    errors.extend(_validate_text_integrity(edition_manifest, edition_file))
    errors.extend(_validate_no_strong_fields(registry, registry_file))
    errors.extend(_validate_no_strong_fields(edition_manifest, edition_file))

    if not isinstance(registry, dict) or not _is_schema_one(registry.get("schema")):
        errors.append(_error("MANIFEST_SCHEMA", registry_file, "$.schema"))
        editions: list[Any] = []
    else:
        editions = registry.get("edities", [])
        if not isinstance(editions, list):
            errors.append(_error("MANIFEST_EDITIONS", registry_file, "$.edities"))
            editions = []

    opv_entries = [
        (index, entry)
        for index, entry in enumerate(editions)
        if isinstance(entry, dict) and entry.get("code") == "nl-opv"
    ]
    if len(opv_entries) != 1:
        errors.append(_error("MANIFEST_OPV_ENTRY", registry_file, "$.edities"))
        registry_chapters: dict[str, list[int]] = {}
        registry_published: dict[str, list[int]] = {}
    else:
        index, entry = opv_entries[0]
        for field in sorted(REQUIRED_REGISTRY_FIELDS):
            if field not in entry or entry[field] in (None, "", [], {}):
                errors.append(
                    _error("MANIFEST_FIELD_MISSING", registry_file, f"$.edities[{index}].{field}")
                )
        for field in ("naam", "taal", "status"):
            if not _is_non_empty_string(entry.get(field)):
                errors.append(
                    _error(
                        "MANIFEST_FIELD_INVALID",
                        registry_file,
                        f"$.edities[{index}].{field}",
                    )
                )
        expected_registry_values = {
            "naam": "Open Parafrase Weergave (proef)",
            "taal": "nl",
            "status": "pilot",
        }
        for field, expected_value in expected_registry_values.items():
            value = entry.get(field)
            if isinstance(value, str) and value != expected_value:
                errors.append(
                    _error(
                        "MANIFEST_METADATA_MISMATCH",
                        registry_file,
                        f"$.edities[{index}].{field}",
                    )
                )
        direction = entry.get("richting")
        if not isinstance(direction, str) or direction != "ltr":
            errors.append(
                _error("MANIFEST_DIRECTION", registry_file, f"$.edities[{index}].richting")
            )
        data_root = entry.get("dataRoot")
        if data_root != OPV_DATA_ROOT:
            errors.append(
                _error("MANIFEST_DATA_ROOT", registry_file, f"$.edities[{index}].dataRoot")
            )
        if _safe_relative_path(repo_root, data_root, require_json=False) is None:
            errors.append(
                _error("MANIFEST_PATH_UNSAFE", registry_file, f"$.edities[{index}].dataRoot")
            )

        raw_books = entry.get("boeken")
        if not isinstance(raw_books, list) or any(
            not isinstance(book, str) or BOOK_CODE_RE.fullmatch(book) is None
            for book in raw_books
        ):
            errors.append(
                _error("MANIFEST_BOOKS_INVALID", registry_file, f"$.edities[{index}].boeken")
            )
        books = (
            [
                book
                for book in raw_books
                if isinstance(book, str) and BOOK_CODE_RE.fullmatch(book)
            ]
            if isinstance(raw_books, list)
            else []
        )
        if len(books) != len(set(books)):
            errors.append(
                _error("MANIFEST_BOOKS_INVALID", registry_file, f"$.edities[{index}].boeken")
            )

        registry_chapters = {}
        raw_registry_chapters = entry.get("hoofdstukken")
        if not isinstance(raw_registry_chapters, dict):
            errors.append(
                _error(
                    "MANIFEST_CHAPTERS_INVALID",
                    registry_file,
                    f"$.edities[{index}].hoofdstukken",
                )
            )
        else:
            for book, chapters in raw_registry_chapters.items():
                if not isinstance(book, str) or BOOK_CODE_RE.fullmatch(book) is None:
                    errors.append(
                        _error(
                            "MANIFEST_PATH_UNSAFE",
                            registry_file,
                            f"$.edities[{index}].hoofdstukken",
                        )
                    )
                    continue
                if not _valid_chapter_numbers(chapters):
                    errors.append(
                        _error(
                            "MANIFEST_CHAPTERS_INVALID",
                            registry_file,
                            f"$.edities[{index}].hoofdstukken.{book}",
                        )
                    )
                    continue
                registry_chapters[book] = chapters
        if set(books) != set(registry_chapters):
            errors.append(
                _error("MANIFEST_BOOKS_MISMATCH", registry_file, f"$.edities[{index}].boeken")
            )
        registry_published = _published_chapter_map(
            entry.get("gepubliceerdeHoofdstukken"),
            registry_chapters,
            registry_file,
            f"$.edities[{index}].gepubliceerdeHoofdstukken",
            errors,
        )

    if not isinstance(edition_manifest, dict):
        errors.append(_error("EDITION_SCHEMA", edition_file, "$"))
        return errors
    if not _is_schema_one(edition_manifest.get("schema")):
        errors.append(_error("EDITION_SCHEMA", edition_file, "$.schema"))
    for field in sorted(REQUIRED_EDITION_FIELDS):
        value = edition_manifest.get(field)
        if (
            field not in edition_manifest
            or value is None
            or value == ""
            or value == []
            or value == {}
        ):
            errors.append(_error("EDITION_FIELD_MISSING", edition_file, f"$.{field}"))
    if edition_manifest.get("editie") != "nl-opv":
        errors.append(_error("EDITION_CODE", edition_file, "$.editie"))
    if edition_manifest.get("naam") != "Open Parafrase Weergave (proef)":
        errors.append(_error("EDITION_NAME", edition_file, "$.naam"))
    if edition_manifest.get("taal") != "nl":
        errors.append(_error("EDITION_LANGUAGE", edition_file, "$.taal"))
    if edition_manifest.get("richting") != "ltr":
        errors.append(_error("EDITION_DIRECTION", edition_file, "$.richting"))
    if edition_manifest.get("status") != "pilot":
        errors.append(_error("EDITION_STATUS", edition_file, "$.status"))
    if not _is_non_empty_string(edition_manifest.get("versie")):
        errors.append(_error("EDITION_VERSION", edition_file, "$.versie"))
    if not _is_non_empty_string(edition_manifest.get("doelgroep")):
        errors.append(_error("EDITION_AUDIENCE", edition_file, "$.doelgroep"))
    source_policy = edition_manifest.get("bronnenbeleid")
    if (
        not isinstance(source_policy, dict)
        or not _is_non_empty_string(source_policy.get("basistekst"))
        or not isinstance(source_policy.get("controlebronnen"), list)
        or not source_policy.get("controlebronnen")
        or any(
            not _is_non_empty_string(source)
            for source in source_policy.get("controlebronnen", [])
        )
    ):
        errors.append(_error("EDITION_SOURCE_POLICY", edition_file, "$.bronnenbeleid"))
    if edition_manifest.get("redactioneleStatussen") != list(REVIEW_STATUS_SEQUENCE):
        errors.append(
            _error("EDITION_REVIEW_STATUSES", edition_file, "$.redactioneleStatussen")
        )

    edition_chapters = _book_chapters_from_edition_manifest(edition_manifest)
    raw_edition_books = edition_manifest.get("boeken")
    if not isinstance(raw_edition_books, list) or not raw_edition_books:
        errors.append(_error("EDITION_BOOKS", edition_file, "$.boeken"))
    else:
        seen_books: set[str] = set()
        for book_index, book in enumerate(raw_edition_books):
            book_path = f"$.boeken[{book_index}]"
            if not isinstance(book, dict):
                errors.append(_error("EDITION_BOOK_INVALID", edition_file, book_path))
                continue
            code = book.get("code")
            if not isinstance(code, str) or BOOK_CODE_RE.fullmatch(code) is None:
                errors.append(_error("MANIFEST_PATH_UNSAFE", edition_file, f"{book_path}.code"))
            elif code in seen_books:
                errors.append(_error("EDITION_BOOK_DUPLICATE", edition_file, f"{book_path}.code"))
            else:
                seen_books.add(code)
            if not _valid_chapter_numbers(book.get("hoofdstukken")):
                errors.append(
                    _error("EDITION_CHAPTER_INVALID", edition_file, f"{book_path}.hoofdstukken")
                )
    if registry_chapters != edition_chapters:
        errors.append(_error("MANIFEST_CHAPTERS_MISMATCH", edition_file, "$.boeken"))
    edition_published = _published_chapter_map(
        edition_manifest.get("gepubliceerdeHoofdstukken"),
        edition_chapters,
        edition_file,
        "$.gepubliceerdeHoofdstukken",
        errors,
    )
    if registry_published != edition_published:
        errors.append(
            _error("PUBLISHED_CHAPTERS_MISMATCH", edition_file, "$.gepubliceerdeHoofdstukken")
        )
    return errors


def validate_review(
    review: Any,
    reading_text: str,
    source_text: str | None,
    filename: str,
    json_path: str,
) -> list[str]:
    """Valideer hashes, status en vereiste definitieve controles."""

    errors: list[str] = []
    if not isinstance(review, dict):
        return [_error("REVIEW_MISSING", filename, json_path)]
    status = review.get("status")
    if not isinstance(status, str) or status not in ALLOWED_REVIEW_STATUSES:
        errors.append(_error("REVIEW_STATUS", filename, f"{json_path}.status"))
    content_hash = _sha256(reading_text)
    if review.get("inhoudSha256") != content_hash:
        errors.append(_error("REVIEW_CONTENT_HASH", filename, f"{json_path}.inhoudSha256"))
    if source_text is not None and review.get("bronSha256") != _sha256(source_text):
        errors.append(_error("REVIEW_SOURCE_HASH", filename, f"{json_path}.bronSha256"))

    controls = review.get("controles")
    if not isinstance(controls, list):
        errors.append(_error("REVIEW_CONTROLS", filename, f"{json_path}.controles"))
        controls = []
    if status == "definitief":
        approved = {
            control.get("type")
            for control in controls
            if isinstance(control, dict)
            and isinstance(control.get("type"), str)
            and control.get("status") == "goedgekeurd"
            and control.get("inhoudSha256") == content_hash
        }
        if not {"bron", "taal", "leesbaarheid"}.issubset(approved):
            errors.append(_error("FINAL_REVIEW_MISSING", filename, f"{json_path}.controles"))
    return errors


def _source_text_for_verse(
    repo_root: Path,
    verse: dict[str, Any],
    filename: str,
    json_path: str,
    source_cache: dict[str, Any],
    expected_book: str,
    expected_chapter: int,
) -> tuple[str | None, str | None, list[str]]:
    errors: list[str] = []
    source_ref = verse.get("bron")
    if not isinstance(source_ref, dict):
        return None, None, [_error("SOURCE_MISSING", filename, f"{json_path}.bron")]
    raw_path = source_ref.get("bestand")
    source_path = _safe_repo_file(repo_root, raw_path)
    if source_path is None:
        return None, None, [
            _error("SOURCE_PATH_UNSAFE", filename, f"{json_path}.bron.bestand")
        ]
    source_name = PurePosixPath(str(raw_path)).as_posix()
    expected_source_name = f"data/{expected_book}/{expected_chapter}.json"
    if source_name != expected_source_name:
        return source_name, None, [
            _error("SOURCE_PATH_MISMATCH", filename, f"{json_path}.bron.bestand")
        ]
    try:
        is_file = source_path.is_file()
    except (OSError, ValueError):
        is_file = False
    if not is_file:
        return source_name, None, [
            _error("SOURCE_FILE_MISSING", filename, f"{json_path}.bron.bestand")
        ]
    if source_name not in source_cache:
        try:
            source_cache[source_name] = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            source_cache[source_name] = None
    source_doc = source_cache[source_name]
    if not isinstance(source_doc, dict) or not isinstance(source_doc.get("verses"), list):
        return source_name, None, [
            _error("SOURCE_JSON_INVALID", filename, f"{json_path}.bron.bestand")
        ]

    source_chapter = source_doc.get("number")
    if not _is_json_integer(source_chapter) or source_chapter != expected_chapter:
        errors.append(
            _error("SOURCE_CHAPTER_MISMATCH", filename, f"{json_path}.bron.bestand")
        )
    verse_number = verse.get("nummer")
    source_verse_reference = source_ref.get("vers")
    if (
        not _is_json_integer(verse_number)
        or not _is_json_integer(source_verse_reference)
        or source_verse_reference != verse_number
    ):
        errors.append(_error("SOURCE_VERSE_MISMATCH", filename, f"{json_path}.bron.vers"))
    for index, source_verse in enumerate(source_doc["verses"]):
        source_number = source_verse.get("number") if isinstance(source_verse, dict) else None
        if not _is_json_integer(source_number):
            errors.append(
                _error(
                    "SOURCE_VERSE_NUMBER_INVALID",
                    source_name,
                    f"$.verses[{index}].number",
                )
            )
    candidates = [
        candidate
        for candidate in source_doc["verses"]
        if isinstance(candidate, dict)
        and _is_json_integer(verse_number)
        and _is_json_integer(candidate.get("number"))
        and candidate.get("number") == verse_number
    ]
    if len(candidates) != 1:
        errors.append(_error("SOURCE_VERSE_MISSING", filename, f"{json_path}.bron.vers"))
        return source_name, None, errors
    text_field = source_ref.get("tekstveld")
    source_text = candidates[0].get(text_field) if isinstance(text_field, str) else None
    if not isinstance(source_text, str):
        errors.append(_error("SOURCE_TEXT_MISSING", filename, f"{json_path}.bron.tekstveld"))
        return source_name, None, errors
    return source_name, source_text, errors


def validate_verse(
    repo_root: Path,
    verse: Any,
    filename: str,
    json_path: str,
    source_cache: dict[str, Any],
    seen_segment_ids: dict[str, str],
    expected_book: str,
    expected_chapter: int,
) -> tuple[list[str], list[str], str | None]:
    """Valideer één vers en retourneer fouten, segment-id's en bronbestand."""

    errors: list[str] = []
    if not isinstance(verse, dict):
        return [_error("VERSE_INVALID", filename, json_path)], [], None
    reading_text = verse.get("tekst")
    if not isinstance(reading_text, str) or not reading_text.strip():
        errors.append(_error("TEXT_EMPTY", filename, f"{json_path}.tekst"))
        reading_text = reading_text if isinstance(reading_text, str) else ""

    segments = verse.get("segmenten")
    segment_ids: list[str] = []
    segment_texts: list[str] = []
    segment_source_anchors: list[tuple[int, str]] = []
    if not isinstance(segments, list) or not segments:
        errors.append(_error("SEGMENTS_MISSING", filename, f"{json_path}.segmenten"))
        segments = []
    for index, segment in enumerate(segments):
        segment_path = f"{json_path}.segmenten[{index}]"
        if not isinstance(segment, dict):
            errors.append(_error("SEGMENT_INVALID", filename, segment_path))
            continue
        segment_id = segment.get("id")
        segment_text = segment.get("tekst")
        source_anchor = segment.get("bronfrase")
        if not isinstance(segment_id, str) or not segment_id:
            errors.append(_error("SEGMENT_ID_MISSING", filename, f"{segment_path}.id"))
        else:
            segment_ids.append(segment_id)
            if segment_id in seen_segment_ids:
                errors.append(_error("SEGMENT_DUPLICATE", filename, f"{segment_path}.id"))
            else:
                seen_segment_ids[segment_id] = f"{filename} {segment_path}.id"
        if not isinstance(segment_text, str):
            errors.append(_error("SEGMENT_TEXT_INVALID", filename, f"{segment_path}.tekst"))
        else:
            segment_texts.append(segment_text)
        if not isinstance(source_anchor, str) or not source_anchor.strip():
            errors.append(
                _error(
                    "SEGMENT_SOURCE_ANCHOR_MISSING",
                    filename,
                    f"{segment_path}.bronfrase",
                )
            )
        else:
            segment_source_anchors.append((index, source_anchor))
    if "".join(segment_texts) != reading_text:
        errors.append(_error("SEGMENTS_TEXT_MISMATCH", filename, f"{json_path}.segmenten"))

    source_name, source_text, source_errors = _source_text_for_verse(
        repo_root,
        verse,
        filename,
        json_path,
        source_cache,
        expected_book,
        expected_chapter,
    )
    errors.extend(source_errors)
    if source_text is not None:
        for index, source_anchor in segment_source_anchors:
            if source_anchor not in source_text:
                errors.append(
                    _error(
                        "SEGMENT_SOURCE_ANCHOR_NOT_FOUND",
                        filename,
                        f"{json_path}.segmenten[{index}].bronfrase",
                    )
                )
    errors.extend(
        validate_review(
            verse.get("review"), reading_text, source_text, filename, f"{json_path}.review"
        )
    )
    return errors, segment_ids, source_name


def validate_annotations(
    verse: Any,
    filename: str,
    json_path: str,
    concept_ids: set[str],
    segment_positions: dict[str, int],
    seen_citation_ids: dict[str, str],
) -> tuple[list[str], list[tuple[int, int, str]]]:
    """Valideer begrippen, citaten en hun segmentverwijzingen."""

    errors: list[str] = []
    ranges: list[tuple[int, int, str]] = []
    if not isinstance(verse, dict):
        return errors, ranges

    concepts = verse.get("begrippen")
    if not isinstance(concepts, list):
        errors.append(_error("CONCEPTS_INVALID", filename, f"{json_path}.begrippen"))
        concepts = []
    for index, concept in enumerate(concepts):
        concept_path = f"{json_path}.begrippen[{index}]"
        if not isinstance(concept, dict):
            errors.append(_error("CONCEPT_INVALID", filename, concept_path))
            continue
        concept_id = concept.get("conceptId")
        if not isinstance(concept_id, str) or concept_id not in concept_ids:
            errors.append(_error("CONCEPT_UNKNOWN", filename, f"{concept_path}.conceptId"))
        references = concept.get("segmenten")
        if not isinstance(references, list):
            errors.append(_error("SEGMENT_REFERENCES_INVALID", filename, f"{concept_path}.segmenten"))
            continue
        for ref_index, reference in enumerate(references):
            if not isinstance(reference, str) or reference not in segment_positions:
                errors.append(
                    _error(
                        "SEGMENT_REFERENCE_UNKNOWN",
                        filename,
                        f"{concept_path}.segmenten[{ref_index}]",
                    )
                )

    citations = verse.get("citaten")
    if not isinstance(citations, list):
        errors.append(_error("CITATIONS_INVALID", filename, f"{json_path}.citaten"))
        citations = []
    for index, citation in enumerate(citations):
        citation_path = f"{json_path}.citaten[{index}]"
        if not isinstance(citation, dict):
            errors.append(_error("CITATION_INVALID", filename, citation_path))
            continue
        citation_id = citation.get("id")
        if not isinstance(citation_id, str) or not citation_id:
            errors.append(_error("CITATION_ID_MISSING", filename, f"{citation_path}.id"))
        elif citation_id in seen_citation_ids:
            errors.append(_error("CITATION_ID_DUPLICATE", filename, f"{citation_path}.id"))
        else:
            seen_citation_ids[citation_id] = f"{filename} {citation_path}.id"

        semantic_id = citation.get("semanticId")
        if not isinstance(semantic_id, str) or not SEMANTIC_ID_RE.fullmatch(semantic_id):
            errors.append(_error("SEMANTIC_ID_INVALID", filename, f"{citation_path}.semanticId"))

        start_id = citation.get("startSegment")
        end_id = citation.get("endSegment")
        start = segment_positions.get(start_id) if isinstance(start_id, str) else None
        end = segment_positions.get(end_id) if isinstance(end_id, str) else None
        if start is None:
            errors.append(_error("SEGMENT_REFERENCE_UNKNOWN", filename, f"{citation_path}.startSegment"))
        if end is None:
            errors.append(_error("SEGMENT_REFERENCE_UNKNOWN", filename, f"{citation_path}.endSegment"))
        if start is not None and end is not None:
            if start > end:
                errors.append(_error("CITATION_RANGE_INVALID", filename, citation_path))
            else:
                ranges.append((start, end, citation_path))

        speaker = citation.get("spreker")
        if not isinstance(speaker, dict):
            errors.append(_error("SPEAKER_ID_MISSING", filename, f"{citation_path}.spreker.id"))
            errors.append(_error("SPEAKER_TYPE_MISSING", filename, f"{citation_path}.spreker.type"))
        else:
            if not isinstance(speaker.get("id"), str) or not speaker.get("id"):
                errors.append(_error("SPEAKER_ID_MISSING", filename, f"{citation_path}.spreker.id"))
            speaker_type = speaker.get("type")
            if not isinstance(speaker_type, str) or not speaker_type:
                errors.append(_error("SPEAKER_TYPE_MISSING", filename, f"{citation_path}.spreker.type"))
            elif speaker_type not in ALLOWED_SPEAKER_TYPES:
                errors.append(_error("SPEAKER_TYPE_INVALID", filename, f"{citation_path}.spreker.type"))
    return errors, ranges


def _validate_blocks(chapter: dict[str, Any], filename: str) -> list[str]:
    errors: list[str] = []
    verses = chapter.get("verzen") if isinstance(chapter.get("verzen"), list) else []
    verse_numbers = {
        verse.get("nummer")
        for verse in verses
        if isinstance(verse, dict)
        and _is_json_integer(verse.get("nummer"))
    }
    coverage = {number: 0 for number in verse_numbers}
    blocks = chapter.get("blokken")
    if not isinstance(blocks, list):
        errors.append(_error("BLOCKS_INVALID", filename, "$.blokken"))
        blocks = []
    block_ids: set[str] = set()
    ordered_ranges: list[tuple[int, int]] = []
    for index, block in enumerate(blocks):
        block_path = f"$.blokken[{index}]"
        if not isinstance(block, dict):
            errors.append(_error("BLOCK_INVALID", filename, block_path))
            continue
        block_id = block.get("id")
        if not _is_non_empty_string(block_id):
            errors.append(_error("BLOCK_ID_MISSING", filename, f"{block_path}.id"))
        elif block_id in block_ids:
            errors.append(_error("BLOCK_ID_DUPLICATE", filename, f"{block_path}.id"))
        else:
            block_ids.add(block_id)
        if not _is_non_empty_string(block.get("kop")):
            errors.append(_error("BLOCK_HEADING_MISSING", filename, f"{block_path}.kop"))
        start = block.get("vanaf")
        end = block.get("tot")
        if (
            not _is_json_integer(start)
            or not _is_json_integer(end)
            or start > end
        ):
            errors.append(_error("BLOCK_RANGE_INVALID", filename, block_path))
            continue
        ordered_ranges.append((start, end))
        covered_numbers = {
            number for number in verse_numbers if start <= number <= end
        }
        if len(covered_numbers) != end - start + 1:
            errors.append(_error("BLOCK_RANGE_UNKNOWN_VERSE", filename, block_path))
        for number in covered_numbers:
            coverage[number] += 1
    if any(count > 1 for count in coverage.values()):
        errors.append(_error("BLOCKS_OVERLAP", filename, "$.blokken"))
    if any(count == 0 for count in coverage.values()) or (verse_numbers and not blocks):
        errors.append(_error("BLOCKS_INCOMPLETE", filename, "$.blokken"))
    if ordered_ranges != sorted(ordered_ranges):
        errors.append(_error("BLOCK_ORDER", filename, "$.blokken"))
    return errors


def validate_chapter(
    repo_root: Path,
    chapter: Any,
    filename: str,
    expected_book: str,
    expected_chapter: int,
    concept_ids: set[str],
    source_cache: dict[str, Any],
    seen_segment_ids: dict[str, str],
    seen_citation_ids: dict[str, str],
) -> list[str]:
    """Valideer één hoofdstuk inclusief corpusbrede identifiers."""

    errors: list[str] = []
    if not isinstance(chapter, dict):
        return [_error("CHAPTER_INVALID", filename, "$" )]
    errors.extend(_validate_text_integrity(chapter, filename))
    errors.extend(_validate_no_strong_fields(chapter, filename))
    if not _is_schema_one(chapter.get("schema")):
        errors.append(_error("CHAPTER_SCHEMA", filename, "$.schema"))
    if chapter.get("editie") != "nl-opv":
        errors.append(_error("CHAPTER_EDITION", filename, "$.editie"))
    if chapter.get("boek") != expected_book:
        errors.append(_error("CHAPTER_BOOK", filename, "$.boek"))
    chapter_number = chapter.get("hoofdstuk")
    if not _is_json_integer(chapter_number) or chapter_number != expected_chapter:
        errors.append(_error("CHAPTER_NUMBER", filename, "$.hoofdstuk"))
    if not _is_non_empty_string(chapter.get("kop")):
        errors.append(_error("CHAPTER_HEADING_MISSING", filename, "$.kop"))

    verses = chapter.get("verzen")
    if not isinstance(verses, list) or not verses:
        errors.append(_error("VERSES_MISSING", filename, "$.verzen"))
        verses = []
    verse_numbers: list[Any] = [
        verse.get("nummer") if isinstance(verse, dict) else None for verse in verses
    ]
    valid_numbers = [
        number
        for number in verse_numbers
        if _is_json_integer(number) and number > 0
    ]
    if len(valid_numbers) != len(verse_numbers):
        errors.append(_error("VERSE_NUMBER_INVALID", filename, "$.verzen"))
    if len(valid_numbers) != len(set(valid_numbers)):
        errors.append(_error("VERSE_DUPLICATE", filename, "$.verzen"))
    if valid_numbers != sorted(valid_numbers):
        errors.append(_error("VERSE_ORDER", filename, "$.verzen"))

    errors.extend(_validate_blocks(chapter, filename))
    segment_order: list[str] = []
    source_names: list[str] = []
    for index, verse in enumerate(verses):
        verse_errors, segment_ids, source_name = validate_verse(
            repo_root,
            verse,
            filename,
            f"$.verzen[{index}]",
            source_cache,
            seen_segment_ids,
            expected_book,
            expected_chapter,
        )
        errors.extend(verse_errors)
        segment_order.extend(segment_ids)
        if source_name is not None:
            source_names.append(source_name)

    if source_names and len(set(source_names)) != 1:
        errors.append(_error("SOURCE_FILE_INCONSISTENT", filename, "$.verzen"))
    elif source_names:
        source_doc = source_cache.get(source_names[0])
        if isinstance(source_doc, dict) and isinstance(source_doc.get("verses"), list):
            source_numbers = [
                source_verse.get("number")
                for source_verse in source_doc["verses"]
                if isinstance(source_verse, dict)
            ]
            if (
                not all(_is_json_integer(number) for number in verse_numbers)
                or not all(_is_json_integer(number) for number in source_numbers)
                or verse_numbers != source_numbers
            ):
                errors.append(_error("VERSE_LIST_MISMATCH", filename, "$.verzen"))

    positions = {segment_id: index for index, segment_id in enumerate(segment_order)}
    ranges: list[tuple[int, int, str]] = []
    for index, verse in enumerate(verses):
        annotation_errors, verse_ranges = validate_annotations(
            verse,
            filename,
            f"$.verzen[{index}]",
            concept_ids,
            positions,
            seen_citation_ids,
        )
        errors.extend(annotation_errors)
        ranges.extend(verse_ranges)
    for first_index, first in enumerate(ranges):
        for second in ranges[first_index + 1 :]:
            a_start, a_end, _ = first
            b_start, b_end, _ = second
            if (a_start < b_start <= a_end < b_end) or (
                b_start < a_start <= b_end < a_end
            ):
                errors.append(_error("CITATION_RANGES_CROSSED", filename, "$.verzen"))
                return errors
    return errors


def _concept_ids(concepts: Any, filename: str) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    identifiers: set[str] = set()
    if not isinstance(concepts, dict) or not _is_schema_one(concepts.get("schema")):
        errors.append(_error("CONCEPT_SCHEMA", filename, "$.schema"))
        return identifiers, errors
    entries = concepts.get("concepten")
    if not isinstance(entries, list):
        errors.append(_error("CONCEPT_LIST", filename, "$.concepten"))
        return identifiers, errors
    for index, concept in enumerate(entries):
        concept_id = concept.get("id") if isinstance(concept, dict) else None
        if not isinstance(concept_id, str) or not concept_id:
            errors.append(_error("CONCEPT_ID_MISSING", filename, f"$.concepten[{index}].id"))
        elif concept_id in identifiers:
            errors.append(_error("CONCEPT_ID_DUPLICATE", filename, f"$.concepten[{index}].id"))
        else:
            identifiers.add(concept_id)
    return identifiers, errors


def _opv_registry_entry(registry: Any) -> dict[str, Any] | None:
    if not isinstance(registry, dict) or not isinstance(registry.get("edities"), list):
        return None
    matches = [
        entry
        for entry in registry["edities"]
        if isinstance(entry, dict) and entry.get("code") == "nl-opv"
    ]
    return matches[0] if len(matches) == 1 else None


def _published_chapters_for_corpus(entry: dict[str, Any] | None) -> dict[str, list[int]]:
    if entry is None or not isinstance(entry.get("gepubliceerdeHoofdstukken"), dict):
        return {}
    return {
        book: chapters
        for book, chapters in entry["gepubliceerdeHoofdstukken"].items()
        if isinstance(book, str)
        and BOOK_CODE_RE.fullmatch(book)
        and isinstance(chapters, list)
        and all(_is_json_integer(chapter) and chapter > 0 for chapter in chapters)
        and len(chapters) == len(set(chapters))
        and chapters == sorted(chapters)
    }


def _validate_published_file_inventory(
    data_root_path: Path,
    data_root: str,
    chapter_map: dict[str, list[int]],
) -> list[str]:
    """Meld ieder hoofdstukbestand dat niet in de publicatielijst staat."""

    errors: list[str] = []
    registered = {
        (book, chapter)
        for book, chapters in chapter_map.items()
        for chapter in chapters
    }
    try:
        candidates = sorted(data_root_path.rglob("*.json"), key=lambda path: path.as_posix())
    except OSError:
        return [_error("MANIFEST_PATH_UNSAFE", data_root, "$")]
    for candidate in candidates:
        try:
            relative = candidate.relative_to(data_root_path)
            candidate.resolve().relative_to(data_root_path.resolve())
        except (OSError, RuntimeError, ValueError):
            errors.append(_error("MANIFEST_PATH_UNSAFE", data_root, "$"))
            continue
        filename = f"{data_root}/{relative.as_posix()}"
        if len(relative.parts) != 2:
            errors.append(_error("PUBLISHED_FILE_PATH_INVALID", filename, "$"))
            continue
        book, chapter_file = relative.parts
        stem = Path(chapter_file).stem
        if (
            BOOK_CODE_RE.fullmatch(book) is None
            or not stem.isdecimal()
            or int(stem) <= 0
            or chapter_file != f"{int(stem)}.json"
        ):
            errors.append(_error("PUBLISHED_FILE_PATH_INVALID", filename, "$"))
            continue
        if (book, int(stem)) not in registered:
            errors.append(_error("PUBLISHED_FILE_UNREGISTERED", filename, "$"))
    return errors


def validate_corpus(repo_root: Path) -> list[str]:
    """Valideer alle werkelijk gepubliceerde OPV-hoofdstukken."""

    root = Path(repo_root).resolve()
    errors: list[str] = []
    registry_file = "data/edities/manifest.json"
    edition_file = "data/edities/opv/manifest.json"
    concepts_file = "data/edities/opv/concepten.json"
    registry = _load_json(root, registry_file, errors)
    edition_manifest = _load_json(root, edition_file, errors)
    concepts = _load_json(root, concepts_file, errors)
    if registry is not None and edition_manifest is not None:
        errors.extend(validate_manifest(root, registry, edition_manifest))
    if concepts is None:
        return sorted(set(errors))
    errors.extend(_validate_text_integrity(concepts, concepts_file))
    errors.extend(_validate_no_strong_fields(concepts, concepts_file))
    concept_ids, concept_errors = _concept_ids(concepts, concepts_file)
    errors.extend(concept_errors)
    if edition_manifest is None:
        return sorted(set(errors))

    registry_entry = _opv_registry_entry(registry)
    data_root = registry_entry.get("dataRoot") if registry_entry is not None else None
    data_root_path = _safe_relative_path(root, data_root, require_json=False)
    if data_root_path is None:
        return sorted(set(errors))
    chapter_map = _published_chapters_for_corpus(registry_entry)
    errors.extend(_validate_published_file_inventory(data_root_path, data_root, chapter_map))
    source_cache: dict[str, Any] = {}
    seen_segment_ids: dict[str, str] = {}
    seen_citation_ids: dict[str, str] = {}
    for book in sorted(chapter_map):
        for chapter_number in chapter_map[book]:
            filename = f"{data_root}/{book}/{chapter_number}.json"
            chapter_path = _safe_relative_path(root, filename, require_json=True)
            if chapter_path is None:
                within_data_root = False
            else:
                try:
                    chapter_path.relative_to(data_root_path)
                    within_data_root = True
                except ValueError:
                    within_data_root = False
            if not within_data_root:
                errors.append(_error("MANIFEST_PATH_UNSAFE", edition_file, "$.boeken"))
                continue
            chapter = _load_json(root, filename, errors)
            if chapter is None:
                continue
            errors.extend(
                validate_chapter(
                    root,
                    chapter,
                    filename,
                    book,
                    chapter_number,
                    concept_ids,
                    source_cache,
                    seen_segment_ids,
                    seen_citation_ids,
                )
            )
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="hoofdmap van de repository",
    )
    args = parser.parse_args(argv)
    errors = validate_corpus(args.root)
    for error in errors:
        print(error)
    if errors:
        return 1
    registry = json.loads((args.root / "data/edities/manifest.json").read_text(encoding="utf-8"))
    entry = _opv_registry_entry(registry)
    chapter_count = 0
    verse_count = 0
    for book, numbers in _published_chapters_for_corpus(entry).items():
        for number in numbers:
            path = args.root / entry["dataRoot"] / book / f"{number}.json"
            chapter = json.loads(path.read_text(encoding="utf-8"))
            chapter_count += 1
            verse_count += len(chapter["verzen"])
    print(f"OPV geldig: {chapter_count} hoofdstukken, {verse_count} verzen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
