import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pas_strongs_aanvullingen_toe import prepare
from strongs_nalopen import laad, indices, platte_tekst, plekken


def fixture():
    verse = {'number': 1, 'text2026': 'De liefde.',
             'grondtekst': [{'woord': 'η', 'strongs': 'G3588'}, {'woord': 'αγαπη', 'strongs': 'G26'}],
             'woordnummers': [{'tekst': 'liefde', 'voorkomen': 1, 'strongs': ['G26'], 'bronwoorden': ['αγαπη']}]}
    item = {'ref': 'voorbeeld/1/1', 'grondindex': 0, 'grondwoord': 'η', 'strongs': 'G3588',
            'tekst': 'De', 'voorkomen': 1, 'vers_tekst': 'De liefde.', 'reden': 'Lidwoord aanvullen.',
            'grondtekst_sha256': hashlib.sha256(json.dumps(verse['grondtekst'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    return verse, item


def test_explicit_addition_preserves_existing_links_and_is_idempotent():
    verse, item = fixture()
    original = copy.deepcopy(verse)
    chapter = {'verses': [verse]}
    with patch('pas_strongs_aanvullingen_toe.laad', return_value=(Path('unused'), chapter)):
        _, added = prepare([item])
        _, repeated = prepare([item])
    assert len(added['voorbeeld']) == 1
    assert not repeated
    assert verse['grondtekst'] == original['grondtekst']
    assert verse['text2026'] == original['text2026']
    assert verse['woordnummers'][0] == original['woordnummers'][0]


def test_changed_translation_is_rejected_before_mutation():
    verse, item = fixture()
    verse['text2026'] = 'Liefde.'
    before = copy.deepcopy(verse)
    with patch('pas_strongs_aanvullingen_toe.laad', return_value=(Path('unused'), {'verses': [verse]})):
        try:
            prepare([item])
        except ValueError:
            pass
        else:
            raise AssertionError('Gewijzigde tekst niet geweigerd')
    assert verse == before


def test_isaiah64_has_matching_source_and_complete_numbered_token_coverage():
    _, chapter = laad('jesaja', 64)
    first, last = chapter['verses'][0], chapter['verses'][-1]
    assert first['grondtekst'][0]['strongs'] == 'H3863'  # Och, niet het vuur van vers 2.
    assert last['grondtekst'][0]['strongs'] == 'H5921'  # over deze dingen
    assert first['grondtekst_versificatie']['bronreferentie'] == 'ISA 63:19b'
    assert last['grondtekst_versificatie']['bronreferentie'] == 'ISA 64:11'
    for verse in chapter['verses']:
        linked = [i for group in indices(verse) for i in group]
        expected = [i for i, g in enumerate(verse['grondtekst']) if g.get('strongs')]
        assert sorted(linked) == expected
        for mapping in verse['woordnummers']:
            target = mapping.get('tekst') or mapping.get('anker')
            assert target and len(plekken(platte_tekst(verse), target)) >= mapping['voorkomen']
