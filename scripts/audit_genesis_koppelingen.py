#!/usr/bin/env python3
"""Inventariseer ankers, grondwoorddekking en ALLE Nederlandse woorden zonder link.

Een woord zonder link is een reviewpunt, niet automatisch een fout: onder meer
lidwoorden, suffixen en hulpwoorden hebben niet altijd een eigen Strong-nummer.
Dit rapport bewijst geen inhoudelijke goedkeuring van de koppelingen.
"""
import json
import re
from pathlib import Path
from strongs_nalopen import laad, indices, platte_tekst, plekken

ROOT = Path(__file__).resolve().parents[1]


def audit(boek="genesis", hoofdstukken=range(1, 51)):
    report = {'boek': boek, 'inhoudelijke_controle_voltooid': False,
              'verzen': 0, 'koppelingen': 0, 'verzen_zonder_grondtekst': 0,
              'verzen_zonder_koppelingslaag': 0, 'fouten': [], 'woorden_zonder_link': []}
    for h in hoofdstukken:
        _, chapter = laad(boek, h)
        for verse in chapter['verses']:
            ref = f"{boek}/{h}/{verse['number']}"
            report['verzen'] += 1
            text = platte_tekst(verse)
            report['verzen_zonder_grondtekst'] += not bool(verse.get('grondtekst'))
            report['verzen_zonder_koppelingslaag'] += not bool(verse.get('woordnummers'))
            covered = set()
            linked = set()
            mappings = (verse.get('woordnummers') or [])
            for mapping, source_indices in zip(mappings, indices(verse)):
                report['koppelingen'] += 1
                if not source_indices:
                    report['fouten'].append({'ref': ref, 'type': 'grondwoord_onvindbaar', 'mapping': mapping})
                target = mapping.get('tekst') or mapping.get('anker') or ''
                if not target or mapping.get('reviewstatus') not in (None, 'handmatig_gecontroleerd', 'automatisch_hoog_vertrouwen'):
                    continue
                positions = plekken(text, target)
                occurrence = mapping.get('voorkomen', 1)
                if not isinstance(occurrence, int) or not 1 <= occurrence <= len(positions):
                    report['fouten'].append({'ref': ref, 'type': 'anker_onvindbaar', 'mapping': mapping})
                else:
                    linked.update(source_indices)
                    start = positions[occurrence - 1]
                    covered.update(range(start, start + len(target)))
            for i, token in enumerate((verse.get('grondtekst') or [])):
                if token.get('strongs') and i not in linked:
                    report['fouten'].append({'ref': ref, 'type': 'grondwoord_zonder_koppeling', 'index': i,
                                             'grondwoord': token.get('woord'), 'strongs': token.get('strongs'),
                                             'context': text,
                                             'categorie': 'aanvulling_bestaande_koppelingen' if mappings else 'geen_koppelingslaag'})
            gaps = [{'woord': match.group(), 'start': match.start(), 'eind': match.end()}
                    for match in re.finditer(r"[^\W_]+(?:[’'-][^\W_]+)*", text)
                    if not set(range(match.start(), match.end())).issubset(covered)]
            if gaps:
                report['woorden_zonder_link'].append({'ref': ref, 'tekst': text, 'woorden': gaps})
    report['aantal_woorden_zonder_link'] = sum(len(v['woorden']) for v in report['woorden_zonder_link'])
    return report


if __name__ == '__main__':
    result = audit()
    destination = ROOT / 'reviews/strongs/controles/genesis.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('woorden_zonder_link', 'fouten')}, ensure_ascii=False))
    print(f"Technische fouten: {len(result['fouten'])}; rapport: {destination}")
    raise SystemExit(bool(result['fouten']))
