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
