"""Browser- en datacontracten voor bronvaste Strong-verwijzingen."""

import contextlib
import hashlib
import http.server
import json
from pathlib import Path
import tempfile
import threading
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_woordnummers import audit
from import_inline_woordnummers import apply_review_file, parse_usj

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    cache_probe_version = "oud"
    cache_probe_requests = 0
    inline_cache_probe_requests = 0

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/data/cache-probe/1.json":
            type(self).cache_probe_requests += 1
            version = type(self).cache_probe_version
            payload = json.dumps({
                "number": 1,
                "verses": [{
                    "number": 1,
                    "text2026": version,
                    "text2026_html": version,
                    "woordnummers": [{
                        "tekst": version,
                        "voorkomen": 1,
                        "strongs": ["G1"],
                        "reviewstatus": "handmatig_gecontroleerd",
                    }],
                    "grondtekst": [],
                }],
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.split("?", 1)[0] == "/data/woordnummers-inline/cache-probe.json":
            type(self).inline_cache_probe_requests += 1
            payload = json.dumps({
                "chapters": {"1": {"1": [{
                    "tekst": "woord",
                    "voorkomen": 1,
                    "strongs": ["G1"],
                    "reviewstatus": "handmatig_gecontroleerd",
                }]}}
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, _format, *_args):
        pass


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, _request, _client_address):
        pass


class StrongsReaderBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = lambda *args, **kwargs: _QuietHandler(
            *args, directory=str(ROOT), **kwargs
        )
        cls.server = _QuietServer(("127.0.0.1", 0), handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.playwright = sync_playwright().start()
        browser_path = next(
            (
                path
                for path in (
                    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                )
                if path.exists()
            ),
            None,
        )
        options = {"headless": True}
        if browser_path:
            options["executable_path"] = str(browser_path)
        cls.browser = cls.playwright.chromium.launch(**options)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        with contextlib.suppress(Exception):
            cls.browser.close()
        with contextlib.suppress(Exception):
            cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def open_reader(self, location="genesis/1", width=1280, height=900):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"{self.base_url}/index.html#{location}", wait_until="domcontentloaded")
        page.locator('.verse-row[data-verse="1"]').wait_for(timeout=15_000)
        return page

    def enable_strongs(self, page, expect_inline=True):
        if page.viewport_size["width"] <= 768:
            page.locator("#topnav-hamburger").click()
            page.locator("#topnav-mobile-tekstopties").click()
        else:
            page.locator("#topnav-tekstopties").click()
        page.locator('details[data-options-category="bronnen"] > summary').click()
        page.locator("#toggle-strongs").check()
        page.locator("#sidebar-right-toggle").click()
        if expect_inline:
            page.locator('.verse-row[data-verse="1"] .col-2026 .strongs-inline').first.wait_for(timeout=5_000)

    def test_strongs_voorkeur_staat_standaard_uit_en_wordt_bewaard(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-tekstopties").click()
            page.locator('details[data-options-category="bronnen"] > summary').click()
            toggle = page.locator("#toggle-strongs")
            self.assertFalse(toggle.is_checked())
            toggle.check()
            page.wait_for_function(
                "JSON.parse(localStorage.getItem('sv2026_vertaalopties')).strongs === 'aan'"
            )
            page.reload(wait_until="domcontentloaded")
            page.locator("#topnav-tekstopties").wait_for(state="visible", timeout=15_000)
            page.locator("#topnav-tekstopties").click()
            page.locator('details[data-options-category="bronnen"] > summary').click()
            self.assertTrue(toggle.is_checked())
        finally:
            page.close()

    def test_strongnummers_staan_inline_na_het_bijbehorende_nederlandse_woord(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            first = cell.locator('[data-strongs="G1722"]').first
            self.assertEqual(first.inner_text(), "<1722>")
            styles = first.evaluate("""el => ({
                verticalAlign: getComputedStyle(el).verticalAlign,
                backgroundColor: getComputedStyle(el).backgroundColor
            })""")
            self.assertEqual(styles["verticalAlign"], "baseline")
            self.assertIn(styles["backgroundColor"], {"transparent", "rgba(0, 0, 0, 0)"})
            self.assertTrue(first.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('In');
            }"""))
            self.assertEqual(cell.locator('.strongs-alignment').count(), 0)
            self.assertEqual(cell.locator('.strongs-source-word').count(), 0)
        finally:
            page.close()

    def test_romeinen_9_plaatst_alle_strongs_bij_hun_nederlandse_woord(self):
        page = self.open_reader("romeinen/9")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            self.assertEqual(
                page.locator('.verse-row .col-2026 .strongs-inline').count(),
                533,
            )
            first = cell.locator('[data-strongs="G225"]')
            self.assertEqual(first.count(), 1)
            self.assertTrue(first.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('waarheid');
            }"""))
        finally:
            page.close()

    def test_opgeslagen_versedit_mag_canonieke_strongkoppelingen_niet_overschrijven(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(f"{self.base_url}/index.html", wait_until="domcontentloaded")
            page.evaluate("""() => {
                localStorage.setItem('sv2026_romeinen', JSON.stringify({
                    '9:1': {
                        woordnummers: [{
                            tekst: 'Ik zeg de waarheid in Christus, ik lieg niet (mijn geweten mij mee getuigenis gevende door de Heilige Geest),',
                            voorkomen: 1,
                            strongs: ['G225', 'G3004'],
                            reviewstatus: 'handmatig_gecontroleerd'
                        }]
                    }
                }));
            }""")
            page.goto(f"{self.base_url}/index.html#romeinen/9", wait_until="domcontentloaded")
            page.locator('.verse-row[data-verse="1"]').wait_for(timeout=15_000)
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            first = cell.locator('[data-strongs="G225"]')
            self.assertEqual(first.count(), 1)
            self.assertTrue(first.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('waarheid');
            }"""))
        finally:
            page.close()

    def test_genesis_1_1_plaatst_strongs_op_lokale_woordankers(self):
        page = self.open_reader("genesis/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            for strong, anchor in [("H7225", "begin"), ("H1254", "schiep"), ("H430", "God"), ("H8064", "hemel"), ("H776", "aarde")]:
                trigger = cell.locator(f'[data-strongs="{strong}"]').first
                self.assertTrue(trigger.evaluate("""(el, anchor) => {
                    const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                    const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(x => x.remove());
                    return fragment.textContent.trimEnd().endsWith(anchor);
                }""", anchor))
        finally:
            page.close()

    def test_genesis_2_6_behoudt_meerdere_lege_strongsankers(self):
        """Niet-afzonderlijk vertaalde woorden blijven elk zichtbaar op hun eigen anker."""
        page = self.open_reader("genesis/2")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="6"] .col-2026')
            for strong, anchor in [("H853", "bevochtigde"), ("H6440", "hele")]:
                trigger = cell.locator(f'[data-strongs="{strong}"]')
                self.assertEqual(trigger.count(), 1)
                self.assertTrue(trigger.evaluate("""(el, anchor) => {
                    const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                    const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(x => x.remove());
                    return fragment.textContent.trimEnd().endsWith(anchor);
                }""", anchor), f"Genesis 2:6 {strong}")
        finally:
            page.close()

    def test_genesis_2_12_tot_15_plaatst_granulaire_ankers_en_behoudt_lokaal_lemma(self):
        page = self.open_reader("genesis/2")
        try:
            self.enable_strongs(page)
            for verse, strong, anchor in [
                (12, "H2091", "goud"),
                (12, "H8033", "daar"),
                (13, "H853", "omloopt"),
                (14, "H2313", "Hiddekel"),
                (14, "H6578", "Frath"),
                (15, "H3240", "zette"),
            ]:
                trigger = page.locator(
                    f'.verse-row[data-verse="{verse}"] .col-2026 [data-strongs="{strong}"]'
                )
                self.assertEqual(trigger.count(), 1, f"Genesis 2:{verse} {strong}")
                self.assertTrue(trigger.evaluate("""(el, anchor) => {
                    const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                    const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(x => x.remove());
                    return fragment.textContent.trimEnd().endsWith(anchor);
                }""", anchor), f"Genesis 2:{verse} {strong}")
            self.assertEqual(
                page.locator('.verse-row[data-verse="15"] .col-2026 [data-strongs="H5117"]').count(),
                0,
            )
        finally:
            page.close()

    def test_genesis_1_6_tot_10_plaatst_strongs_op_lokale_woordankers(self):
        page = self.open_reader("genesis/1")
        try:
            self.enable_strongs(page)
            for verse, strong, anchor in [
                (6, "H559", "zei"),
                (6, "H7549", "uitspansel"),
                (7, "H6213", "maakte"),
                (8, "H8064", "hemel"),
                (9, "H6960", "verzameld"),
                (10, "H4723", "vergadering"),
                (11, "H1876", "uitschiete"),
                (12, "H3318", "bracht voort"),
                (13, "H7992", "derde"),
                (14, "H3974", "lichten"),
                (15, "H215", "licht te geven"),
                (16, "H3556", "sterren"),
                (17, "H5414", "stelde"),
                (18, "H4910", "heersen"),
                (19, "H7243", "vierde"),
                (20, "H8318", "gewemel"),
                (21, "H8577", "walvissen"),
                (22, "H1288", "zegende"),
                (23, "H2549", "vijfde"),
                (24, "H3318", "brenge"),
                (25, "H7431", "kruipend"),
            ]:
                trigger = page.locator(
                    f'.verse-row[data-verse="{verse}"] .col-2026 [data-strongs="{strong}"]'
                ).first
                self.assertTrue(trigger.evaluate("""(el, anchor) => {
                    const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                    const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(x => x.remove());
                    return fragment.textContent.trimEnd().endsWith(anchor);
                }""", anchor), f"Genesis 1:{verse} {strong}")
        finally:
            page.close()

    def test_johannes_1_6_plaatst_de_naamstrong_na_johannes(self):
        """De gecontroleerde naamkoppeling volgt de Nederlandse woordvolgorde."""
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="6"] .col-2026')
            trigger = cell.locator('[data-strongs="G2491"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('Johannes');
            }"""))
        finally:
            page.close()

    def test_johannes_1_7_plaatst_g846_na_hem(self):
        """De Griekse woordvolgorde verandert de Nederlandse ankerplek niet."""
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="7"] .col-2026')
            trigger = cell.locator('[data-strongs="G846"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const firstStrong = el.previousElementSibling;
                if (!firstStrong || firstStrong.dataset.strongs !== 'G1223') return false;
                const range = document.createRange();
                range.setStart(firstStrong.parentNode, 0);
                range.setEndBefore(firstStrong);
                return range.toString().trimEnd().endsWith('hem');
            }"""))
        finally:
            page.close()

    def test_johannes_1_8_plaatst_getuigenisstrong_na_getuigen(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="8"] .col-2026')
            trigger = cell.locator('[data-strongs="G3140"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('getuigen');
            }"""))
        finally:
            page.close()

    def test_johannes_1_9_plaatst_wereldstrong_na_wereld(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="9"] .col-2026')
            trigger = cell.locator('[data-strongs="G2889"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const firstStrong = el.previousElementSibling?.previousElementSibling;
                if (!firstStrong || firstStrong.dataset.strongs !== 'G1519') return false;
                const range = document.createRange();
                range.setStart(firstStrong.parentNode, 0);
                range.setEndBefore(firstStrong);
                return range.toString().trimEnd().endsWith('wereld');
            }"""))
        finally:
            page.close()

    def test_johannes_1_10_plaatst_kennenstrong_na_gekend(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="10"] .col-2026')
            trigger = cell.locator('[data-strongs="G1097"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('gekend');
            }"""))
        finally:
            page.close()

    def test_johannes_1_11_plaatst_ontvangststrong_na_aangenomen(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="11"] .col-2026')
            trigger = cell.locator('[data-strongs="G3880"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('aangenomen');
            }"""))
        finally:
            page.close()

    def test_johannes_1_12_plaatst_ontvangststrong_na_aangenomen(self):
        """Ook bij de volgende zin blijft G2983 aan het Nederlandse werkwoord."""
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="12"] .col-2026')
            trigger = cell.locator('[data-strongs="G2983"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('aangenomen');
            }"""))
        finally:
            page.close()

    def test_johannes_1_20_plaatst_christusstrong_na_christus(self):
        """De belijdenis in Johannes 1:20 houdt de titel aan het juiste woord."""
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="20"] .col-2026')
            trigger = cell.locator('[data-strongs="G5547"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('Christus');
            }"""))
        finally:
            page.close()

    def test_johannes_1_25_plaatst_doopstrong_na_doopt(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="25"] .col-2026')
            trigger = cell.locator('[data-strongs="G907"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('doopt');
            }"""))
        finally:
            page.close()

    def test_johannes_1_29_plaatst_lamstrong_bij_lam_van_god(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="29"] .col-2026')
            trigger = cell.locator('[data-strongs="G286"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('Lam van God');
            }"""))
        finally:
            page.close()

    def test_johannes_1_34_plaatst_zoonstrong_bij_de_zoon_van_god(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="34"] .col-2026')
            trigger = cell.locator('[data-strongs="G5207"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('de Zoon van God');
            }"""))
        finally:
            page.close()

    def test_johannes_1_36_plaatst_lamstrong_bij_lam_van_god(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="36"] .col-2026')
            trigger = cell.locator('[data-strongs="G286"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('het Lam van God');
            }"""))
        finally:
            page.close()

    def test_johannes_1_38_plaatst_volgstrong_na_volgen(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="38"] .col-2026')
            trigger = cell.locator('[data-strongs="G190"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('volgen');
            }"""))
        finally:
            page.close()

    def test_johannes_2_1_plaatst_derdestrong_bij_de_derde_dag(self):
        page = self.open_reader("johannes/2")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="1"] .col-2026 [data-strongs="G5154"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('op de derde dag');
            }"""))
        finally:
            page.close()

    def test_johannes_2_rendert_alle_434_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/2")
        try:
            self.enable_strongs(page)
            self.assertEqual(
                page.locator('.verse-row .col-2026 .strongs-inline').count(),
                434,
            )
        finally:
            page.close()

    def test_johannes_2_11_plaatst_tekenstrong_bij_van_de_tekenen(self):
        page = self.open_reader("johannes/2")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="11"] .col-2026 [data-strongs="G4592"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('van de tekenen');
            }"""))
        finally:
            page.close()

    def test_johannes_2_25_plaatst_mensstrong_bij_in_de_mens(self):
        page = self.open_reader("johannes/2")
        try:
            self.enable_strongs(page)
            triggers = page.locator('.verse-row[data-verse="25"] .col-2026 [data-strongs="G444"]')
            self.assertEqual(triggers.count(), 2)
            self.assertTrue(triggers.nth(1).evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('wat in de mens was');
            }"""))
        finally:
            page.close()

    def test_johannes_3_rendert_alle_672_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/3")
        try:
            self.enable_strongs(page)
            self.assertEqual(page.locator('.verse-row .col-2026 .strongs-inline').count(), 672)
        finally:
            page.close()

    def test_johannes_3_16_plaatst_eniggeborenstrong_bij_eniggeboren_zoon(self):
        page = self.open_reader("johannes/3")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="16"] .col-2026 [data-strongs="G3439"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('eniggeboren Zoon gegeven heeft');
            }"""))
        finally:
            page.close()

    def test_johannes_3_36_plaatst_toornstrong_bij_de_toorn_van_god(self):
        page = self.open_reader("johannes/3")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="36"] .col-2026 [data-strongs="G3709"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('de toorn van God');
            }"""))
        finally:
            page.close()

    def test_johannes_4_rendert_alle_953_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            per_verse = {
                number: page.locator(f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline').count()
                for number in range(1, 55)
            }
            rendered_last = page.locator('.verse-row[data-verse="54"] .col-2026 .strongs-inline').evaluate_all(
                "elements => elements.map(element => element.dataset.strongs)"
            )
            self.assertEqual(sum(per_verse.values()), 953, {"counts": per_verse, "verse54": rendered_last})
        finally:
            page.close()

    def test_johannes_4_1_plaatst_vergelijkende_vormstrong_bij_meer_discipelen_maakte(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="1"] .col-2026 [data-strongs="G4119"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('meer discipelen maakte');
            }"""))
        finally:
            page.close()

    def test_johannes_4_10_plaatst_waterstrong_bij_levend_water(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="10"] .col-2026 [data-strongs="G5204"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('levend water');
            }"""))
        finally:
            page.close()

    def test_johannes_4_14_plaatst_toekomstcode_bij_zal_geven(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="14"] .col-2026 [data-strongs="G1325"]').first
            self.assertEqual(trigger.inner_text(), "<1325>(5692)")
            self.assertEqual(trigger.get_attribute("data-tvm"), "G5692")
        finally:
            page.close()

    def test_johannes_4_25_plaatst_messiasstrong_bij_de_messias(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="25"] .col-2026 [data-strongs="G3323"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('dat de Messias komt');
            }"""))
        finally:
            page.close()

    def test_johannes_4_42_plaatst_zaligmakerstrong_bij_zaligmaker(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="42"] .col-2026 [data-strongs="G4990"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('de Zaligmaker van de wereld');
            }"""))
        finally:
            page.close()

    def test_johannes_4_46_toont_vormnummer_en_tijdcode_bij_was(self):
        page = self.open_reader("johannes/4")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="46"] .col-2026 [data-strongs="G2258"]')
            self.assertEqual(trigger.inner_text(), "<2258>(5713)")
            self.assertEqual(trigger.get_attribute("data-tvm"), "G5713")
        finally:
            page.close()

    def test_johannes_5_rendert_alle_832_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/5")
        try:
            self.enable_strongs(page)
            per_verse = {
                number: page.locator(f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline').count()
                for number in range(1, 48)
            }
            self.assertEqual(sum(per_verse.values()), 832, per_verse)
        finally:
            page.close()

    def test_johannes_5_5_gebruikt_de_uitgeschreven_tr_getalvariant(self):
        page = self.open_reader("johannes/5")
        try:
            self.enable_strongs(page)
            verse = page.locator('.verse-row[data-verse="5"] .col-2026')
            self.assertEqual(verse.locator('[data-strongs="G5144"]').count(), 1)
            self.assertEqual(verse.locator('[data-strongs="G3638"]').count(), 1)
            self.assertEqual(verse.locator('[data-strongs="G2258"]').inner_text(), "<2258>(5713)")
        finally:
            page.close()

    def test_johannes_5_19_plaatst_zoonstrong_bij_de_zoon(self):
        page = self.open_reader("johannes/5")
        try:
            self.enable_strongs(page)
            triggers = page.locator('.verse-row[data-verse="19"] .col-2026 [data-strongs="G5207"]')
            self.assertEqual(triggers.count(), 2)
        finally:
            page.close()

    def test_johannes_5_29_plaatst_opstandingstrong_tweemaal(self):
        page = self.open_reader("johannes/5")
        try:
            self.enable_strongs(page)
            triggers = page.locator('.verse-row[data-verse="29"] .col-2026 [data-strongs="G386"]')
            self.assertEqual(triggers.count(), 2)
        finally:
            page.close()

    def test_johannes_5_39_plaatst_schriftenstrong_bij_de_schriften(self):
        page = self.open_reader("johannes/5")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="39"] .col-2026 [data-strongs="G1124"]')
            self.assertEqual(trigger.count(), 1)
        finally:
            page.close()

    def test_johannes_6_rendert_alle_1284_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/6")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 72)}
            self.assertEqual(sum(per_verse.values()), 1284, per_verse)
        finally:
            page.close()

    def test_johannes_7_rendert_alle_873_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/7")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 54)}
            self.assertEqual(sum(per_verse.values()), 873, per_verse)
        finally:
            page.close()

    def test_johannes_8_rendert_1110_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/8")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 60)}
            self.assertEqual(sum(per_verse.values()), 1110, per_verse)
        finally:
            page.close()

    def test_johannes_9_rendert_698_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/9")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 42)}
            self.assertEqual(sum(per_verse.values()), 698, per_verse)
        finally:
            page.close()

    def test_johannes_10_rendert_711_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/10")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 43)}
            self.assertEqual(sum(per_verse.values()), 711, per_verse)
        finally:
            page.close()

    def test_johannes_11_rendert_958_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/11")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 58)}
            self.assertEqual(sum(per_verse.values()), 958, per_verse)
        finally:
            page.close()

    def test_johannes_12_rendert_891_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/12")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 51)}
            self.assertEqual(sum(per_verse.values()), 891, per_verse)
        finally:
            page.close()

    def test_johannes_13_rendert_669_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/13")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 39)}
            self.assertEqual(sum(per_verse.values()), 669, per_verse)
        finally:
            page.close()

    def test_johannes_14_1_10_rendert_189_gecontroleerde_tr_tokens_inline(self):
        page = self.open_reader("johannes/14")
        try:
            self.enable_strongs(page)
            per_verse = {number: page.locator(
                f'.verse-row[data-verse="{number}"] .col-2026 .strongs-inline'
            ).count() for number in range(1, 11)}
            self.assertEqual(sum(per_verse.values()), 189, per_verse)
        finally:
            page.close()

    def test_1korinthiers_4_plaatst_alle_strongs_bij_hun_nederlandse_woord(self):
        """Een terugval naar hele-verskoppelingen mag de nummers niet achteraan zetten."""
        page = self.open_reader("1korinthiers/4")
        try:
            self.enable_strongs(page)
            self.assertEqual(page.locator('.verse-row .col-2026 .strongs-inline').count(), 347)
            for verse, strong, anchor in [
                (1, "G3779", "Zo"),
                (2, "G3739", "En"),
                (2, "G1161", "En"),
                (6, "G5426", "te gevoelen"),
            ]:
                trigger = page.locator(
                    f'.verse-row[data-verse="{verse}"] .col-2026 [data-strongs="{strong}"]'
                )
                self.assertEqual(trigger.count(), 1)
                self.assertTrue(trigger.evaluate("""(el, anchor) => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().endsWith(anchor);
                }""", anchor))
        finally:
            page.close()

    def test_2korinthiers_4_plaatst_de_eerste_strongs_direct_na_daarom(self):
        page = self.open_reader("2korinthiers/4")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            first = cell.locator('[data-strongs="G1223"]').first
            self.assertTrue(first.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('Daarom');
            }"""))
        finally:
            page.close()

    def test_2korinthiers_5_plaatst_oordelen_strongs_direct_bij_het_woord(self):
        page = self.open_reader("2korinthiers/5")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="14"] .col-2026')
            trigger = cell.locator('[data-strongs="G2919"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('oordelen');
            }"""))
        finally:
            page.close()

    def test_2korinthiers_6_plaatst_strongs_direct_bij_lastige_ankers(self):
        page = self.open_reader("2korinthiers/6")
        try:
            self.enable_strongs(page)
            verse_five = page.locator('.verse-row[data-verse="5"] .col-2026')
            onlusten = verse_five.locator('[data-strongs="G181"]')
            self.assertEqual(onlusten.count(), 1)
            self.assertTrue(onlusten.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('onlusten');
            }"""))

            verse_sixteen = page.locator('.verse-row[data-verse="16"] .col-2026')
            untranslated = verse_sixteen.locator('[data-strongs="G3754"]')
            self.assertEqual(untranslated.count(), 1)
            self.assertTrue(untranslated.evaluate("""el => {
                let next = el.nextSibling;
                while (next && !String(next.textContent || '').trim()) next = next.nextSibling;
                return String(next?.textContent || '').trimStart().startsWith('Ik');
            }"""))
        finally:
            page.close()

    def test_2korinthiers_7_plaatst_strongs_direct_bij_herhaalde_woorden(self):
        page = self.open_reader("2korinthiers/7")
        try:
            self.enable_strongs(page)
            verse_nine = page.locator('.verse-row[data-verse="9"] .col-2026')
            grieved = verse_nine.locator('[data-strongs="G3076"]')
            self.assertEqual(grieved.count(), 3)
            for index in range(3):
                self.assertTrue(grieved.nth(index).evaluate("""el => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().endsWith('bedroefd');
                }"""))

            verse_eleven = page.locator('.verse-row[data-verse="11"] .col-2026')
            yes = verse_eleven.locator('[data-strongs="G235"]')
            self.assertEqual(yes.count(), 6)
            for index in range(6):
                self.assertTrue(yes.nth(index).evaluate("""el => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().toLocaleLowerCase().endsWith('ja');
                }"""))

            verse_sixteen = page.locator('.verse-row[data-verse="16"] .col-2026')
            confidence = verse_sixteen.locator('[data-strongs="G2292"]')
            self.assertEqual(confidence.count(), 1)
            self.assertTrue(confidence.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('vertrouwen');
            }"""))
        finally:
            page.close()

    def test_2korinthiers_8_plaatst_de_grensvers_strongs_direct_bij_de_woorden(self):
        page = self.open_reader("2korinthiers/8")
        try:
            self.enable_strongs(page)
            verse_fourteen = page.locator('.verse-row[data-verse="14"] .col-2026')

            equality = verse_fourteen.locator('[data-strongs="G2471"]')
            self.assertEqual(equality.count(), 2)
            for index in range(2):
                self.assertTrue(equality.nth(index).evaluate("""el => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().endsWith('gelijkheid');
                }"""))

            lack = verse_fourteen.locator('[data-strongs="G5303"]')
            self.assertEqual(lack.count(), 2)
            for index in range(2):
                self.assertTrue(lack.nth(index).evaluate("""el => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().endsWith('gebrek');
                }"""))

            purpose = verse_fourteen.locator('[data-strongs="G2443"]')
            self.assertEqual(purpose.count(), 1)
            self.assertTrue(purpose.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return (fragment.textContent.match(/\\bopdat\\b/gi) || []).length === 2;
            }"""))

            becoming = verse_fourteen.locator('[data-strongs="G1096"]')
            self.assertEqual(becoming.count(), 2)
            self.assertTrue(becoming.nth(0).evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return (fragment.textContent.match(/\\bzij\\b/gi) || []).length === 2;
            }"""))
            self.assertTrue(becoming.nth(1).evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('worde');
            }"""))

            verse_twenty_four = page.locator('.verse-row[data-verse="24"] .col-2026')
            conjunctions = verse_twenty_four.locator('[data-strongs="G2532"]')
            self.assertEqual(conjunctions.count(), 2)
            expected = ['en', 'ook']
            for index, word in enumerate(expected):
                self.assertTrue(conjunctions.nth(index).evaluate("""(el, word) => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().toLocaleLowerCase().endsWith(word);
                }""", word))
        finally:
            page.close()

    def test_1korinthiers_12_plaatst_strongs_bij_de_doelwoorden(self):
        """Atomaire mappings mogen in de browser niet als slotblok renderen."""
        page = self.open_reader("1korinthiers/12")
        try:
            self.enable_strongs(page)
            self.assertEqual(page.locator('.verse-row .col-2026 .strongs-inline').count(), 475)
            trigger = page.locator(
                '.verse-row[data-verse="31"] .col-2026 [data-strongs="G2206"]'
            )
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('ijvert');
            }"""))
        finally:
            page.close()

    def test_1korinthiers_13_plaatst_strongs_bij_de_doelwoorden(self):
        """Ook een gidsloos TR-token moet op zijn Nederlandse woord blijven staan."""
        page = self.open_reader("1korinthiers/13")
        try:
            self.enable_strongs(page)
            self.assertEqual(page.locator('.verse-row .col-2026 .strongs-inline').count(), 199)
            trigger = page.locator(
                '.verse-row[data-verse="10"] .col-2026 [data-strongs="G5119"]'
            )
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('dan');
            }"""))
        finally:
            page.close()

    def test_1korinthiers_14_plaatst_strongs_bij_de_doelwoorden(self):
        """Een gidsloos bezittelijk voornaamwoord blijft bij de tweede 'u' staan."""
        page = self.open_reader("1korinthiers/14")
        try:
            self.enable_strongs(page)
            self.assertEqual(page.locator('.verse-row .col-2026 .strongs-inline').count(), 615)
            trigger = page.locator(
                '.verse-row[data-verse="26"] .col-2026 [data-strongs="G4771"]'
            )
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('u');
            }"""))
        finally:
            page.close()

    def test_1korinthiers_15_plaatst_prikkel_en_overwinning_afzonderlijk(self):
        """De omgekeerde bronvolgorde in vers 55 blijft bij de Nederlandse woorden."""
        page = self.open_reader("1korinthiers/15")
        try:
            self.enable_strongs(page)
            self.assertEqual(page.locator('.verse-row .col-2026 .strongs-inline').count(), 853)
            for strong, word in (("G2759", "prikkel"), ("G86", "Hel"), ("G3534", "overwinning")):
                trigger = page.locator(
                    f'.verse-row[data-verse="55"] .col-2026 [data-strongs="{strong}"]'
                )
                self.assertEqual(trigger.count(), 1)
                self.assertTrue(trigger.evaluate("""(el, word) => {
                    const range = document.createRange();
                    range.setStart(el.parentNode, 0);
                    range.setEndBefore(el);
                    const fragment = range.cloneContents();
                    fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                    return fragment.textContent.trimEnd().endsWith(word);
                }""", word))
        finally:
            page.close()

    def test_mattheus_1_1_plaatst_christusstrong_na_christus(self):
        page = self.open_reader("mattheus/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            trigger = cell.locator('[data-strongs="G5547"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('CHRISTUS');
            }"""))
        finally:
            page.close()

    def test_mattheus_1_20_plaatst_engelstrong_na_engel(self):
        """De boodschapper blijft aan het Nederlandse zelfstandig naamwoord gekoppeld."""
        page = self.open_reader("mattheus/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="20"] .col-2026')
            trigger = cell.locator('[data-strongs="G32"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('engel');
            }"""))
        finally:
            page.close()

    def test_gebed_van_manasse_plaatst_g2464_alleen_na_izaak(self):
        page = self.open_reader("gebedvanmanasse/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            trigger = cell.locator('[data-strongs="G2464"]')
            self.assertEqual(trigger.count(), 1)
            self.assertTrue(trigger.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('Izaäk');
            }"""))
        finally:
            page.close()

    def test_nagekeken_genesis_haalt_corpusmapping_op_zonder_grondtekstregel(self):
        page = self.open_reader("genesis/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            self.assertGreater(cell.locator('.strongs-inline').count(), 0)
            self.assertEqual(cell.locator('.strongs-alignment').count(), 0)
            self.assertEqual(cell.locator('.strongs-source-word').count(), 0)
        finally:
            page.close()

    def test_nagekeken_1samuel_haalt_corpusmapping_op_zonder_grondtekstregel(self):
        page = self.open_reader("1samuel/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            self.assertGreater(cell.locator('.strongs-inline').count(), 0)
            self.assertEqual(cell.locator('.strongs-alignment').count(), 0)
            self.assertEqual(cell.locator('.strongs-source-word').count(), 0)
        finally:
            page.close()

    def test_mattheus_1_24_plaatst_opstaanstrong_na_opgewekt(self):
        """G1453 hoort bij 'opgewekt zijnde', nooit bij het lidwoord 'de'."""
        page = self.open_reader("mattheus/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="24"] .col-2026')
            wake = cell.locator('[data-strongs="G1453"]')
            self.assertEqual(wake.count(), 1)
            self.assertTrue(wake.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                const fragment = range.cloneContents();
                fragment.querySelectorAll('.strongs-inline').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('opgewekt zijnde');
            }"""))
            sleep = cell.locator('[data-strongs="G5258"]')
            self.assertEqual(sleep.count(), 1)
            self.assertTrue(sleep.evaluate("""el => {
                const range = document.createRange();
                range.setStart(el.parentNode, 0);
                range.setEndBefore(el);
                return range.toString().trimEnd().endsWith('slaap');
            }"""))
        finally:
            page.close()

    def test_klik_op_strong_opent_toegankelijke_bottom_sheet_met_woordenboeklink(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="1"] .col-2026 [data-strongs="G1722"]').first
            trigger.click()
            sheet = page.locator("#strongs-sheet")
            sheet.wait_for(state="visible", timeout=5_000)
            self.assertEqual(sheet.get_attribute("role"), "dialog")
            self.assertEqual(sheet.get_attribute("aria-modal"), "true")
            self.assertIn("G1722", page.locator("#strongs-sheet-number").inner_text())
            self.assertIn("WOORDENBOEKARTIKEL", page.locator("#strongs-sheet .lexicon-source").inner_text())
            article = page.frame_locator("#strongs-sheet-article")
            article.locator(".lex-entry-head").wait_for(timeout=15_000)
            self.assertIn(
                "het meest voorkomende voorzetsel",
                article.locator(".lex-def").first.inner_text(),
            )
            self.assertIn(
                "taal=grieks&entry=G1722",
                page.locator("#strongs-sheet .strongs-sheet-full-link").get_attribute("href"),
            )

            article.locator(".lex-entry-head").click()
            self.assertTrue(sheet.is_visible(), "interactie binnen het paneel mag het niet sluiten")

            page.locator(".strongs-sheet-close").focus()
            page.keyboard.press("Shift+Tab")
            self.assertIn("strongs-sheet-full-link", page.evaluate("document.activeElement.className"))
            page.keyboard.press("Tab")
            self.assertIn("strongs-sheet-close", page.evaluate("document.activeElement.className"))

            page.keyboard.press("Escape")
            self.assertFalse(sheet.is_visible())
            self.assertTrue(trigger.evaluate("el => document.activeElement === el"))
        finally:
            page.close()

    def test_meerdere_strongnummers_worden_afzonderlijk_aanklikbaar(self):
        page = self.open_reader()
        try:
            html = page.evaluate(
                """() => OVWoordnummers.renderInline('testwoord', [{
                    tekst: 'testwoord', voorkomen: 1, strongs: ['H1', 'G3056'],
                    bronwoorden: ['bronwoord'], transliteraties: ['test'], glossen: ['betekenis']
                }])"""
            )
            self.assertIn('data-strongs="H1"', html)
            self.assertIn('data-strongs="G3056"', html)
            self.assertIn("&lt;1&gt;</button>", html)
            self.assertIn("&lt;3056&gt;</button>", html)
        finally:
            page.close()

    def test_inline_markeringen_behouden_de_nederlandse_leesrichting(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            self.assertEqual(cell.evaluate("el => getComputedStyle(el).direction"), "ltr")
            self.assertGreater(cell.locator('.strongs-inline').count(), 0)
        finally:
            page.close()

    def test_bottom_sheet_past_op_mobiel_en_sluit_via_de_achtergrond(self):
        page = self.open_reader("johannes/1", width=390, height=844)
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="1"] [data-strongs="G1722"]').first
            trigger.click()
            sheet = page.locator("#strongs-sheet")
            sheet.wait_for(state="visible", timeout=5_000)
            panel = page.locator(".strongs-sheet-panel")
            panel_box = panel.bounding_box()
            self.assertLessEqual(panel_box["width"], 390)
            self.assertAlmostEqual(panel_box["x"], 0, delta=1)
            self.assertAlmostEqual(panel_box["y"] + panel_box["height"], 844, delta=1)
            self.assertEqual(panel.evaluate("el => getComputedStyle(el).position"), "absolute")
            self.assertEqual(panel.evaluate("el => getComputedStyle(el).bottom"), "0px")

            sheet.click(position={"x": 4, "y": 4})
            self.assertFalse(sheet.is_visible())
            self.assertTrue(trigger.evaluate("el => document.activeElement === el"))
        finally:
            page.close()

    def test_ongemapte_latijnse_en_geez_woordnummers_krijgen_geen_aparte_grondtekstregel(self):
        page = self.open_reader("4ezra/1")
        try:
            self.enable_strongs(page, expect_inline=False)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            self.assertEqual(cell.locator('.strongs-alignment').count(), 0)
            self.assertEqual(cell.locator('.strongs-source-word').count(), 0)
        finally:
            page.close()

    def test_woordenboekpaneel_is_op_desktop_hoog_en_in_twee_richtingen_aanpasbaar(self):
        page = self.open_reader("johannes/1", width=1280, height=900)
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="1"] [data-strongs="G1722"]').first
            trigger.click()
            panel = page.locator(".strongs-sheet-panel")
            panel.wait_for(state="visible", timeout=5_000)
            initial = panel.bounding_box()
            self.assertAlmostEqual(initial["height"], 450, delta=2)

            resize_handle = page.locator(".strongs-sheet-resize-handle")
            self.assertTrue(resize_handle.is_visible())
            handle_box = resize_handle.bounding_box()
            page.mouse.move(handle_box["x"] + handle_box["width"] / 2, handle_box["y"] + handle_box["height"] / 2)
            page.mouse.down()
            page.mouse.move(handle_box["x"] + 150, handle_box["y"] - 90, steps=5)
            page.mouse.up()

            resized = panel.bounding_box()
            self.assertGreater(resized["width"], initial["width"] + 80)
            self.assertGreater(resized["height"], initial["height"] + 50)
            saved = page.evaluate("JSON.parse(localStorage.getItem('ov-strongs-sheet-size'))")
            self.assertAlmostEqual(saved["width"], resized["width"], delta=2)
            self.assertAlmostEqual(saved["height"], resized["height"], delta=2)

            page.locator(".strongs-sheet-close").click()
            trigger.click()
            restored = page.locator(".strongs-sheet-panel").bounding_box()
            self.assertAlmostEqual(restored["width"], resized["width"], delta=2)
            self.assertAlmostEqual(restored["height"], resized["height"], delta=2)
        finally:
            page.close()

    def test_opgeslagen_desktopformaat_blijft_binnen_het_huidige_scherm(self):
        page = self.open_reader("johannes/1", width=900, height=700)
        try:
            page.evaluate("localStorage.setItem('ov-strongs-sheet-size', JSON.stringify({width: 4000, height: 3000}))")
            self.enable_strongs(page)
            page.locator('.verse-row[data-verse="1"] [data-strongs="G1722"]').first.click()
            box = page.locator(".strongs-sheet-panel").bounding_box()
            self.assertLessEqual(box["width"], 860)
            self.assertLessEqual(box["height"], 660)
            self.assertGreaterEqual(box["x"], 20)
            self.assertGreaterEqual(box["y"], 20)
            self.assertTrue(page.locator(".strongs-sheet-close").is_visible())
        finally:
            page.close()

    def test_niet_afzonderlijk_vertaald_grondwoord_blijft_inline_zichtbaar(self):
        page = self.open_reader()
        try:
            html = page.evaluate(
                """() => OVWoordnummers.renderInline('het Woord', [{
                    tekst: '', anker: 'Woord', voorkomen: 1, plaats: 'na',
                    strongs: ['G3588'], bronwoorden: ['ὁ'],
                    status: 'niet_afzonderlijk_weergegeven',
                    reviewstatus: 'handmatig_gecontroleerd'
                }])"""
            )
            self.assertIn('Woord<button', html)
            self.assertIn('data-strongs="G3588"', html)
            self.assertIn('data-alignment-status="niet_afzonderlijk_weergegeven"', html)
        finally:
            page.close()

    def test_johannes_1_toont_tr_vormnummer_en_ongemapt_grondwoord_inline(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            first = page.locator('.verse-row[data-verse="1"] .col-2026')
            was = first.locator('[data-strongs="G2258"]').first
            self.assertEqual(was.inner_text(), "<2258>(5713)")
            self.assertTrue(was.evaluate("""el => {
                const range = document.createRange(); range.setStart(el.parentNode, 0); range.setEndBefore(el);
                const fragment = range.cloneContents(); fragment.querySelectorAll('.strongs-inline, .note-marker').forEach(marker => marker.remove());
                return fragment.textContent.trimEnd().endsWith('was');
            }"""))

            twelfth = page.locator('.verse-row[data-verse="12"] .col-2026')
            unrendered = twelfth.locator(
                '[data-strongs="G846"][data-alignment-status="niet_afzonderlijk_weergegeven"]'
            )
            self.assertEqual(unrendered.count(), 1)
            unrendered.click()
            page.locator("#strongs-sheet").wait_for(state="visible", timeout=5_000)
        finally:
            page.close()

    def test_johannes_1_2_toont_woordnummer_met_tijdcode(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            was = page.locator(
                '.verse-row[data-verse="2"] .col-2026 [data-strongs="G2258"]'
            ).first
            self.assertEqual(was.inner_text(), "<2258>(5713)")
            self.assertEqual(was.get_attribute("data-tvm"), "G5713")
        finally:
            page.close()

    def test_griekse_sheet_toont_het_volledige_woordenboekartikel(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            page.locator('.verse-row[data-verse="1"] .col-2026 [data-strongs="G1722"]').first.click()
            article = page.frame_locator("#strongs-sheet-article")
            article.locator(".lex-entry-head").wait_for(timeout=15_000)
            article.locator(".lex-lexlabel", has_text="Abbott-Smith").wait_for(timeout=15_000)
            labels = article.locator(".lex-lexlabel").all_inner_texts()
            self.assertTrue(any("TBESG" in label.upper() for label in labels), labels)
            self.assertTrue(any("ABBOTT-SMITH" in label.upper() for label in labels), labels)
            reference = article.locator('a[href="index.html#lukas/7/37"]')
            self.assertGreater(reference.count(), 0)
            self.assertEqual(reference.first.inner_text(), "Lukas 7:37")
        finally:
            page.close()

    def test_geez_woordnummer_staat_inline_en_opent_het_dillmann_woordenboek(self):
        page = self.open_reader("henoch/1")
        try:
            self.enable_strongs(page)
            trigger = page.locator('.verse-row[data-verse="1"] .col-2026 [data-strongs="OVG3907"]')
            self.assertEqual(trigger.inner_text(), "<3907>")
            trigger.click()
            sheet = page.locator("#strongs-sheet")
            sheet.wait_for(state="visible", timeout=5_000)
            self.assertIn("WOORDENBOEKARTIKEL", sheet.locator(".lexicon-source").inner_text())
            self.assertIn(
                "taal=geez&entry=OVG3907&embed=1",
                sheet.locator("#strongs-sheet-article").get_attribute("src"),
            )
            article = page.frame_locator("#strongs-sheet-article")
            article.locator(".lex-entry-head").wait_for(timeout=20_000)
            self.assertIn("OVG3907", article.locator(".lex-entry-strong").inner_text())
        finally:
            page.close()

    def test_strongnummers_blijven_helderblauw_in_donker_thema(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.add_init_script(
            "localStorage.setItem('sv2026_vertaalopties', JSON.stringify({thema:'donker'}))"
        )
        try:
            page.goto(f"{self.base_url}/index.html#johannes/1", wait_until="domcontentloaded")
            page.locator('.verse-row[data-verse="1"]').wait_for(timeout=15_000)
            self.enable_strongs(page)
            color = page.locator('.verse-row[data-verse="1"] [data-strongs="G1722"]').first.evaluate(
                "el => getComputedStyle(el).color"
            )
            self.assertEqual(color, "rgb(131, 187, 239)")
        finally:
            page.close()

        page = self.open_reader("henoch/1")
        try:
            self.enable_strongs(page, expect_inline=False)
            cell = page.locator('.verse-row[data-verse="1"] .col-2026')
            self.assertEqual(cell.locator('.strongs-alignment').count(), 0)
            self.assertEqual(cell.locator('.strongs-source-word').count(), 0)
        finally:
            page.close()

    def test_gedeelde_renderer_is_beschikbaar_voor_interne_citaties(self):
        page = self.open_reader("johannes/1")
        try:
            html = page.evaluate(
                """() => OVWoordnummers.renderInline('In het begin', [{
                    tekst: 'begin', voorkomen: 1, strongs: ['G746'],
                    bronwoorden: ['ἀρχῇ'], transliteraties: ['arche'], glossen: ['begin']
                }])"""
            )
            self.assertIn('begin<button', html)
            self.assertIn('data-strongs="G746"', html)
        finally:
            page.close()

    def test_ingebedde_woordnummers_winnen_van_een_verouderde_externe_laag(self):
        page = self.open_reader("handelingen/22")
        try:
            mappings = page.evaluate(
                """() => {
                    const chapter = {verses: [{number: 1, woordnummers: [{
                        tekst: 'Broeders', voorkomen: 1, strongs: ['G80'],
                        reviewstatus: 'handmatig_gecontroleerd'
                    }]}]};
                    const staleExternal = {chapters: {'22': {'1': [{
                        tekst: 'Broeders en vaders, hoort mijn verantwoording.',
                        voorkomen: 1, strongs: ['G80', 'G3962']
                    }]}}};
                    OVWoordnummers.mergeChapterMappings(chapter, staleExternal, 22);
                    return chapter.verses[0].woordnummers;
                }"""
            )
            self.assertEqual(mappings, [{
                "tekst": "Broeders",
                "voorkomen": 1,
                "strongs": ["G80"],
                "reviewstatus": "handmatig_gecontroleerd",
            }])
        finally:
            page.close()

    def test_hoofdstukdata_wordt_opnieuw_bevestigd_na_publicatie(self):
        """Een verse publicatie mag niet door een nog verse browsercache worden gemaskeerd."""
        page = self.open_reader("johannes/1")
        try:
            page.evaluate("""() => {
                const realFetch = window.fetch.bind(window);
                window.__chapterFetchOptions = [];
                window.fetch = (input, options) => {
                    if (String(input).includes('data/cache-probe/1.json')) {
                        window.__chapterFetchOptions.push(options || {});
                    }
                    return realFetch(input, options);
                };
            }""")
            _QuietHandler.cache_probe_version = "oud"
            _QuietHandler.cache_probe_requests = 0
            first = page.evaluate(
                """() => DataLoader.loadChapter('cache-probe', 1)
                    .then(chapter => chapter.verses[0].woordnummers[0].tekst)"""
            )
            self.assertEqual(first, "oud")

            _QuietHandler.cache_probe_version = "nieuw"
            page.evaluate("() => DataLoader.invalidateCache('cache-probe')")
            second = page.evaluate(
                """() => DataLoader.loadChapter('cache-probe', 1)
                    .then(chapter => chapter.verses[0].woordnummers[0].tekst)"""
            )

            self.assertEqual(second, "nieuw")
            self.assertEqual(_QuietHandler.cache_probe_requests, 2)
            self.assertEqual(
                page.evaluate("() => window.__chapterFetchOptions.map(options => options.cache)"),
                ["no-cache", "no-cache"],
            )
        finally:
            page.close()

    def test_externe_woordnummerlaag_wordt_opnieuw_bevestigd_na_publicatie(self):
        page = self.open_reader("johannes/1")
        try:
            page.evaluate("""() => {
                const realFetch = window.fetch.bind(window);
                window.__inlineFetchOptions = [];
                window.fetch = (input, options) => {
                    if (String(input).includes('woordnummers-inline/cache-probe.json')) {
                        window.__inlineFetchOptions.push(options || {});
                    }
                    return realFetch(input, options);
                };
            }""")
            _QuietHandler.inline_cache_probe_requests = 0
            mappings = page.evaluate(
                """() => OVWoordnummers.loadBookMappings('cache-probe')
                    .then(book => book.chapters['1']['1'][0].tekst)"""
            )

            self.assertEqual(mappings, "woord")
            self.assertEqual(_QuietHandler.inline_cache_probe_requests, 1)
            self.assertEqual(
                page.evaluate("() => window.__inlineFetchOptions.map(options => options.cache)"),
                ["no-cache"],
            )
        finally:
            page.close()

    def test_doorlopende_leesversie_neemt_woordnummervoorkeur_over(self):
        page = self.browser.new_page(viewport={"width": 900, "height": 900})
        page.add_init_script(
            "localStorage.setItem('sv2026_vertaalopties', JSON.stringify({strongs:'aan'}))"
        )
        try:
            page.goto(f"{self.base_url}/lees.html#johannes/1", wait_until="domcontentloaded")
            trigger = page.locator('.verse-span[data-verse="1"] .verse-text [data-strongs="G1722"]')
            trigger.wait_for(state="visible", timeout=15_000)
            self.assertEqual(trigger.inner_text(), "<1722>")
            self.assertEqual(page.locator('.verse-span[data-verse="1"] .strongs-alignment').count(), 0)
            trigger.click()
            page.locator("#strongs-sheet").wait_for(state="visible", timeout=5_000)
        finally:
            page.close()

    def test_doorlopende_leesversie_bevestigt_hoofdstukdata_opnieuw(self):
        page = self.browser.new_page(viewport={"width": 900, "height": 900})
        try:
            page.goto(f"{self.base_url}/lees.html#johannes/1", wait_until="domcontentloaded")
            page.locator('.verse-span[data-verse="1"]').wait_for(timeout=15_000)
            page.evaluate("""() => {
                const realFetch = window.fetch.bind(window);
                window.__leesFetchOptions = [];
                window.fetch = (input, options) => {
                    if (String(input).includes('data/cache-probe/1.json')) {
                        window.__leesFetchOptions.push(options || {});
                    }
                    return realFetch(input, options);
                };
            }""")

            text = page.evaluate(
                """() => Lees.fetchJSON('/data/cache-probe/1.json')
                    .then(chapter => chapter.verses[0].woordnummers[0].tekst)"""
            )

            self.assertIn(text, {"oud", "nieuw"})
            self.assertEqual(
                page.evaluate("() => window.__leesFetchOptions.map(options => options.cache)"),
                ["no-cache"],
            )
        finally:
            page.close()

    def test_stronglabels_blijven_buiten_gekopieerde_bijbeltekst(self):
        page = self.open_reader("johannes/1")
        try:
            self.enable_strongs(page)
            copied = page.evaluate(
                """() => {
                    VerseSelect.selected = new Set(['johannes/1/1']);
                    return VerseSelect._buildRefAndText().plain;
                }"""
            )
            self.assertNotIn("G1722", copied)
            self.assertIn("begin", copied.lower())
        finally:
            page.close()


class StrongsDataTests(unittest.TestCase):
    def test_importer_gebruikt_explicit_source_verse_voor_verschoven_lokaal_vers(self):
        source_document = {
            "type": "USJ",
            "content": [
                {"type": "chapter", "number": "1"},
                {"type": "verse", "number": "2"},
                {"type": "char", "marker": "w", "strong": "G3056", "content": ["Word"]},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "source"; source_dir.mkdir()
            source_path = source_dir / "demo.usj"
            source_path.write_text(json.dumps(source_document), encoding="utf-8")
            digest = hashlib.sha256(source_path.read_bytes()).hexdigest().upper()
            data_dir = root / "data" / "demo"; data_dir.mkdir(parents=True)
            (data_dir / "1.json").write_text(json.dumps({"verses":[{"number":1,"text2026":"Woord","grondtekst":[{"woord":"λόγος","strongs":"G3056"}]}]}), encoding="utf-8")
            review = {"source":{"id":"test","version":"1","sha256":"x"},"books":[{"code":"DEM","repo_book":"demo","chapter":1,"source_file":"demo.usj","source_file_sha256":digest,"verses":[{"verse":1,"source_verse":2,"mappings":[{"tekst":"Woord","bronindices":[0],"grondindices":[0],"confidence":1.0,"reviewstatus":"handmatig_gecontroleerd"}]}]}]}
            review_path = root / "review.json"; review_path.write_text(json.dumps(review), encoding="utf-8")
            report = apply_review_file(review_path, source_dir, root / "data", write=True)
            result = json.loads((data_dir / "1.json").read_text(encoding="utf-8"))
        self.assertEqual(report["added"], 1)
        self.assertEqual(result["verses"][0]["woordnummers"][0]["herkomst"]["referentie"], "DEM 1:2")

    def test_johannes_review_metadata_bewaart_bewezen_verscorrespondentie(self):
        pilot = json.loads((ROOT / "data" / "woordnummers-pilot-johannes.json").read_text(encoding="utf-8"))
        correspondence = {
            item["local_verse"]: item
            for item in pilot["books"][0]["verse_correspondence"]
        }
        self.assertEqual(correspondence[38]["status"], "gedeeltelijk")
        self.assertEqual(correspondence[39]["status"], "afwijkend")
        for local_verse in range(40, 46):
            self.assertEqual(correspondence[local_verse]["status"], "afwijkend")
            self.assertIn("grondtekst", correspondence[local_verse]["reden"])

    def test_usj_parser_behoudt_geneste_versgrens_in_char_inhoud(self):
        """Een USJ-versmarker kan binnen opgemaakte inhoud staan (Johannes 1:39)."""
        fixture = {
            "type": "USJ",
            "content": [
                {"type": "chapter", "number": "1"},
                {
                    "type": "para",
                    "content": [
                        {"type": "verse", "number": "38"},
                        {
                            "type": "char",
                            "marker": "qt",
                            "content": [
                                {"type": "verse", "number": "39"},
                                {
                                    "type": "char",
                                    "marker": "w",
                                    "strong": "G4226",
                                    "content": ["where"],
                                },
                            ],
                        },
                    ],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "nested.usj"
            source.write_text(json.dumps(fixture), encoding="utf-8")
            parsed = parse_usj(source)
        self.assertEqual(parsed[(1, 39)], [{"text": "where", "strongs": ["G4226"]}])

    def test_alle_88_boeken_hebben_bronvaste_woordnummers(self):
        report = audit()
        self.assertEqual(report["books"], 88)
        self.assertEqual(report["books_with_numbers"], 88)
        self.assertFalse(report["invalid"])
        self.assertEqual(set(report["families"]), {"H", "G", "OVL", "OVG"})

    def test_woordverwijzingen_gebruiken_alleen_ondersteunde_nummerfamilies(self):
        families = set()
        for chapter_file in ROOT.glob("data/*/[0-9]*.json"):
            data = json.loads(chapter_file.read_text(encoding="utf-8"))
            for verse in data.get("verses", []):
                if not isinstance(verse, dict):
                    continue
                for word in verse.get("grondtekst", []) or []:
                    if not isinstance(word, dict):
                        continue
                    value = str(word.get("strongs") or "")
                    if value:
                        for number in value.split():
                            if number.startswith("OVL"):
                                families.add("OVL")
                            elif number.startswith("OVG"):
                                families.add("OVG")
                            elif number.startswith("H"):
                                families.add("H")
                            elif number.startswith("G"):
                                families.add("G")
                            else:
                                self.fail(f"Onbekende woordnummerfamilie: {number}")
        self.assertEqual(families, {"H", "G", "OVL", "OVG"})


if __name__ == "__main__":
    unittest.main()
