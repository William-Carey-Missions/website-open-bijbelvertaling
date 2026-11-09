import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import herzie_genesis_toelichtingen_20261109 as revision
import build_principes_data as catalog
class EditorialRevisions(unittest.TestCase):
 def current(self):return json.loads((ROOT/'data/genesis/1.json').read_text()),json.loads((ROOT/'data/genesis.json').read_text())
 def test_idempotent_and_historical_sources_preserved(self):
  chapter,book=self.current();c,b,changes=revision.prepare(chapter,book)
  self.assertEqual(changes,[]);self.assertEqual(c,chapter);self.assertEqual(b,book)
  note=next(n for v in c['verses'] if v['number']==4 for n in v['marginNotes'] if n['marker']=='12')
  self.assertIn('menselijke wijze',note['text2026']);self.assertIn(note['herzieningen'][0]['bronpassage'],note['textSV1888'])
 def test_changed_source_rejects_correction_without_mutating_inputs(self):
  c,b=self.current();n=next(n for v in c['verses'] if v['number']==4 for n in v['marginNotes'] if n['marker']=='12');n['text2026']='God beschouwde zijn schepping als goed.';n.pop('herzieningen');n['textSV1888']='Afwijkende bron';n['text1637']='Afwijkende bron';old=copy.deepcopy(c)
  with self.assertRaises(AssertionError):revision.prepare(c,b)
  self.assertEqual(c,old)
 def test_catalog_distinguishes_notes_introductions_and_verses(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data/genesis').mkdir(parents=True)
   r={'principe':'KT1','soort':'kanttekening','old':'oud','new':'nieuw','reden':'reden','bronpassage':'bron','bronveld':'text1637','datum':'2026-11-09','id':'note'}
   (root/'data/books.json').write_text(json.dumps({'books':[{'id':'genesis','nameDutch':'Genesis'}]}))
   (root/'data/genesis.json').write_text(json.dumps({'bookIntro':{'herzieningen':[{**r,'principe':'BI1','soort':'boekinleiding','id':'intro'}]}}))
   (root/'data/genesis/1.json').write_text(json.dumps({'number':1,'verses':[{'number':4,'phraseDiff':[{'principe':['N1','N2'],'old':'den','new':'de'}],'marginNotes':[{'marker':'12','herzieningen':[r]}]}]}))
   with patch.object(catalog,'WORTEL',tmp):catalog.main()
   out=json.loads((root/'data/principes-data.json').read_text());self.assertEqual(out['counts'],{'BI1':1,'KT1':1,'N1':1,'N2':1});self.assertEqual(out['verses']['KT1'][0]['m'],'12');self.assertEqual(out['verses']['BI1'][0]['k'],'boekinleiding')
