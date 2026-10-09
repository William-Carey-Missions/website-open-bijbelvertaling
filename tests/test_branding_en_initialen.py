"""Browserverificatie van de gedeelde branding en hoofdstukinitialen."""

import contextlib
import hashlib
import http.server
from pathlib import Path
import re
import threading
import unittest
import xml.etree.ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SVG_NS = "{http://www.w3.org/2000/svg}"

EXPECTED_BRANDING_SHA256 = {
    "open-folio-mark.png": "3466DC4943EAD2C4D81FCB392FF84D015720B798FF8CF484AFF122ED14511209",
    "open-folio-mark.svg": "65DCDE5456A9045875CA0CA2BB0A81E3F9AD4B1066A25C5F5C8BF38E8F07AF39",
    "open-vertaling-logo.png": "66D9BBDFCBAFA6315ADE0CDA24E5D23215CCCAAD201D370EA785757FC1A93B3E",
    "open-vertaling-logo.svg": "5A96EE77D0E949D2F8D6B54429369E90605B72B9EE866799D3D4B55A720BFD25",
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _path_geometry(root):
    return [
        (path.get("d"), path.get("transform"))
        for path in root.findall(f".//{SVG_NS}path")
    ]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, _request, _client_address):
        pass


def test_alle_goedgekeurde_merkassets_en_initialen_zijn_leverbaar():
    branding = ROOT / "images" / "branding"
    assert {
        "open-vertaling-logo.svg",
        "open-vertaling-logo.png",
        "open-folio-mark.svg",
        "open-folio-mark.png",
        "open-vertaling-logo-light.svg",
        "open-folio-mark-light.svg",
    } <= {path.name for path in branding.glob("*")}

    initialen = ROOT / "images" / "initialen" / "vrije-penkrul"
    letters = {f"{letter}.svg" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
    assert letters == {path.name for path in initialen.glob("*.svg")}
    assert letters == {path.name for path in (initialen / "donker").glob("*.svg")}


def test_definitieve_merkassets_zijn_bytegetrouw_en_lichte_variant_behoudt_geometrie():
    branding = ROOT / "images" / "branding"
    assert {
        name: _sha256(branding / name)
        for name in EXPECTED_BRANDING_SHA256
    } == EXPECTED_BRANDING_SHA256

    for stem in ("open-folio-mark", "open-vertaling-logo"):
        dark_path = branding / f"{stem}.svg"
        light_path = branding / f"{stem}-light.svg"
        dark_text = dark_path.read_text(encoding="utf-8")
        light_text = light_path.read_text(encoding="utf-8")
        assert light_text == dark_text.replace("#143247", "#FFFFFF")
        assert "#C4A048" in light_text
        assert _path_geometry(ET.parse(dark_path).getroot()) == _path_geometry(
            ET.parse(light_path).getroot()
        )


def test_favicon_en_webapp_iconen_gebruiken_het_folio_beeldmerk():
    source_root = ET.parse(ROOT / "images" / "branding" / "open-folio-mark.svg").getroot()
    source_geometry = _path_geometry(source_root)

    for relative in (
        "favicon.svg",
        "icons/app-icon.svg",
        "icons/app-icon-maskable.svg",
    ):
        root = ET.parse(ROOT / relative).getroot()
        mark = root.find(f".//{SVG_NS}g[@data-role='open-folio-mark']")
        assert mark is not None
        assert _path_geometry(mark) == source_geometry
        assert not any("OV" in (text.text or "") for text in root.findall(f".//{SVG_NS}text"))

    for relative, size in (
        ("icons/icon-192.png", (192, 192)),
        ("icons/icon-512.png", (512, 512)),
        ("icons/icon-maskable-512.png", (512, 512)),
    ):
        with Image.open(ROOT / relative) as image:
            assert image.size == size


class BrandingBrowserTests(unittest.TestCase):
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

    def test_volledige_merknaam_blijft_zichtbaar_bij_hamburgermenu(self):
        for width in (1440, 1000, 390):
            page = self.browser.new_page(viewport={"width": width, "height": 900})
            try:
                page.goto(f"{self.base_url}/over-ov.html")
                logo = page.locator(".topnav-logo")
                logo.wait_for(state="visible", timeout=3_000)
                self.assertEqual(logo.get_attribute("alt"), "Open Vertaling")
                self.assertGreater(logo.evaluate("img => img.naturalWidth"), 0)
                self.assertGreater(
                    logo.evaluate("img => img.getBoundingClientRect().width"), 100
                )
                natural_ratio = logo.evaluate("img => img.naturalWidth / img.naturalHeight")
                rendered_ratio = logo.evaluate(
                    "img => img.getBoundingClientRect().width / "
                    "img.getBoundingClientRect().height"
                )
                self.assertAlmostEqual(rendered_ratio, natural_ratio, delta=0.02)
                if width < 1200:
                    self.assertTrue(page.locator("#topnav-hamburger").is_visible())
                    self.assertFalse(page.locator("#topnav-links").is_visible())
                else:
                    self.assertFalse(page.locator("#topnav-hamburger").is_visible())
            finally:
                page.close()

    def test_stabiele_merkbestanden_worden_online_ververst(self):
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn("path.startsWith('/images/branding/')", service_worker)
        self.assertIn("path.startsWith('/images/initialen/')", service_worker)
        self.assertIn("path === '/favicon.svg'", service_worker)
        self.assertIn("path.startsWith('/icons/')", service_worker)

    def test_kritieke_letteropmaak_bestanden_hebben_releaseversie_in_de_url(self):
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        versie = re.search(r"const VERSION = 'v([^']+)'", service_worker).group(1)
        index = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn(f'href="css/style.css?v={versie}"', index)
        self.assertIn(f'src="js/app.js?v={versie}"', index)

    def test_hamburger_blijft_rechtsboven_op_alle_responsieve_breekpunten(self):
        for width, expected_right_gap in (
            (1000, 30),
            (769, 30),
            (768, 12),
            (700, 12),
            (390, 12),
        ):
            page = self.browser.new_page(viewport={"width": width, "height": 900})
            try:
                page.goto(f"{self.base_url}/over-ov.html")
                hamburger = page.locator("#topnav-hamburger")
                hamburger.wait_for(state="visible", timeout=3_000)
                right_gap = page.evaluate(
                    """() => {
                        const nav = document.querySelector('#topnav').getBoundingClientRect();
                        const button = document.querySelector('#topnav-hamburger').getBoundingClientRect();
                        return nav.right - button.right;
                    }"""
                )
                self.assertAlmostEqual(
                    right_gap,
                    expected_right_gap,
                    delta=1,
                    msg=f"hamburger staat niet rechtsboven bij {width}px",
                )
            finally:
                page.close()

    def test_documentatie_lokaal_en_achtergrond_op_open_gods_woord(self):
        # Sinds de splitsing (2026-10-08) heeft de OV geen wiki: documentatie
        # hangt aan over-ov.html#documentatie, achtergrond staat op OGW.
        page = self.browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(f"{self.base_url}/over-ov.html")
            hoofdlinks = page.locator("#topnav-links a")
            self.assertEqual(
                [t.strip() for t in hoofdlinks.all_text_contents()],
                ["Over OV", "Tekst", "Documentatie", "Achtergrond ↗"],
            )
            self.assertEqual(
                page.locator("#topnav-links a", has_text="Achtergrond").get_attribute("data-ogw-href"),
                "wiki.html",
            )
            doc = page.locator("#documentatie + p + ul.ov-doc-lijst a")
            hrefs = [a.get_attribute("href") for a in doc.all()]
            for verwacht in ("uitgangspunten.html", "principes.html", "bronnen.html", "downloads.html"):
                self.assertIn(verwacht, hrefs)
            # wiki.html is alleen nog een doorverwijzing voor oude links.
            page.goto(f"{self.base_url}/wiki.html#principes")
            page.wait_for_url("**/principes.html")
        finally:
            page.close()

    def test_aparte_leesheader_toont_het_woordmerk_in_beide_themas(self):
        page = self.browser.new_page(viewport={"width": 390, "height": 900})
        try:
            page.goto(f"{self.base_url}/lees.html")
            logos = page.locator(".reader-logo")
            self.assertEqual(logos.count(), 2)
            self.assertEqual(sum(logo.is_visible() for logo in logos.all()), 1)
            self.assertTrue(logos.nth(0).is_visible())
            page.locator("#dark-mode-toggle").click()
            self.assertTrue(page.locator("body.dark").is_visible())
            self.assertEqual(sum(logo.is_visible() for logo in logos.all()), 1)
            self.assertTrue(logos.nth(1).is_visible())
        finally:
            page.close()

    def test_genesis_hoofdstukken_gebruiken_de_juiste_kopieerbare_penkrul(self):
        for chapter, letter in ((1, "I"), (2, "Z")):
            page = self.browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                page.goto(f"{self.base_url}/index.html#genesis/{chapter}")
                dropcap = page.locator(
                    f'.verse-row[data-chapter="{chapter}"][data-verse="1"] '
                    ".col-2026 .dropcap"
                )
                dropcap.wait_for(state="visible", timeout=15_000)
                state = dropcap.evaluate(
                    """el => ({
                        text: el.dataset.letter,
                        lightSrc: el.querySelector('.dropcap-image--light').src,
                        lightVisible: !!el.querySelector('.dropcap-image--light').getClientRects().length
                    })"""
                )
                self.assertEqual(state["text"], letter)
                self.assertIn(f"/{letter}.svg", state["lightSrc"])
                self.assertTrue(state["lightVisible"])
                if chapter == 1:
                    page.locator("#topnav-theme-toggle").click()
                    dark_state = dropcap.evaluate(
                        """el => ({
                            color: getComputedStyle(el).color,
                            darkSrc: el.querySelector('.dropcap-image--dark').src,
                            lightVisible: !!el.querySelector('.dropcap-image--light').getClientRects().length,
                            darkVisible: !!el.querySelector('.dropcap-image--dark').getClientRects().length
                        })"""
                    )
                    self.assertIn(f"/donker/{letter}.svg", dark_state["darkSrc"])
                    self.assertFalse(dark_state["lightVisible"])
                    self.assertTrue(dark_state["darkVisible"])
                    self.assertEqual(dark_state["color"], "rgba(0, 0, 0, 0)")
            finally:
                page.close()

    def test_lukas_22_krijgt_op_vers_een_decoratieve_e_initiaal(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(f"{self.base_url}/index.html#lukas/22")
            dropcap = page.locator(
                '.verse-row[data-chapter="22"][data-verse="1"] '
                ".col-2026 .dropcap"
            )
            dropcap.wait_for(state="visible", timeout=15_000)
            state = dropcap.evaluate(
                """el => ({
                    letter: el.dataset.letter,
                    source: el.querySelector('.dropcap-image--light').src
                })"""
            )
            self.assertEqual(state["letter"], "E")
            self.assertIn("/E.svg", state["source"])
        finally:
            page.close()

    def test_alle_initiaalbeelden_zijn_strak_op_het_tekenwerk_bijgesneden(self):
        page = self.browser.new_page()
        try:
            page.goto(f"{self.base_url}/index.html", wait_until="domcontentloaded")
            audit = page.evaluate(
                """async () => {
                    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
                    const resultaten = [];
                    for (const thema of ['', 'donker/']) {
                        for (const letter of letters) {
                            const url = `/images/initialen/vrije-penkrul/${thema}${letter}.svg`;
                            const tekst = await (await fetch(url)).text();
                            const bron = new DOMParser().parseFromString(tekst, 'image/svg+xml').documentElement;
                            const svg = document.importNode(bron, true);
                            svg.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:400px;height:400px';
                            document.body.append(svg);
                            const vak = svg.viewBox.baseVal;
                            const onderdelen = [...svg.querySelectorAll('[data-role]')];
                            const dozen = onderdelen.map(el => el.getBBox());
                            const links = Math.min(...dozen.map(b => b.x));
                            const boven = Math.min(...dozen.map(b => b.y));
                            const rechts = Math.max(...dozen.map(b => b.x + b.width));
                            const onder = Math.max(...dozen.map(b => b.y + b.height));
                            resultaten.push({
                                url,
                                marges: [links - vak.x, boven - vak.y,
                                    vak.x + vak.width - rechts, vak.y + vak.height - onder]
                            });
                            svg.remove();
                        }
                    }
                    return resultaten;
                }"""
            )
            for resultaat in audit:
                with self.subTest(asset=resultaat["url"]):
                    self.assertGreaterEqual(min(resultaat["marges"]), 3)
                    self.assertLessEqual(max(resultaat["marges"]), 12)
        finally:
            page.close()

    def test_initiaalbeeld_volgt_eigen_breedte_en_sluit_dicht_aan_op_de_tekst(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(f"{self.base_url}/index.html#genesis/1")
            dropcap = page.locator(
                '.verse-row[data-chapter="1"][data-verse="1"] .col-2026 .dropcap'
            )
            dropcap.wait_for(state="visible", timeout=15_000)
            meting = dropcap.evaluate(
                """el => {
                    const beeld = el.querySelector('img:not([hidden])');
                    const walker = document.createTreeWalker(el.parentElement, NodeFilter.SHOW_TEXT);
                    let node;
                    while ((node = walker.nextNode())) {
                        if (el.contains(node) || !node.nodeValue.trim()) continue;
                    const index = node.nodeValue.search(/\\S/);
                        const bereik = document.createRange();
                        bereik.setStart(node, index);
                        bereik.setEnd(node, index + 1);
                        return {
                            letter: el.dataset.letter,
                            vorm: getComputedStyle(el).shapeOutside,
                            beeld: beeld && beeld.getBoundingClientRect().toJSON(),
                            volgende: bereik.getBoundingClientRect().toJSON(),
                        };
                    }
                    return {letter: el.dataset.letter, beeld: null, volgende: null};
                }"""
            )
            self.assertEqual(meting["letter"], "I")
            self.assertIn("/I.svg", meting["vorm"])
            self.assertIsNotNone(meting["beeld"])
            self.assertIsNotNone(meting["volgende"])
            self.assertLessEqual(meting["volgende"]["left"] - meting["beeld"]["right"], -5)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
