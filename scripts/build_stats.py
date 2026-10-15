#!/usr/bin/env python3
"""Genereer data/stats.json — de ENIGE bron voor alle aantallen op de site.

Draai dit na elke inhoudelijke wijziging (nieuwe nagelezen boeken, principes,
diffs). Alle pagina's lezen via js/stats-inject.js uit data/stats.json, zodat
er nooit verschillende aantallen op verschillende pagina's staan.

Gebruik:  python3 scripts/build_stats.py [versie] [datum]
"""
import json, os, re, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
SKIP = {'speech-v2', 'speech', 'audio', 'tts'}

def parse_verified():
    """Releasesnapshot uit export_review_status.py; nooit handmatig bijwerken."""
    pad = os.path.join(DATA, 'verified-chapters.json')
    with open(pad, encoding='utf-8') as fh:
        return json.load(fh)


def default_release_metadata():
    """Lees de versie en datum van de actuele uitgave."""
    pad = os.path.join(DATA, 'release.json')
    with open(pad, encoding='utf-8') as fh:
        release = json.load(fh)
    dag = datetime.date.fromisoformat(release['datum'])
    maanden = ('', 'januari', 'februari', 'maart', 'april', 'mei', 'juni',
               'juli', 'augustus', 'september', 'oktober', 'november', 'december')
    return release['versie'], f'{dag.day} {maanden[dag.month]} {dag.year}'


def schrijf_vaste_waarden(stats):
    """Zet de aantallen die in de HTML zelf staan gelijk aan stats.json.

    js/stats-inject.js vult ze bij het laden, maar wat er in het bestand staat
    is wat je ziet zolang dat script nog niet gedraaid heeft -- en wat je ziet
    als het misgaat of als de service worker een oude versie serveert. Op de
    changelogpagina stond zo maandenlang 11.175 van de 37.235 verzen met een
    verwachte afronding in januari 2027, terwijl de echte stand allang hoger
    lag. Nu schrijft deze build ze mee, met dezelfde opmaak als de injector.
    """
    def nl(n):
        if not isinstance(n, (int, float)):
            return str(n)
        if isinstance(n, float):
            heel, rest = str(n).split('.')
            return '{:,}'.format(int(heel)).replace(',', '.') + ',' + rest
        return '{:,}'.format(n).replace(',', '.')

    patroon = re.compile(r'(<span data-stat="([a-z_]+)"((?:(?!</span>)[^<])*)>)'
                         r'((?:(?!</span>).)*)(</span>)')

    def een(m):
        sleutel, attrs = m.group(2), m.group(3)
        if sleutel not in stats:
            return m.group(0)
        w = str(stats[sleutel]) if 'data-stat-format="raw"' in attrs else nl(stats[sleutel])
        suffix = re.search(r'data-stat-suffix="([^"]*)"', attrs)
        if suffix:
            w += suffix.group(1)
        return m.group(1) + w + m.group(5)

    for naam in sorted(os.listdir(ROOT)):
        if not naam.endswith('.html'):
            continue
        pad = os.path.join(ROOT, naam)
        with open(pad, encoding='utf-8', newline='') as fh:
            ruw = fh.read()
        if 'data-stat=' not in ruw:
            continue
        nieuw = patroon.sub(een, ruw)
        if nieuw != ruw:
            with open(pad, 'w', encoding='utf-8', newline='') as fh:
                fh.write(nieuw)
            print('bijgewerkt: ' + naam)


def main():
    standaardversie, standaarddatum = default_release_metadata()
    version = sys.argv[1] if len(sys.argv) > 1 else standaardversie
    datum = sys.argv[2] if len(sys.argv) > 2 else standaarddatum

    books = json.load(open(os.path.join(DATA, 'books.json'), encoding='utf-8'))['books']
    verified = parse_verified()

    ch_total = verses_total = ch_ver = verses_ver = books_full = diff_total = diff_via_principe = 0
    verified_books = []   # weergavelabels van (deels) nagekeken boeken, in canonieke volgorde
    by_test = {'OT': [0, 0], 'NT': [0, 0], 'AP': [0, 0]}   # testament -> [verzen_totaal, verzen_nagekeken]
    for b in books:
        if b.get('ethiopic'):
            continue   # Ethiopische stub-boeken tellen niet mee in de statistieken (nog geen tekst)
        bid = b['id']; chs = b.get('chaptersIncluded', [])
        test = b.get('testament')
        # De kopcijfers en de nakijksnelheid gaan over de 66 canonieke boeken.
        # De apocriefe boeken staan in het corpus en houden hun eigen regel in
        # by_test, maar tellen niet mee in totalen, percentages en einddatum.
        canoniek = test in ('OT', 'NT')
        if canoniek:
            ch_total += len(chs)
        v = verified.get(bid, [])
        full = len(chs) > 0 and len(v) >= len(chs)
        if full and canoniek:
            books_full += 1
            verified_books.append(b['nameDutch'])
        elif canoniek and len(v) > 0:
            # gedeeltelijk nagekeken → naam + hoofdstukbereik (bv. "Genesis 1–20")
            verified_books.append(f"{b['nameDutch']} {min(v)}–{max(v)}")
        for ch in chs:
            fp = os.path.join(DATA, bid, f'{ch}.json')
            if not os.path.exists(fp):
                continue
            d = json.load(open(fp, encoding='utf-8'))
            vs = [x for x in d.get('verses', []) if isinstance(x, dict)]
            if canoniek:
                verses_total += len(vs)
            if test in by_test:
                by_test[test][0] += len(vs)
            verified_ch = ch in v
            if verified_ch:
                if canoniek:
                    ch_ver += 1; verses_ver += len(vs)
                if test in by_test:
                    by_test[test][1] += len(vs)
            if not canoniek:
                continue
            for x in vs:
                pds = x.get('phraseDiff') or []
                # Tel het AANTAL GEWIJZIGDE WOORDEN t.o.v. SV1888 (niet het aantal
                # diff-segmenten): per segment het maximum van oud/nieuw aantal woorden.
                for pd in pds:
                    nw = max(len(str(pd.get('old', '')).split()),
                             len(str(pd.get('new', '')).split())) or 1
                    diff_total += nw
                    if pd.get('principe'):
                        diff_via_principe += nw

    principes = len(json.load(open(os.path.join(DATA, 'wijzigingsprincipes.json'), encoding='utf-8'))['principes'])

    def pct(a, b):
        return round(100 * a / b, 1) if b else 0

    stats = {
        'version': version,
        'date': datum,
        'books_total': len([b for b in books
                            if not b.get('ethiopic') and b.get('testament') in ('OT', 'NT')]),
        'books_verified': books_full,
        'chapters_total': ch_total,
        'chapters_verified': ch_ver,
        'chapters_verified_pct': pct(ch_ver, ch_total),
        'verses_total': verses_total,
        'verses_verified': verses_ver,
        'verses_verified_pct': pct(verses_ver, verses_total),
        'principes': principes,
        'text_changes': diff_total,
        'changes_via_principe': diff_via_principe,
        'changes_via_principe_pct': pct(diff_via_principe, diff_total),
        'changes_los': diff_total - diff_via_principe,
        'verified_books': verified_books,
        'ot_verses_total': by_test['OT'][0],
        'ot_verses_verified': by_test['OT'][1],
        'ot_verses_verified_pct': pct(by_test['OT'][1], by_test['OT'][0]),
        'nt_verses_total': by_test['NT'][0],
        'nt_verses_verified': by_test['NT'][1],
        'nt_verses_verified_pct': pct(by_test['NT'][1], by_test['NT'][0]),
        'ap_verses_total': by_test['AP'][0],
        'ap_verses_verified': by_test['AP'][1],
        'ap_verses_verified_pct': pct(by_test['AP'][1], by_test['AP'][0]),
        # verses_total gaat over de 66 canonieke boeken. Wie het volledige
        # corpus nodig heeft — zoals de naslagbouw, die ook de apocriefen
        # indexeert — telt hier de drie testamenten samen.
        'corpus_verses_total': sum(v[0] for v in by_test.values()),
        'corpus_verses_verified': sum(v[1] for v in by_test.values()),
    }

    # === Nakijksnelheid + verwachte einddatum (zelf-bijwerkend) ===
    # data/review-history.json wordt door het reviewproces bijgehouden. Deze build
    # leest het bestand uitsluitend; releasebouw mag de reviewhistorie niet wijzigen.
    NL_M = ['', 'januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli',
            'augustus', 'september', 'oktober', 'november', 'december']
    hist_fp = os.path.join(DATA, 'review-history.json')
    try:
        hist = json.load(open(hist_fp, encoding='utf-8'))
    except Exception:
        hist = {}
    today = datetime.date.today()
    pts = sorted((datetime.date.fromisoformat(d), v) for d, v in hist.items())
    if not pts or pts[-1][0] != today:
        pts.append((today, verses_ver))
    elif pts[-1][1] != verses_ver:
        pts[-1] = (today, verses_ver)
    if len(pts) >= 2:
        x0 = pts[0][0].toordinal()
        xs = [p[0].toordinal() - x0 for p in pts]
        ys = [p[1] for p in pts]
        n = len(xs); sx = sum(xs); sy = sum(ys)
        sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
        denom = n * sxx - sx * sx
        slope = (n * sxy - sx * sy) / denom if denom else 0.0   # verzen/dag
        remaining = verses_total - verses_ver
        # Een lagere actuele stand betekent dat eerder foutief toegekende
        # reviewstatus is gecorrigeerd. Toon dan geen misleidende snelheid/ETA.
        corrected_downward = verses_ver < max(ys[:-1], default=0)
        if corrected_downward:
            slope = 0.0
        stats['review_verses_per_day'] = round(slope, 1)
        stats['review_verses_per_week'] = round(slope * 7)
        stats['review_remaining_verses'] = remaining
        stats['review_since'] = f"{pts[0][0].day} {NL_M[pts[0][0].month]} {pts[0][0].year}"
        if slope > 0:
            eta = today + datetime.timedelta(days=remaining / slope)
            stats['review_eta'] = f"{eta.day} {NL_M[eta.month]} {eta.year}"
            stats['review_eta_month'] = f"{NL_M[eta.month]} {eta.year}"
        else:
            stats['review_eta'] = stats['review_eta_month'] = 'onbekend'

    schrijf_vaste_waarden(stats)

    out = os.path.join(DATA, 'stats.json')
    json.dump(stats, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(out, 'a', encoding='utf-8').write('\n')
    print('stats.json geschreven:')
    print(json.dumps(stats, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
