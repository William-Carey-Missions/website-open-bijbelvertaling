import base64
import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from component_fixtures import fingerprint_catalog


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog_module = load_module("build_review_catalog", "scripts/build_review_catalog.py")
api_module = load_module("collaboration_api", "server/collaboration_api.py")


class ReviewCatalogTests(unittest.TestCase):
    def test_catalog_generalizes_text_chapters_and_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data" / "genesis").mkdir(parents=True)
            (root / "data" / "books.json").write_text(
                json.dumps({"books": [{
                    "id": "genesis", "nameDutch": "Genesis",
                    "chaptersIncluded": [1]
                }]}),
                encoding="utf-8",
            )
            (root / "migrations").mkdir()
            (root / 'migrations/review-components-v1.json').write_text('{"schemaVersion":1,"subjects":[]}')
            for filename in ("review-history-v1.json", "review-history-v2.json"):
                (root / "migrations" / filename).write_text(
                    json.dumps({"schemaVersion": 1, "subjects": []}), encoding="utf-8"
                )
            (root / "data" / "genesis" / "1.json").write_text(
                json.dumps({
                    "number": 1,
                    "chapterIntro": {"text2026": "Begin"},
                    "verses": [{"number": 1, "text2026": "In het begin."}],
                }),
                encoding="utf-8",
            )
            (root / "data" / "geografie-runtime.geojson").write_text(
                json.dumps({"type": "FeatureCollection", "features": [{
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [35.2, 31.7]},
                    "properties": {
                        "id": "geo-jerusalem", "naam": "Jerusalem",
                        "humanReviewed": False, "bron": {"dataset": "bron"},
                    },
                }]}),
                encoding="utf-8",
            )

            catalog = catalog_module.build_catalog(root)

        subjects = {(item["type"], item["id"]): item for item in catalog["subjects"]}
        chapter = subjects[("text-chapter", "genesis/1")]
        location = subjects[("location", "geo-jerusalem")]
        self.assertNotIn("publishedStatus", chapter)
        self.assertNotIn("migrationSource", chapter)
        self.assertIn(("text-verse", "genesis/1/1"), subjects)
        self.assertEqual(len(chapter["metadata"]["sourceHash"]), 64)
        self.assertEqual(len(chapter["revision"]), 64)
        self.assertEqual(len(location["revision"]), 64)

    def test_text_revision_only_hashes_reviewable_text(self):
        first = {
            "number": 1,
            "chapterIntro": {"text2026": "Begin", "text1637": "Beginsel"},
            "verses": [{"number": 1, "text2026": "Tekst", "grondtekst": [1]}],
        }
        changed_non_review_data = json.loads(json.dumps(first))
        changed_non_review_data["verses"][0]["grondtekst"] = [2]
        changed_text = json.loads(json.dumps(first))
        changed_text["verses"][0]["text2026"] = "Nieuwe tekst"

        self.assertEqual(
            catalog_module.text_revision(first),
            catalog_module.text_revision(changed_non_review_data),
        )
        self.assertNotEqual(
            catalog_module.text_revision(first),
            catalog_module.text_revision(changed_text),
        )


class CollaborationStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = api_module.ReviewStore(
            Path(self.directory.name) / "reviews.sqlite3",
            {"real.johnheikens@gmail.com", "maartenvroegindeweij@gmail.com"},
        )
        self.catalog = {
            "schemaVersion": 2, "historicalSubjects": [],
            "subjectTypes": {
                "text-chapter": "Bijbelhoofdstuk",
                "location": "Geografische locatie",
            },
            "subjects": [
                {
                    "type": "text-chapter", "id": "genesis/1",
                    "revision": "a" * 64, "label": "Genesis 1",
                    "href": "index.html#genesis/1", "source": "data/genesis/1.json",
                    "publishedStatus": "approved",
                    "migrationSource": "data/verified-chapters.json",
                },
                {
                    "type": "location", "id": "geo-jerusalem",
                    "revision": "b" * 64, "label": "Jerusalem",
                    "href": "plaats.html?id=geo-jerusalem",
                    "source": "data/geografie-runtime.geojson",
                    "publishedStatus": "pending",
                },
            ],
        }
        self.catalog["historicalSubjects"] = [dict(self.catalog["subjects"][0])]
        for subject in self.catalog["subjects"]:
            subject["metadata"] = {"sourceHash": subject["revision"]}
        self.catalog["catalogRevision"] = fingerprint_catalog(self.catalog)
        self.store.sync_catalog(self.catalog)
        self.admin = self.store.upsert_user({
            "sub": "john", "email": "real.johnheikens@gmail.com",
            "email_verified": True, "name": "John", "picture": "https://example.test/john.png",
        })
        self.maarten = self.store.upsert_user({
            "sub": "maarten", "email": "maartenvroegindeweij@gmail.com",
            "email_verified": True, "name": "Maarten",
        })
        self.user = self.store.upsert_user({
            "sub": "reader", "email": "reader@example.test",
            "email_verified": True, "name": "Reader",
        })

    def tearDown(self):
        self.directory.cleanup()

    def test_database_context_closes_connections_after_commit_and_rollback(self):
        import sqlite3
        with self.store._connect() as db:
            db.execute("CREATE TABLE connection_probe (value TEXT)")
            db.execute("INSERT INTO connection_probe VALUES ('committed')")
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.store._connect() as failed:
                failed.execute("INSERT INTO connection_probe VALUES ('rolled back')")
                raise RuntimeError("rollback")
        with self.assertRaises(sqlite3.ProgrammingError):
            failed.execute("SELECT 1")
        with self.store._connect() as check:
            self.assertEqual([row[0] for row in check.execute("SELECT value FROM connection_probe")], ["committed"])

    def test_bootstrap_accounts_are_administrators_and_reviewers(self):
        self.assertEqual(self.admin["roles"], ["administrator", "reviewer"])
        self.assertEqual(self.maarten["roles"], ["administrator", "reviewer"])
        self.assertEqual(self.user["roles"], [])

    def test_administrator_can_search_users_and_assign_roles(self):
        found = self.store.list_users(self.admin, "reader")
        self.assertEqual(found["total"], 1)
        self.assertEqual([item["uid"] for item in found["items"]], ["reader"])

        updated = self.store.set_roles(self.admin, "reader", ["reviewer"])

        self.assertEqual(updated["roles"], ["reviewer"])
        events = self.store.list_role_events(self.admin)
        self.assertEqual(events[0]["actor"]["uid"], self.admin["uid"])
        self.assertEqual(events[0]["targetUid"], "reader")
        self.assertEqual(events[0]["targetEmail"], "reader@example.test")

    def test_audit_events_cannot_be_changed_or_deleted(self):
        self.store.set_roles(self.admin, "reader", ["reviewer"])
        with self.store._connect() as db:
            with self.assertRaises(api_module.sqlite3.IntegrityError):
                db.execute("DELETE FROM role_events")
            with self.assertRaises(api_module.sqlite3.IntegrityError):
                db.execute("UPDATE review_events SET note = 'gewijzigd'")

    def test_non_administrator_cannot_list_users_or_assign_roles(self):
        with self.assertRaises(api_module.Forbidden):
            self.store.list_users(self.user, "")
        with self.assertRaises(api_module.Forbidden):
            self.store.set_roles(self.user, "john", ["reviewer"])

    def test_reviewer_approval_records_actor_and_requires_current_revision(self):
        reviewer = self.store.set_roles(self.admin, "reader", ["reviewer"])

        approval = self.store.record_review(reviewer, {
            "subjectType": "location",
            "subjectId": "geo-jerusalem",
            "revision": "b" * 64,
            "sourceHash": "b" * 64,
            "decision": "approved",
            "note": "Coordinaten met de bron vergeleken.",
        })

        self.assertEqual(approval["status"], "approved")
        self.assertNotIn("latestReview", approval)
        history = self.store.list_review_events(self.admin)
        self.assertEqual(history["total"], 2)
        self.assertEqual(history["items"][0]["actor"]["uid"], "reader")
        with self.assertRaises(api_module.Conflict):
            self.store.record_review(reviewer, {
                "subjectType": "location", "subjectId": "geo-jerusalem",
                "revision": "c" * 64, "decision": "approved", "note": "",
            })

    def test_regular_user_cannot_approve(self):
        with self.assertRaises(api_module.Forbidden):
            self.store.record_review(self.user, {
                "subjectType": "location", "subjectId": "geo-jerusalem",
                "revision": "b" * 64, "sourceHash": "b" * 64, "decision": "approved", "note": "",
            })

    def test_historical_status_is_migrated_once_with_confirmed_attribution(self):
        subjects = self.store.list_subjects(self.admin, subject_type="text-chapter")
        self.assertEqual(subjects["items"][0]["status"], "approved")
        self.assertEqual(subjects["items"][0]["typeLabel"], "Bijbelhoofdstuk")
        self.assertEqual(subjects["types"][0]["id"], "text-chapter")
        self.assertEqual(subjects["items"][0]["latestReview"]["actor"]["kind"], "historical-import")
        self.assertEqual(subjects["items"][0]["latestReview"]["actor"]["uid"], self.maarten["uid"])

        changed = json.loads(json.dumps(self.catalog))
        changed["subjects"][0]["revision"] = "d" * 64
        changed["catalogRevision"] = fingerprint_catalog(changed)
        self.store.sync_catalog(changed)
        subjects = self.store.list_subjects(self.admin, subject_type="text-chapter")
        self.assertEqual(subjects["items"][0]["status"], "pending")

    def test_catalog_revision_must_match_its_contents(self):
        altered = json.loads(json.dumps(self.catalog))
        altered["subjects"][0]["label"] = "Gewijzigd zonder nieuwe catalogushash"
        with self.assertRaises(api_module.InvalidRequest):
            self.store.sync_catalog(altered)


class TokenClaimTests(unittest.TestCase):
    def test_claims_are_bound_to_project_and_verified_email(self):
        valid = {
            "sub": "uid", "aud": "open-vertaling",
            "iss": "https://securetoken.google.com/open-vertaling",
            "iat": 900, "auth_time": 800, "exp": 1100,
            "email": "user@example.test", "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }
        api_module.validate_token_claims(valid, "open-vertaling", now=1000)

        for key, value in (
            ("aud", "other"), ("iss", "https://example.test"),
            ("email_verified", False), ("exp", 999), ("iat", 1001),
        ):
            invalid = dict(valid)
            invalid[key] = value
            with self.assertRaises(api_module.Unauthorized):
                api_module.validate_token_claims(invalid, "open-vertaling", now=1000)

        invalid = dict(valid)
        invalid["firebase"] = {"sign_in_provider": "password"}
        with self.assertRaises(api_module.Unauthorized):
            api_module.validate_token_claims(invalid, "open-vertaling", now=1000)

    def test_configured_app_imports_catalog_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "catalog.json"
            database_path = root / "reviews.sqlite3"
            catalog = {
                "schemaVersion": 2, "historicalSubjects": [],
                "subjectTypes": {"text-chapter": "Bijbelhoofdstuk"},
                "subjects": [{
                    "type": "text-chapter", "id": "genesis/1",
                    "revision": "a" * 64, "label": "Genesis 1",
                    "href": "index.html#genesis/1", "source": "data/genesis/1.json",
                    "publishedStatus": "approved",
                    "migrationSource": "data/verified-chapters.json",
                }],
            }
            catalog["historicalSubjects"] = [dict(catalog["subjects"][0])]
            catalog["subjects"][0]["metadata"] = {"sourceHash": "a" * 64}
            catalog["catalogRevision"] = fingerprint_catalog(catalog)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            environment = {
                "OV_COLLABORATION_DB": str(database_path),
                "OV_REVIEW_CATALOG": str(catalog_path),
                "OV_BOOTSTRAP_ADMIN_EMAILS": "real.johnheikens@gmail.com",
            }
            with unittest.mock.patch.dict(api_module.os.environ, environment, clear=False):
                app = api_module.configured_app()

            admin = app["store"].upsert_user({
                "sub": "john", "email": "real.johnheikens@gmail.com",
                "email_verified": True, "name": "John",
            })
            subjects = app["store"].list_subjects(admin, subject_type="text-chapter")
            self.assertEqual(subjects["items"][0]["status"], "approved")

    def test_verifier_accepts_valid_signature_and_rejects_tampering(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
            .sign(private_key, hashes.SHA256())
        )
        current = int(time.time())
        header = {"alg": "RS256", "kid": "test-key"}
        claims = {
            "sub": "uid", "aud": "open-vertaling",
            "iss": "https://securetoken.google.com/open-vertaling",
            "iat": current - 10, "auth_time": current - 20, "exp": current + 3600,
            "email": "user@example.test", "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }

        def segment(value):
            raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
            return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

        signing_input = f"{segment(header)}.{segment(claims)}"
        signature = private_key.sign(
            signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
        )
        token = signing_input + "." + base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        verifier = api_module.FirebaseTokenVerifier()
        verifier.certificates = {"test-key": certificate.public_bytes(
            serialization.Encoding.PEM
        ).decode("ascii")}
        verifier.expires_at = time.time() + 3600

        self.assertEqual(verifier.verify(token)["sub"], "uid")
        tampered = dict(claims)
        tampered["email"] = "attacker@example.test"
        tampered_token = f"{segment(header)}.{segment(tampered)}.{token.rsplit('.', 1)[1]}"
        with self.assertRaises(api_module.Unauthorized):
            verifier.verify(tampered_token)


class CollaborationHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.catalog_path = root / "catalog.json"
        catalog = {
            "schemaVersion": 2, "historicalSubjects": [],
            "subjectTypes": {"location": "Geografische locatie"},
            "subjects": [{
                "type": "location", "id": "geo-test", "revision": "a" * 64,
                "label": "Testplaats", "href": "plaats.html?id=geo-test",
                "source": "data/geografie-runtime.geojson", "publishedStatus": "pending",
                "metadata": {"sourceHash": "a" * 64},
            }],
        }
        catalog["catalogRevision"] = fingerprint_catalog(catalog)
        self.catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
        self.store = api_module.ReviewStore(
            root / "reviews.sqlite3", {"real.johnheikens@gmail.com"}
        )

        class Verifier:
            def verify(inner_self, token):
                if token != "admin-token":
                    raise api_module.Unauthorized()
                return {
                    "sub": "john", "email": "real.johnheikens@gmail.com",
                    "email_verified": True, "name": "John",
                }

        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), api_module.CollaborationHandler
        )
        self.server.app = {
            "corrections": api_module.Corrections(self.store, root),
            "store": self.store,
            "verifier": Verifier(),
            "catalog_path": self.catalog_path,
            "static_root": None,
        }
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}/api/collaboration"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.directory.cleanup()

    def request(self, path, method="GET", body=None, authenticated=True):
        headers = {}
        if authenticated:
            headers["Authorization"] = "Bearer admin-token"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_authenticated_api_flow_and_unauthorized_response(self):
        status, payload = self.request("/session", method="POST", body={})
        self.assertEqual(status, 200)
        self.assertIn("administrator", payload["user"]["roles"])
        account_uid = payload["user"]["uid"]

        status, payload = self.request("/users?q=john")
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"][0]["uid"], account_uid)

        status, payload = self.request("/subjects?type=location")
        self.assertEqual(status, 200)
        subject = payload["items"][0]
        status, payload = self.request("/reviews", method="POST", body={
            "subjectType": subject["type"], "subjectId": subject["id"],
            "revision": subject["revision"], "decision": "approved", "note": "Gecheckt",
            "sourceHash": subject["metadata"]["sourceHash"],
        })
        self.assertEqual(status, 201)
        self.assertEqual(payload["subject"]["latestReview"]["actor"]["uid"], account_uid)

        status, payload = self.request("/users", authenticated=False)
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "Inloggen is vereist."})


class CollaborationFrontendTests(unittest.TestCase):
    def test_google_login_uses_popup_on_every_viewport(self):
        auth = (ROOT / "js" / "auth.js").read_text(encoding="utf-8")

        self.assertIn("await signInWithPopup(this.auth, provider)", auth)
        self.assertNotIn("signInWithRedirect", auth)
        self.assertNotIn("getRedirectResult", auth)
        self.assertNotIn("matchMedia('(max-width: 768px)')", auth)

    def test_pages_and_global_client_exist(self):
        auth = (ROOT / "js" / "auth.js").read_text(encoding="utf-8")
        topnav = (ROOT / "js" / "topnav.js").read_text(encoding="utf-8")
        bootstrap = (ROOT / "js" / "auth-bootstrap.js").read_text(encoding="utf-8")
        client = (ROOT / "js" / "collaboration.js").read_text(encoding="utf-8")
        users = (ROOT / "gebruikers.html").read_text(encoding="utf-8")
        reviews = (ROOT / "beoordelingen.html").read_text(encoding="utf-8")
        history = (ROOT / "beoordelingsgeschiedenis.html").read_text(encoding="utf-8")
        users_client = (ROOT / "js" / "gebruikers.js").read_text(encoding="utf-8")
        reviews_client = (ROOT / "js" / "beoordelingen.js").read_text(encoding="utf-8")
        history_client = (ROOT / "js" / "beoordelingsgeschiedenis.js").read_text(encoding="utf-8")

        self.assertNotIn("js/collaboration.js", topnav)
        self.assertIn("import './collaboration.js'", bootstrap)
        for page in (users, reviews, history):
            self.assertIn('type="module" src="/js/auth-bootstrap.js"', page)
        self.assertIn("'/api/collaboration' + path", client)
        self.assertIn("Gebruikers", users)
        self.assertIn("Beoordelingen", reviews)
        self.assertIn('href="css/style.css"', users)
        self.assertIn('href="css/style.css"', reviews)
        self.assertIn('href="css/style.css"', history)
        self.assertIn('href="beoordelingsgeschiedenis.html"', reviews)
        self.assertNotIn('<dialog', reviews)
        self.assertNotIn('review-events-table', reviews)
        self.assertIn('js/beoordelingsgeschiedenis.js', history)

        self.assertIn("stateResolved: false", auth)
        self.assertIn("ready: false", client)
        for page in (users, reviews, history):
            self.assertRegex(page, r'<main[^>]+class="collaboration-main"[^>]+hidden')
        for page_client in (users_client, reviews_client, history_client):
            self.assertIn("if (!ready) return;", page_client)
            self.assertIn("location.replace('index.html')", page_client)


if __name__ == "__main__":
    unittest.main()
