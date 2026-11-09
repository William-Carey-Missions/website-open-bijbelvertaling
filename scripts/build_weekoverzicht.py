"""Bouw het inhoudelijke weekoverzicht uit data/weekoverzicht-2026.json.
Werk bij een volgende inhoudelijke publicatie de weekpunten en hun bronnen bij;
noem geen voortgangspercentage zonder een afgebakende, gecontroleerde telling.
"""
import html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MONTHS=['','januari','februari','maart','april','mei','juni','juli','augustus','september','oktober','november','december']
def date(s):
 y,m,d=map(int,s.split('-'));return f'{d} {MONTHS[m]}'
def build(data):
 esc=html.escape;sections=[]
 for i,w in enumerate(data['weken']):
  body='<ul>'+''.join('<li>'+esc(p)+'</li>' for p in w['punten'])+'</ul>' if w['punten'] else '<p class="stil">Geen inhoudelijke wijziging teruggevonden in de beschikbare projectgeschiedenis.</p>'
  sections.append(f'<details id="week-{w["week"]}"'+(' open' if i==0 else '')+f'><summary><strong>Week {w["week"]}</strong><span>{date(w["van"])} – {date(w["tot"])}</span></summary>{body}</details>')
 site=esc(data['site']);links=' · '.join(f'<a href="https://{domain}/changelog.html">{label}</a>' for domain,label in [('openvertaling.nl','Open Vertaling'),('open-parafrase-weergave.nl','Open Parafrase'),('opengodsword.com','Open Gods Word')])
 return f'''<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<script src="/js/theme.js"></script><title>Wijzigingen per week · {site}</title>
<meta name="description" content="De inhoudelijke verbeteringen in {site}, per week vanaf januari 2026.">
<link rel="canonical" href="https://{data['domein']}/changelog.html"><link rel="icon" href="/favicon.svg">
<style>
:root{{color-scheme:light;--bg:#f8f7f3;--paper:#fff;--ink:#233d4b;--muted:#53616a;--line:#d9dfdf;--accent:#075c63}}
:root[data-theme="donker"]{{color-scheme:dark;--bg:#142530;--paper:#1b303c;--ink:#f0eee6;--muted:#c2cbd0;--line:#405560;--accent:#93d5cd}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:18px/1.65 system-ui,sans-serif}}a{{color:var(--accent);text-underline-offset:3px}}header,main,footer{{max-width:860px;margin:auto;padding:24px}}header{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line)}}header a{{font-size:15px}}h1{{font:700 clamp(30px,6vw,44px)/1.2 Georgia,serif;margin:12px 0 22px}}.kicker{{font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}}.intro{{max-width:68ch}}.status{{border-left:3px solid var(--accent);padding:10px 18px;margin:28px 0;background:var(--paper)}}.stil,footer{{font-size:15px;color:var(--muted)}}details{{border:1px solid var(--line);border-radius:8px;background:var(--paper);margin:12px 0;padding:0 20px}}summary{{cursor:pointer;padding:18px 0}}summary span{{display:block;font-size:15px;color:var(--muted);margin-left:20px}}li{{margin:12px 0}}ul{{padding-left:22px}}details p{{padding-bottom:12px}}footer{{border-top:1px solid var(--line);margin-top:28px;padding-bottom:48px}}@media(max-width:480px){{header,main,footer{{padding:18px}}details{{padding:0 14px}}}}
</style></head><body><header><a href="/">{site}</a><a href="https://opengodsword.com/wiki.html#principes">Bekijk de principes</a></header>
<main><p class="kicker">Weekoverzicht · {data['jaar']}</p><h1>Wat is er verbeterd?</h1><p class="intro">{esc(data['toelichting'])}</p>
<p class="stil">Bijgewerkt op {date(data['bijgewerkt'])} 2026.</p><div class="status">{esc(data['controle'])}</div>
{''.join(sections)}</main><footer><p>De weekoverzichten van de drie sites:</p><p>{links}</p></footer></body></html>'''
if __name__=='__main__':
 data=json.loads((ROOT/'data/weekoverzicht-2026.json').read_text());(ROOT/'changelog.html').write_text(build(data)+'\n');print(data['site'],len(data['weken']),'weken')
