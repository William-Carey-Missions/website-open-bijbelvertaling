"""Browserverificatie van het responsieve optiespaneel."""

import contextlib
import http.server
from pathlib import Path
import threading
import unittest

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, _request, _client_address):
        pass


class OptionsPanelBrowserTests(unittest.TestCase):
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

    def open_reader(self, width=1280, height=900, location="genesis/1"):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"{self.base_url}/index.html#{location}", wait_until="domcontentloaded")
        if width <= 768:
            page.locator("#topnav-hamburger").wait_for(state="visible", timeout=15_000)
        else:
            page.locator("#topnav-weergave").wait_for(state="visible", timeout=15_000)
        return page

    @staticmethod
    def open_mobile_options(page):
        page.locator("#topnav-weergave").click()

    def test_opties_opent_modaal_zonder_de_leestekst_te_versmallen(self):
        page = self.open_reader()
        try:
            content = page.locator("#content")
            before = content.bounding_box()["width"]
            page.locator("#topnav-weergave").click()
            dialog_is_open = page.locator("#sidebar-right").evaluate(
                "el => el instanceof HTMLDialogElement && el.open"
            )
            after = content.bounding_box()["width"]

            self.assertTrue(dialog_is_open)
            self.assertAlmostEqual(after, before, delta=1)
        finally:
            page.close()

    def test_opties_heeft_inklapbare_categorieen_in_plaats_van_tabs(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            self.assertEqual(page.get_by_role("tab").count(), 0)
            self.assertEqual(page.locator("details.options-category").count(), 5)
            # Alle kopjes staan open, zodat het paneel in een keer door te
            # scrollen is en niemand eerst vijf laatjes hoeft open te klikken.
            self.assertEqual(page.locator("details.options-category:not([open])").count(), 0)
        finally:
            page.close()

    def test_zoeken_filtert_tijdens_het_typen_over_alle_categorieen(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            search = page.locator("#options-search")
            self.assertEqual(search.get_attribute("spellcheck"), "false")
            search.press_sequentially("regelafsta")
            rows = page.locator("#sidebar-right .option-row:visible, #sidebar-right .option-choice:visible")
            # Elke instelling één keer: de kopie onder Meest gebruikt valt weg.
            self.assertEqual(rows.count(), 1)
            self.assertIn("Regelafstand", rows.first.inner_text())
            self.assertFalse(page.locator('[data-options-category="meest-gebruikt"]').is_visible())
            search.fill("")
            self.assertTrue(page.locator('[data-options-category="meest-gebruikt"]').is_visible())
            self.assertGreater(rows.count(), 10)
        finally:
            page.close()

    def test_zoeken_zonder_treffers_zegt_dat_er_niets_is_gevonden(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            page.locator("#options-search").press_sequentially("xyzq")
            empty = page.locator("#options-search-empty")
            self.assertTrue(empty.is_visible())
            self.assertIn("Geen instellingen gevonden", empty.inner_text())
            page.locator("#options-search").fill("")
            self.assertFalse(empty.is_visible())
        finally:
            page.close()

    def test_hoofdinstellingen_gebruiken_de_aangeleverde_iconen(self):
        expected = {
            "thema.png",
            "lettertype.png",
            "tekstgrootte.png",
            "regelafstand.png",
            "versnummers.png",
            "godsnaam.png",
            "voorkeurseditie.png",
            "voorleesstem.png",
        }
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            sources = page.locator("#sidebar-right .options-list > :not(.option-mirror) .option-icon").evaluate_all(
                "els => els.map(el => new URL(el.src).pathname.split('/').pop())"
            )
            self.assertTrue(expected.issubset(set(sources)))
            self.assertTrue(page.locator("#sidebar-right .options-list > :not(.option-mirror) .option-icon").evaluate_all(
                "els => els.every(el => el.complete && el.naturalWidth > 0)"
            ))
        finally:
            page.close()

    def test_desktop_paneel_is_compact_en_handmatig_verstelbaar(self):
        page = self.open_reader(width=1280, height=900)
        try:
            page.locator("#topnav-weergave").click()
            panel = page.locator("#sidebar-right")
            box = panel.bounding_box()
            self.assertLessEqual(box["width"], 521)
            self.assertEqual(panel.evaluate("el => getComputedStyle(el).resize"), "both")
            self.assertLess(box["height"], 820)
        finally:
            page.close()

    def test_mobiel_optiescherm_is_een_drie_kwart_hoge_bottom_sheet(self):
        page = self.open_reader(width=390, height=844)
        try:
            self.open_mobile_options(page)
            panel = page.locator("#sidebar-right")
            box = panel.bounding_box()
            self.assertAlmostEqual(box["height"], 633, delta=2)
            self.assertAlmostEqual(box["y"] + box["height"], 844, delta=1)
            self.assertEqual(
                panel.evaluate("el => getComputedStyle(el, '::backdrop').backgroundColor"),
                "rgba(0, 0, 0, 0)",
            )
        finally:
            page.close()

    def test_optiecategorieen_sluiten_horizontaal_op_het_paneel_aan(self):
        page = self.open_reader(width=1280, height=900)
        try:
            page.locator("#topnav-weergave").click()
            panel = page.locator("#sidebar-right")
            category = panel.locator(".options-category").first
            body_padding = panel.locator("#sidebar-right-body").evaluate(
                "el => ({left: getComputedStyle(el).paddingLeft, right: getComputedStyle(el).paddingRight})"
            )
            category_margin = category.evaluate(
                "el => ({left: getComputedStyle(el).marginLeft, right: getComputedStyle(el).marginRight})"
            )
            self.assertEqual(body_padding, {"left": "0px", "right": "0px"})
            self.assertEqual(category_margin, {"left": "0px", "right": "0px"})
        finally:
            page.close()

    def test_weergaveknop_staat_in_de_hoofdbalk_en_opent_hetzelfde_paneel(self):
        page = self.open_reader()
        try:
            opener = page.locator("#topnav-weergave")
            self.assertTrue(opener.is_visible())
            self.assertEqual(opener.get_attribute("aria-controls"), "sidebar-right")

            opener.click()
            self.assertTrue(page.locator("#sidebar-right").evaluate(
                "el => el instanceof HTMLDialogElement && el.open"
            ))
        finally:
            page.close()

    def test_mobiele_weergaveknop_staat_apart_in_de_hoofdbalk(self):
        page = self.open_reader(width=390, height=844)
        try:
            opener = page.locator("#topnav-weergave")
            self.assertTrue(opener.is_visible())
            opener.click()
            self.assertTrue(page.locator("#sidebar-right").evaluate("el => el.open"))
        finally:
            page.close()

    def test_iedere_zichtbare_instelling_heeft_een_eigen_icoon(self):
        expected = {
            "thema.png", "lettertype.png", "tekstgrootte.png", "regelafstand.png",
            "versnummers.png", "godsnaam.png", "voorkeurseditie.png", "voorleesstem.png",
            "boekinleiding.png", "hoofdstukinleiding.png", "dyslexiemodus.png",
            "citaatopmaak.png", "hoofdstuknummers.png", "perikoopkopjes.png",
            "doorlopend-lezen.png", "boekvolgorde.png", "aanspreektitel-nt.png",
            "sheol.png", "namen-personen.png", "naam-jezus.png",
            "maten-gewichten.png", "grote-getallen.png", "tijdsaanduidingen.png",
            "afspeelsnelheid.png", "kanttekeningen.png", "extra-kolommen.png",
            "vergelijkingsedities.png",
            "verschillen-vertalingen.png", "verschillen-kanttekeningen.png",
            "grondtalen.png", "oudste-handschrift.png", "onderwerptags.png",
            "strong-nummers.png",
            "apocriefe-boeken.png", "ethiopische-boeken.png",
            "spoor.png",
        }
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            sources = page.locator("#sidebar-right .options-list > :not(.option-mirror) .option-icon").evaluate_all(
                "els => els.map(el => new URL(el.src).pathname.split('/').pop())"
            )
            self.assertEqual(set(sources), expected)
            self.assertEqual(len(sources), len(expected))
            self.assertTrue(page.locator("#sidebar-right .options-list > :not(.option-mirror) .option-icon").evaluate_all(
                "els => els.every(el => el.complete && el.naturalWidth > 0)"
            ))
        finally:
            page.close()

    def test_ieder_instellingenblok_heeft_exact_een_rastericoon(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            instellingen = page.locator(
                "#sidebar-right .options-list > .option-row, "
                "#sidebar-right .options-list > .option-choice"
            )
            self.assertGreater(instellingen.count(), 30)
            for index in range(instellingen.count()):
                with self.subTest(index=index):
                    blok = instellingen.nth(index)
                    self.assertEqual(blok.locator(":scope .option-icon").count(), 1)
                    bron = blok.locator(":scope .option-icon").get_attribute("src")
                    self.assertTrue(bron.endswith(".png"), bron)

            self.assertEqual(
                page.locator("#sidebar-right .options-section-icon").count(),
                0,
                "Sectiekoppen mogen geen teksttekens als pseudo-iconen gebruiken",
            )
        finally:
            page.close()

    def test_desktop_is_compact_en_mobiel_houdt_aanraakdoelen(self):
        page = self.open_reader(width=1280, height=900)
        try:
            page.locator("#topnav-weergave").click()
            maten = page.locator("#sidebar-right").evaluate(
                """panel => {
                    const row = panel.querySelector('.option-row');
                    const heading = panel.querySelector('.options-category > summary');
                    const body = panel.querySelector('.options-body');
                    return {
                        rowMinHeight: parseFloat(getComputedStyle(row).minHeight),
                        rowPaddingTop: parseFloat(getComputedStyle(row).paddingTop),
                        headingHeight: parseFloat(getComputedStyle(heading).minHeight),
                        bodyPaddingTop: parseFloat(getComputedStyle(body).paddingTop),
                    };
                }"""
            )
            self.assertLessEqual(maten["rowMinHeight"], 50)
            self.assertLessEqual(maten["rowPaddingTop"], 7)
            self.assertLessEqual(maten["headingHeight"], 52)
            self.assertLessEqual(maten["bodyPaddingTop"], 14)
        finally:
            page.close()

        page = self.open_reader(width=390, height=844)
        try:
            self.open_mobile_options(page)
            page.locator("#sidebar-right").wait_for(state="visible", timeout=3_000)
            self.assertGreaterEqual(
                page.locator("#sidebar-right .option-row").first.evaluate(
                    "el => parseFloat(getComputedStyle(el).minHeight)"
                ),
                44,
            )
            self.assertGreaterEqual(
                page.locator('details[data-options-category="bronnen"] .option-choice-inline label')
                .first.evaluate("el => parseFloat(getComputedStyle(el).minHeight)"),
                44,
            )
        finally:
            page.close()

    def test_lettertype_en_regelafstand_worden_toegepast_en_bewaard(self):
        page = self.open_reader()
        try:
            page.wait_for_function("window.Opties && window.Opties.state")
            page.locator("#topnav-weergave").click()
            page.locator('#toggle-lettertype-alternatief').check()
            page.locator('#opt-regelafstand').fill("2")
            page.locator('#opt-regelafstand').dispatch_event("change")

            self.assertTrue(page.locator("body").evaluate(
                "el => el.classList.contains('reader-font-rustig')"
            ))
            self.assertTrue(page.locator("body").evaluate(
                "el => el.classList.contains('reader-spacing-ruim')"
            ))
            verse = page.locator("#verses-container .verse-cell.col-2026").first
            verse.wait_for(timeout=5000)
            typography = verse.evaluate(
                "el => ({font: getComputedStyle(el).fontFamily, line: parseFloat(getComputedStyle(el).lineHeight)})"
            )
            # Ontwerp 2026: het alternatieve (schreefloze) lettertype is IBM Plex Sans.
            self.assertIn("IBM Plex Sans", typography["font"])
            self.assertGreater(typography["line"], 32)
            page.wait_for_function(
                """() => {
                    const state = JSON.parse(localStorage.getItem('sv2026_vertaalopties'));
                    return state.lettertype === 'rustig' && state.regelafstand === 'ruim';
                }"""
            )

            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "window.Opties && window.Opties.state.lettertype === 'rustig'"
            )
            self.assertTrue(page.locator("body.reader-font-rustig.reader-spacing-ruim").count())
        finally:
            page.close()

    def test_bestaande_controls_staan_in_de_juiste_categorie(self):
        expected_category = {
            "toggle-versnummers": "leestekst",
            "toggle-citaten": "leestekst",
            "toggle-doorlopend": "leestekst",
            "opt-audio-speed": "voorlezen",
            "toggle-kt-popup": "bronnen",
            "toggle-contextmarkeringen": "bronnen",
            "toggle-hs-vers": "bronnen",
        }
        page = self.open_reader()
        try:
            for control_id, category in expected_category.items():
                with self.subTest(control=control_id):
                    self.assertEqual(
                        page.locator(f'details[data-options-category="{category}"] #{control_id}').count(),
                        1,
                    )
        finally:
            page.close()

    def test_datawaarden_blijven_compatibel_met_bestaande_voorkeuren(self):
        page = self.open_reader()
        try:
            godsnaam_values = page.locator('[data-optie="godsnaam"]').evaluate_all(
                "els => els.map(el => el.value)"
            )
            column_values = page.locator("[data-toggle-col]").evaluate_all(
                "els => els.map(el => el.dataset.toggleCol)"
            )
            self.assertEqual(
                godsnaam_values,
                ["ov", "klassiek", "jehovah", "yehovah", "jhwh", "yhwh"],
            )
            self.assertEqual(
                set(column_values),
                {
                    "1637",
                    "sv1888",
                    "2026",
                    "margin1637",
                    "marginSV1888",
                    "margin2026",
                    "hebrew",
                    "diff",
                    "noteDiff",
                },
            )
        finally:
            page.close()

    def test_vertaalkeuze_blijft_bewaard_na_herladen(self):
        page = self.open_reader()
        try:
            page.wait_for_function(
                "window.Opties && window.Opties.state && window.Opties.state.godsnaam"
            )
            page.locator("#topnav-weergave").click()
            theology = page.locator('details[data-options-category="theologie"]')
            godsnaam = theology.locator('[data-option-summary="godsnaam"]')
            godsnaam.locator(":scope > summary").click()
            klassiek = godsnaam.locator('[data-optie="godsnaam"][value="klassiek"]')
            klassiek.check()
            page.wait_for_function(
                "JSON.parse(localStorage.getItem('sv2026_vertaalopties')).godsnaam === 'klassiek'"
            )

            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "window.Opties && window.Opties.state.godsnaam === 'klassiek'"
            )
            self.assertTrue(klassiek.is_checked())
        finally:
            page.close()

    def test_godsnaam_yehovah_vervangt_de_naam_in_de_leestekst(self):
        page = self.open_reader(location="genesis/2")
        try:
            page.wait_for_function(
                "window.Opties && window.Opties.state && window.Opties.state.godsnaam"
            )
            vers = page.locator('.verse-row[data-verse="4"] .col-2026')
            vers.wait_for(state="visible", timeout=15_000)
            self.assertIn("God JAHWEH", vers.inner_text())

            page.locator("#topnav-weergave").click()
            theology = page.locator('details[data-options-category="theologie"]')
            godsnaam = theology.locator('[data-option-summary="godsnaam"]')
            godsnaam.locator(":scope > summary").click()
            godsnaam.locator('[data-optie="godsnaam"][value="yehovah"]').check()
            page.wait_for_function(
                "document.querySelector('.verse-row[data-verse=\"4\"] .col-2026')"
                ".innerText.includes('Yehováh')"
            )

            self.assertIn("God Yehováh", vers.inner_text())
            self.assertNotIn("JAHWEH", vers.inner_text())
        finally:
            page.close()

    def test_zoom_staat_in_leestekst_en_niet_meer_zwevend(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            self.assertEqual(page.locator('details[data-options-category="leestekst"] #options-zoom').count(), 1)
            self.assertEqual(page.locator("body > #ov-zoom").count(), 0)
        finally:
            page.close()

    def test_boekvolgorde_staat_bij_theologie_en_niet_in_de_boekenzijbalk(self):
        page = self.open_reader()
        try:
            self.assertEqual(page.locator("#sidebar #sb-boekvolgorde").count(), 0)
            page.locator("#topnav-weergave").click()
            keuze = page.locator('details[data-options-category="theologie"] [data-optie="boekvolgorde"]')
            self.assertEqual(keuze.count(), 1)
            self.assertEqual(keuze.get_attribute("aria-label"), "Boekvolgorde")
        finally:
            page.close()

    def test_boekenzijbalk_begint_direct_met_de_eerste_boekgroep(self):
        page = self.open_reader()
        try:
            sidebar = page.locator("#sidebar")
            eerste_groep = page.locator("#sidebar-tree .tree-group").first

            self.assertEqual(page.locator("#sidebar .sidebar-left-title").count(), 0)
            self.assertEqual(page.locator("#sidebar-search").count(), 0)
            self.assertEqual(page.locator("#book-search").count(), 0)
            self.assertLessEqual(
                eerste_groep.bounding_box()["y"] - sidebar.bounding_box()["y"],
                8,
            )

            inklappen = page.locator("#sidebar-toggle")
            self.assertTrue(inklappen.is_visible())
            inklappen.click()
            self.assertTrue(sidebar.evaluate("el => el.classList.contains('collapsed')"))
        finally:
            page.close()

    def test_boekvolgorde_in_leesvoorkeuren_wordt_bewaard(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            keuze = page.locator('details[data-options-category="theologie"] [data-optie="boekvolgorde"]')
            keuze.select_option("tenach")
            page.wait_for_function(
                "JSON.parse(localStorage.getItem('sv2026_vertaalopties')).boekvolgorde === 'tenach'"
            )
            page.reload(wait_until="domcontentloaded")
            page.locator("#topnav-weergave").wait_for(state="visible", timeout=15_000)
            page.locator("#topnav-weergave").click()
            self.assertEqual(keuze.input_value(), "tenach")
        finally:
            page.close()

    def test_mobiele_boekenpicker_opent_bij_huidig_boek_en_hoofdstuk(self):
        page = self.open_reader(width=390, height=844, location="2koningen/15")
        try:
            page.locator("#mobile-book-btn").click()
            page.locator("#mobile-picker").wait_for(state="visible", timeout=3_000)
            self.assertEqual(page.locator("#mobile-picker .mp-order").count(), 0)
            self.assertEqual(page.locator("#mobile-picker .mp-search").count(), 0)
            self.assertEqual(page.locator("#mp-title").inner_text(), "2 Koningen — kies hoofdstuk")
            self.assertEqual(page.locator("#mobile-picker .mp-item.active").inner_text(), "15")
        finally:
            page.close()

    def test_zoom_blijft_bewaard_na_herladen(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            page.locator("#options-zoom-in").click()
            page.wait_for_function("localStorage.getItem('ov_zoom') === '1.1'")
            self.assertEqual(page.locator("#options-zoom-value").inner_text(), "110%")

            page.reload(wait_until="domcontentloaded")
            page.locator("#topnav-weergave").wait_for(state="visible", timeout=15_000)
            page.locator("#topnav-weergave").click()
            self.assertEqual(page.locator("#options-zoom-value").inner_text(), "110%")
        finally:
            page.close()

    def test_alleen_getallen_vanaf_eenentwintig_kunnen_ook_in_cijfers_worden_getoond(self):
        page = self.open_reader(location="numeri/2")
        try:
            page.wait_for_function("window.Opties && window.Opties._eenheden")
            page.locator("#topnav-weergave").click()
            getallen = page.locator('[data-option-summary="getalweergave"]')
            self.assertEqual(
                getallen.locator(".option-label-with-icon > span:last-child").inner_text(),
                "Getallen",
            )
            getallen.locator(":scope > summary").click()
            cijfers = page.locator('[data-optie="getalweergave"][value="cijfers"]')
            self.assertEqual(cijfers.count(), 1)
            cijfers.check()

            voorbeelden = page.evaluate(
                """() => ({
                    klein: Opties.toonGetalcijfers('drie dagen en twintig nachten, maar een mens'),
                    grens: Opties.toonGetalcijfers('twintig en een stammen'),
                    samengesteld: Opties.toonGetalcijfers('zeven en vijftig duizend en vierhonderd'),
                    meervoud: Opties.toonGetalcijfers('met de duizenden van de hemel'),
                    html: Opties.toonGetalcijfers('<i>twaalf</i> stammen')
                })"""
            )
            self.assertNotIn('getal-cijfer', voorbeelden["klein"])
            self.assertNotIn('een <span class="getal-cijfer"', voorbeelden["klein"])
            self.assertIn('(21)</span>', voorbeelden["grens"])
            self.assertIn('(57.400)</span>', voorbeelden["samengesteld"])
            # Een meervoud als "duizenden" is geen getal (4 Ezra 13:3).
            self.assertNotIn('getal-cijfer', voorbeelden["meervoud"])
            self.assertEqual(voorbeelden["html"], '<i>twaalf</i> stammen')

            verse_acht = page.locator('.verse-row[data-verse="8"] .col-2026')
            verse_acht.wait_for(state="visible", timeout=5_000)
            self.assertIn("zeven en vijftig duizend en vierhonderd", verse_acht.inner_text())
            self.assertIn("57.400", verse_acht.inner_text())
        finally:
            page.close()

    def test_desktop_paneel_blijft_compact_bij_brede_viewports(self):
        for width in (1440, 1000):
            with self.subTest(width=width):
                page = self.open_reader(width=width, height=900)
                try:
                    page.locator("#topnav-weergave").click()
                    page.wait_for_timeout(250)
                    box = page.locator("#sidebar-right").bounding_box()
                    self.assertLessEqual(box["width"], 521)
                    self.assertLessEqual(box["width"], width - 24)
                    self.assertAlmostEqual(box["x"] + box["width"], width - 16, delta=1)
                finally:
                    page.close()

    def test_achtergrond_blijft_op_desktop_onvervaagd(self):
        page = self.open_reader(width=1280, height=900)
        try:
            page.locator("#topnav-weergave").click()
            backdrop = page.locator("#sidebar-right").evaluate(
                """el => {
                    const stijl = getComputedStyle(el, '::backdrop');
                    return {
                        achtergrond: stijl.backgroundColor,
                        vervaging: stijl.backdropFilter || stijl.webkitBackdropFilter,
                    };
                }"""
            )
            self.assertEqual(backdrop["achtergrond"], "rgba(0, 0, 0, 0)")
            self.assertEqual(backdrop["vervaging"], "none")
        finally:
            page.close()

    def test_getaloptie_herkent_de_getalvormen_uit_1_kronieken(self):
        page = self.open_reader(location="1kronieken/12")
        try:
            page.wait_for_function("window.Opties && window.Opties._eenheden")
            page.evaluate("Opties.state.getalweergave = 'cijfers'")
            voorbeelden = page.evaluate(
                """() => ({
                    zesduizend: Opties.toonGetalcijfers('zes duizend en achthonderd'),
                    twintigduizend: Opties.toonGetalcijfers('twintig duizend en achthonderd'),
                    tweehonderd: Opties.toonGetalcijfers('tweehonderd acht en tachtig'),
                    vierentwintigduizend: Opties.toonGetalcijfers('vier en twintig duizend')
                })"""
            )
            self.assertIn('(6.800)</span>', voorbeelden["zesduizend"])
            self.assertIn('(20.800)</span>', voorbeelden["twintigduizend"])
            self.assertIn('(288)</span>', voorbeelden["tweehonderd"])
            self.assertIn('(24.000)</span>', voorbeelden["vierentwintigduizend"])
        finally:
            page.close()

    def test_metrische_optie_rekent_een_dagreis_in_1_koningen_om(self):
        """Een dagreis is een afstandsmaat en mag niet als archaÃ¯sch restant blijven staan."""
        page = self.open_reader(location="1koningen/19")
        try:
            page.wait_for_function("window.Opties && window.Opties._eenheden")
            page.evaluate(
                """() => {
                    Opties.state.maatstelsel = 'metrisch';
                    App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
                }"""
            )

            vers = page.locator('.verse-row[data-verse="4"] .col-2026')
            vers.wait_for(state="visible", timeout=5_000)
            self.assertIn("dagreis", vers.inner_text())
            self.assertIn("ongeveer 35 km", vers.inner_text())
        finally:
            page.close()

    def test_metrische_optie_vult_de_elliptische_el_in_1_koningen_aan(self):
        """Een niet-herhaald 'ellen' mag de tweede afmeting niet onleesbaar laten."""
        page = self.open_reader(location="1koningen/6")
        try:
            page.wait_for_function("window.Opties && window.Opties._eenheden")
            page.evaluate(
                """() => {
                    Opties.state.maatstelsel = 'metrisch';
                    App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
                }"""
            )

            vers = page.locator('.verse-row[data-verse="2"] .col-2026')
            vers.wait_for(state="visible", timeout=5_000)
            self.assertIn("twintig (ongeveer 8,9 meter) in zijn breedte", vers.inner_text())
        finally:
            page.close()

    def test_metrische_optie_rekent_de_gemelde_maten_in_2_koningen_om(self):
        controles = [
            ("2koningen/14", "13", "meter"),
            ("2koningen/15", "19", "ton"),
            ("2koningen/18", "14", "ton"),
        ]
        for locatie, versnummer, eenheid in controles:
            with self.subTest(locatie=locatie, vers=versnummer):
                page = self.open_reader(location=locatie)
                try:
                    page.wait_for_function("window.Opties && window.Opties._eenheden")
                    page.evaluate(
                        """() => {
                            Opties.state.maatstelsel = 'metrisch';
                            App.renderChapter(Navigation.currentBook, Navigation.currentChapter);
                        }"""
                    )
                    vers = page.locator(f'.verse-row[data-verse="{versnummer}"] .col-2026')
                    vers.wait_for(state="visible", timeout=5_000)
                    self.assertIn(eenheid, vers.inner_text().lower())
                finally:
                    page.close()


    def test_desktop_paneel_is_via_de_kop_versleepbaar_en_bewaart_de_positie(self):
        page = self.open_reader(width=1280, height=900)
        try:
            page.locator("#topnav-weergave").click()
            panel = page.locator("#sidebar-right")
            header = page.locator("#sidebar-right-header")
            begin = panel.bounding_box()
            kop = header.bounding_box()

            page.mouse.move(kop["x"] + 180, kop["y"] + kop["height"] - 22)
            page.mouse.down()
            page.mouse.move(kop["x"] + 30, kop["y"] + 120, steps=8)
            page.mouse.up()

            verplaatst = panel.bounding_box()
            self.assertLess(verplaatst["x"], begin["x"] - 100)
            opgeslagen = page.evaluate(
                "JSON.parse(localStorage.getItem('ov_options_panel_position'))"
            )
            self.assertAlmostEqual(opgeslagen["x"], verplaatst["x"], delta=2)
            self.assertAlmostEqual(opgeslagen["y"], verplaatst["y"], delta=2)

            panel.locator("#sidebar-right-toggle").click()
            page.locator("#topnav-weergave").click()
            heropend = panel.bounding_box()
            self.assertAlmostEqual(heropend["x"], verplaatst["x"], delta=2)
            self.assertAlmostEqual(heropend["y"], verplaatst["y"], delta=2)
        finally:
            page.close()

    def test_desktop_sleepbeweging_blijft_binnen_de_viewport(self):
        page = self.open_reader(width=1000, height=700)
        try:
            page.locator("#topnav-weergave").click()
            panel = page.locator("#sidebar-right")
            header = page.locator("#sidebar-right-header")
            kop = header.bounding_box()

            page.mouse.move(kop["x"] + 180, kop["y"] + kop["height"] - 22)
            page.mouse.down()
            page.mouse.move(-500, -500, steps=5)
            page.mouse.up()
            linksboven = panel.bounding_box()
            self.assertGreaterEqual(linksboven["x"], 15)
            self.assertGreaterEqual(linksboven["y"], 15)

            kop = header.bounding_box()
            page.mouse.move(kop["x"] + 180, kop["y"] + kop["height"] - 22)
            page.mouse.down()
            page.mouse.move(2000, 1500, steps=5)
            page.mouse.up()
            rechtsonder = panel.bounding_box()
            self.assertLessEqual(rechtsonder["x"] + rechtsonder["width"], 985)
            self.assertLessEqual(rechtsonder["y"] + rechtsonder["height"], 685)
        finally:
            page.close()

    def test_mobiel_negeert_een_opgeslagen_desktoppositie(self):
        page = self.open_reader(width=390, height=844)
        try:
            page.evaluate(
                "localStorage.setItem('ov_options_panel_position', JSON.stringify({x: 240, y: 40}))"
            )
            self.open_mobile_options(page)
            panel = page.locator("#sidebar-right")
            panel.wait_for(state="visible", timeout=3_000)
            box = panel.bounding_box()
            self.assertAlmostEqual(box["x"], 0, delta=1)
            self.assertAlmostEqual(box["width"], 390, delta=1)
            self.assertAlmostEqual(box["y"], 211, delta=2)
        finally:
            page.close()

    def test_mobiel_paneel_gebruikt_de_beschikbare_breedte(self):
        for width in (768, 545, 390):
            with self.subTest(width=width):
                page = self.open_reader(width=width, height=844)
                try:
                    self.open_mobile_options(page)
                    page.locator("#sidebar-right").wait_for(state="visible", timeout=3_000)
                    page.wait_for_timeout(250)
                    box = page.locator("#sidebar-right").bounding_box()
                    self.assertAlmostEqual(box["x"], 0, delta=1)
                    self.assertAlmostEqual(box["width"], width, delta=1)
                finally:
                    page.close()

    def test_mobiele_darkmode_blijft_een_heldere_drie_kwart_hoge_bottom_sheet(self):
        page = self.open_reader(width=390, height=844)
        try:
            page.evaluate(
                """localStorage.setItem('sv2026_vertaalopties',
                JSON.stringify({thema: 'donker'}))"""
            )
            page.reload(wait_until="domcontentloaded")
            self.open_mobile_options(page)
            panel = page.locator("#sidebar-right")
            panel.wait_for(state="visible", timeout=3_000)
            page.wait_for_timeout(250)

            box = panel.bounding_box()
            style = panel.evaluate(
                """el => ({
                    background: getComputedStyle(el).backgroundColor,
                    radius: parseFloat(getComputedStyle(el).borderTopLeftRadius)
                })"""
            )

            self.assertAlmostEqual(box["y"], 211, delta=2)
            self.assertAlmostEqual(box["height"], 633, delta=2)
            self.assertGreater(style["radius"], 0)
            self.assertGreater(int(style["background"].split("(")[1].split(",")[0]), 230)
            self.assertEqual(page.locator("#options-title").inner_text(), "Weergave")
            self.assertEqual(page.locator(".options-preview").count(), 0)
            self.assertEqual(page.locator("details.options-category").count(), 5)
        finally:
            page.close()

    def test_desktop_darkmode_houdt_categoriekoppen_en_keuzewaarden_leesbaar(self):
        page = self.open_reader(width=1000, height=900)
        try:
            page.evaluate(
                """localStorage.setItem('sv2026_vertaalopties',
                JSON.stringify({thema: 'donker'}))"""
            )
            page.reload(wait_until="domcontentloaded")
            page.locator("#topnav-weergave").click()

            contrasten = page.locator("#sidebar-right").evaluate(
                """panel => {
                    const rgb = value => value.match(/[\\d.]+/g).slice(0, 3).map(Number);
                    const luminance = value => {
                        const channels = rgb(value).map(channel => {
                            channel /= 255;
                            return channel <= 0.04045
                                ? channel / 12.92
                                : Math.pow((channel + 0.055) / 1.055, 2.4);
                        });
                        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
                    };
                    const ratio = (voorgrond, achtergrond) => {
                        const a = luminance(voorgrond);
                        const b = luminance(achtergrond);
                        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
                    };
                    const achtergrond = getComputedStyle(panel).backgroundColor;
                    return {
                        koppen: [...panel.querySelectorAll('.options-category > summary')]
                            .map(el => ratio(getComputedStyle(el).color, achtergrond)),
                        waarden: [...panel.querySelectorAll('.option-current')]
                            .filter(el => el.getClientRects().length)
                            .map(el => ratio(getComputedStyle(el).color, achtergrond)),
                    };
                }"""
            )

            self.assertTrue(contrasten["koppen"])
            self.assertTrue(contrasten["waarden"])
            self.assertGreaterEqual(min(contrasten["koppen"]), 4.5)
            self.assertGreaterEqual(min(contrasten["waarden"]), 7)
        finally:
            page.close()

    def test_sectiekoppen_hebben_in_elk_thema_een_eigen_accentvlak(self):
        def kopstijl(theme):
            page = self.open_reader(width=1000, height=900)
            try:
                page.evaluate(
                    """theme => localStorage.setItem('sv2026_vertaalopties',
                    JSON.stringify({thema: theme}))""",
                    theme,
                )
                page.reload(wait_until="domcontentloaded")
                page.locator("#topnav-weergave").click()
                return page.locator(".options-category > summary").first.evaluate(
                    """el => {
                        const rgb = value => value.match(/[\\d.]+/g).slice(0, 3).map(Number);
                        const luminance = value => rgb(value).map(channel => {
                            channel /= 255;
                            return channel <= 0.04045
                                ? channel / 12.92
                                : Math.pow((channel + 0.055) / 1.055, 2.4);
                        }).reduce((total, channel, index) => total + channel * [0.2126, 0.7152, 0.0722][index], 0);
                        const background = getComputedStyle(el).backgroundColor;
                        const color = getComputedStyle(el).color;
                        return {
                            background,
                            color,
                            panelBackground: getComputedStyle(el.closest('#sidebar-right')).backgroundColor,
                            contrast: (Math.max(luminance(color), luminance(background)) + 0.05) /
                                (Math.min(luminance(color), luminance(background)) + 0.05),
                            width: el.getBoundingClientRect().width,
                            categoryWidth: el.parentElement.getBoundingClientRect().width
                        };
                    }"""
                )
            finally:
                page.close()

        licht = kopstijl("licht")
        donker = kopstijl("donker")
        self.assertNotEqual(licht["background"], licht["panelBackground"])
        self.assertNotEqual(donker["background"], donker["panelBackground"])
        self.assertNotEqual(licht["background"], donker["background"])
        self.assertGreaterEqual(licht["contrast"], 4.5)
        self.assertGreaterEqual(donker["contrast"], 4.5)
        self.assertAlmostEqual(licht["width"], licht["categoryWidth"], delta=2)
        self.assertAlmostEqual(donker["width"], donker["categoryWidth"], delta=2)

    def test_compacte_kop_en_eenregelige_keuzes(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            panel = page.locator("#sidebar-right")
            self.assertEqual(panel.get_attribute("aria-label"), "Weergave")
            self.assertEqual(panel.locator("#options-title").inner_text(), "Weergave")
            self.assertEqual(panel.locator(".options-preview").count(), 0)

            weergave = panel.locator('details[data-options-category="leestekst"]')
            self.assertEqual(weergave.locator('select[data-optie="thema"]').count(), 1)
            self.assertEqual(weergave.locator('input[data-optie="thema"]').count(), 0)
            self.assertEqual(weergave.locator("#toggle-lettertype-alternatief").count(), 1)

            primary_rows = weergave.locator(":scope > .options-list > :not(.option-mirror)")
            self.assertEqual(primary_rows.last.locator("#toggle-dyslexia").count(), 1)
            self.assertEqual(weergave.locator("#toggle-dyslexia").locator("xpath=ancestor::label[1]").locator("small").count(), 0)

            bronnen = panel.locator('details[data-options-category="bronnen"]')
            self.assertEqual(bronnen.locator("#toggle-strongs").locator("xpath=ancestor::label[1]").locator("small").count(), 0)
            self.assertEqual(
                bronnen.locator("#toggle-strongs").locator("xpath=ancestor::label[1]").locator(".option-status-inline").inner_text(),
                "IN BEWERKING",
            )

            most = panel.locator('details[data-options-category="meest-gebruikt"]')
            self.assertEqual(most.locator('[data-option-mirror="regelafstand"] input[type="range"]').count(), 1)
            self.assertEqual(most.locator('[data-option-mirror="teksteditie"] select').count(), 1)
        finally:
            page.close()

    def test_thema_select_heeft_een_enkele_rand_en_pijl(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            thema = page.locator('[data-options-category="meest-gebruikt"] select').filter(has=page.locator('option[value="licht"]'))
            stijl = thema.evaluate(
                """element => {
                    const css = getComputedStyle(element);
                    const shell = getComputedStyle(element.closest('.option-select-shell'));
                    return {
                        backgroundImage: css.backgroundImage,
                        borderWidth: css.borderTopWidth,
                        shellBorderWidth: shell.borderTopWidth,
                    };
                }"""
            )
            self.assertEqual(stijl["backgroundImage"], "none")
            self.assertEqual(stijl["borderWidth"], "0px")
            self.assertEqual(stijl["shellBorderWidth"], "1px")
        finally:
            page.close()

    def test_lange_keuzerij_toont_de_actuele_waarde(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            current = page.locator('[data-option-mirror="godsnaam"] .option-current')
            self.assertEqual(current.count(), 1)
            self.assertEqual(current.inner_text(), "JAHWEH / God JAHWEH")
        finally:
            page.close()

    def test_desktop_opener_heeft_een_duidelijke_toegankelijke_naam(self):
        page = self.open_reader()
        try:
            self.assertEqual(
                page.locator("#topnav-weergave").get_attribute("aria-label"),
                "Weergave openen",
            )
            self.assertEqual(
                page.locator("#topnav-weergave").evaluate(
                    "el => getComputedStyle(el).display"
                ),
                "flex",
            )
        finally:
            page.close()

    def test_escape_sluit_en_herstelt_focus_naar_de_opener(self):
        page = self.open_reader()
        try:
            opener = page.locator("#topnav-weergave")
            opener.click()
            page.keyboard.press("Escape")
            self.assertFalse(page.locator("#sidebar-right").evaluate("el => el.open"))
            self.assertEqual(page.evaluate("document.activeElement.id"), "topnav-weergave")
        finally:
            page.close()

    def test_enter_klapt_een_categorie_dicht_en_weer_open(self):
        page = self.open_reader()
        try:
            page.locator("#topnav-weergave").click()
            category = page.locator('details[data-options-category="leestekst"]')
            self.assertIsNotNone(category.get_attribute("open"))
            category.locator("summary").focus()
            page.keyboard.press("Enter")
            self.assertIsNone(category.get_attribute("open"))
            page.keyboard.press("Enter")
            self.assertIsNotNone(category.get_attribute("open"))
        finally:
            page.close()

    def test_klik_op_verduisterde_achtergrond_sluit_het_paneel(self):
        page = self.open_reader(width=1440, height=900)
        try:
            page.locator("#topnav-weergave").click()
            page.wait_for_timeout(250)
            page.mouse.click(100, 450)
            self.assertFalse(page.locator("#sidebar-right").evaluate("el => el.open"))
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
