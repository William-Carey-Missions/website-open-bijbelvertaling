"""Regressietests voor de mobiele login en snelle Strong-schakelaar."""

import contextlib
import http.server
from pathlib import Path
import threading
import unittest
import re

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


class TopnavQuickActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = lambda *args, **kwargs: _QuietHandler(
            *args, directory=str(ROOT), **kwargs
        )
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        with contextlib.suppress(Exception):
            cls.browser.close()
        with contextlib.suppress(Exception):
            cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_strong_knop_staat_naast_verschillen_en_synchroniseert_optie(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(f"{self.base_url}/index.html#johannes/1", wait_until="domcontentloaded")
            button = page.locator("#quick-strongs-btn")
            self.assertEqual(button.count(), 1)
            self.assertEqual(
                page.locator("#column-toggles-wrapper > button").all_text_contents(),
                ["Verschillen SV-OV", "Grondtekst-link"],
            )
            button.click()
            self.assertEqual(button.get_attribute("aria-pressed"), "true")
            self.assertTrue(page.locator("#toggle-strongs").is_checked())
            self.assertEqual(page.evaluate("Opties.state.strongs"), "aan")
            button.click()
            self.assertEqual(button.get_attribute("aria-pressed"), "false")
            self.assertFalse(page.locator("#toggle-strongs").is_checked())
        finally:
            page.close()

    def test_google_login_verhuist_alleen_op_mobiel_naar_hamburgermenu(self):
        mobile = self.browser.new_page(viewport={"width": 390, "height": 844})
        desktop = self.browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            mobile.goto(f"{self.base_url}/over-ov.html", wait_until="domcontentloaded")
            self.assertEqual(
                mobile.locator("#topnav-links > #auth-slot").count(), 1
            )
            mobile.locator("#topnav-hamburger").click()
            self.assertTrue(mobile.locator("#auth-slot").is_visible())

            desktop.goto(f"{self.base_url}/over-ov.html", wait_until="domcontentloaded")
            self.assertEqual(
                desktop.locator("#topnav > #auth-slot").count(), 1
            )
            self.assertEqual(
                desktop.locator("#topnav-links > #auth-slot").count(), 0
            )
        finally:
            mobile.close()
            desktop.close()

    def test_strong_koppeling_en_rendercode_hebben_dezelfde_cacheversie(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        opties = re.search(r'<script src="js/opties\.js\?v=([^"]+)">', html)
        app = re.search(r'<script src="js/app\.js\?v=([^"]+)">', html)
        self.assertIsNotNone(opties)
        self.assertIsNotNone(app)
        self.assertEqual(opties.group(1), app.group(1))


if __name__ == "__main__":
    unittest.main()
