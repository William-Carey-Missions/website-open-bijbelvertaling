import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import herstel_nt_versgrenzen as nt
from herstel_en_voorkomens import corrections


class VerseBoundaries(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(nt.PLAN.read_text())
        log = json.loads((ROOT/'reviews/strongs/controles/nt-versgrenzen-2026-11-07.json').read_text())
        self.chapters = {}
        for row in log:
            b,c,n = row['ref'].split('/')
            self.chapters.setdefault((b,int(c)),{'verses':[]})['verses'].append(row['voor'])

    def load(self,b,c):
        return Path(f'{b}/{c}.json'), copy.deepcopy(self.chapters[b,c])

    def test_boundaries_and_conjunction_occurrences(self):
        with patch.object(nt,'laad',self.load):
            chapters,changes = nt.prepare(self.plan)
        self.assertEqual(len(changes),10)
        rev = chapters['openbaring',13][1]['verses'][0]
        self.assertEqual(rev['grondtekst'][0]['woord'],'και')
        self.assertEqual([m['voorkomen'] for m in rev['woordnummers'] if m.get('tekst','').lower()=='en'],[1,2,3,4])
        preceding = chapters['openbaring',12][1]['verses'][0]
        self.assertEqual(len(preceding['grondtekst']),7)
        self.chapters = {k:v[1] for k,v in chapters.items()}
        with patch.object(nt,'laad',self.load):
            self.assertEqual(nt.prepare(self.plan),({},[]))

    def test_changed_source_is_rejected(self):
        self.chapters['hebreeen',1]['verses'][0]['grondtekst'][0]['woord']='gewijzigd'
        with patch.object(nt,'laad',self.load), self.assertRaises(AssertionError):
            nt.prepare(self.plan)


class ApocryphalBoundaries(unittest.TestCase):
    def test_split_shift_and_empty_final_verse_preserve_source(self):
        plan = json.loads((ROOT/'reviews/strongs/plannen/3ezra9-versgrenzen-2026-11-07.json').read_text())
        log = json.loads((ROOT/'reviews/strongs/controles/3ezra9-versgrenzen-2026-11-07.json').read_text())
        before = {'verses': [row['voor'] for row in log]}
        self.assertIsNone(before['verses'][-1]['grondtekst'])
        with patch.object(nt, 'laad', lambda b,c: (Path('fixture.json'), copy.deepcopy(before))):
            chapters, changes = nt.prepare(plan)
        verses = {v['number']: v for v in chapters['3ezra',9][1]['verses']}
        self.assertEqual(len(changes), 9)
        self.assertEqual(verses[48]['grondtekst'][-1]['woord'], 'κυρίου')
        self.assertEqual(verses[49]['grondtekst'][4]['woord'], 'ἀνεγίνωσκον')
        self.assertEqual(verses[56]['grondtekst'][0]['woord'], 'ὅτι')
        for v in verses.values():
            spans = []
            for m in v['woordnummers']:
                start = nt.plekken(nt.platte_tekst(v), m['tekst'])[m['voorkomen']-1]
                span = (start, start + len(m['tekst']))
                self.assertFalse(any(span[0] < end and start < span[1] for start,end in spans))
                spans.append(span)
        with patch.object(nt, 'laad', lambda b,c: (Path('fixture.json'), copy.deepcopy(chapters['3ezra',9][1]))):
            self.assertEqual(nt.prepare(plan), ({}, []))


class Conjunctions(unittest.TestCase):
    def sample(self,text='En hij kwam en hij ging.'):
        return {'text2026':text,'grondtekst':[{'woord':'και','strongs':'G2532'},{'woord':'και','strongs':'G2532'}],
                'woordnummers':[{'tekst':t,'voorkomen':1,'strongs':['G2532'],'bronwoorden':['και'],'herkomst':{'grondindices':[i]}} for i,t in enumerate(['En','en'])]}

    def test_case_does_not_reset_occurrence(self):
        v=self.sample()
        self.assertEqual(len(corrections(v)),1)
        self.assertEqual(v['woordnummers'][1]['voorkomen'],2)
        self.assertEqual(corrections(v),[])

    def test_extra_dutch_word_prevents_guessing(self):
        self.assertEqual(corrections(self.sample('En hij kwam en hij zag en hij ging.')),[])


if __name__=='__main__':
    unittest.main()
