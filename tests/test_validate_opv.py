from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.validate_opv import _validate_blocks, validate_corpus


READING_TEXT = "God maakte in het begin de hemel en de aarde."
SOURCE_TEXT = "In den beginne schiep God den hemel en de aarde."


VALID_CHAPTER = {
    "schema": 1,
    "editie": "nl-opv",
    "boek": "genesis",
    "hoofdstuk": 1,
    "kop": "God maakt de hemel en de aarde",
    "blokken": [{"id": "gen-1-b1", "kop": "Het begin", "vanaf": 1, "tot": 1}],
    "verzen": [
        {
            "nummer": 1,
            "tekst": READING_TEXT,
            "bron": {
                "bestand": "data/genesis/1.json",
                "vers": 1,
                "tekstveld": "textSV1888",
            },
            "segmenten": [
                {
                    "id": "GEN.1.1.s1",
                    "tekst": READING_TEXT,
                    "bronfrase": "In den beginne schiep God den hemel en de aarde.",
                }
            ],
            "begrippen": [],
            "citaten": [],
            "review": {
                "status": "concept",
                "inhoudSha256": "3de1d2d8d4735d49b002aca96ba7fc4b0227acabe72cf4d03f9330f10c99f45c",
                "bronSha256": "ad7db6a21814ca5d62e90b9d9f04b435d51c91f41fbea1dcd872f573e4d4d5ee",
                "controles": [],
            },
        }
    ],
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class ValidateOpvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "repo"
        self.chapter = copy.deepcopy(VALID_CHAPTER)
        self.registry = {
            "schema": 1,
            "edities": [
                {
                    "code": "nl-opv",
                    "naam": "Open Parafrase Weergave (proef)",
                    "taal": "nl",
                    "richting": "ltr",
                    "dataRoot": "data/edities/opv/chapters",
                    "boeken": ["genesis"],
                    "hoofdstukken": {"genesis": [1]},
                    "gepubliceerdeHoofdstukken": {"genesis": [1]},
                    "status": "pilot",
                }
            ],
        }
        self.edition_manifest = {
            "schema": 1,
            "editie": "nl-opv",
            "naam": "Open Parafrase Weergave (proef)",
            "taal": "nl",
            "richting": "ltr",
            "status": "pilot",
            "versie": "0.1.0",
            "doelgroep": "16-jarige HAVO-lezer",
            "bronnenbeleid": {
                "basistekst": "Statenvertaling 1888",
                "controlebronnen": [
                    "Statenvertaling 1637",
                    "Open Vertaling",
                    "Hebreeuwse en Griekse grondtekst",
                ],
            },
            "redactioneleStatussen": [
                "concept",
                "bron_gecontroleerd",
                "taal_gecontroleerd",
                "definitief",
            ],
            "gepubliceerdeHoofdstukken": {"genesis": [1]},
            "boeken": [{"code": "genesis", "hoofdstukken": [1]}],
        }
        self.concepts = {
            "schema": 1,
            "concepten": [
                {
                    "id": "schepping",
                    "label": "Schepping",
                    "uitleg": "God brengt de werkelijkheid tot bestaan.",
                }
            ],
        }
        self._write_all()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_all(self) -> None:
        write_json(self.root / "data/edities/manifest.json", self.registry)
        write_json(self.root / "data/edities/opv/manifest.json", self.edition_manifest)
        write_json(self.root / "data/edities/opv/concepten.json", self.concepts)
        self._write_source("genesis", 1, SOURCE_TEXT)
        self._write_chapter(self.chapter)

    def _write_source(self, book: str, chapter: int, text: str) -> None:
        self._write_source_verses(
            book, chapter, [{"number": 1, "textSV1888": text}]
        )

    def _write_source_verses(
        self, book: str, chapter: int, verses: list[dict]
    ) -> None:
        write_json(
            self.root / f"data/{book}/{chapter}.json",
            {"number": chapter, "verses": verses},
        )

    def _write_chapter(self, chapter: dict) -> None:
        write_json(
            self.root
            / "data/edities/opv/chapters"
            / chapter["boek"]
            / f'{chapter["hoofdstuk"]}.json',
            chapter,
        )

    def _errors_after_rewrite(self) -> list[str]:
        self._write_all()
        return validate_corpus(self.root)

    def assertHasCode(self, errors: list[str], code: str) -> None:
        self.assertTrue(
            any(error.split(" ", 1)[0] == code for error in errors),
            f"{code!r} niet gevonden in {errors!r}",
        )

    def _configure_two_verse_chapter(self) -> None:
        second = {
            "nummer": 2,
            "tekst": "De aarde was leeg en donker.",
            "bron": {
                "bestand": "data/genesis/1.json",
                "vers": 2,
                "tekstveld": "textSV1888",
            },
            "segmenten": [
                {
                    "id": "GEN.1.2.s1",
                    "tekst": "De aarde was leeg en donker.",
                    "bronfrase": "De aarde nu was woest en ledig.",
                }
            ],
            "begrippen": [],
            "citaten": [],
            "review": {
                "status": "concept",
                "inhoudSha256": "9c6fcc12a7bbf286f47042b100fb8cb9c8462c1585ab444443074f5bcbb5951c",
                "bronSha256": "25f782d86a4d2b779fce6a903d2d5770cdc7c363d0ee92842bc6b76c6a683583",
                "controles": [],
            },
        }
        self.chapter["verzen"].append(second)
        self.chapter["blokken"][0]["tot"] = 2

    def test_valid_mini_corpus_has_no_errors(self) -> None:
        self.assertEqual([], validate_corpus(self.root))

    def test_gepubliceerde_hoofdstukken_is_verplicht_in_beide_manifesten(self) -> None:
        del self.registry["edities"][0]["gepubliceerdeHoofdstukken"]
        del self.edition_manifest["gepubliceerdeHoofdstukken"]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_FIELD_MISSING")
        self.assertHasCode(errors, "EDITION_FIELD_MISSING")

    def test_gepubliceerde_hoofdstukken_weigert_malformed_waarden(self) -> None:
        cases = (
            ({"genesis": "1"}, "PUBLISHED_CHAPTERS_INVALID"),
            ({"genesis": [True]}, "PUBLISHED_CHAPTERS_INVALID"),
            ({"genesis": [1, 1]}, "PUBLISHED_CHAPTERS_INVALID"),
            ({"genesis": [2, 1]}, "PUBLISHED_CHAPTERS_INVALID"),
            ({"exodus": [1]}, "PUBLISHED_BOOK_UNKNOWN"),
            ({"../escape": [True, 999, "1"]}, "MANIFEST_PATH_UNSAFE"),
        )
        for value, expected_code in cases:
            with self.subTest(value=value):
                self.registry["edities"][0]["hoofdstukken"]["genesis"] = [1, 2]
                self.edition_manifest["boeken"][0]["hoofdstukken"] = [1, 2]
                self.registry["edities"][0]["gepubliceerdeHoofdstukken"] = copy.deepcopy(value)
                self.edition_manifest["gepubliceerdeHoofdstukken"] = copy.deepcopy(value)
                errors = self._errors_after_rewrite()
                self.assertHasCode(errors, expected_code)
                self.assertEqual(sorted(errors), errors)

    def test_gepubliceerde_hoofdstukken_moet_binnen_de_planning_vallen(self) -> None:
        published = {"genesis": [2]}
        self.registry["edities"][0]["gepubliceerdeHoofdstukken"] = published
        self.edition_manifest["gepubliceerdeHoofdstukken"] = copy.deepcopy(published)
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "PUBLISHED_CHAPTER_OUTSIDE_PLAN")

    def test_publicatielijsten_in_beide_manifesten_moeten_gelijk_zijn(self) -> None:
        self.edition_manifest["gepubliceerdeHoofdstukken"] = {"genesis": []}
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "PUBLISHED_CHAPTERS_MISMATCH")

    def test_geregistreerd_gepubliceerd_hoofdstuk_moet_bestaan(self) -> None:
        planned = [1, 2]
        published = {"genesis": [1, 2]}
        self.registry["edities"][0]["hoofdstukken"]["genesis"] = planned
        self.edition_manifest["boeken"][0]["hoofdstukken"] = planned
        self.registry["edities"][0]["gepubliceerdeHoofdstukken"] = published
        self.edition_manifest["gepubliceerdeHoofdstukken"] = copy.deepcopy(published)
        errors = self._errors_after_rewrite()
        self.assertIn(
            "FILE_MISSING data/edities/opv/chapters/genesis/2.json $",
            errors,
        )

    def test_aanwezig_hoofdstukbestand_moet_geregistreerd_zijn(self) -> None:
        second = copy.deepcopy(self.chapter)
        second["hoofdstuk"] = 2
        second["blokken"][0]["id"] = "gen-2-b1"
        second["verzen"][0]["bron"]["bestand"] = "data/genesis/2.json"
        self.registry["edities"][0]["hoofdstukken"]["genesis"] = [1, 2]
        self.edition_manifest["boeken"][0]["hoofdstukken"] = [1, 2]
        self._write_all()
        self._write_source("genesis", 2, SOURCE_TEXT)
        self._write_chapter(second)
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "PUBLISHED_FILE_UNREGISTERED")

    def test_json_booleans_are_rejected_for_every_schema_field(self) -> None:
        self.registry["schema"] = True
        self.edition_manifest["schema"] = True
        self.concepts["schema"] = True
        self.chapter["schema"] = True
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_SCHEMA")
        self.assertHasCode(errors, "EDITION_SCHEMA")
        self.assertHasCode(errors, "CONCEPT_SCHEMA")
        self.assertHasCode(errors, "CHAPTER_SCHEMA")

    def test_json_boolean_is_not_an_opv_chapter_number(self) -> None:
        self.chapter["hoofdstuk"] = True
        write_json(
            self.root / "data/edities/opv/chapters/genesis/1.json",
            self.chapter,
        )
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "CHAPTER_NUMBER")

    def test_json_booleans_are_rejected_for_source_chapter_and_verse_numbers(self) -> None:
        self.chapter["verzen"][0]["bron"]["vers"] = True
        self._write_all()
        write_json(
            self.root / "data/genesis/1.json",
            {
                "number": True,
                "verses": [{"number": True, "textSV1888": SOURCE_TEXT}],
            },
        )
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "SOURCE_CHAPTER_MISMATCH")
        self.assertHasCode(errors, "SOURCE_VERSE_MISMATCH")
        self.assertHasCode(errors, "SOURCE_VERSE_NUMBER_INVALID")

    def test_boolean_verse_and_block_numbers_remain_invalid(self) -> None:
        self.chapter["verzen"][0]["nummer"] = True
        self.chapter["blokken"][0]["vanaf"] = True
        self.chapter["blokken"][0]["tot"] = True
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "VERSE_NUMBER_INVALID")
        self.assertHasCode(errors, "BLOCK_RANGE_INVALID")

    def test_boolean_manifest_chapter_number_remains_invalid(self) -> None:
        self.registry["edities"][0]["hoofdstukken"]["genesis"] = [True]
        self.edition_manifest["boeken"][0]["hoofdstukken"] = [True]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_CHAPTERS_INVALID")
        self.assertHasCode(errors, "EDITION_CHAPTER_INVALID")

    def test_nul_in_source_path_returns_a_deterministic_error(self) -> None:
        self.chapter["verzen"][0]["bron"]["bestand"] = "data/genesis/\x00.json"
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SOURCE_PATH_UNSAFE")
        self.assertEqual(sorted(errors), errors)

    def test_nul_in_data_root_returns_a_deterministic_error(self) -> None:
        self.registry["edities"][0]["dataRoot"] = "data/edities/\x00/chapters"
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_PATH_UNSAFE")
        self.assertEqual(sorted(errors), errors)

    def test_other_unsafe_path_characters_return_contract_errors(self) -> None:
        for character in ("\n", "\r", "\t", ":", "?", "*", "<", ">", '"', "|"):
            with self.subTest(character=repr(character)):
                self.chapter["verzen"][0]["bron"]["bestand"] = (
                    f"data/genesis/unsafe{character}.json"
                )
                self.registry["edities"][0]["dataRoot"] = (
                    "data/edities/opv/chapters"
                )
                source_errors = self._errors_after_rewrite()
                self.assertHasCode(source_errors, "SOURCE_PATH_UNSAFE")

                self.chapter["verzen"][0]["bron"]["bestand"] = "data/genesis/1.json"
                self.registry["edities"][0]["dataRoot"] = (
                    f"data/edities/opv/{character}/chapters"
                )
                manifest_errors = self._errors_after_rewrite()
                self.assertHasCode(manifest_errors, "MANIFEST_PATH_UNSAFE")

    def test_dynamic_json_path_control_characters_stay_on_one_cli_line(self) -> None:
        self.chapter["strong\nbad"] = "H1"
        self._write_all()
        script = Path(__file__).parents[1] / "scripts/validate_opv.py"
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertEqual(1, len(result.stdout.splitlines()), result.stdout)
        self.assertIn(r"\n", result.stdout)

    def test_source_verse_must_match_current_opv_verse(self) -> None:
        self._configure_two_verse_chapter()
        self.chapter["verzen"][1]["bron"]["vers"] = 1
        self.chapter["verzen"][1]["review"]["bronSha256"] = (
            "ad7db6a21814ca5d62e90b9d9f04b435d51c91f41fbea1dcd872f573e4d4d5ee"
        )
        self._write_all()
        self._write_source_verses(
            "genesis",
            1,
            [
                {"number": 1, "textSV1888": SOURCE_TEXT},
                {
                    "number": 2,
                    "textSV1888": "De aarde nu was woest en ledig.",
                },
            ],
        )
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "SOURCE_VERSE_MISMATCH")

    def test_source_file_must_match_current_opv_book_and_chapter(self) -> None:
        self.chapter["verzen"][0]["bron"]["bestand"] = "data/johannes/2.json"
        self._write_all()
        self._write_source("johannes", 2, SOURCE_TEXT)
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "SOURCE_PATH_MISMATCH")

    def test_source_document_chapter_must_match_current_opv_chapter(self) -> None:
        self._write_all()
        write_json(
            self.root / "data/genesis/1.json",
            {"number": 2, "verses": [{"number": 1, "textSV1888": SOURCE_TEXT}]},
        )
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "SOURCE_CHAPTER_MISMATCH")

    def test_edition_manifest_requires_all_contract_metadata(self) -> None:
        complete = copy.deepcopy(self.edition_manifest)
        fields = [
            "naam",
            "taal",
            "richting",
            "status",
            "versie",
            "doelgroep",
            "bronnenbeleid",
            "redactioneleStatussen",
        ]
        for field in fields:
            with self.subTest(field=field):
                self.edition_manifest = copy.deepcopy(complete)
                del self.edition_manifest[field]
                self._write_all()
                errors = validate_corpus(self.root)
                self.assertTrue(
                    any(
                        error.startswith("EDITION_FIELD_MISSING ")
                        and error.endswith(f"$.{field}")
                        for error in errors
                    ),
                    errors,
                )

    def test_edition_manifest_rejects_incorrect_editorial_statuses(self) -> None:
        self.edition_manifest["redactioneleStatussen"] = ["concept", "klaar"]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "EDITION_REVIEW_STATUSES")

    def test_chapter_and_block_require_non_empty_headings_and_block_id(self) -> None:
        self.chapter["kop"] = " "
        self.chapter["blokken"][0]["kop"] = ""
        self.chapter["blokken"][0]["id"] = None
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "CHAPTER_HEADING_MISSING")
        self.assertHasCode(errors, "BLOCK_HEADING_MISSING")
        self.assertHasCode(errors, "BLOCK_ID_MISSING")

    def test_block_ids_are_unique(self) -> None:
        self._configure_two_verse_chapter()
        self.chapter["blokken"] = [
            {"id": "gen-1-b1", "kop": "Eerste", "vanaf": 1, "tot": 1},
            {"id": "gen-1-b1", "kop": "Tweede", "vanaf": 2, "tot": 2},
        ]
        self._write_all()
        self._write_source_verses(
            "genesis",
            1,
            [
                {"number": 1, "textSV1888": SOURCE_TEXT},
                {
                    "number": 2,
                    "textSV1888": "De aarde nu was woest en ledig.",
                },
            ],
        )
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "BLOCK_ID_DUPLICATE")

    def test_blocks_must_be_sorted_by_verse_range(self) -> None:
        self._configure_two_verse_chapter()
        self.chapter["blokken"] = [
            {"id": "gen-1-b2", "kop": "Tweede", "vanaf": 2, "tot": 2},
            {"id": "gen-1-b1", "kop": "Eerste", "vanaf": 1, "tot": 1},
        ]
        self._write_all()
        self._write_source_verses(
            "genesis",
            1,
            [
                {"number": 1, "textSV1888": SOURCE_TEXT},
                {
                    "number": 2,
                    "textSV1888": "De aarde nu was woest en ledig.",
                },
            ],
        )
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "BLOCK_ORDER")

    def test_manifest_book_code_cannot_escape_data_root(self) -> None:
        malicious_book = "../../../../../escaped"
        self.registry["edities"][0]["boeken"] = [malicious_book]
        self.registry["edities"][0]["hoofdstukken"] = {malicious_book: [1]}
        self.edition_manifest["boeken"] = [
            {"code": malicious_book, "hoofdstukken": [1]}
        ]
        escaped_chapter = copy.deepcopy(self.chapter)
        escaped_chapter["boek"] = malicious_book
        self._write_all()
        write_json(self.root.parent / "escaped/1.json", escaped_chapter)
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "MANIFEST_PATH_UNSAFE")

    def test_wrong_registry_container_types_return_errors_without_traceback(self) -> None:
        self.registry["edities"][0]["boeken"] = ["genesis", 1]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_BOOKS_INVALID")
        self.assertEqual(sorted(errors), errors)

    def test_wrong_registry_scalar_container_returns_error_without_traceback(self) -> None:
        self.registry["edities"][0]["richting"] = {}
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_DIRECTION")
        self.assertEqual(sorted(errors), errors)

    def test_registry_text_fields_reject_non_empty_containers(self) -> None:
        self.registry["edities"][0]["naam"] = {"waarde": "OPV"}
        self.registry["edities"][0]["taal"] = ["nl"]
        self.registry["edities"][0]["status"] = {"fase": "pilot"}
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "MANIFEST_FIELD_INVALID")
        self.assertEqual(sorted(errors), errors)

    def test_duplicate_verse_number_is_reported(self) -> None:
        self.chapter["verzen"].append(copy.deepcopy(self.chapter["verzen"][0]))
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "VERSE_DUPLICATE")

    def test_empty_reading_text_is_reported(self) -> None:
        self.chapter["verzen"][0]["tekst"] = ""
        self.chapter["verzen"][0]["segmenten"][0]["tekst"] = ""
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "TEXT_EMPTY")

    def test_html_in_reading_text_is_reported(self) -> None:
        self.chapter["verzen"][0]["tekst"] = "God <em>maakte</em> alles."
        self.chapter["verzen"][0]["segmenten"][0]["tekst"] = (
            "God <em>maakte</em> alles."
        )
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "TEXT_HTML")

    def test_missing_source_is_reported(self) -> None:
        del self.chapter["verzen"][0]["bron"]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SOURCE_MISSING")

    def test_unsafe_source_path_is_reported(self) -> None:
        self.chapter["verzen"][0]["bron"]["bestand"] = "../geheim.json"
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SOURCE_PATH_UNSAFE")

    def test_overlapping_blocks_are_reported(self) -> None:
        self.chapter["blokken"].append(
            {"id": "gen-1-b2", "kop": "Nogmaals", "vanaf": 1, "tot": 1}
        )
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "BLOCKS_OVERLAP")

    def test_incomplete_blocks_are_reported(self) -> None:
        self.chapter["blokken"] = []
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "BLOCKS_INCOMPLETE")

    def test_extreme_block_range_is_bounded_and_reports_one_compact_error(self) -> None:
        self.chapter["blokken"][0]["tot"] = 100_000

        started_at = time.perf_counter()
        errors = _validate_blocks(self.chapter, "chapter.json")
        elapsed = time.perf_counter() - started_at

        unknown_verse_errors = [
            error
            for error in errors
            if error.startswith("BLOCK_RANGE_UNKNOWN_VERSE ")
        ]
        self.assertEqual(1, len(unknown_verse_errors), errors[:3])
        self.assertLess(elapsed, 0.25)

    def test_duplicate_segment_id_across_chapters_is_reported(self) -> None:
        second = copy.deepcopy(self.chapter)
        second["hoofdstuk"] = 2
        second["blokken"][0]["id"] = "gen-2-b1"
        second["verzen"][0]["bron"]["bestand"] = "data/genesis/2.json"
        self.registry["edities"][0]["hoofdstukken"]["genesis"] = [1, 2]
        self.edition_manifest["boeken"][0]["hoofdstukken"] = [1, 2]
        self.registry["edities"][0]["gepubliceerdeHoofdstukken"]["genesis"] = [1, 2]
        self.edition_manifest["gepubliceerdeHoofdstukken"]["genesis"] = [1, 2]
        self._write_all()
        self._write_source("genesis", 2, SOURCE_TEXT)
        self._write_chapter(second)
        errors = validate_corpus(self.root)
        self.assertHasCode(errors, "SEGMENT_DUPLICATE")

    def test_unknown_concept_is_reported(self) -> None:
        self.chapter["verzen"][0]["begrippen"] = [
            {"conceptId": "onbekend", "segmenten": ["GEN.1.1.s1"]}
        ]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "CONCEPT_UNKNOWN")

    def test_unknown_segment_reference_is_reported(self) -> None:
        self.chapter["verzen"][0]["begrippen"] = [
            {"conceptId": "schepping", "segmenten": ["GEN.1.1.s9"]}
        ]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SEGMENT_REFERENCE_UNKNOWN")

    def test_citation_without_speaker_id_is_reported(self) -> None:
        self.chapter["verzen"][0]["citaten"] = [self._valid_citation()]
        del self.chapter["verzen"][0]["citaten"][0]["spreker"]["id"]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SPEAKER_ID_MISSING")

    def test_citation_without_speaker_type_is_reported(self) -> None:
        self.chapter["verzen"][0]["citaten"] = [self._valid_citation()]
        del self.chapter["verzen"][0]["citaten"][0]["spreker"]["type"]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SPEAKER_TYPE_MISSING")

    def test_segments_must_reconstruct_reading_text_exactly(self) -> None:
        self.chapter["verzen"][0]["segmenten"][0]["tekst"] += " "
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SEGMENTS_TEXT_MISMATCH")

    def test_segment_source_anchor_must_be_an_exact_source_substring(self) -> None:
        segment = self.chapter["verzen"][0]["segmenten"][0]
        segment["bronfrase"] = "In den beginne schiep God den hemel en de aardÃ«"
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SEGMENT_SOURCE_ANCHOR_NOT_FOUND")

    def test_segment_source_anchor_is_required(self) -> None:
        del self.chapter["verzen"][0]["segmenten"][0]["bronfrase"]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "SEGMENT_SOURCE_ANCHOR_MISSING")

    def test_source_and_content_hashes_are_checked(self) -> None:
        review = self.chapter["verzen"][0]["review"]
        review["inhoudSha256"] = "0" * 64
        review["bronSha256"] = "f" * 64
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "REVIEW_CONTENT_HASH")
        self.assertHasCode(errors, "REVIEW_SOURCE_HASH")

    def test_non_nfc_text_and_replacement_character_are_reported(self) -> None:
        self.chapter["kop"] = "Schépping \ufffd"
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "UNICODE_NOT_NFC")
        self.assertHasCode(errors, "UNICODE_REPLACEMENT")

    def test_any_strong_field_is_rejected(self) -> None:
        self.chapter["verzen"][0]["segmenten"][0]["strongs"] = "H430"
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "STRONG_FIELD_FORBIDDEN")

    def test_citation_requires_unique_id_and_canonical_semantic_id(self) -> None:
        citation = self._valid_citation()
        duplicate = copy.deepcopy(citation)
        duplicate["semanticId"] = "Niet canoniek"
        self.chapter["verzen"][0]["citaten"] = [citation, duplicate]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "CITATION_ID_DUPLICATE")
        self.assertHasCode(errors, "SEMANTIC_ID_INVALID")

    def test_crossed_citation_ranges_are_rejected(self) -> None:
        verse = self.chapter["verzen"][0]
        verse["tekst"] = "Een twee drie vier."
        verse["segmenten"] = [
            {"id": "GEN.1.1.s1", "tekst": "Een "},
            {"id": "GEN.1.1.s2", "tekst": "twee "},
            {"id": "GEN.1.1.s3", "tekst": "drie "},
            {"id": "GEN.1.1.s4", "tekst": "vier."},
        ]
        verse["review"]["inhoudSha256"] = (
            "de028ba98b32ff4e609ddbc792e427579b42046c8a66870de16fae4d524379b3"
        )
        first = self._valid_citation()
        first.update({"startSegment": "GEN.1.1.s1", "endSegment": "GEN.1.1.s3"})
        second = self._valid_citation()
        second.update(
            {
                "id": "GEN.1.1.q2",
                "semanticId": "spraak.god.tweede",
                "startSegment": "GEN.1.1.s2",
                "endSegment": "GEN.1.1.s4",
            }
        )
        verse["citaten"] = [first, second]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "CITATION_RANGES_CROSSED")

    def test_final_status_requires_three_current_approvals(self) -> None:
        review = self.chapter["verzen"][0]["review"]
        review["status"] = "definitief"
        review["controles"] = [
            {
                "type": "bron",
                "status": "goedgekeurd",
                "inhoudSha256": review["inhoudSha256"],
            },
            {
                "type": "taal",
                "status": "goedgekeurd",
                "inhoudSha256": review["inhoudSha256"],
            },
        ]
        errors = self._errors_after_rewrite()
        self.assertHasCode(errors, "FINAL_REVIEW_MISSING")

    def test_errors_are_deterministically_sorted(self) -> None:
        self.chapter["verzen"][0]["tekst"] = ""
        self.chapter["verzen"][0]["segmenten"] = []
        errors = self._errors_after_rewrite()
        self.assertEqual(sorted(errors), errors)

    def test_cli_returns_zero_for_valid_data_and_one_error_per_line(self) -> None:
        script = Path(__file__).parents[1] / "scripts/validate_opv.py"
        valid = subprocess.run(
            [sys.executable, str(script), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, valid.returncode, valid.stdout + valid.stderr)
        self.assertEqual("OPV geldig: 1 hoofdstukken, 1 verzen.\n", valid.stdout)

        self.chapter["verzen"][0]["tekst"] = ""
        self.chapter["verzen"][0]["segmenten"] = []
        self._write_all()
        invalid = subprocess.run(
            [sys.executable, str(script), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, invalid.returncode)
        lines = invalid.stdout.splitlines()
        self.assertGreater(len(lines), 0)
        self.assertTrue(all(line.count(" ") >= 2 for line in lines))

    @staticmethod
    def _valid_citation() -> dict:
        return {
            "id": "GEN.1.1.q1",
            "semanticId": "spraak.god.schepping",
            "startSegment": "GEN.1.1.s1",
            "endSegment": "GEN.1.1.s1",
            "spreker": {"id": "god", "type": "god", "naam": "God"},
            "aangesprokene": [],
        }


class OpvCalibrationCorpusTests(unittest.TestCase):
    """Detecteer ontbrekende verzen en ongeldige bron- of metadatakoppelingen."""

    root = Path(__file__).resolve().parents[1]

    def _chapter(self, book: str) -> dict:
        path = self.root / f"data/edities/opv/chapters/{book}/1.json"
        self.assertTrue(path.is_file(), f"Kalibratiehoofdstuk ontbreekt: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_genesis_one_has_all_31_verses(self) -> None:
        chapter = self._chapter("genesis")
        self.assertEqual(list(range(1, 32)), [v["nummer"] for v in chapter["verzen"]])

    def test_john_one_has_all_52_repository_verses(self) -> None:
        chapter = self._chapter("johannes")
        self.assertEqual(list(range(1, 53)), [v["nummer"] for v in chapter["verzen"]])

    def test_calibration_sources_point_to_corresponding_sv_verse(self) -> None:
        for book in ("genesis", "johannes"):
            chapter = self._chapter(book)
            self.assertEqual((book, 1), (chapter["boek"], chapter["hoofdstuk"]))
            for verse in chapter["verzen"]:
                with self.subTest(book=book, verse=verse["nummer"]):
                    self.assertEqual(
                        {"bestand": f"data/{book}/1.json", "vers": verse["nummer"],
                         "tekstveld": "textSV1888"}, verse["bron"],
                    )

    @staticmethod
    def _concept_texts(verse: dict, concept_id: str) -> list[str]:
        segments = {segment["id"]: segment["tekst"] for segment in verse["segmenten"]}
        return [
            "".join(segments[reference] for reference in concept["segmenten"])
            for concept in verse["begrippen"] if concept["conceptId"] == concept_id
        ]

    @staticmethod
    def _citation_text(verse: dict, citation: dict) -> str:
        ids = [segment["id"] for segment in verse["segmenten"]]
        start = ids.index(citation["startSegment"])
        end = ids.index(citation["endSegment"])
        return "".join(segment["tekst"] for segment in verse["segmenten"][start:end + 1])

    def test_john_links_both_life_occurrences_and_required_concepts(self) -> None:
        chapter = self._chapter("johannes")
        self.assertEqual(["leven", "Dat leven"], self._concept_texts(chapter["verzen"][3], "leven"))
        required = {"woord", "leven", "licht", "genade", "waarheid", "messias",
                    "lam-van-god", "heilige-geest", "zoon-van-god", "mensenzoon"}
        linked = {c["conceptId"] for v in chapter["verzen"] for c in v["begrippen"]}
        registry = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))
        self.assertLessEqual(required, linked)
        self.assertLessEqual(required, {c["id"] for c in registry["concepten"]})

    def test_john_isaiah_quote_is_exact_and_nested(self) -> None:
        verse = self._chapter("johannes")["verzen"][22]
        self.assertEqual(2, len(verse["citaten"]))
        outer, inner = verse["citaten"]
        self.assertEqual("johannes", outer["spreker"]["id"])
        self.assertEqual(("jesaja", "human"), (inner["spreker"]["id"], inner["spreker"]["type"]))
        self.assertEqual("Maak voor de Heere een rechte weg.", self._citation_text(verse, inner))
        self.assertEqual("Ik ben de stem van iemand die in de woestijn roept: Maak voor de Heere een rechte weg. Dat heeft de profeet Jesaja gezegd.", self._citation_text(verse, outer))
        ids = [s["id"] for s in verse["segmenten"]]
        self.assertLess(ids.index(outer["startSegment"]), ids.index(inner["startSegment"]))
        self.assertLess(ids.index(inner["endSegment"]), ids.index(outer["endSegment"]))

    def test_concept_anchors_include_essential_modifiers_and_action(self) -> None:
        for book, number, concept, expected in (
            ("genesis", 21, "zeedieren", "grote zeedieren"),
            ("johannes", 14, "menswording", "werd mens"),
            ("johannes", 21, "de-profeet", "de profeet"),
        ):
            with self.subTest(book=book, verse=number):
                verse = self._chapter(book)["verzen"][number - 1]
                self.assertEqual([expected], self._concept_texts(verse, concept))

    def test_calibration_blocks_follow_the_repository_verse_boundaries(self) -> None:
        expected = {
            "genesis": [(1, 2), (3, 5), (6, 8), (9, 13), (14, 19), (20, 23), (24, 31)],
            "johannes": [(1, 5), (6, 13), (14, 18), (19, 28), (29, 34), (35, 43), (44, 52)],
        }
        for book, ranges in expected.items():
            self.assertEqual(ranges, [(b["vanaf"], b["tot"]) for b in self._chapter(book)["blokken"]])

    def test_john_creation_statement_retains_the_created_scope(self) -> None:
        text = self._chapter("johannes")["verzen"][2]["tekst"]
        self.assertIn("Niets wat gemaakt is, is zonder Hem ontstaan.", text)
        self.assertNotIn("wat bestaat", text)

    def test_genesis_water_both_produces_and_teems_with_life(self) -> None:
        verses = self._chapter("genesis")["verzen"]
        self.assertIn("voortbr", verses[19]["tekst"])
        for number in (20, 21):
            with self.subTest(verse=number):
                text = verses[number - 1]["tekst"]
                self.assertIn("overvloed", text)
                self.assertIn("wemel", text)

    def test_genesis_food_refers_explicitly_to_plants_and_fruit(self) -> None:
        text = self._chapter("genesis")["verzen"][28]["tekst"]
        self.assertIn("De planten en de vruchten zijn jullie voedsel.", text)

    def test_john_second_identity_question_has_a_narrative_speaker_intro(self) -> None:
        verse = self._chapter("johannes")["verzen"][20]
        self.assertIn("Ze vroegen verder: Bent u de profeet?", verse["tekst"])
        self.assertEqual(["gezanten", "johannes", "gezanten", "johannes"],
                         [q["spreker"]["id"] for q in verse["citaten"]])
        self.assertEqual("Bent u de profeet?", self._citation_text(verse, verse["citaten"][2]))

    def test_annotations_are_owned_by_their_verse_and_segments_are_sequential(self) -> None:
        for book, prefix in (("genesis", "GEN"), ("johannes", "JHN")):
            for verse in self._chapter(book)["verzen"]:
                ids = [s["id"] for s in verse["segmenten"]]
                self.assertEqual([f"{prefix}.1.{verse['nummer']}.s{i}" for i in range(1, len(ids) + 1)], ids)
                for concept in verse["begrippen"]:
                    self.assertLessEqual(set(concept["segmenten"]), set(ids))
                for citation in verse["citaten"]:
                    self.assertIn(citation["startSegment"], ids)
                    self.assertIn(citation["endSegment"], ids)

    def test_capitalization_preserves_sentence_starts_without_extra_reverence(self) -> None:
        cases = [
            ("genesis", 30, "geef ik de groene planten"),
            ("johannes", 12, ". Dat zijn de mensen die in Zijn naam geloven."),
            ("johannes", 13, ". Dat komt niet door hun afkomst"),
            ("johannes", 14, ". Wij zagen Zijn majesteit"),
            ("johannes", 15, "Dit is degene over wie ik sprak."),
            ("johannes", 30, "een man die boven mij staat"),
            ("johannes", 38, "Jezus draaide zich om"),
            ("johannes", 44, "Volg mij."),
            ("johannes", 48, "naar Hem toe"),
            ("johannes", 49, "zag ik je al"),
            ("johannes", 51, "omdat ik je zei dat ik je"),
        ]
        for book, number, expected in cases:
            with self.subTest(book=book, verse=number):
                self.assertIn(expected, self._chapter(book)["verzen"][number - 1]["tekst"])

    def test_concept_explanations_do_not_add_reverence_capitals(self) -> None:
        registry = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))
        for concept in registry["concepten"]:
            with self.subTest(concept=concept["id"]):
                self.assertNotRegex(concept["uitleg"], r"\b(?:Naam|Persoon|Zichzelf)\b")
        explanations = {c["id"]: c["uitleg"] for c in registry["concepten"]}
        self.assertIn("Zijn naam", explanations["kinderen-van-god"])

    def test_editorial_decisions_do_not_add_reverence_capitals(self) -> None:
        register = (self.root / "docs/opv/besluitregister.md").read_text(encoding="utf-8")
        own_prose = re.sub(r"“[^”]*”|`[^`]*`", "", register)
        self.assertEqual([], re.findall(r"\b(?:Naam|Persoon|Zichzelf|Degene door Wie)\b", own_prose))
        self.assertIn("Jezus Christus als degene door wie", own_prose)

    def test_calibration_slice_passes_real_corpus_validation(self) -> None:
        chapters = {book: self._chapter(book) for book in ("genesis", "johannes")}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = json.loads((self.root / "data/edities/manifest.json").read_text(encoding="utf-8"))
            registry["edities"] = [entry for entry in registry["edities"] if entry["code"] == "nl-opv"]
            edition = json.loads((self.root / "data/edities/opv/manifest.json").read_text(encoding="utf-8"))
            registry["edities"][0]["boeken"] = ["genesis", "johannes"]
            registry["edities"][0]["hoofdstukken"] = {"genesis": [1], "johannes": [1]}
            registry["edities"][0]["gepubliceerdeHoofdstukken"] = {"genesis": [1], "johannes": [1]}
            edition["boeken"] = [
                {"code": "genesis", "hoofdstukken": [1]},
                {"code": "johannes", "hoofdstukken": [1]},
            ]
            edition["gepubliceerdeHoofdstukken"] = {"genesis": [1], "johannes": [1]}
            write_json(root / "data/edities/manifest.json", registry)
            write_json(root / "data/edities/opv/manifest.json", edition)
            concepts = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))
            write_json(root / "data/edities/opv/concepten.json", concepts)
            for book, chapter in chapters.items():
                write_json(root / f"data/edities/opv/chapters/{book}/1.json", chapter)
                source = json.loads((self.root / f"data/{book}/1.json").read_text(encoding="utf-8"))
                write_json(root / f"data/{book}/1.json", source)
            self.assertEqual([], validate_corpus(root))

    def test_productie_cli_meldt_de_volledige_gepubliceerde_pilot(self) -> None:
        script = self.root / "scripts/validate_opv.py"
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("OPV geldig: 1604 hoofdstukken, 41181 verzen.\n", result.stdout)


class OpvGenesisPilotTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/genesis/{number}.json"
        self.assertTrue(path.is_file(), f"Genesis-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_genesis_has_exact_source_verse_lists_and_1533_verses(self) -> None:
        total = 0
        for number in range(1, 51):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads((self.root / f"data/genesis/{number}.json").read_text(encoding="utf-8"))
                self.assertEqual([v["number"] for v in source["verses"]],
                                 [v["nummer"] for v in chapter["verzen"]])
                total += len(chapter["verzen"])
                self.assertEqual(("genesis", number), (chapter["boek"], chapter["hoofdstuk"]))
                self.assertTrue(chapter["blokken"])
                for verse in chapter["verzen"]:
                    self.assertEqual({"bestand": f"data/genesis/{number}.json",
                                      "vers": verse["nummer"], "tekstveld": "textSV1888"}, verse["bron"])
        self.assertEqual(1533, total)

    def test_new_genesis_blocks_cover_the_approved_passages(self) -> None:
        expected = {
            2: [(1, 3), (4, 7), (8, 14), (15, 17), (18, 20), (21, 25)],
            3: [(1, 5), (6, 7), (8, 13), (14, 19), (20, 21), (22, 24)],
            4: [(1, 5), (6, 7), (8, 16), (17, 24), (25, 26)],
            5: [(1, 5), (6, 20), (21, 24), (25, 27), (28, 32)],
        }
        for number, ranges in expected.items():
            with self.subTest(chapter=number):
                self.assertEqual(ranges, [(b["vanaf"], b["tot"]) for b in self.chapter(number)["blokken"]])

    def test_publication_registers_current_opv_coverage(self) -> None:
        registry = json.loads((self.root / "data/edities/manifest.json").read_text(encoding="utf-8"))
        edition = json.loads((self.root / "data/edities/opv/manifest.json").read_text(encoding="utf-8"))
        entry = next(e for e in registry["edities"] if e["code"] == "nl-opv")
        expected = {
            "genesis": list(range(1, 51)),
            "exodus": list(range(1, 41)),
            "leviticus": list(range(1, 28)),
            "numeri": list(range(1, 37)),
            "deuteronomium": list(range(1, 35)),
            "jozua": list(range(1, 25)),
            "richteren": list(range(1, 22)),
            "ruth": list(range(1, 5)),
            "1samuel": list(range(1, 32)),
            "2samuel": list(range(1, 25)),
            "1koningen": list(range(1, 23)),
            "2koningen": list(range(1, 26)),
            "1kronieken": list(range(1, 30)),
            "2kronieken": list(range(1, 37)),
            "ezra": list(range(1, 11)),
            "nehemia": list(range(1, 14)),
            "esther": list(range(1, 11)),
            "job": list(range(1, 43)),
            "psalmen": list(range(1, 151)),
            "spreuken": list(range(1, 32)),
            "prediker": list(range(1, 13)),
            "hooglied": list(range(1, 9)),
            "jesaja": list(range(1, 67)),
            "jeremia": list(range(1, 53)),
            "klaagliederen": list(range(1, 6)),
            "ezechiel": list(range(1, 49)),
            "daniel": list(range(1, 13)),
            "hosea": list(range(1, 15)),
            "joel": list(range(1, 4)),
            "amos": list(range(1, 10)),
            "obadja": [1],
            "jona": list(range(1, 5)),
            "micha": list(range(1, 8)),
            "nahum": list(range(1, 4)),
            "habakuk": list(range(1, 4)),
            "zefanja": list(range(1, 4)),
            "haggai": list(range(1, 3)),
            "zacharia": list(range(1, 15)),
            "maleachi": list(range(1, 5)),
            "mattheus": list(range(1, 29)),
            "markus": list(range(1, 17)),
            "lukas": list(range(1, 25)),
            "johannes": list(range(1, 22)),
            "handelingen": list(range(1, 29)),
            "romeinen": list(range(1, 17)),
    "1korinthiers": list(range(1, 17)),
    "2korinthiers": list(range(1, 14)),
    "galaten": list(range(1, 7)),
    "efeziers": list(range(1, 7)),
    "filippenzen": list(range(1, 5)),
    "kolossenzen": list(range(1, 5)),
    "1tessalonicensen": list(range(1, 6)),
    "2tessalonicensen": list(range(1, 4)),
    "1timotheus": list(range(1, 7)),
    "2timotheus": list(range(1, 5)),
    "titus": list(range(1, 4)),
    "filemon": [1],
    "hebreeen": list(range(1, 14)),
    "jakobus": list(range(1, 6)),
    "1petrus": list(range(1, 6)),
    "2petrus": list(range(1, 4)),
    "1johannes": list(range(1, 6)),
    "2johannes": [1],
    "3johannes": [1],
    "judas": [1],
    "openbaring": list(range(1, 23)),
    "tobit": list(range(1, 15)),
    "judith": list(range(1, 17)),
    "estherapocrief": list(range(10, 17)),
    "gebedvanazaria": [1],
    "gezangindevuuroven": [1],
    "susanna": [1],
    "belenddedraak": [1],
    "gebedvanmanasse": [1],
    "baruch": list(range(1, 7)),
    "3makkabeeen": list(range(1, 8)),
    "3meqabyan": list(range(1, 11)),
    "2meqabyan": list(range(1, 22)),
    "1meqabyan": list(range(1, 37)),
    "henoch": list(range(1, 109)),
    "jubileeen": list(range(1, 51)),
    "4baruch": list(range(1, 10)),
    "3ezra": list(range(1, 10)),
    "4ezra": list(range(1, 17)),
    "boekderwijsheid": list(range(1, 20)),
    "1makkabeeen": list(range(1, 17)),
    "2makkabeeen": list(range(1, 16)),
    "jezussirach": list(range(1, 52)),
        }
        self.assertEqual(expected, entry["gepubliceerdeHoofdstukken"])
        self.assertEqual(expected, edition["gepubliceerdeHoofdstukken"])
        pending = [(book, n) for book, ns in entry["hoofdstukken"].items()
                   for n in ns if n not in entry["gepubliceerdeHoofdstukken"][book]]
        self.assertEqual([], pending)
        self.assertEqual([], validate_corpus(self.root))

    def test_genesis_five_preserves_names_numbers_children_and_death_refrain(self) -> None:
        verses = self.chapter(5)["verzen"]
        expected_numbers = {3: [130], 4: [800], 5: [930], 6: [105], 7: [807], 8: [912],
                            9: [90], 10: [815], 11: [905], 12: [70], 13: [840], 14: [910],
                            15: [65], 16: [830], 17: [895], 18: [162], 19: [800], 20: [962],
                            21: [65], 22: [300], 23: [365], 25: [187], 26: [782], 27: [969],
                            28: [182], 30: [595], 31: [777], 32: [500]}
        for number, values in expected_numbers.items():
            self.assertEqual(values, [int(n) for n in re.findall(r"\b\d+\b", verses[number - 1]["tekst"])])
        source = json.loads((self.root / "data/genesis/5.json").read_text(encoding="utf-8"))
        names = ("Adam", "Seth", "Enos", "Kenan", "Mahalal-el", "Jered", "Henoch", "Methusalach", "Lamech", "Noach", "Sem", "Cham", "Jafeth")
        for original, verse in zip(source["verses"], verses):
            for name in names:
                if name in original["textSV1888"]:
                    self.assertIn(name, verse["tekst"])
        for number in (4, 7, 10, 13, 16, 19, 22, 26, 30):
            self.assertIn("zonen en dochters", verses[number - 1]["tekst"])
        self.assertEqual([5, 8, 11, 14, 17, 20, 27, 31],
                         [v["nummer"] for v in verses if "en hij stierf" in v["tekst"]])
        for number in (22, 24):
            self.assertIn("met God", verses[number - 1]["tekst"])

    def test_new_metadata_has_local_exact_anchors_and_concept_reviews(self) -> None:
        for number in range(2, 6):
            chapter = self.chapter(number)
            source = json.loads((self.root / f"data/genesis/{number}.json").read_text(encoding="utf-8"))
            for block in chapter["blokken"]:
                self.assertEqual("concept", block["review"]["status"])
            for verse, original in zip(chapter["verzen"], source["verses"]):
                ids = [s["id"] for s in verse["segmenten"]]
                self.assertEqual([f"GEN.{number}.{verse['nummer']}.s{i}" for i in range(1, len(ids) + 1)], ids)
                self.assertEqual(verse["tekst"], "".join(s["tekst"] for s in verse["segmenten"]))
                for segment in verse["segmenten"]:
                    self.assertTrue(segment["bronfrase"])
                    self.assertIn(segment["bronfrase"], original["textSV1888"])
                for concept in verse["begrippen"]:
                    self.assertTrue(concept["segmenten"])
                    self.assertLessEqual(set(concept["segmenten"]), set(ids))
                for quote in verse["citaten"]:
                    self.assertIn(quote["startSegment"], ids)
                    self.assertIn(quote["endSegment"], ids)
                    self.assertIsInstance(quote["aangesprokene"], list)
                self.assertEqual("concept", verse["review"]["status"])
                self.assertEqual([], verse["review"]["controles"])

    def test_dialogue_speakers_and_embedded_divine_quotes_are_preserved(self) -> None:
        expected = {2: {16: ["god"], 17: ["god"], 18: ["god"], 23: ["adam"]},
                    3: {1: ["slang", "god"], 2: ["eva"], 3: ["eva", "god"], 4: ["slang"],
                        5: ["slang"], 9: ["god"], 10: ["adam"], 11: ["god"], 12: ["adam"],
                        13: ["god", "eva"], 14: ["god"], 15: ["god"], 16: ["god"],
                        17: ["god"], 18: ["god"], 19: ["god"], 22: ["god"]},
                    4: {1: ["eva"], 6: ["god"], 7: ["god"], 9: ["god", "kain"],
                        10: ["god"], 11: ["god"], 12: ["god"], 13: ["kain"], 14: ["kain"],
                        15: ["god"], 23: ["lamech-kain"], 24: ["lamech-kain"], 25: ["eva"]},
                    5: {29: ["lamech-noach"]}}
        for number, speakers in expected.items():
            actual = {v["nummer"]: [q["spreker"]["id"] for q in v["citaten"]]
                      for v in self.chapter(number)["verzen"] if v["citaten"]}
            self.assertEqual(speakers, actual)

    def test_risk_passages_preserve_primary_readings_without_added_explanations(self) -> None:
        third = self.chapter(3)["verzen"]
        fourth = self.chapter(4)["verzen"]
        self.assertNotRegex(third[14]["tekst"], r"Christus|Jezus|Messias|Satan")
        self.assertIn("vergeven", fourth[12]["tekst"])
        self.assertNotIn("straf", fourth[12]["tekst"])
        self.assertIn("zeventig keer zeven", fourth[23]["tekst"])
        for verse in fourth[2:5]:
            self.assertNotRegex(verse["tekst"], r"omdat|slechte|beste|ongeloof|geloof")

    def test_genesis_three_22_prevents_a_possibility_without_new_permission_bans(self) -> None:
        verse = self.chapter(3)["verzen"][21]
        text = verse["tekst"]
        self.assertNotRegex(text, r"(?i)\bmag\b[^.!?]*\bniet\b")
        self.assertIn("zou", text)
        self.assertIn("voorkomen", text)
        for element in ("een van ons", "goed en kwaad", "hand", "uitsteken", "boom van het leven", "nemen", "eten", "voor altijd leven"):
            self.assertIn(element, text)
        self.assertEqual(1, len(verse["citaten"]))
        self.assertEqual("god", verse["citaten"][0]["spreker"]["id"])
        self.assertEqual([], verse["citaten"][0]["aangesprokene"])
        self.assertIn("voorkomen", OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))

    def test_genesis_two_5_does_not_make_plants_before_they_exist(self) -> None:
        text = self.chapter(2)["verzen"][4]["tekst"]
        self.assertNotRegex(text, r"(?i)maakte[^.!?]*voordat ze er waren")
        self.assertNotRegex(text, r"(?i)maakte Hij|daarvoor|daarvóór")
        self.assertRegex(text, r"(?i)nog geen struiken[^.!?]*land")
        self.assertRegex(text, r"(?i)veldplanten[^.!?]*nog niet opgekomen")
        for element in ("De HEERE God", "nog niet laten regenen", "nog geen mens", "grond te bewerken"):
            self.assertIn(element, text)
        self.assertLess(text.index("struiken"), text.index("regenen"))
        self.assertLess(text.index("regenen"), text.index("grond te bewerken"))

    def test_genesis_three_24_keeps_combined_placement_as_the_guarding_means(self) -> None:
        text = self.chapter(3)["verzen"][23]["tekst"]
        self.assertNotIn("Ze moesten", text)
        self.assertRegex(text, r"plaatste Hij cherubs en een vlammend zwaard")
        self.assertRegex(text, r"(?:Zo|Daarmee) liet Hij[^.!?]*bewaken")
        for element in ("oosten", "Eden", "draaide", "weg naar de boom van het leven"):
            self.assertIn(element, text)
        self.assertNotRegex(text, r"vasthield|vasthielden|hanteerde|hanteerden")

    def test_henoch_retains_the_repeated_walking_image_and_its_exact_anchors(self) -> None:
        expected_anchors = {22: "wandelde Henoch met God", 24: "wandelde met God"}
        for number in (22, 24):
            with self.subTest(verse=number):
                verse = self.chapter(5)["verzen"][number - 1]
                self.assertIn("Henoch", verse["tekst"])
                self.assertIn("wandelde", verse["tekst"])
                self.assertEqual([expected_anchors[number]],
                                 OpvCalibrationCorpusTests._concept_texts(verse, "wandelen-met-god"))
        self.assertEqual([300], [int(n) for n in re.findall(r"\b\d+\b", self.chapter(5)["verzen"][21]["tekst"])])

    def test_lamechs_from_distinct_families_never_share_a_speaker_identity(self) -> None:
        fourth = self.chapter(4)["verzen"]
        fifth = self.chapter(5)["verzen"]
        first, repeated, other = fourth[22]["citaten"][0], fourth[23]["citaten"][0], fifth[28]["citaten"][0]
        self.assertNotEqual(first["spreker"]["id"], other["spreker"]["id"])
        self.assertEqual(first["spreker"]["id"], repeated["spreker"]["id"])
        self.assertEqual("lamech-kain", first["spreker"]["id"])
        self.assertEqual("lamech-noach", other["spreker"]["id"])
        for citation in (first, repeated, other):
            self.assertEqual(("Lamech", "human"), (citation["spreker"]["naam"], citation["spreker"]["type"]))
        self.assertTrue(fifth[28]["tekst"].startswith("Lamech noemde hem Noach"))

    def test_genesis_four_7_keeps_the_disputed_referent_out_of_the_reading_text(self) -> None:
        verse = self.chapter(4)["verzen"][6]
        self.assertNotIn("goede band", verse["tekst"])
        self.assertNotRegex(verse["tekst"], r"(?i)\b(?:abel|broer)\b")
        self.assertIn("zijn verlangen op jou gericht", verse["tekst"])
        self.assertIn("jij zult over hem heersen", verse["tekst"])
        self.assertNotRegex(verse["tekst"], r"\bstraf\b|eerstgeboren|oudste|moet.*heersen")
        self.assertIn("ligt de zonde aan de deur", verse["tekst"])
        concepts = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))["concepten"]
        explanation = next(c["uitleg"] for c in concepts if c["id"] == "zonde")
        self.assertIn("Genesis 4:7", explanation)
        self.assertIn("straf", explanation)
        self.assertIn("Statenvertaling", explanation)

    def test_genesis_four_7_documents_both_readings_in_the_second_layer(self) -> None:
        verse = self.chapter(4)["verzen"][6]
        self.assertEqual(["zijn verlangen op jou gericht"],
                         OpvCalibrationCorpusTests._concept_texts(verse, "verlangen-genesis-4-7"))
        concepts = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))["concepten"]
        explanation = next(c["uitleg"] for c in concepts if c["id"] == "verlangen-genesis-4-7")
        for element in ("Genesis 4:7", "Abel", "zonde", "Statenvertaling"):
            self.assertIn(element, explanation)
        lowered = explanation.lower()
        self.assertIn("een andere uitleg", lowered)
        self.assertIn("hoofdtekst", lowered)
        self.assertIn("open", lowered)
        self.assertEqual("god", verse["citaten"][0]["spreker"]["id"])
        self.assertEqual(["kain"], verse["citaten"][0]["aangesprokene"])

    def test_task7_genesis_source_and_clarity_findings_remain_fixed(self) -> None:
        chapters = {number: self.chapter(number) for number in range(1, 5)}
        self.assertRegex(chapters[1]["verzen"][17]["tekst"], r"(?:De|Deze) lichten")
        self.assertIn("Die damp", chapters[2]["verzen"][5]["tekst"])
        self.assertIn("één vlees", chapters[2]["verzen"][23]["tekst"])
        self.assertNotIn("één lichaam", chapters[2]["verzen"][23]["tekst"])
        self.assertIn("Toen vroeg de slang", chapters[3]["verzen"][0]["tekst"])
        self.assertNotIn("Toen gingen bij allebei de ogen open", chapters[3]["verzen"][6]["tekst"])
        wind_sentence = next(
            sentence for sentence in re.split(r"(?<=[.!?])\s+", chapters[3]["verzen"][7]["tekst"])
            if "wind" in sentence.lower()
        )
        self.assertIn("dag", wind_sentence.lower())
        self.assertIn("De grond", chapters[4]["verzen"][10]["tekst"])


class OpvExodusProductionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/exodus/{number}.json"
        self.assertTrue(path.is_file(), f"Exodus-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_exodus_has_exact_source_verse_lists_and_1213_verses(self) -> None:
        total = 0
        for number in range(1, 41):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads((self.root / f"data/exodus/{number}.json").read_text(encoding="utf-8"))
                self.assertEqual([v["number"] for v in source["verses"]],
                                 [v["nummer"] for v in chapter["verzen"]])
                total += len(chapter["verzen"])
                self.assertEqual(("exodus", number), (chapter["boek"], chapter["hoofdstuk"]))
                self.assertTrue(chapter["blokken"])
                for verse in chapter["verzen"]:
                    self.assertEqual({"bestand": f"data/exodus/{number}.json",
                                      "vers": verse["nummer"], "tekstveld": "textSV1888"}, verse["bron"])
        self.assertEqual(1213, total)

    def test_tabernacle_terminology_is_readable_and_consistent(self) -> None:
        text = " ".join(
            verse["tekst"]
            for number in range(25, 41)
            for verse in self.chapter(number)["verzen"]
        )
        self.assertNotRegex(text, r"\b(?:sittimhout|hemelsblauw)\b")
        self.assertNotRegex(text, r"\b(?:borstlap|draagbomen|wasvat)\b")
        self.assertIn("acaciahout", text)
        self.assertIn("blauw", text)
        self.assertIn("borststuk", text)
        self.assertIn("draagstokken", text)
        self.assertIn("wasbekken", text)

    def test_meeting_tent_and_evening_are_consistent_plain_dutch(self) -> None:
        tabernacle_text = " ".join(
            verse["tekst"]
            for number in range(27, 41)
            for verse in self.chapter(number)["verzen"]
        )
        self.assertNotRegex(tabernacle_text, r"\btent van (?:samenkomst|ontmoeting)\b")
        self.assertIn("ontmoetingstent", tabernacle_text)

        offering_text = " ".join(
            verse["tekst"]
            for number in (29, 30)
            for verse in self.chapter(number)["verzen"]
        )
        self.assertNotIn("tussen de twee avonden", offering_text)
        self.assertIn("tegen de avond", offering_text)

    def test_tabernacle_measurements_use_modern_approximations(self) -> None:
        text = " ".join(
            verse["tekst"]
            for number in range(25, 41)
            for verse in self.chapter(number)["verzen"]
        )
        self.assertNotRegex(text, r"\b(?:el|ellen|span|talent|handbreed)\b")
        expected = {
            (25, 10): ("1,1 meter", "70 centimeter"),
            (25, 39): ("34 kilo",),
            (26, 2): ("12,5 meter", "1,8 meter"),
            (27, 18): ("45 meter", "22,5 meter", "2,25 meter"),
            (28, 16): ("22 centimeter",),
            (29, 40): ("2 liter", "1 liter olie", "1 liter wijn"),
            (30, 2): ("45 centimeter", "90 centimeter"),
            (30, 13): ("twintig gera", "11 gram", "5,5 gram"),
            (30, 23): ("5,5 kilo", "2,75 kilo"),
            (30, 24): ("5,5 kilo", "4 liter"),
            (36, 9): ("12,5 meter", "1,8 meter"),
            (37, 1): ("1,1 meter", "70 centimeter"),
            (38, 24): ("994 kilo",),
            (38, 26): ("5,7 gram", "603.550"),
            (39, 9): ("22 centimeter",),
        }
        for (chapter, verse), phrases in expected.items():
            with self.subTest(chapter=chapter, verse=verse):
                actual = self.chapter(chapter)["verzen"][verse - 1]["tekst"]
                for phrase in phrases:
                    self.assertIn(phrase, actual)


class OpvLeviticusProductionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/leviticus/{number}.json"
        self.assertTrue(path.is_file(), f"Leviticus-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_leviticus_has_exact_source_verse_lists_and_859_verses(self) -> None:
        total = 0
        for number in range(1, 28):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads(
                    (self.root / f"data/leviticus/{number}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    [verse["number"] for verse in source["verses"]],
                    [verse["nummer"] for verse in chapter["verzen"]],
                )
                total += len(chapter["verzen"])
                self.assertEqual(("leviticus", number), (chapter["boek"], chapter["hoofdstuk"]))
                self.assertTrue(chapter["blokken"])
                for verse in chapter["verzen"]:
                    self.assertEqual(
                        {
                            "bestand": f"data/leviticus/{number}.json",
                            "vers": verse["nummer"],
                            "tekstveld": "textSV1888",
                        },
                        verse["bron"],
                    )
        self.assertEqual(859, total)

    def test_offer_terminology_is_readable_and_consistent(self) -> None:
        text = " ".join(
            verse["tekst"]
            for number in range(1, 28)
            for verse in self.chapter(number)["verzen"]
        )
        self.assertNotRegex(text, r"\b(?:spijsoffer|meelbloem|schenkelen|smeer|weekdarmen|wijfje|var)\b")
        self.assertNotRegex(text, r"\btent van (?:de )?(?:samenkomst|ontmoeting)\b")
        for phrase in ("graanoffer", "fijn meel", "onderpoten", "ontmoetingstent"):
            self.assertIn(phrase, text)

    def test_leviticus_nine_preserves_both_one_year_old_animals(self) -> None:
        text = self.chapter(9)["verzen"][2]["tekst"]
        self.assertIn("een eenjarig kalf", text)
        self.assertIn("een eenjarig lam", text)
        self.assertIn("Beide dieren moeten zonder gebrek zijn", text)

    def test_leviticus_preserves_key_source_nuances_in_readable_dutch(self) -> None:
        expected_phrases = {
            (14, 5): ("aardewerken vat met vers bronwater",),
            (19, 16): ("Breng je naaste niet om", "door valse getuigenis"),
            (20, 7): ("Wijd jullie aan mij toe",),
            (22, 3): ("Wie er toch van eet terwijl hij onrein is",),
            (23, 5): ("tegen de avond",),
            (25, 10): ("naar zijn familie en krijgt zijn familiebezit terug",),
            (26, 45): ("om hun God te zijn",),
            (27, 13): ("vastgestelde waarde plus twintig procent",),
        }
        for (chapter_number, verse_number), phrases in expected_phrases.items():
            with self.subTest(chapter=chapter_number, verse=verse_number):
                text = self.chapter(chapter_number)["verzen"][verse_number - 1]["tekst"]
                for phrase in phrases:
                    self.assertIn(phrase, text)

    def test_leviticus_ten_uses_lowercase_first_person_inside_gods_quote(self) -> None:
        text = self.chapter(10)["verzen"][2]["tekst"]
        self.assertIn("tot mij naderen, zal ik", text)
        self.assertIn("hoe heerlijk ik ben", text)
        self.assertNotRegex(text, r"\b(?:Mij|Mijn)\b")


class OpvNumeriProductionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/numeri/{number}.json"
        self.assertTrue(path.is_file(), f"Numeri-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_numeri_one_to_six_have_exact_source_verse_lists_and_246_verses(self) -> None:
        total = 0
        for number in range(1, 7):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads(
                    (self.root / f"data/numeri/{number}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    [verse["number"] for verse in source["verses"]],
                    [verse["nummer"] for verse in chapter["verzen"]],
                )
                total += len(chapter["verzen"])
                self.assertEqual(("numeri", number), (chapter["boek"], chapter["hoofdstuk"]))
                self.assertTrue(chapter["blokken"])
                for verse in chapter["verzen"]:
                    self.assertEqual(
                        {
                            "bestand": f"data/numeri/{number}.json",
                            "vers": verse["nummer"],
                            "tekstveld": "textSV1888",
                        },
                        verse["bron"],
                    )
        self.assertEqual(246, total)

    def test_numeri_preserves_the_key_census_totals_and_age_ranges(self) -> None:
        chapter_one = self.chapter(1)["verzen"]
        self.assertIn("603.550", chapter_one[45]["tekst"])
        chapter_three = self.chapter(3)["verzen"]
        for number in (15, 22, 28, 34, 39):
            with self.subTest(chapter=3, verse=number):
                self.assertIn("1 maand of ouder", chapter_three[number - 1]["tekst"])
                self.assertNotIn("mannen van 1 maand", chapter_three[number - 1]["tekst"])
        for number in (40, 41, 43, 45, 46, 48):
            with self.subTest(chapter=3, verse=number):
                self.assertIn("eerstgeboren", chapter_three[number - 1]["tekst"])
                self.assertNotIn("eerstgeboren jongens", chapter_three[number - 1]["tekst"])
        self.assertIn("22.000", chapter_three[38]["tekst"])
        self.assertIn("22.273", chapter_three[42]["tekst"])
        self.assertIn("1.365", chapter_three[49]["tekst"])
        self.assertIn("8.580", self.chapter(4)["verzen"][47]["tekst"])


class OpvMattheusProductionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/mattheus/{number}.json"
        self.assertTrue(path.is_file(), f"Mattheüs-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_mattheus_one_to_twenty_eight_have_exact_source_verse_lists_and_1071_verses(self) -> None:
        total = 0
        for number in range(1, 29):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads(
                    (self.root / f"data/mattheus/{number}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    [verse["number"] for verse in source["verses"]],
                    [verse["nummer"] for verse in chapter["verzen"]],
                )
                total += len(chapter["verzen"])
                self.assertEqual(("mattheus", number), (chapter["boek"], chapter["hoofdstuk"]))
                self.assertTrue(chapter["blokken"])
                for verse in chapter["verzen"]:
                    self.assertEqual(
                        {
                            "bestand": f"data/mattheus/{number}.json",
                            "vers": verse["nummer"],
                            "tekstveld": "textSV1888",
                        },
                        verse["bron"],
                    )
        self.assertEqual(1071, total)

    def test_mattheus_preserves_key_names_numbers_and_nested_scripture_speakers(self) -> None:
        chapter_one = self.chapter(1)["verzen"]
        self.assertIn("veertien generaties", chapter_one[16]["tekst"])
        self.assertIn("Heilige Geest", chapter_one[17]["tekst"])
        self.assertIn("Immanuël", chapter_one[22]["tekst"])
        self.assertEqual(
            {"jesaja", "god"},
            {citation["spreker"]["id"] for citation in chapter_one[22]["citaten"]},
        )
        chapter_two = self.chapter(2)["verzen"]
        self.assertIn("twee jaar en jonger", chapter_two[15]["tekst"])
        self.assertEqual(
            {"hosea", "god"},
            {citation["spreker"]["id"] for citation in chapter_two[14]["citaten"]},
        )
        self.assertIn("Dit is mijn geliefde Zoon", self.chapter(3)["verzen"][16]["tekst"])
        self.assertNotIn("Volg Mij", self.chapter(4)["verzen"][18]["tekst"])
        self.assertIn("Volg mij", self.chapter(4)["verzen"][18]["tekst"])
        self.assertIn("40 dagen en 40 nachten", self.chapter(4)["verzen"][1]["tekst"])
        self.assertNotIn("Zich", self.chapter(8)["verzen"][16]["tekst"])

    def test_mattheus_does_not_reuse_johannes_specific_concepts_by_word_match(self) -> None:
        johannes_specific = {
            "aanroepen-heere",
            "de-profeet",
            "groter-kleiner",
            "koning-van-israel",
            "leven",
            "licht",
            "reiniging",
            "woord",
        }
        for chapter_number in range(1, 29):
            chapter_path = (
                self.root
                / f"data/edities/opv/chapters/mattheus/{chapter_number}.json"
            )
            if not chapter_path.is_file():
                continue
            chapter = json.loads(chapter_path.read_text(encoding="utf-8"))
            for verse in chapter["verzen"]:
                with self.subTest(chapter=chapter_number, verse=verse["nummer"]):
                    used = {
                        concept["conceptId"]
                        for concept in verse.get("begrippen", [])
                    }
                    self.assertFalse(
                        used & johannes_specific,
                        "Een woordovereenkomst is geen semantische conceptkoppeling",
                    )


class OpvMarkusProductionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/markus/{number}.json"
        self.assertTrue(path.is_file(), f"Markus-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_markus_one_to_sixteen_have_exact_source_verse_lists_and_678_verses(self) -> None:
        total = 0
        for number in range(1, 17):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads(
                    (self.root / f"data/markus/{number}.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    [verse["number"] for verse in source["verses"]],
                    [verse["nummer"] for verse in chapter["verzen"]],
                )
                total += len(chapter["verzen"])
                self.assertEqual(("markus", number), (chapter["boek"], chapter["hoofdstuk"]))
                self.assertTrue(chapter["blokken"])
                for verse in chapter["verzen"]:
                    self.assertEqual(
                        {
                            "bestand": f"data/markus/{number}.json",
                            "vers": verse["nummer"],
                            "tekstveld": "textSV1888",
                        },
                        verse["bron"],
                    )
        self.assertEqual(678, total)

    def test_markus_preserves_nested_scripture_speakers_without_harmonizing(self) -> None:
        self.assertEqual(
            {"profeten", "god"},
            {citation["spreker"]["id"] for citation in self.chapter(1)["verzen"][1]["citaten"]},
        )
        self.assertEqual(
            {"jezus", "david", "heilige-geest", "god"},
            {citation["spreker"]["id"] for citation in self.chapter(12)["verzen"][35]["citaten"]},
        )
        self.assertEqual(
            {"jezus", "david"},
            {citation["spreker"]["id"] for citation in self.chapter(15)["verzen"][33]["citaten"]},
        )
        self.assertIn("een jonge man", self.chapter(16)["verzen"][4]["tekst"])
        self.assertNotIn("engel", self.chapter(16)["verzen"][4]["tekst"].lower())

    def test_markus_long_ending_is_preserved_and_documented(self) -> None:
        verses = self.chapter(16)["verzen"]
        for verse in verses[8:]:
            with self.subTest(verse=verse["nummer"]):
                ids = {concept["conceptId"] for concept in verse["begrippen"]}
                self.assertIn("markus-lang-slot-handschriften", ids)
        registry = json.loads(
            (self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8")
        )
        note = next(
            concept["uitleg"]
            for concept in registry["concepten"]
            if concept["id"] == "markus-lang-slot-handschriften"
        )
        self.assertIn("Codex Sinaiticus", note)
        self.assertIn("Statenvertaling", note)
        self.assertIn("Textus Receptus", note)

    def test_markus_does_not_reuse_johannes_specific_concepts_by_word_match(self) -> None:
        johannes_specific = {
            "aanroepen-heere",
            "de-profeet",
            "groter-kleiner",
            "koning-van-israel",
            "leven",
            "licht",
            "reiniging",
            "woord",
        }
        for chapter_number in range(1, 17):
            for verse in self.chapter(chapter_number)["verzen"]:
                with self.subTest(chapter=chapter_number, verse=verse["nummer"]):
                    used = {concept["conceptId"] for concept in verse.get("begrippen", [])}
                    self.assertFalse(used & johannes_specific)


class OpvJohannesPilotTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def chapter(self, number: int) -> dict:
        path = self.root / f"data/edities/opv/chapters/johannes/{number}.json"
        self.assertTrue(path.is_file(), f"Johannes-hoofdstuk {number} ontbreekt")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_johannes_one_to_twenty_one_have_880_verses_and_corpus_has_6480(self) -> None:
        total = 0
        for number in range(1, 22):
            with self.subTest(chapter=number):
                chapter = self.chapter(number)
                source = json.loads((self.root / f"data/johannes/{number}.json").read_text(encoding="utf-8"))
                self.assertEqual([v["number"] for v in source["verses"]],
                                 [v["nummer"] for v in chapter["verzen"]])
                self.assertEqual(("johannes", number), (chapter["boek"], chapter["hoofdstuk"]))
                total += len(chapter["verzen"])
                for verse in chapter["verzen"]:
                    self.assertEqual({"bestand": f"data/johannes/{number}.json",
                                      "vers": verse["nummer"], "tekstveld": "textSV1888"}, verse["bron"])
        self.assertEqual(880, total)
        genesis_total = sum(len(json.loads(p.read_text(encoding="utf-8"))["verzen"])
                            for p in (self.root / "data/edities/opv/chapters/genesis").glob("*.json"))
        exodus_total = sum(
            len(json.loads(
                (self.root / f"data/edities/opv/chapters/exodus/{number}.json")
                .read_text(encoding="utf-8")
            )["verzen"])
            for number in range(1, 41)
        )
        leviticus_total = sum(
            len(json.loads(
                (self.root / f"data/edities/opv/chapters/leviticus/{number}.json")
                .read_text(encoding="utf-8")
            )["verzen"])
            for number in range(1, 28)
        )
        numeri_total = sum(
            len(json.loads(
                (self.root / f"data/edities/opv/chapters/numeri/{number}.json")
                .read_text(encoding="utf-8")
            )["verzen"])
            for number in range(1, 7)
        )
        mattheus_total = sum(
            len(json.loads(
                (self.root / f"data/edities/opv/chapters/mattheus/{number}.json")
                .read_text(encoding="utf-8")
            )["verzen"])
            for number in range(1, 29)
        )
        markus_total = sum(
            len(json.loads(
                (self.root / f"data/edities/opv/chapters/markus/{number}.json")
                .read_text(encoding="utf-8")
            )["verzen"])
            for number in range(1, 17)
        )
        lukas_total = sum(
            len(json.loads(
                (self.root / f"data/edities/opv/chapters/lukas/{number}.json")
                .read_text(encoding="utf-8")
            )["verzen"])
            for number in range(1, 10)
        )
        self.assertEqual(
            6950,
            total + genesis_total + exodus_total + leviticus_total + numeri_total
            + mattheus_total + markus_total + lukas_total,
        )

    def test_johannes_blocks_match_all_approved_boundaries(self) -> None:
        expected = {
            2: [(1, 12), (13, 17), (18, 22), (23, 25)],
            3: [(1, 8), (9, 15), (16, 21), (22, 30), (31, 36)],
            4: [(1, 6), (7, 15), (16, 26), (27, 30), (31, 38), (39, 42), (43, 45), (46, 54)],
            5: [(1, 9), (10, 18), (19, 30), (31, 40), (41, 47)],
        }
        for number, ranges in expected.items():
            with self.subTest(chapter=number):
                self.assertEqual(ranges, [(b["vanaf"], b["tot"]) for b in self.chapter(number)["blokken"]])

    def test_new_johannes_annotations_are_precise_owned_and_unique(self) -> None:
        all_ids = set()
        citation_ids = set()
        for number in range(2, 22):
            for verse in self.chapter(number)["verzen"]:
                ids = [s["id"] for s in verse["segmenten"]]
                self.assertEqual([f"JHN.{number}.{verse['nummer']}.s{i}" for i in range(1, len(ids) + 1)], ids)
                self.assertFalse(all_ids.intersection(ids))
                all_ids.update(ids)
                self.assertEqual(verse["tekst"], "".join(s["tekst"] for s in verse["segmenten"]))
                source = json.loads((self.root / verse["bron"]["bestand"]).read_text(encoding="utf-8"))
                original = source["verses"][verse["nummer"] - 1]["textSV1888"]
                for segment in verse["segmenten"]:
                    self.assertTrue(segment["bronfrase"])
                    self.assertIn(segment["bronfrase"], original)
                for concept in verse["begrippen"]:
                    self.assertTrue(concept["segmenten"])
                    self.assertLessEqual(set(concept["segmenten"]), set(ids))
                for citation in verse["citaten"]:
                    self.assertNotIn(citation["id"], citation_ids)
                    citation_ids.add(citation["id"])
                    self.assertIn(citation["startSegment"], ids)
                    self.assertIn(citation["endSegment"], ids)
                    self.assertLessEqual(ids.index(citation["startSegment"]), ids.index(citation["endSegment"]))
                    self.assertIsInstance(citation["aangesprokene"], list)
                self.assertEqual("concept", verse["review"]["status"])
                self.assertEqual([], verse["review"]["controles"])
        self.assertEqual([], validate_corpus(self.root))

    def test_full_johannes_independent_qa_findings_remain_fixed(self) -> None:
        expected_text = {
            (3, 8): (
                "De wind waait waarheen hij wil. Je hoort zijn geluid, maar weet niet waar hij "
                "vandaan komt of naartoe gaat. Zo is het ook met iedereen die uit de Geest geboren is."
            ),
            (4, 18): (
                "Je hebt namelijk vijf mannen gehad. De man met wie je nu samenleeft, is niet je man. "
                "Wat je zei, is waar."
            ),
            (6, 4): "Het Pascha, het feest van de Joden, kwam eraan.",
            (7, 20): "De menigte antwoordde: U bent door een demon bezeten! Wie probeert U te doden?",
            (8, 9): (
                "Toen ze dit hoorden, klaagde hun geweten hen aan. Ze gingen één voor één weg, "
                "te beginnen bij de oudsten. Zo bleef Jezus achter met de vrouw, die nog in het midden stond."
            ),
            (8, 50): "Ik zoek niet mijn eigen eer. God zoekt mijn eer en Hij oordeelt.",
            (10, 20): (
                "Veel van hen zeiden: Hij is door een demon bezeten en krankzinnig! "
                "Waarom luisteren jullie naar Hem?"
            ),
            (16, 21): (
                "Wanneer een vrouw gaat bevallen, heeft ze pijn omdat haar tijd gekomen is. "
                "Na de geboorte denkt ze niet meer aan haar pijn, uit blijdschap dat er een mens ter wereld is gekomen."
            ),
            (17, 2): (
                "U hebt Hem gezag gegeven over alle mensen, zodat Hij eeuwig leven geeft aan "
                "iedereen die U aan Hem hebt gegeven."
            ),
            (18, 15): (
                "Simon Petrus volgde Jezus, samen met een andere leerling. Die leerling was bekend "
                "bij de hogepriester en ging met Jezus de binnenplaats van de hogepriester op."
            ),
            (18, 38): (
                "Pilatus vroeg Hem: Wat is waarheid? Daarna ging hij weer naar buiten en zei tegen "
                "de Joden: Ik vind niets waaraan Hij schuldig is."
            ),
            (19, 30): (
                "Nadat Jezus van de zure wijn had genomen, zei Hij: Het is volbracht! "
                "Toen boog Hij Zijn hoofd en gaf Hij Zijn geest over."
            ),
        }
        for (chapter, number), expected in expected_text.items():
            with self.subTest(chapter=chapter, verse=number):
                self.assertEqual(expected, self.chapter(chapter)["verzen"][number - 1]["tekst"])

        self.assertIn("ongeveer 80 tot 120 liter", self.chapter(2)["verzen"][5]["tekst"])
        self.assertIn("ongeveer 5.000", self.chapter(6)["verzen"][9]["tekst"])
        self.assertIn("5.000", self.chapter(6)["blokken"][0]["kop"])
        self.assertNotIn("Mij", self.chapter(20)["verzen"][16]["tekst"])
        self.assertNotIn("Mij", self.chapter(20)["verzen"][28]["tekst"])
        self.assertNotIn("Zich", self.chapter(21)["verzen"][0]["tekst"])
        self.assertNotIn("Zich", self.chapter(21)["verzen"][13]["tekst"])

        law_speakers = {
            citation["spreker"]["id"] for citation in self.chapter(8)["verzen"][16]["citaten"]
        }
        self.assertEqual({"jezus", "mozes"}, law_speakers)
        psalm = next(
            citation
            for citation in self.chapter(12)["verzen"][12]["citaten"]
            if citation["spreker"]["id"] == "psalmist"
        )
        self.assertEqual(("JHN.12.13.s2", "JHN.12.13.s3"),
                         (psalm["startSegment"], psalm["endSegment"]))

        word_refs = {
            (chapter, verse["nummer"])
            for chapter in range(1, 22)
            for verse in self.chapter(chapter)["verzen"]
            if any(concept["conceptId"] == "woord" for concept in verse["begrippen"])
        }
        self.assertEqual({(1, 1), (1, 14)}, word_refs)
        forbidden = {
            "weg-van-de-heere": ((14, 4), (14, 5), (14, 6)),
            "werken-in-god": ((14, 10), (14, 11), (14, 12), (15, 2), (15, 5), (15, 8), (15, 24)),
            "aanroepen-heere": ((14, 13), (14, 14), (15, 7), (15, 16)),
            "offer": ((15, 13),),
            "oordeel": ((14, 30),),
        }
        for concept_id, references in forbidden.items():
            for chapter, number in references:
                with self.subTest(concept=concept_id, chapter=chapter, verse=number):
                    ids = {c["conceptId"] for c in self.chapter(chapter)["verzen"][number - 1]["begrippen"]}
                    self.assertNotIn(concept_id, ids)

        scoped = {
            (13, 1, "pascha"): ["pascha"],
            (13, 1, "uur-jezus"): ["Zijn tijd gekomen was"],
            (13, 1, "vader-zoon"): ["naar de Vader te gaan"],
            (17, 24, "heerlijkheid"): ["mijn heerlijkheid"],
            (17, 24, "liefde-god"): ["U hebt mij namelijk liefgehad"],
            (18, 28, "reiniging"): ["niet onrein worden"],
            (18, 28, "pascha"): ["pascha"],
        }
        for (chapter, number, concept_id), expected in scoped.items():
            with self.subTest(concept=concept_id, chapter=chapter, verse=number):
                verse = self.chapter(chapter)["verzen"][number - 1]
                self.assertEqual(expected, OpvCalibrationCorpusTests._concept_texts(verse, concept_id))

    def test_johannes_three_speaker_choices_are_explicit_in_metadata(self) -> None:
        verses = self.chapter(3)["verzen"]
        for start, end, speaker in ((16, 21, "jezus"), (31, 36, "johannes")):
            for number in range(start, end + 1):
                verse = verses[number - 1]
                self.assertEqual(speaker, verse["citaten"][0]["spreker"]["id"])
                citation = OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0])
                self.assertEqual(verse["tekst"], citation)
        self.assertTrue(OpvCalibrationCorpusTests._concept_texts(verses[15], "sprekergrens-johannes-3"))
        self.assertTrue(OpvCalibrationCorpusTests._concept_texts(verses[30], "sprekergrens-johannes-3"))

    def test_johannes_five_tr_passage_has_exact_variant_anchors(self) -> None:
        verses = self.chapter(5)["verzen"]
        waiting, angel = verses[2], verses[3]
        self.assertEqual(["Ze wachtten tot het water bewoog."],
                         OpvCalibrationCorpusTests._concept_texts(waiting, "bethesda-handschriften"))
        self.assertEqual([angel["tekst"]],
                         OpvCalibrationCorpusTests._concept_texts(angel, "bethesda-handschriften"))
        for word in ("engel", "water", "eerste", "gezond", "ziekte"):
            self.assertIn(word, angel["tekst"])
        self.assertIn("blinden", waiting["tekst"])
        self.assertIn("armen of benen die dun en krachteloos waren geworden", waiting["tekst"])
        registry = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))
        note = next(c["uitleg"] for c in registry["concepten"] if c["id"] == "bethesda-handschriften")
        self.assertIn("handschriften", note)
        self.assertIn("Statenvertaling", note)

    def test_johannes_eight_tr_passage_is_preserved_and_documented(self) -> None:
        verses = self.chapter(8)["verzen"]
        for verse in verses[:11]:
            with self.subTest(verse=verse["nummer"]):
                self.assertEqual(
                    [verse["tekst"]],
                    OpvCalibrationCorpusTests._concept_texts(
                        verse, "overspelige-vrouw-handschriften"
                    ),
                )
        registry = json.loads(
            (self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8")
        )
        note = next(
            concept["uitleg"]
            for concept in registry["concepten"]
            if concept["id"] == "overspelige-vrouw-handschriften"
        )
        self.assertIn("vroegste bewaard gebleven Griekse handschriften", note)
        self.assertIn("Statenvertaling", note)
        self.assertIn("Textus Receptus", note)

    def test_johannes_images_units_and_wordplay_keep_the_second_layer(self) -> None:
        cases = ((2, 6, "metreet"), (3, 3, "opnieuw-van-boven"), (3, 8, "wind-geest"),
                 (4, 10, "levend-water"), (4, 24, "aanbidden-geest-waarheid"),
                 (5, 39, "schriften-onderzoeken"))
        for chapter, number, concept in cases:
            with self.subTest(chapter=chapter, verse=number):
                verse = self.chapter(chapter)["verzen"][number - 1]
                self.assertTrue(OpvCalibrationCorpusTests._concept_texts(verse, concept))
        measure = self.chapter(2)["verzen"][5]["tekst"]
        self.assertIn("zes", measure)
        self.assertIn("ongeveer 80 tot 120 liter", measure)
        self.assertNotIn("metreten", measure)
        registry = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))
        explanation = next(c["uitleg"] for c in registry["concepten"] if c["id"] == "metreet")
        self.assertIn("oude inhoudsmaat", explanation)
        self.assertIn("Twee of drie metreten", explanation)

    def test_johannes_eleven_modernizes_stadia_with_an_exact_second_layer(self) -> None:
        verse = self.chapter(11)["verzen"][17]
        self.assertEqual(
            "Bethanië lag dicht bij Jeruzalem, op ongeveer drie kilometer afstand.",
            verse["tekst"],
        )
        self.assertNotIn("stadi", verse["tekst"].lower())
        self.assertEqual(
            ["drie kilometer"],
            OpvCalibrationCorpusTests._concept_texts(verse, "stadie"),
        )
        registry = json.loads(
            (self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8")
        )
        explanation = next(
            concept["uitleg"] for concept in registry["concepten"]
            if concept["id"] == "stadie"
        )
        self.assertIn("vijftien stadiën", explanation)
        self.assertIn("ongeveer drie kilometer", explanation)

    def test_johannes_six_and_twelve_explain_old_measures_and_money(self) -> None:
        rowing = self.chapter(6)["verzen"][18]
        self.assertEqual(
            "Nadat ze ongeveer vijf kilometer hadden geroeid, zagen ze Jezus over het meer lopen. Hij kwam naar het schip, en ze werden bang.",
            rowing["tekst"],
        )
        self.assertNotIn("stadi", rowing["tekst"].lower())
        self.assertEqual(
            ["ongeveer vijf kilometer"],
            OpvCalibrationCorpusTests._concept_texts(rowing, "stadie"),
        )

        feeding = self.chapter(6)["verzen"][6]
        anointing = self.chapter(12)["verzen"][2]
        sale = self.chapter(12)["verzen"][4]
        self.assertEqual(
            ["200 penningen"],
            OpvCalibrationCorpusTests._concept_texts(feeding, "penning"),
        )
        self.assertEqual(
            ["300 penningen"],
            OpvCalibrationCorpusTests._concept_texts(sale, "penning"),
        )
        self.assertEqual(
            ["330 gram"],
            OpvCalibrationCorpusTests._concept_texts(anointing, "romeins-pond"),
        )

        registry = json.loads(
            (self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8")
        )
        explanations = {
            concept["id"]: concept["uitleg"] for concept in registry["concepten"]
        }
        self.assertIn("dagloon", explanations["penning"])
        self.assertIn("Romeins pond", explanations["romeins-pond"])
        self.assertIn("ongeveer 330 gram", explanations["romeins-pond"])

    def test_johannes_nineteen_and_twenty_one_keep_exact_unit_explanations(self) -> None:
        hour = self.chapter(19)["verzen"][13]
        self.assertEqual(
            ["ongeveer het zesde uur"],
            OpvCalibrationCorpusTests._concept_texts(hour, "zesde-uur"),
        )
        weight = self.chapter(19)["verzen"][38]
        self.assertEqual(
            ["33 kilo"],
            OpvCalibrationCorpusTests._concept_texts(weight, "romeins-pond"),
        )
        distance = self.chapter(21)["verzen"][7]
        self.assertEqual(
            ["ongeveer 90 meter"],
            OpvCalibrationCorpusTests._concept_texts(distance, "el"),
        )

        registry = json.loads(
            (self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8")
        )
        explanations = {
            concept["id"]: concept["uitleg"] for concept in registry["concepten"]
        }
        self.assertIn("honderd Romeinse ponden", explanations["romeins-pond"])
        self.assertIn("ongeveer 33 kilo", explanations["romeins-pond"])
        self.assertIn("ongeveer 45 centimeter", explanations["el"])
        self.assertIn("200 el", explanations["el"])

    def test_johannes_nested_speech_excludes_narrative_introductions(self) -> None:
        for chapter, number, expected in ((3, 7, "Jullie moeten opnieuw geboren worden."),
                                           (4, 17, "Ik heb geen man."),
                                           (4, 35, "Nog vier maanden en dan komt de oogst."),
                                           (5, 11, "Pak je slaapmat op en loop.")):
            verse = self.chapter(chapter)["verzen"][number - 1]
            self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][-1]))

    def test_unspoken_questions_are_not_quotes_and_proverb_has_jesus_as_speaker(self) -> None:
        verses = self.chapter(4)["verzen"]
        self.assertEqual([], verses[26]["citaten"])
        self.assertIn("Toch vroeg niemand", verses[26]["tekst"])
        self.assertEqual("jezus", verses[43]["citaten"][0]["spreker"]["id"])
        self.assertEqual("Een profeet krijgt in zijn eigen land geen eer.",
                         OpvCalibrationCorpusTests._citation_text(verses[43], verses[43]["citaten"][0]))

    def test_all_registry_concepts_are_linked_in_the_published_pilot(self) -> None:
        registry = json.loads((self.root / "data/edities/opv/concepten.json").read_text(encoding="utf-8"))
        linked = {c["conceptId"] for p in (self.root / "data/edities/opv/chapters").glob("*/*.json")
                  for v in json.loads(p.read_text(encoding="utf-8"))["verzen"] for c in v["begrippen"]}
        self.assertEqual({c["id"] for c in registry["concepten"]}, linked)

    def test_johannes_human_address_and_future_temple_question_are_preserved(self) -> None:
        human_address = self.chapter(3)["verzen"][25]["tekst"]
        self.assertNotIn("Rabbi, U", human_address)
        self.assertNotIn("U weet toch", human_address)
        temple_question = self.chapter(2)["verzen"][19]["tekst"]
        self.assertIn("zult U", temple_question)
        self.assertNotIn("wilt", temple_question)

    def test_johannes_five_keeps_all_distinct_life_judgment_and_number_statements(self) -> None:
        verses = self.chapter(5)["verzen"]
        for number, phrase in ((2, "vijf"), (5, "38"), (19, "niets uit zichzelf"),
                               (21, "wie Hij wil"), (22, "het hele oordeel"),
                               (24, "al overgegaan"), (25, "nu al"),
                               (26, "gekregen van de Vader"), (27, "omdat de Zoon de Mensenzoon is"),
                               (28, "iedereen in de graven"), (29, "veroordeeld"),
                               (30, "de wil van de Vader"), (45, "Mozes"),
                               (46, "over mij geschreven")):
            with self.subTest(verse=number):
                self.assertIn(phrase, verses[number - 1]["tekst"])

    def test_johannes_four_10_keeps_jesus_as_the_one_requesting_water(self) -> None:
        verse = self.chapter(4)["verzen"][9]
        self.assertIn("wie jou nu om drinken vraagt", verse["tekst"])
        self.assertIn("zou jij mij om levend water vragen", verse["tekst"])
        self.assertNotIn("wie je om drinken vraagt", verse["tekst"])
        self.assertEqual("jezus", verse["citaten"][0]["spreker"]["id"])
        self.assertIn("wie jou nu om drinken vraagt", OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))
        self.assertEqual(["levend water"], OpvCalibrationCorpusTests._concept_texts(verse, "levend-water"))

    def test_johannes_five_23_preserves_the_purpose_of_giving_judgment(self) -> None:
        verse = self.chapter(5)["verzen"][22]
        self.assertTrue(verse["tekst"].startswith("Dat heeft Hij gedaan zodat alle mensen de Zoon eren zoals zij de Vader eren."))
        self.assertNotIn("Zo zal iedereen", verse["tekst"])
        self.assertIn("Wie de Zoon niet eert, eert ook de Vader niet die Hem gestuurd heeft.", verse["tekst"])
        self.assertEqual(["de Zoon eren zoals zij de Vader eren"], OpvCalibrationCorpusTests._concept_texts(verse, "vader-zoon"))
        self.assertEqual(verse["tekst"], OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))

    def test_johannes_five_18_keeps_intensified_effort_to_kill(self) -> None:
        text = self.chapter(5)["verzen"][17]["tekst"]
        self.assertIn("waren de Joden er nog sterker op uit Hem te doden", text)
        self.assertNotIn("liever", text)
        for phrase in ("Hij brak niet alleen de sabbat", "Zijn eigen Vader", "zichzelf gelijk aan God"):
            self.assertIn(phrase, text)

    def test_johannes_two_22_refers_to_the_specific_temple_statement(self) -> None:
        verse = self.chapter(2)["verzen"][21]
        self.assertIn("de Schrift en deze uitspraak van Jezus", verse["tekst"])
        self.assertNotIn("de woorden van Jezus", verse["tekst"])
        self.assertIn("dat Hij dit tegen hen had gezegd", verse["tekst"])
        self.assertEqual(["de Schrift"], OpvCalibrationCorpusTests._concept_texts(verse, "schriften"))

    def test_johannes_four_27_keeps_the_object_of_the_unasked_question(self) -> None:
        verse = self.chapter(4)["verzen"][26]
        self.assertIn("Toch vroeg niemand wat Hij van haar wilde", verse["tekst"])
        self.assertNotIn("Wat vraagt U?", verse["tekst"])
        self.assertIn("waarom Hij met haar sprak", verse["tekst"])
        self.assertEqual([], verse["citaten"])

    def test_johannes_five_22_keeps_the_explanatory_link_to_judgment(self) -> None:
        verse = self.chapter(5)["verzen"][21]
        self.assertTrue(verse["tekst"].startswith("De Vader oordeelt namelijk niemand."))
        self.assertIn("Hij heeft het hele oordeel aan de Zoon gegeven.", verse["tekst"])
        self.assertNotIn("ook over niemand", verse["tekst"])
        self.assertEqual(["het hele oordeel"], OpvCalibrationCorpusTests._concept_texts(verse, "oordeel"))
        self.assertEqual(verse["tekst"], OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))


    def test_johannes_three_17_identifies_the_son_as_the_means_of_rescue(self) -> None:
        verse = self.chapter(3)["verzen"][16]
        expected = "God stuurde Zijn Zoon immers niet naar de wereld om die te veroordelen, maar om de wereld door Zijn Zoon te redden."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))
        self.assertEqual(["de wereld door Zijn Zoon te redden"], OpvCalibrationCorpusTests._concept_texts(verse, "redding"))

    def test_johannes_three_35_gives_everything_to_the_son(self) -> None:
        verse = self.chapter(3)["verzen"][34]
        expected = "De Vader houdt van de Zoon en heeft Hem alles in handen gegeven."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))
        self.assertEqual(["Hem alles in handen gegeven"], OpvCalibrationCorpusTests._concept_texts(verse, "alles-in-zijn-hand"))

    def test_johannes_five_20_names_the_father_as_the_one_showing_his_works(self) -> None:
        verse = self.chapter(5)["verzen"][19]
        expected = "Want de Vader houdt van de Zoon en laat Hem alles zien wat de Vader doet. De Vader zal Hem nog grotere werken laten zien, zodat jullie verbaasd zullen zijn."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))

    def test_johannes_five_27_names_the_giver_and_recipient_of_judgment(self) -> None:
        verse = self.chapter(5)["verzen"][26]
        expected = "De Vader heeft de Zoon ook gezag gegeven om te oordelen, omdat de Zoon de Mensenzoon is."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))
        self.assertEqual(["Mensenzoon"], OpvCalibrationCorpusTests._concept_texts(verse, "mensenzoon"))

    def test_johannes_four_42_keeps_the_womans_witness_and_adds_direct_hearing(self) -> None:
        verse = self.chapter(4)["verzen"][41]
        expected = "We geloven nu niet meer alleen vanwege jouw verhaal, want we hebben Hem zelf gehoord. We weten dat Hij werkelijk de Christus is, de Redder van de wereld."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))
        self.assertEqual(["Christus"], OpvCalibrationCorpusTests._concept_texts(verse, "messias"))
        self.assertEqual(["Redder van de wereld"], OpvCalibrationCorpusTests._concept_texts(verse, "redder-wereld"))

    def test_johannes_four_1_gives_the_report_content_directly(self) -> None:
        verse = self.chapter(4)["verzen"][0]
        expected = "De Heere wist dat de Farizeeën hadden gehoord dat Hij meer leerlingen maakte en doopte dan Johannes."
        self.assertEqual(expected, verse["tekst"])

    def test_johannes_four_25_keeps_the_promise_to_make_everything_known(self) -> None:
        verse = self.chapter(4)["verzen"][24]
        expected = "Ik weet dat de Messias komt. Wanneer Hij komt, zal Hij ons alles bekendmaken."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))

    def test_johannes_two_6_expresses_capacity_with_a_rounded_conversion(self) -> None:
        verse = self.chapter(2)["verzen"][5]
        expected = "Er stonden zes stenen watervaten voor de reiniging van de Joden. Elk vat kon ongeveer 80 tot 120 liter bevatten."
        self.assertEqual(expected, verse["tekst"])
        self.assertEqual(["ongeveer 80 tot 120 liter"], OpvCalibrationCorpusTests._concept_texts(verse, "metreet"))

    def test_johannes_two_13_connects_the_passover_and_the_journey(self) -> None:
        verse = self.chapter(2)["verzen"][12]
        expected = "Het Joodse paasfeest naderde. Daarom ging Jezus naar Jeruzalem."
        self.assertEqual(expected, verse["tekst"])
        self.assertEqual(["Joodse paasfeest"], OpvCalibrationCorpusTests._concept_texts(verse, "pascha"))

    def test_johannes_two_25_describes_human_testimony_in_plain_words(self) -> None:
        verse = self.chapter(2)["verzen"][24]
        expected = "Hij had niemand nodig om Hem iets over mensen te vertellen. Hij wist zelf wat er in een mens omging."
        self.assertEqual(expected, verse["tekst"])

    def test_johannes_three_23_connects_johns_baptizing_and_its_location(self) -> None:
        verse = self.chapter(3)["verzen"][22]
        expected = "Ook Johannes doopte in Enon bij Salim, omdat daar veel water was. Mensen kwamen naar hem toe en werden gedoopt."
        self.assertEqual(expected, verse["tekst"])
        self.assertEqual(["doopte"], OpvCalibrationCorpusTests._concept_texts(verse, "doop"))

    def test_johannes_four_26_makes_jesus_identity_statement_direct(self) -> None:
        verse = self.chapter(4)["verzen"][25]
        expected = "Ik ben het. Ik ben degene die met je spreekt."
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))

    def test_johannes_four_46_identifies_the_royal_official_in_plain_words(self) -> None:
        verse = self.chapter(4)["verzen"][45]
        expected = "Jezus kwam weer in Kana in Galilea, waar Hij water in wijn had veranderd. Een ambtenaar van de koning had een zoon die ziek lag in Kapernaüm."
        self.assertEqual(expected, verse["tekst"])
        self.assertEqual(["ambtenaar van de koning"], OpvCalibrationCorpusTests._concept_texts(verse, "hoveling"))

    def test_johannes_four_52_asks_when_the_son_recovered(self) -> None:
        verse = self.chapter(4)["verzen"][51]
        expected = "Hij vroeg op welk uur zijn zoon was opgeknapt. Ze zeiden: Gisteren, op het zevende uur volgens de oude dagtelling, verdween zijn koorts."
        self.assertEqual(expected, verse["tekst"])
        self.assertEqual(["zevende uur"], OpvCalibrationCorpusTests._concept_texts(verse, "zevende-uur"))

    def test_johannes_five_23_makes_human_honor_to_both_explicit(self) -> None:
        verse = self.chapter(5)["verzen"][22]
        expected = ("Dat heeft Hij gedaan zodat alle mensen de Zoon eren zoals zij de Vader eren. "
                    "Wie de Zoon niet eert, eert ook de Vader niet die Hem gestuurd heeft.")
        self.assertEqual(expected, verse["tekst"])
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(verse, verse["citaten"][0]))
        self.assertEqual(["de Zoon eren zoals zij de Vader eren"],
                         OpvCalibrationCorpusTests._concept_texts(verse, "vader-zoon"))

    def test_johannes_four_46_to_49_uses_one_visible_name_for_official(self) -> None:
        chapter = self.chapter(4)
        block = next(b for b in chapter["blokken"] if b["vanaf"] == 46)
        with self.subTest(surface="heading"):
            self.assertEqual("De zoon van de ambtenaar leeft", block["kop"])
        for verse in chapter["verzen"][45:49]:
            with self.subTest(verse=verse["nummer"], surface="reading"):
                self.assertNotIn("hoveling", verse["tekst"].lower())
            for citation in verse["citaten"]:
                with self.subTest(verse=verse["nummer"], surface="speaker"):
                    self.assertNotIn("hoveling", citation["spreker"]["naam"].lower())
        self.assertIn("Toen de ambtenaar hoorde", chapter["verzen"][46]["tekst"])
        self.assertTrue(chapter["verzen"][48]["tekst"].startswith("De ambtenaar zei tegen Hem:"))
        self.assertEqual("De ambtenaar van de koning", chapter["verzen"][48]["citaten"][0]["spreker"]["naam"])
        self.assertEqual("hoveling", chapter["verzen"][48]["citaten"][0]["spreker"]["id"])
        self.assertEqual(["ambtenaar van de koning"],
                         OpvCalibrationCorpusTests._concept_texts(chapter["verzen"][45], "hoveling"))

    def test_johannes_four_51_and_52_show_servants_of_the_official(self) -> None:
        chapter = self.chapter(4)
        for number in (51, 52):
            with self.subTest(verse=number):
                citation = chapter["verzen"][number - 1]["citaten"][0]
                self.assertEqual("De dienaren van de ambtenaar", citation["spreker"]["naam"])
                self.assertEqual("dienaren-hoveling", citation["spreker"]["id"])
                self.assertEqual(f"spraak.dienarenhoveling.jhn4v{number}q1", citation["semanticId"])

    def test_task7_johannes_source_findings_remain_fixed(self) -> None:
        first = self.chapter(1)["verzen"]
        third = self.chapter(3)["verzen"]
        fourth = self.chapter(4)["verzen"]
        self.assertNotIn("steeds opnieuw", first[15]["tekst"])
        expected = ("Want zo liet God zien dat Hij van de wereld hield: Hij gaf Zijn enige Zoon. "
                    "Hij deed dat zodat iedereen die in Hem gelooft niet verloren zal gaan, "
                    "maar eeuwig leven zal hebben.")
        self.assertEqual(expected, third[15]["tekst"])
        self.assertEqual(expected, OpvCalibrationCorpusTests._citation_text(third[15], third[15]["citaten"][0]))
        self.assertNotIn("verdergegaan", fourth[37]["tekst"])
        self.assertIn("delen", fourth[37]["tekst"])

    def test_task7_johannes_referents_and_plain_language_remain_clear(self) -> None:
        chapters = {number: self.chapter(number) for number in range(1, 6)}
        self.assertNotIn("wat van Hem was", chapters[1]["verzen"][10]["tekst"])
        for chapter, number in ((1, 39), (1, 42), (1, 43), (4, 25)):
            with self.subTest(chapter=chapter, verse=number):
                self.assertRegex(chapters[chapter]["verzen"][number - 1]["tekst"], r"(?:Het woord|Die naam)")
        self.assertNotIn("metreten", chapters[2]["verzen"][5]["tekst"])
        self.assertRegex(chapters[2]["verzen"][5]["tekst"], r"\b(?:liter|inhoud)\b")
        self.assertIn("in God zijn gedaan", chapters[3]["verzen"][20]["tekst"])
        self.assertNotIn("laat hij zien", chapters[3]["verzen"][20]["tekst"])
        self.assertIn("God", chapters[3]["verzen"][26]["tekst"])
        wedding_text = chapters[3]["verzen"][28]["tekst"].lower()
        self.assertIn("de bruidegom", wedding_text)
        self.assertIn("de vriend van de bruidegom", wedding_text)
        self.assertNotRegex(chapters[3]["verzen"][30]["tekst"], r"^Johannes")
        self.assertRegex(chapters[4]["verzen"][9]["tekst"], r"\bmij\b")
        self.assertIn("die bron", chapters[4]["verzen"][13]["tekst"].lower())
        self.assertRegex(chapters[4]["verzen"][22]["tekst"], r"Er komt een tijd")
        self.assertNotIn("Of:", chapters[4]["verzen"][26]["tekst"])
        self.assertNotIn("namelijk", chapters[4]["verzen"][43]["tekst"])
        for number in (26, 27):
            with self.subTest(verse=number):
                text = chapters[5]["verzen"][number - 1]["tekst"]
                self.assertIn("Vader", text)
                self.assertIn("Zoon", text)
        self.assertNotIn("Zijn gestalte", chapters[5]["verzen"][36]["tekst"])
        self.assertNotIn("Zijn woord blijft niet", chapters[5]["verzen"][37]["tekst"])

    def test_task7_source_rereview_findings_remain_fixed(self) -> None:
        genesis_two = json.loads(
            (self.root / "data/edities/opv/chapters/genesis/2.json").read_text(encoding="utf-8")
        )
        chapters = {number: self.chapter(number) for number in range(1, 6)}
        expected = {
            ("genesis", 2, 12): (
                "Het goud uit dat land is van goede kwaliteit. Ook het materiaal bedolah en "
                "de edelsteen sardonix zijn er te vinden."
            ),
            ("johannes", 1, 11): (
                "Hij kwam naar wat Hem toebehoorde, maar Zijn eigen mensen namen Hem niet aan."
            ),
            ("johannes", 1, 48): (
                "Jezus zag Nathanaël naar Hem toe komen en zei over hem: Kijk, daar komt een "
                "echte Israëliet! Er is geen bedrog in hem."
            ),
            ("johannes", 2, 17): (
                "Zijn leerlingen herinnerden zich deze woorden uit de Schrift: Mijn ijver voor "
                "Uw huis heeft mij verteerd."
            ),
            ("johannes", 2, 24): (
                "Maar Jezus vertrouwde zichzelf niet aan hen toe, want Hij kende hen allemaal."
            ),
            ("johannes", 3, 8): (
                "De wind waait waarheen hij wil. Je hoort zijn geluid, maar weet niet waar hij "
                "vandaan komt of naartoe gaat. Zo is het ook met iedereen die uit de Geest "
                "geboren is."
            ),
            ("johannes", 3, 21): (
                "Maar wie naar de waarheid handelt, komt naar het Licht. Dan wordt zichtbaar dat "
                "zijn daden in God zijn gedaan."
            ),
            ("johannes", 3, 31): (
                "Wie van boven komt, staat boven iedereen. Wie van de aarde komt, hoort bij de "
                "aarde en spreekt als iemand van de aarde. Wie uit de hemel komt, staat boven iedereen."
            ),
            ("johannes", 4, 10): (
                "Jezus antwoordde: Als je wist wat God geeft, en wist wie jou nu om drinken vraagt, "
                "zou jij mij om levend water vragen. Dan zou ik het je geven."
            ),
            ("johannes", 4, 36): (
                "Wie maait, krijgt loon en verzamelt de oogst voor het eeuwige leven. Zo kunnen de "
                "zaaier en de maaier samen blij zijn."
            ),
            ("johannes", 4, 45): (
                "Toen Hij in Galilea kwam, ontvingen de Galileeërs Hem. Ze hadden alles gezien wat "
                "Hij tijdens het feest in Jeruzalem had gedaan. Zij waren zelf ook naar het feest gegaan."
            ),
            ("johannes", 5, 26): (
                "Zoals de Vader het leven in zichzelf heeft, zo heeft ook de Zoon het leven in "
                "zichzelf gekregen van de Vader."
            ),
            ("johannes", 1, 16): (
                "Uit Zijn overvloed hebben wij allemaal volop onverdiende goedheid ontvangen."
            ),
            ("johannes", 3, 5): (
                "Jezus antwoordde: Luister goed, ik verzeker je: als iemand niet uit water en Geest "
                "geboren wordt, kan hij het koninkrijk van God niet binnengaan."
            ),
            ("johannes", 3, 29): (
                "De bruid hoort bij de bruidegom. De vriend van de bruidegom staat ernaast en luistert. "
                "Wanneer hij de stem van de bruidegom hoort, is hij heel blij. Zo is mijn blijdschap "
                "nu helemaal vervuld."
            ),
            ("johannes", 4, 38): (
                "Ik heb jullie gestuurd om te maaien waar jullie niet voor hebben gewerkt. Anderen "
                "hebben het werk gedaan en jullie delen nu in het resultaat van hun werk."
            ),
            ("johannes", 5, 24): (
                "Luister goed, ik verzeker jullie: wie mijn woord hoort en vertrouwt op Hem die mij "
                "gestuurd heeft, heeft eeuwig leven. Hij wordt niet veroordeeld, maar is al overgegaan "
                "van de dood naar het leven."
            ),
            ("johannes", 5, 36): (
                "Maar ik heb een belangrijker getuigenis dan dat van Johannes. De Vader gaf mij werken "
                "om te doen. De werken die ik doe, getuigen ervan dat de Vader mij gestuurd heeft."
            ),
        }
        for (book, chapter, number), wanted in expected.items():
            with self.subTest(book=book, chapter=chapter, verse=number):
                data = genesis_two if book == "genesis" else chapters[chapter]
                self.assertEqual(wanted, data["verzen"][number - 1]["tekst"])
        third = chapters[3]
        self.assertEqual("Hij die uit de hemel komt", third["blokken"][-1]["kop"])
        verse_31 = third["verzen"][30]
        self.assertEqual(
            verse_31["tekst"],
            OpvCalibrationCorpusTests._citation_text(verse_31, verse_31["citaten"][0]),
        )
        self.assertNotIn("Johannes zei verder", verse_31["tekst"])
        self.assertNotIn("Toch ontvingen", chapters[4]["verzen"][44]["tekst"])
        self.assertEqual(
            "Toen de wind van de dag waaide, hoorden ze de stem van de HEERE God terwijl Hij door "
            "de tuin liep. Adam en zijn vrouw verstopten zich tussen de bomen voor Hem.",
            json.loads(
                (self.root / "data/edities/opv/chapters/genesis/3.json").read_text(encoding="utf-8")
            )["verzen"][7]["tekst"],
        )
        self.assertEqual(
            "Lamech zei tegen zijn vrouwen Ada en Zilla: Luister naar mijn stem, vrouwen van Lamech! "
            "Hoor wat ik zeg! Ja, ik doodde een man vanwege mijn wond, en een jonge man vanwege mijn buil!",
            json.loads(
                (self.root / "data/edities/opv/chapters/genesis/4.json").read_text(encoding="utf-8")
            )["verzen"][22]["tekst"],
        )


if __name__ == "__main__":
    unittest.main()
