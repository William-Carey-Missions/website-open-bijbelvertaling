"""Bouw een sitemap van de openbare lees- en downloadpagina's."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://openvertaling.nl/"
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

def main():
    ET.register_namespace("", NS)
    sitemap = ET.Element("{" + NS + "}urlset")
    urls = {"", "downloads.html", "over-ov.html"}
    for file in (ROOT / "bijbel").rglob("*.html"):
        route = file.relative_to(ROOT).as_posix()
        urls.add(route[:-10] if route.endswith("index.html") else route)
    for route in sorted(urls):
        entry = ET.SubElement(sitemap, "{" + NS + "}url")
        ET.SubElement(entry, "{" + NS + "}loc").text = BASE + route
    ET.ElementTree(sitemap).write(ROOT / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    print(f"Sitemap: {len(urls)} openbare pagina's")

if __name__ == "__main__":
    main()
