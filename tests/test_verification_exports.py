"""Real HTTP/database export and release build, using a small temporary corpus."""
import importlib.util
import json
from component_fixtures import fingerprint_catalog
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "collaboration_tests", Path(__file__).with_name("test_collaboration_system.py")
)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
exporter = fixtures.load_module("export_review_status", "scripts/export_review_status.py")
downloads = fixtures.load_module("build_downloads", "scripts/build_downloads.py")
stats_builder = fixtures.load_module("build_stats", "scripts/build_stats.py")


class VerificationExportTests(fixtures.CollaborationHttpTests):
    def setUp(self):
        super().setUp()
        self.root = Path(self.directory.name)
        (self.root / "data/genesis").mkdir(parents=True)
        catalog = json.loads(self.catalog_path.read_text())
        catalog["subjectTypes"]["text-chapter"] = "Hoofdstuk"
        catalog["subjects"].append({
            "type": "text-chapter", "id": "genesis/1", "revision": "b" * 64,
            "label": "Genesis 1", "href": "index.html#genesis/1", "source": "data/genesis/1.json",
            "metadata": {"sourceHash": "b" * 64},
        })
        catalog["catalogRevision"] = fingerprint_catalog(catalog)
        self.catalog_path.write_text(json.dumps(catalog))
        (self.root / "data/review-catalog.json").write_text(json.dumps(catalog))
        (self.root / "data/books.json").write_text(json.dumps({"books": [{
            "id": "genesis", "nameDutch": "Genesis", "testament": "OT",
            "totalChapters": 1, "chaptersIncluded": [1],
        }]}))
        (self.root / "data/genesis/1.json").write_text(json.dumps({
            "number": 1, "verses": [{"number": 1, "text2026": "In het begin."}],
        }))
        (self.root / "data/stats.json").write_text(json.dumps({"version": "test", "date": "test"}))
        (self.root / "data/release.json").write_text(json.dumps({
            "versie": "test", "datum": "2026-09-14",
        }))
        (self.root / "data/wijzigingsprincipes.json").write_text('{"principes":[]}')
        (self.root / "data/review-history.json").write_text('{}')

    def snapshot(self):
        return exporter.export_status(self.root, self.base.split("/api/")[0])

    def build(self):
        with unittest.mock.patch.multiple(
            stats_builder, ROOT=str(self.root), DATA=str(self.root / "data")
        ), unittest.mock.patch.object(stats_builder.sys, "argv", ["build_stats.py"]):
            stats_builder.main()
        with unittest.mock.patch.multiple(
            downloads, ROOT=str(self.root), DATA=str(self.root / "data"), UIT=str(self.root / "downloads")
        ):
            self.assertEqual(downloads.main(), 0)
        return json.loads((self.root / "downloads/index.json").read_text())

    def test_export_and_downloads_follow_approval_and_revocation_without_identities(self):
        self.assertEqual(self.snapshot(), {})
        self.assertEqual(len(self.build()["uitgaven"]), 1)
        body = {"subjectType": "text-chapter", "subjectId": "genesis/1",
                "revision": "b" * 64, "sourceHash": "b" * 64, "decision": "approved"}
        self.assertEqual(self.request("/reviews", method="POST", body=body)[0], 201)
        self.assertEqual(self.snapshot(), {"genesis": [1]})
        self.assertEqual(len(self.build()["uitgaven"]), 2)
        stats = json.loads((self.root / "data/stats.json").read_text())
        self.assertEqual(stats["chapters_verified"], 1)
        self.assertEqual(stats["verses_verified"], 1)
        epub = self.root / "downloads" / downloads.EPUB_NAAM
        self.assertTrue(epub.exists())
        body["decision"] = "revoked"
        self.assertEqual(self.request("/reviews", method="POST", body=body)[0], 201)
        self.assertEqual(self.snapshot(), {})
        self.assertEqual(len(self.build()["uitgaven"]), 1)
        self.assertEqual(json.loads((self.root / "data/stats.json").read_text())["verses_verified"], 0)
        self.assertFalse(epub.exists())

    def test_export_fails_without_overwriting_when_local_content_is_a_different_release(self):
        self.snapshot()
        path = self.root / "data/verified-chapters.json"
        before = path.read_bytes()
        catalog_path = self.root / "data/review-catalog.json"
        catalog = json.loads(catalog_path.read_text())
        catalog["catalogRevision"] = "c" * 64
        catalog_path.write_text(json.dumps(catalog))
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.snapshot()
        self.assertEqual(failure.exception.code, 409)
        self.assertEqual(path.read_bytes(), before)
