#!/usr/bin/env python3
"""Leg de openbare Gospelimages-catalogus en ongewijzigde afbeeldingen vast."""
import concurrent.futures
import hashlib
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://www.gospelimages.nl'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'OpenVertaling/illustratie-import'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def plain(s):
    return html.unescape(re.sub('<[^>]+>', '', s)).strip()

def main():
    source = get(BASE + '/schilderijen').decode()
    cards = re.findall(r'<a\b[^>]*class="painting-card__overlay-link[^>]*>(.*?)</a>', source, re.S)
    anchors = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*class="painting-card__overlay-link', source)
    if len(cards) != len(anchors) or not cards:
        raise ValueError('Catalogus niet volledig herkend')
    out = ROOT / 'images/gospelimages/reeks'; out.mkdir(parents=True, exist_ok=True)
    def download(pair):
        url, card = pair
        url = html.unescape(url).rstrip('?')
        ident = int(re.search(r'/schilderijen/(\d+)/',url)[1])
        title = plain(re.search(r'painting-card__title[^>]*>(.*?)</h3>',card,re.S)[1])
        ref = plain(re.search(r'painting-card__indexation[^>]*>(.*?)</span>',card,re.S)[1])
        img = html.unescape(re.search(r'<img[^>]*\bsrc="([^"]+)"',card)[1])
        img = img if img.startswith('http') else BASE + img
        dest = out / f'{ident}.jpg'
        if not dest.is_file():dest.write_bytes(get(img))
        data=dest.read_bytes()
        return {'id':ident,'titel':title,'verwijzing':ref,'bron':url,'afbeelding_bron':img,
                'bestand':dest.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),
                'maker':"Jan van ’t Hoff",'voorwaarden':['Naamsvermelding','Niet commercieel','Geen afgeleide werken']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        paintings=list(pool.map(download,zip(anchors,cards)))
    if len({p['id'] for p in paintings}) != len(paintings):raise ValueError('Dubbele catalogus-ID')
    manifest={'bron':BASE+'/schilderijen','maker':"Jan van ’t Hoff",'afbeeldingen':sorted(paintings,key=lambda p:p['id'])}
    (ROOT/'data/gospelimages.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(paintings)} afbeeldingen vastgelegd',flush=True)
if __name__=='__main__':main()
