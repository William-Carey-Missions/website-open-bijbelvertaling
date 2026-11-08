import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_genesis_koppelingen import audit


def test_audit_accepts_missing_ground_text_and_records_unlinked_words():
    chapter = {'verses': [{'number': 1, 'text2026': 'Een woord.', 'grondtekst': None, 'woordnummers': None}]}
    with patch('audit_genesis_koppelingen.laad', return_value=(None, chapter)):
        report = audit('voorbeeld', [1])
    assert report['verzen'] == 1
    assert report['aantal_woorden_zonder_link'] == 2
    assert report['inhoudelijke_controle_voltooid'] is False


def test_audit_counts_occurrences_without_case_and_keeps_unlinked_second_word():
    chapter = {'verses': [{'number': 1, 'text2026': 'En licht en leven.',
        'grondtekst': [{'woord': 'και', 'strongs': 'G2532'}],
        'woordnummers': [{'tekst': 'En', 'voorkomen': 1, 'strongs': ['G2532'], 'bronwoorden': ['και']}]}]}
    with patch('audit_genesis_koppelingen.laad', return_value=(None, chapter)):
        report = audit('voorbeeld', [1])
    assert report['fouten'] == []
    assert [w['woord'] for w in report['woorden_zonder_link'][0]['woorden']] == ['licht', 'en', 'leven']


def test_audit_detects_unfindable_anchor_and_missing_source_link():
    chapter = {'verses': [{'number': 1, 'text2026': 'licht',
        'grondtekst': [{'woord': 'και', 'strongs': 'G2532'}, {'woord': 'φως', 'strongs': 'G5457'}],
        'woordnummers': [{'tekst': 'en', 'voorkomen': 1, 'strongs': ['G2532'], 'bronwoorden': ['και']}]}]}
    with patch('audit_genesis_koppelingen.laad', return_value=(None, chapter)):
        report = audit('voorbeeld', [1])
    assert {e['type'] for e in report['fouten']} == {'anker_onvindbaar', 'grondwoord_zonder_koppeling'}


def test_empty_and_pending_mappings_do_not_hide_unlinked_source_words():
    for target, status in [('', 'handmatig_gecontroleerd'), ('licht', 'controle_nodig')]:
        chapter = {'verses': [{'number': 1, 'text2026': 'licht',
            'grondtekst': [{'woord': 'φως', 'strongs': 'G5457'}],
            'woordnummers': [{'tekst': target, 'strongs': ['G5457'], 'bronwoorden': ['φως'], 'reviewstatus': status}]}]}
        with patch('audit_genesis_koppelingen.laad', return_value=(None, chapter)):
            report = audit('voorbeeld', [1])
        assert [e['type'] for e in report['fouten']] == ['grondwoord_zonder_koppeling']
        assert report['aantal_woorden_zonder_link'] == 1


def test_mapping_without_a_number_does_not_cover_a_dutch_word():
    chapter = {'verses': [{'number':1, 'text2026':'ons',
        'grondtekst':[{'woord':'bron','strongs':''}],
        'woordnummers':[{'tekst':'ons','strongs':[''],'bronwoorden':['bron']}]}]}
    with patch('audit_genesis_koppelingen.laad', return_value=(None,chapter)):
        report=audit('voorbeeld',[1])
    assert report['aantal_woorden_zonder_link'] == 1
    assert report['fouten'] == []
