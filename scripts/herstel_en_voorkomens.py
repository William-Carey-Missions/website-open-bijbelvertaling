#!/usr/bin/env python3
"""Herstel dubbele voorkomens van En/en, met volledige controle van alle καί's.

Alleen als elke καί afzonderlijk als en is vertaald, het aantal Nederlandse
voorkomens exact klopt en geen andere ankers overlappen. Geen nieuwe links.
"""
import argparse
from copy import deepcopy
import json
from collections import Counter
from strongs_nalopen import ROOT, laad, bewaar, indices, norm, plekken, platte_tekst


def corrections(verse):
    mappings = verse.get('woordnummers', [])
    en = [j for j,m in enumerate(mappings) if m.get('tekst','').lower() == 'en']
    occurrences = [mappings[j].get('voorkomen',1) for j in en]
    if len(en) < 2 or len(set(occurrences)) == len(occurrences):
        return []
    ground = verse.get('grondtekst', [])
    ix = indices(verse)
    kai = [i for i,w in enumerate(ground) if w.get('strongs') == 'G2532' and norm(w.get('woord')) == 'και']
    positions = plekken(platte_tekst(verse), 'en')
    if len(en) != len(positions) or len(kai) != len(en):
        return []
    if any(mappings[j].get('strongs') != ['G2532'] or len(ix[j]) != 1 for j in en):
        return []
    if {ix[j][0] for j in en} != set(kai):
        return []
    for j,m in enumerate(mappings):
        if j in en or not m.get('tekst'):
            continue
        starts = plekken(platte_tekst(verse), m['tekst'])
        occurrence = m.get('voorkomen',1)
        if 0 < occurrence <= len(starts):
            start = starts[occurrence-1]
            if any(p < start+len(m['tekst']) and p+2 > start for p in positions):
                return []
    changes = []
    for occurrence,j in enumerate(sorted(en,key=lambda j:ix[j][0]),1):
        m = mappings[j]
        if m.get('voorkomen',1) != occurrence:
            previous = deepcopy(m)
            m['voorkomen'] = occurrence
            m.setdefault('herkomst', {}).update(grondindices=ix[j], voorkomenscontrole='en-kai-2026-11-07')
            changes.append({'voor':previous,'na':deepcopy(m)})
    return changes


def main(write=False):
    changes = []
    for book in json.loads((ROOT/'data/books.json').read_text())['books']:
        for chapter in book['chaptersIncluded']:
            path,data = laad(book['id'],chapter)
            changed = False
            for verse in data['verses']:
                records = corrections(verse)
                if records:
                    changed = True
                    changes.append({'ref':f'{book["id"]}/{chapter}/{verse["number"]}',
                                    'tekst':platte_tekst(verse),'correcties':records})
            if write and changed:
                bewaar(path,data)
    if write and changes:
        (ROOT/'reviews/strongs/controles/en-voorkomens-2026-11-07.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
    print(('Geschreven' if write else 'Voorbereid'),sum(len(c['correcties']) for c in changes),'correcties in',len(changes),'verzen')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    main(parser.parse_args().write)
