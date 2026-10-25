"""Controleer het openbare LLM-contract met kleine, afgeschermde bronfixtures."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_llm_catalog as llm
import build_leespaginas as pages


class CatalogTests(unittest.TestCase):
    def test_schema_citation_and_deterministic_version(self):
        books = [{"id": "johannes", "name": "Johannes", "chapters": [{"chapter": 3,
                  "verses": [{"verse": 16, "text": "Een openbare tekst.", "notes": []}]}]}]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            index = llm.build_catalog(output, books=books)
            chapter = json.loads((output / "data/llm/johannes/3.json").read_text(encoding="utf-8"))
            verse = chapter["verses"][0]
            self.assertTrue({"id", "book", "chapter", "verse", "text", "citation", "url"} <= set(verse))
            self.assertEqual(verse["id"], f"urn:{llm.EDITION}:johannes:3:16")
            anchor = "#vers-16" if llm.EDITION == "opw" else "#v16"
            self.assertEqual(verse["url"], llm.BASE + "/bijbel/johannes/3.html" + anchor)
            self.assertEqual(index["books"][0]["chapters"][0]["json"], llm.BASE + "/data/llm/johannes/3.json")
            self.assertEqual(llm.build_catalog(output, books=books)["version"], index["version"])
            books[0]["chapters"][0]["verses"][0]["text"] = "Een herziene tekst."
            self.assertNotEqual(llm.build_catalog(output, books=books)["version"], index["version"])

    def test_source_whitelist_and_82_public_books(self):
        public = pages.BOOK_ORDER[:82] if llm.EDITION == "opw" else [book for _, ids in pages.GROEPEN for book in ids.split()]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def write(relative, value):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            if llm.EDITION == "opw":
                write("data/vertalingen/manifest.json", {"edities": [{"code": "nl-opv", "boeken": public + ["henoch"]}]})
                write("data/books.json", {"books": [{"id": book, "nameDutch": book, "testament": "OT"} for book in public + ["henoch"]]})
                for book in public + ["henoch"]:
                    write(f"data/vertalingen/nl-opv/{book}/1.json", {"hoofdstuk": 1, "verzen": [{"nummer": 1, "tekst": "PARAFRASE", "text2026": "VERBODEN_BRONVELD"}]})
            else:
                write("data/books-index.json", {"boeken": [{"id": book, "naam": book} for book in public + ["henoch"]]})
                for book in public + ["henoch"]:
                    write(f"data/{book}/1.json", {"verses": [{"number": 1, "text2026": "OV TEKST", "textOther": "VERBODEN_BRONVELD", "marginNotes": [{"marker": "a", "text2026": "OV NOOT", "textOther": "VERBODEN_BRONVELD"}]}]})
            books = llm.source_books(root)
            self.assertEqual(len(books), 82)
            self.assertNotIn("henoch", [book["id"] for book in books])
            index = llm.build_catalog(root, books=books)
            self.assertEqual(index["bookCount"], 82)
            self.assertNotIn("VERBODEN_BRONVELD", json.dumps(books))
            verse = books[0]["chapters"][0]["verses"][0]
            self.assertEqual(verse["text"], "PARAFRASE" if llm.EDITION == "opw" else "OV TEKST")
            if llm.EDITION == "ov":
                self.assertEqual(verse["notes"][0]["text"], "OV NOOT")

    def test_duplicate_verses_fail(self):
        verse = {"verse": 1, "text": "Tekst"}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                llm.build_catalog(Path(temp), books=[{"id": "genesis", "name": "Genesis", "chapters": [{"chapter": 1, "verses": [verse, verse]}]}])


if __name__ == "__main__":
    unittest.main()
