#!/usr/bin/env python3
"""Genereer sitemap.xml voor openvertaling.nl.

Bevat: de vaste hoofdpagina's + alle per-boek handschriftenpagina's
(handschriften/<boek>.html). Draai vanuit de repo-root:  python3 scripts/build_sitemap.py
"""
import json, glob, os, datetime

BASE = "https://openvertaling.nl"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Vaste hoofdpagina's met prioriteit + wijzigingsfrequentie
MAIN = [
    ("/", "1.0", "daily"),
    ("/lees.html", "0.9", "daily"),
    ("/lexicon-viewer.html", "0.8", "weekly"),
    ("/onderwerpen.html", "0.7", "weekly"),
    ("/kaart.html", "0.6", "monthly"),
    ("/grondteksten.html", "0.7", "monthly"),
    ("/handschriften.html", "0.7", "weekly"),
    ("/over-ov.html", "0.6", "monthly"),
    ("/bronnen.html", "0.5", "monthly"),
    ("/uitgangspunten.html", "0.5", "monthly"),
    ("/principes.html", "0.5", "monthly"),
    ("/geografie.html", "0.5", "monthly"),
    ("/materialen.html", "0.5", "monthly"),
    ("/dieren.html", "0.5", "monthly"),
    ("/bomen-planten.html", "0.5", "monthly"),
    ("/personen.html", "0.5", "monthly"),
    ("/muziekinstrumenten.html", "0.5", "monthly"),
    ("/statistieken.html", "0.5", "weekly"),
    ("/changelog.html", "0.5", "weekly"),
    ("/lexicon.html", "0.4", "monthly"),
    ("/voor-ai.html", "0.5", "monthly"),
    ("/handschriften-henoch.html", "0.4", "monthly"),
    ("/over-ov.html#over-ons", "0.3", "yearly"),
    ("/woordenboeken.html", "0.5", "monthly"),
]

def main():
    today = datetime.date.today().isoformat()
    urls = []
    for loc, prio, freq in MAIN:
        p = loc.lstrip("/")
        if loc == "/" or os.path.exists(os.path.join(ROOT, p)):
            urls.append((BASE + loc, prio, freq))
    # Per-boek handschriftenpagina's
    for f in sorted(glob.glob(os.path.join(ROOT, "handschriften", "*.html"))):
        name = os.path.basename(f)
        urls.append((f"{BASE}/handschriften/{name}", "0.6", "monthly"))
    # Leespagina's (scripts/build_leespaginas.py bouwt ze bij de uitrol uit de data)
    urls.append((f"{BASE}/bijbel/", "0.9", "weekly"))
    with open(os.path.join(ROOT, "data", "books-index.json"), encoding="utf-8") as fh:
        boeken = json.load(fh)["boeken"]
    for boek in boeken:
        urls.append((f"{BASE}/bijbel/{boek['id']}/", "0.7", "weekly"))
        eerste = boek.get("eerste_hoofdstuk", 1)
        for nummer in range(eerste, eerste + boek["hoofdstukken"]):
            urls.append((f"{BASE}/bijbel/{boek['id']}/{nummer}.html", "0.8", "weekly"))

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, prio, freq in urls:
        out.append("  <url>")
        out.append(f"    <loc>{loc}</loc>")
        out.append(f"    <lastmod>{today}</lastmod>")
        out.append(f"    <changefreq>{freq}</changefreq>")
        out.append(f"    <priority>{prio}</priority>")
        out.append("  </url>")
    out.append("</urlset>")
    # newline="\n": ook op Windows LF, zoals de rest van de repo
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"sitemap.xml geschreven: {len(urls)} URL's ({len(urls)-len([u for u in urls if '/handschriften/' not in u[0]])} boekpagina's)")

if __name__ == "__main__":
    main()
