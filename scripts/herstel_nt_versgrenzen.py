#!/usr/bin/env python3
"""Herstel vijf beoordeelde NT-versgrenzen met tekst- en bronhashcontrole."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from strongs_nalopen import laad, bewaar, indices, norm, plekken, platte_tekst, ROOT

PLAN = ROOT / 'reviews/strongs/plannen/nt-versgrenzen-2026-11-07.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def prepare(plan):
    chapters, verses = {}, {}
    for ref in plan['verzen']:
        b, c, n = ref.split('/')
        chapters.setdefault((b, int(c)), laad(b, int(c)))
        verses[ref] = next(v for v in chapters[b, int(c)][1]['verses'] if str(v['number']) == n)
    done = [v.get('grondtekst_versificatie', {}).get('correctie') == plan['id'] for v in verses.values()]
    if all(done):
        return {}, []
    assert not any(done), 'Gedeeltelijk toegepast plan; eerst beoordelen'
    old = deepcopy(verses)
    for ref, v in verses.items():
        expected = plan['verzen'][ref]
        assert digest((v.get('grondtekst') or [])) == expected['grondtekst_sha256'], ref
        assert digest({k: x for k, x in v.items() if k.startswith('text')}) == expected['tekst_sha256'], ref
    origins = {ref: [(ref, i) for i in range(len((v.get('grondtekst') or [])))] for ref, v in old.items()}
    for source, start, end, target, placement in plan['verplaatsingen']:
        segment = [(source, i) for i in range(start, end)]
        assert all(pair in origins[source] for pair in segment)
        origins[source] = [p for p in origins[source] if p not in segment]
        origins[target] = segment + origins[target] if placement == 'prepend' else origins[target] + segment
    location = {pair: (ref, i) for ref, pairs in origins.items() for i, pair in enumerate(pairs)}
    templates = {}
    for ref, v in verses.items():
        v['grondtekst'] = [deepcopy(old[r]['grondtekst'][i]) for r, i in origins[ref]]
        v['woordnummers'] = []
    for ref, v in old.items():
        for previous, ix in zip(v.get('woordnummers', []), indices(v)):
            assert ix and [v['grondtekst'][i]['strongs'] for i in ix] == previous['strongs'], (ref, previous)
            assert [norm(v['grondtekst'][i]['woord']) for i in ix] == [norm(w) for w in previous['bronwoorden']], ref
            targets = [location[ref, i] for i in ix]
            assert len({r for r, _ in targets}) == 1, 'Een koppeling overspant de verplaatste grens'
            target = targets[0][0]
            new_ix = [i for _, i in targets]
            mapping = deepcopy(previous)
            mapping.setdefault('herkomst', {}).update(grondindices=new_ix, bronindices=new_ix)
            templates[target, tuple(new_ix)] = mapping
            if target not in plan['herbouw']:
                verses[target]['woordnummers'].append(mapping)
    for ref, anchors in plan['ankers'].items():
        verse = verses[ref]
        for ix, text, occurrence in anchors:
            assert len(plekken(platte_tekst(verse), text)) >= occurrence, (ref, text, occurrence)
            assert not set(ix) & {i for m in verse['woordnummers'] for i in m['herkomst']['grondindices']}, (ref, ix)
            source = [verse['grondtekst'][i] for i in ix]
            mapping = deepcopy(templates.get((ref, tuple(ix)), {}))
            mapping.update(tekst=text, voorkomen=occurrence,
                           strongs=[w['strongs'] for w in source], bronwoorden=[w['woord'] for w in source],
                           transliteraties=[w.get('transliteratie', '') for w in source],
                           glossen=[w.get('betekenis') or w.get('gloss') or '' for w in source],
                           status='uitgelijnd', confidence=1.0, reviewstatus='handmatig_gecontroleerd')
            mapping.setdefault('herkomst', {}).update(grondindices=ix, bronindices=ix)
            verse['woordnummers'].append(mapping)
    for ref, v in verses.items():
        for m in v['woordnummers']:
            m['herkomst'].update(dataset='lokale-griekse-grondtekst', versie=plan['id'],
                                 sha256=digest(v['grondtekst']), referentie=ref,
                                 bronplaatsen=[list(origins[ref][i]) for i in m['herkomst']['grondindices']])
            text = m.get('tekst') or m.get('anker')
            assert not text or len(plekken(platte_tekst(v), text)) >= m.get('voorkomen', 1), (ref, text)
        v['grondtekst_versificatie'] = {'correctie': plan['id'], 'toelichting': plan['reden']}
    def tokens(data):
        return Counter(json.dumps(w, sort_keys=True, ensure_ascii=False) for v in data.values() for w in (v.get('grondtekst') or []))
    assert tokens(old) == tokens(verses), 'Bronwoorden verloren of toegevoegd'
    ignore = {'grondtekst', 'woordnummers', 'grondtekst_versificatie'}
    for ref, v in verses.items():
        assert {k:x for k,x in v.items() if k not in ignore} == {k:x for k,x in old[ref].items() if k not in ignore}
    return chapters, [{'ref':ref, 'reden':plan['reden'], 'voor':old[ref], 'na':v} for ref,v in verses.items()]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--plan', type=Path, default=PLAN)
    parser.add_argument('--report', type=Path, default=ROOT / 'reviews/strongs/controles/nt-versgrenzen-2026-11-07.json')
    args = parser.parse_args()
    chapters, changes = prepare(json.loads(args.plan.read_text()))
    if args.write and changes:
        for path, data in chapters.values():
            bewaar(path, data)
        destination = args.report
        destination.write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n')
    print(('Geschreven' if args.write else 'Voorbereid'), len(changes), 'verzen')
