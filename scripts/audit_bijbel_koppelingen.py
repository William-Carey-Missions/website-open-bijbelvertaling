#!/usr/bin/env python3
"""Maak per boek een werklijst, inclusief alle woorden zonder tekstanker.

Gebruik: python3 scripts/audit_bijbel_koppelingen.py [--boek exodus]
Geen automatische inhoudelijke goedkeuring of wijzigingen aan Bijbeldata.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from audit_genesis_koppelingen import audit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boek')
    args = parser.parse_args()
    books = json.loads((ROOT / 'data/books.json').read_text())['books']
    selected = [b for b in books if not args.boek or b['id'] == args.boek]
    if not selected:
        parser.error('Onbekend boek')
    destination = ROOT / 'reviews/strongs/controles'
    destination.mkdir(parents=True, exist_ok=True)
    summary = []
    for book in selected:
        report = audit(book['id'], book['chaptersIncluded'])
        (destination / f"{book['id']}.json").write_text(
            json.dumps(report, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        row = {k: v for k, v in report.items() if k not in ('fouten', 'woorden_zonder_link')}
        row['technische_meldingen'] = dict(Counter(x['type'] for x in report['fouten']))
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if not args.boek:
        (destination / 'bijbel-overzicht.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
