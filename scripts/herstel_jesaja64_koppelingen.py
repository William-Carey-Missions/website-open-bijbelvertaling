#!/usr/bin/env python3
"""Herstel de expliciet gecontroleerde versificatie van Jesaja 63:19–64:12.
Bron: https://classic.net.bible.org/verse.php?book=Isa&chapter=64&verse=1
Standaard droge run; --write schrijft en logt de bronverplaatsing en ankers.
"""
import argparse
import copy
import hashlib
import json
from collections import Counter
from strongs_nalopen import laad, bewaar, bouw, indices, LOG

# Per grondtoken het Nederlandse anker, met optioneel #voorkomen.
# None = geen zelfstandig genummerd lexeme; @ = plaatsingsanker.
ANCHORS = {
1: ['Och','scheurde','hemelen','neerkwam','aangezicht','bergen','wegsmolten'],
2: ['brandt','smeltvuur','smeltvuur','wateren','doet opbobbelen','vuur','bekend te maken','Naam','tegenstanders','aangezicht','heidenen','beven'],
3: ['deedt','vreselijke dingen','niet','verwachtten','kwam neer','aangezicht','bergen','smolten'],
4: ['ouds','niet','gehoord','noch','met oren vernomen','oog','geen','gezien','God','behalve U','doen','wacht',None],
5: ['ontmoet','@vrolijke','vrolijke','doet','gerechtigheid','wegen','gedenken','zie','U#3','toornig','gezondigd',None,'eeuwigheid','behouden'],
6: ['zijn','onreine','allen','kleed','wegwerpelijk','al','gerechtigheden','vallen af','blad','allen#2','misdaden','wind','voeren'],
7: ['niemand','aanroept','Naam','opwekt','aangrijpe',None,'want','verbergt','aangezicht','ons','doet ons smelten','door middel van','ongerechtigheden'],
8: ['nu','JAHWEH','Vader','U','wij','leem','U#2','pottenbakker','werk','handen','allen'],
9: ['niet','toornig','JAHWEH','zo','zeer','niet#2','eeuwig','gedenk','ongerechtigheid','zie','aanschouw','toch','volk','allen'],
10: ['steden','heilige','geworden','woestijn','Sion','woestijn#2','geworden#2','Jeruzalem','verwoesting'],
11: ['huis','heilig','heerlijk','waarin','loofden','vaders','is','verbrand','vuur','al','gewenste dingen','geworden','woestheid'],
12: ['over','deze dingen','inhouden','JAHWEH','stilzwijgen','bedrukken','zozeer','zozeer'],
}


def prepare():
    p63, c63 = laad('jesaja', 63)
    p64, c64 = laad('jesaja', 64)
    if c64['verses'][0].get('grondtekst_versificatie', {}).get('correctie') == 'jesaja64-2026-11-07':
        return [], []
    before = copy.deepcopy([c63, c64])
    tail = c63['verses'][-1]
    assert tail['number'] == 19 and len(tail['grondtekst']) == 16
    assert tail['grondtekst'][9]['strongs'] == 'H3863'
    assert not c64['verses'][-1].get('grondtekst')
    assert all(not v.get('woordnummers') for v in c64['verses'])
    original = {v['number']: copy.deepcopy(v.get('grondtekst') or []) for v in c64['verses']}
    source1 = copy.deepcopy(tail['grondtekst'][9:])
    old_tail = copy.deepcopy(tail)
    retained = []
    for m, ii in zip(tail['woordnummers'], indices(tail)):
        if all(i < 9 for i in ii):
            retained.append(m)
        else:
            assert all(i >= 9 for i in ii) and not m.get('tekst') and not m.get('anker')
    tail['woordnummers'] = retained
    tail['grondtekst'] = tail['grondtekst'][:9]
    logs = [{'ref': 'jesaja/63/19', 'reden': 'Hebreeuws 63:19b hoort bij Nederlands 64:1.',
             'oude_grondtekst': old_tail['grondtekst'], 'nieuwe_grondtekst': tail['grondtekst'],
             'oude_woordnummers': old_tail['woordnummers'], 'nieuwe_woordnummers': retained}]
    for v in c64['verses']:
        n = v['number']
        old_ground = copy.deepcopy(v.get('grondtekst'))
        source = source1 if n == 1 else original[n-1]
        assert len(source) == len(ANCHORS[n]), n
        v['grondtekst'] = source
        groups = {}
        for i, label in enumerate(ANCHORS[n]):
            if label is None:
                assert not source[i].get('strongs')
                continue
            groups.setdefault(label, []).append(i)
        mappings = []
        for label, ii in groups.items():
            text, sep, occurrence = label.partition('#')
            record = {'i': ii, 'voorkomen': int(occurrence) if sep else 1}
            if text.startswith('@'):
                record.update(anker=text[1:], plaats='voor')
            else:
                record['tekst'] = text
            mappings.append(record)
        errors = []
        records = bouw(v, mappings, errors, f'jesaja/64/{n}')
        if errors:
            raise ValueError(errors)
        origin = 'ISA 63:19b' if n == 1 else f'ISA 64:{n-1}'
        digest = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        for m in records:
            m['herkomst'].update(dataset='lokale-hebreeuwse-grondtekst', versie='versificatie-2026-11-07',
                                 sha256=digest, referentie=origin)
            m['herkomst']['bronindices'] = [i+9 if n == 1 else i for i in m['herkomst']['grondindices']]
        v['woordnummers'] = records
        v['grondtekst_versificatie'] = {'correctie': 'jesaja64-2026-11-07', 'bronreferentie': origin,
            'toelichting': 'Hebreeuws 63:19b = Nederlands 64:1; Hebreeuws 64:1–11 = Nederlands 64:2–12.',
            'controlebron': 'https://classic.net.bible.org/verse.php?book=Isa&chapter=64&verse=1'}
        logs.append({'ref': f'jesaja/64/{n}', 'reden': 'Versificatie hersteld en Nederlandse koppelingen per grondwoord nagekeken.',
                     'bronreferentie': origin, 'oude_grondtekst': old_ground, 'nieuwe_grondtekst': source,
                     'nieuwe_woordnummers': records})
    def tokens(chapters):
        return Counter(json.dumps(g, ensure_ascii=False, sort_keys=True) for c in chapters for v in c['verses'] for g in (v.get('grondtekst') or []))
    assert tokens(before) == tokens([c63, c64]), 'Grondtokens verloren of toegevoegd'
    for oldc, newc in zip(before, [c63, c64]):
        for oldv, newv in zip(oldc['verses'], newc['verses']):
            ignored = {'grondtekst', 'woordnummers', 'grondtekst_versificatie'}
            assert {k:v for k,v in oldv.items() if k not in ignored} == {k:v for k,v in newv.items() if k not in ignored}
    return [(p63, c63), (p64, c64)], logs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    chapters, logs = prepare()
    if args.write:
        for p, d in chapters:
            bewaar(p, d)
        with (LOG / 'jesaja.jsonl').open('a', encoding='utf-8') as f:
            for entry in logs:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(('Geschreven' if args.write else 'Gecontroleerd'), len(logs), 'verzen')
