#!/usr/bin/env python3
"""Pas een expliciet nagekeken aanvullingsplan toe; standaard alleen controleren.

python3 scripts/pas_strongs_aanvullingen_toe.py plan.json [--write]
Bestaande koppelingen blijven behouden; tekst en grondtekst worden niet gewijzigd.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from strongs_nalopen import laad, bewaar, indices, plekken, platte_tekst, LOG


def prepare(plan):
    cache, additions = {}, defaultdict(list)
    for item in plan:
        book, chapter, verse = item['ref'].split('/')
        key = (book, int(chapter))
        if key not in cache:
            cache[key] = laad(*key)
        v = next(v for v in cache[key][1]['verses'] if str(v['number']) == verse)
        source_hash = hashlib.sha256(json.dumps(v['grondtekst'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if source_hash != item['grondtekst_sha256'] or platte_tekst(v) != item['vers_tekst']:
            raise ValueError(f"Gewijzigde bron of tekst: {item['ref']}")
        i = item['grondindex']
        source = v['grondtekst'][i]
        if (source['strongs'], source['woord']) != (item['strongs'], item['grondwoord']):
            raise ValueError(f"Afwijkend grondwoord: {item['ref']}")
        if not isinstance(item['voorkomen'], int) or not 1 <= item['voorkomen'] <= len(plekken(platte_tekst(v), item['tekst'])):
            raise ValueError(f"Onvindbaar anker: {item['ref']}")
        if any(m.get('herkomst', {}).get('aanvullingsplan') == '2026-11-07'
               and m['herkomst'].get('grondindices') == [i]
               and (m.get('tekst'), m.get('voorkomen')) == (item['tekst'], item['voorkomen'])
               for m in v.get('woordnummers', [])):
            continue
        if i in {i for group in indices(v) for i in group}:
            raise ValueError(f"Grondwoord al gekoppeld: {item['ref']} #{i}")
        record = {'tekst': item['tekst'], 'voorkomen': item['voorkomen'],
                  'strongs': [source['strongs']], 'bronwoorden': [source['woord']],
                  'transliteraties': [source.get('transliteratie', '')],
                  'glossen': [source.get('gloss') or source.get('betekenis') or ''],
                  'status': 'uitgelijnd', 'confidence': 0.9,
                  'reviewstatus': 'automatisch_hoog_vertrouwen',
                  'herkomst': {'dataset': 'lokale-grondtekst', 'versie': '1',
                               'sha256': source_hash, 'referentie': item['ref'],
                               'grondindices': [i], 'bronindices': [i],
                               'aanvullingsplan': '2026-11-07'}}
        if source.get('morfologie') or source.get('morph'):
            record['morfologie'] = [source.get('morfologie') or source['morph']]
        v.setdefault('woordnummers', []).append(record)
        additions[book].append({'ref': item['ref'], 'toegevoegd': record,
                                'reden': item['reden'], 'datum': '2026-11-07'})
    return cache, additions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    cache, additions = prepare(json.loads(args.plan.read_text()))
    if args.write:
        changed = {(b, int(x['ref'].split('/')[1])) for b, items in additions.items() for x in items}
        for key in changed:
            bewaar(*cache[key])
        for book, items in additions.items():
            with (LOG / f'{book}.jsonl').open('a', encoding='utf-8') as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"{'Toegevoegd' if args.write else 'Voorbereid'}: {sum(map(len, additions.values()))}")


if __name__ == '__main__':
    main()
