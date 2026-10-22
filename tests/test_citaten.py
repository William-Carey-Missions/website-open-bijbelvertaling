"""Bewijsteksten laden licht, en ook vanaf een andere site.

Open Gods Woord haalt zijn bewijsteksten via embed.js van openvertaling.nl. Een
fetch naar een andere site lukt alleen als die CORS toestaat, en dat doet
openvertaling.nl niet: zo bleef in oktober 2026 elke bewijstekst op Open Gods
Woord op "…" staan, zonder foutmelding. Lokaal viel dat nooit op, omdat alle
sites daar op 127.0.0.1 draaien en embed.js dan de eigen site neemt.

Deze tests draaien daarom twee servers op verschillende poorten — twee origins,
net als de twee domeinen live — en laten een pagina op de ene de tekst van de
andere halen. Python's http.server stuurt net als de productieserver geen
CORS-kop mee.
"""

import contextlib
import http.server
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_citaten  # noqa: E402

BOEKEN = {"genesis", "johannes"}


def lees_citaat(pad):
    """De data uit een citaatbestand: alles tussen de sleutel en de afsluiting."""
    tekst = pad.read_text(encoding="utf-8")
    kop, _, rest = tekst.partition(",")
    assert kop.startswith("OSV._ontvang("), kop
    assert rest.endswith(");\n"), rest[-20:]
    return json.loads(kop[len("OSV._ontvang("):]), json.loads(rest[:-3])


class BouwTests(unittest.TestCase):
    """Het bouwscript schrijft dezelfde tekst, alleen zonder de rest."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.uit = Path(cls.tmp.name)
        build_citaten.bouw(ROOT / "data", cls.uit, alleen=BOEKEN)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_elk_vers_draagt_de_tekst_van_de_bron(self):
        for boek in sorted(BOEKEN):
            for bron in sorted((ROOT / "data" / boek).glob("*.json")):
                if not bron.stem.isdigit():
                    continue
                with self.subTest(hoofdstuk=f"{boek} {bron.stem}"):
                    sleutel, citaat = lees_citaat(self.uit / boek / f"{bron.stem}.js")
                    self.assertEqual(sleutel, f"{boek}/{bron.stem}")
                    verzen = json.loads(bron.read_text(encoding="utf-8"))["verses"]
                    self.assertEqual(
                        citaat["verzen"],
                        [[v["number"], v.get("text2026_html") or v.get("text2026") or "", v.get("text2026") or ""]
                         for v in verzen],
                    )
                    self.assertEqual(citaat["woorden"], any(v.get("woordnummers") for v in verzen))

    def test_een_citaat_weegt_een_fractie_van_het_hoofdstuk(self):
        bron = (ROOT / "data" / "genesis" / "1.json").stat().st_size
        citaat = (self.uit / "genesis" / "1.js").stat().st_size
        self.assertLess(citaat, bron * 0.1, f"{citaat} B tegen {bron} B")

    def test_de_woordnummers_staan_apart(self):
        verzen = json.loads((ROOT / "data" / "genesis" / "1.json").read_text(encoding="utf-8"))["verses"]
        if not any(v.get("woordnummers") for v in verzen):
            self.skipTest("Genesis 1 heeft geen woordnummers")
        sleutel, woorden = lees_citaat(self.uit / "genesis" / "1.woorden.js")
        self.assertEqual(sleutel, "genesis/1#woorden")
        self.assertEqual(woorden["1"], verzen[0]["woordnummers"])

    def test_de_boekenlijst_is_compleet(self):
        sleutel, boeken = lees_citaat(self.uit / "boeken.js")
        bron = json.loads((ROOT / "data" / "books.json").read_text(encoding="utf-8"))["books"]
        self.assertEqual(sleutel, "boeken")
        self.assertEqual(set(boeken), {b["id"] for b in bron})
        self.assertEqual(boeken["genesis"], {"naam": "Genesis", "testament": "OT"})


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Dient de repo, met de citaatbestanden uit een tijdelijke map.

    Zonder citaatmap geeft /data/citaat/ een 404, zoals lokaal zonder bouwstap.
    /proef.html is een minimale pagina die embed.js van de bronsite insluit.
    """

    def log_message(self, _format, *_args):
        pass

    def translate_path(self, path):
        citaten = self.server.citaten
        schoon = path.split("?", 1)[0].split("#", 1)[0]
        if schoon.startswith("/data/citaat/"):
            if citaten is None:
                return str(ROOT / "bestaat-niet")
            return str(Path(citaten) / schoon[len("/data/citaat/"):])
        return super().translate_path(path)

    def do_GET(self):
        schoon = self.path.split("?", 1)[0]
        if self.server.html_bij_ontbreken and schoon.startswith("/data/citaat/") \
                and not Path(self.translate_path(self.path)).is_file():
            # Zo antwoordt de productieserver op een bestand dat er niet is:
            # status 200 met de HTML van de startpagina.
            inhoud = b"<!DOCTYPE html><html><head><title>Open Vertaling</title></head></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(inhoud)))
            self.end_headers()
            self.wfile.write(inhoud)
            return
        if schoon == "/proef.html":
            bron = self.server.bron_url
            base = f' data-base="{bron}"' if bron else ""
            inhoud = (f'<!doctype html><meta charset="utf-8"><title>proef</title>'
                      f'<script src="{bron or ""}/embed.js"{base}></script>').encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(inhoud)))
            self.end_headers()
            self.wfile.write(inhoud)
            return
        super().do_GET()


class _Server(http.server.ThreadingHTTPServer):
    def __init__(self, citaten=None, html_bij_ontbreken=False):
        super().__init__(("127.0.0.1", 0), lambda *a, **k: _Handler(*a, directory=str(ROOT), **k))
        self.citaten = citaten
        self.html_bij_ontbreken = html_bij_ontbreken
        self.bron_url = None
        self.draad = threading.Thread(target=self.serve_forever, daemon=True)
        self.draad.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"

    def handle_error(self, _request, _client_address):
        pass

    def stop(self):
        self.shutdown()
        self.server_close()
        self.draad.join(timeout=2)


class OverDeGrensTests(unittest.TestCase):
    """Browserverificatie: een pagina op site A haalt tekst van site B."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        build_citaten.bouw(ROOT / "data", Path(cls.tmp.name), alleen=BOEKEN)
        cls.bron_met = _Server(citaten=cls.tmp.name)    # openvertaling.nl na de uitrol
        cls.bron_zonder = _Server(citaten=None)         # openvertaling.nl vóór de uitrol
        cls.bron_html = _Server(citaten=cls.tmp.name, html_bij_ontbreken=True)
        cls.pagina = _Server()                          # opengodsword.com

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

    @classmethod
    def tearDownClass(cls):
        with contextlib.suppress(Exception):
            cls.browser.close()
        with contextlib.suppress(Exception):
            cls.playwright.stop()
        for server in (cls.bron_met, cls.bron_zonder, cls.bron_html, cls.pagina):
            server.stop()
        cls.tmp.cleanup()

    def citeer(self, pagina_server, bron_server, ref, opties=None):
        """Open de proefpagina en citeer; geeft (uitkomst, opgevraagde paden)."""
        pagina_server.bron_url = bron_server.url if bron_server is not pagina_server else None
        page = self.browser.new_page()
        verzoeken = []
        page.on("request", lambda req: verzoeken.append(req.url))
        try:
            page.goto(f"{pagina_server.url}/proef.html", wait_until="load")
            # Een uitdrukking die een functie oplevert, roept Playwright zelf aan.
            page.wait_for_function("typeof window.OSV === 'object' && typeof OSV.cite === 'function'")
            uitkomst = page.evaluate(
                """async ([ref, opties]) => {
                    try {
                        const r = await OSV.cite(ref, opties);
                        return { html: r.html, label: r.label, base: OSV.base };
                    } catch (e) {
                        return { fout: String(e && e.message || e), base: OSV.base };
                    }
                }""",
                [ref, opties or {"link": False}],
            )
        finally:
            page.close()
        bron = bron_server.url
        return uitkomst, [u[len(bron):] for u in verzoeken if u.startswith(bron)]

    def test_de_bewijstekst_komt_van_de_andere_site(self):
        uitkomst, paden = self.citeer(self.pagina, self.bron_met, "genesis 1:1")
        self.assertNotIn("fout", uitkomst, uitkomst)
        self.assertEqual(uitkomst["base"], self.bron_met.url)
        self.assertIn("In", uitkomst["html"])
        self.assertIn("het begin", uitkomst["html"])
        self.assertEqual(uitkomst["label"], "Genesis 1:1")
        self.assertIn("/data/citaat/genesis/1.js", paden)
        # Het zware hoofdstukbestand blijft onaangeroerd.
        self.assertNotIn("/data/genesis/1.json", paden)
        # Zonder Strong blijven ook de woordnummers weg.
        self.assertFalse([p for p in paden if p.endswith(".woorden.js")], paden)

    def test_een_reeks_verzen_komt_uit_een_bestand(self):
        uitkomst, paden = self.citeer(self.pagina, self.bron_met, "johannes 3:16-18")
        self.assertNotIn("fout", uitkomst, uitkomst)
        self.assertEqual(uitkomst["html"].count('class="osv-vers"'), 3)
        self.assertEqual(paden.count("/data/citaat/johannes/3.js"), 1)

    def test_met_strong_komen_de_woordnummers_er_apart_bij(self):
        uitkomst, paden = self.citeer(
            self.pagina, self.bron_met, "genesis 1:1", {"link": False, "strongs": True}
        )
        self.assertNotIn("fout", uitkomst, uitkomst)
        self.assertIn("/data/citaat/genesis/1.woorden.js", paden)
        self.assertNotIn("/data/genesis/1.json", paden)

    def test_een_json_over_de_grens_faalt_zoals_live(self):
        """Zonder citaatbestanden valt embed.js terug op de JSON — en die
        weigert de browser van een andere site. Zo zag de storing er live uit;
        slaagt deze test niet, dan bootst de opzet de productie niet na."""
        uitkomst, _ = self.citeer(self.pagina, self.bron_zonder, "genesis 1:1")
        self.assertIn("fout", uitkomst, uitkomst)

    # De productieserver beantwoordt een bestand dat er niet is met een
    # HTML-pagina en status 200, niet met een 404.

    def test_een_ontbrekend_bestand_over_de_grens_geeft_snel_op(self):
        """Over de grens blokkeert de browser HTML als script; het citaat moet
        dan opgeven in plaats van eeuwig '…' te tonen."""
        begin = time.monotonic()
        uitkomst, paden = self.citeer(self.pagina, self.bron_html, "psalmen 23:1")
        self.assertIn("fout", uitkomst, uitkomst)
        self.assertLess(time.monotonic() - begin, 10)
        self.assertIn("/data/citaat/psalmen/23.js", paden)
        # Een gebouwd boek op dezelfde server werkt gewoon.
        uitkomst, _ = self.citeer(self.pagina, self.bron_html, "genesis 1:1")
        self.assertNotIn("fout", uitkomst, uitkomst)

    def test_een_ontbrekend_bestand_op_de_eigen_site_valt_terug_op_json(self):
        """Op de eigen site voert de browser die HTML wél uit als script: het
        laadt, maar meldt zich nooit aan. Dan hoort embed.js door te gaan naar
        de JSON van het hoofdstuk, die hier gewoon bereikbaar is."""
        uitkomst, paden = self.citeer(self.bron_html, self.bron_html, "psalmen 23:1")
        self.assertNotIn("fout", uitkomst, uitkomst)
        self.assertEqual(uitkomst["base"], "")
        self.assertIn("/data/citaat/psalmen/23.js", paden)
        self.assertIn("/data/psalmen/23.json", paden)

    def test_op_de_eigen_site_werkt_de_json_nog_als_terugval(self):
        """Lokaal, zonder bouwstap, blijft de lezer gewoon citeren."""
        uitkomst, paden = self.citeer(self.bron_zonder, self.bron_zonder, "genesis 1:1")
        self.assertNotIn("fout", uitkomst, uitkomst)
        self.assertEqual(uitkomst["base"], "")
        self.assertIn("het begin", uitkomst["html"])
        self.assertIn("/data/genesis/1.json", paden)


if __name__ == "__main__":
    unittest.main()
