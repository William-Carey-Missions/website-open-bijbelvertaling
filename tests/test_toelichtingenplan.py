import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from pas_toelichtingenplan_toe import prepare
PLAN=json.loads((ROOT/'reviews/herzieningen/genesis-exodus-2026-11-09-vervolg-plan.json').read_text())
class ReviewedNotes(unittest.TestCase):
 def test_repeated_application_preserves_current_text_and_history(self):
  output,changes=prepare(PLAN);self.assertEqual(changes,[])
  for path,data in output.items():self.assertEqual(data,json.loads(path.read_text()))
 def test_wrong_source_aborts_before_writing_any_file(self):
  row=next(r for r in PLAN['wijzigingen'] if r['veld']=='text2026')
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);p=root/row['bestand'];p.parent.mkdir(parents=True)
   n={'marker':row['marker'],'text2026':row['old'],'text1637':'andere bron'}
   p.write_text(json.dumps({'verses':[{'number':row['vers'],'marginNotes':[n]}]}));before=p.read_bytes()
   with self.assertRaises(AssertionError):prepare({**PLAN,'wijzigingen':[row]},root)
   self.assertEqual(p.read_bytes(),before)
 def test_1888_comparison_matches_subject_of_1637_note(self):
  c=json.loads((ROOT/'data/genesis/2.json').read_text());notes={n['marker']:n for v in c['verses'] for n in v.get('marginNotes',[])}
  self.assertIn('een damp',notes['11']['textSV1888'])
  self.assertEqual(notes['12']['textSV1888'],'');self.assertIn('aangezicht',notes['12']['text2026']);self.assertEqual(notes['12']['noteDiff'],[])
  self.assertIn('pottenbakker',notes['13']['textSV1888']);self.assertIn('pottenbakker',notes['13']['text2026'])
 def test_source_reassignments_are_exact_existing_passages(self):
  rows=[r for r in PLAN['wijzigingen'] if r.get('veld')=='textSV1888'];old={r['old'] for r in rows}
  self.assertEqual(sum(bool(r['new']) for r in rows),23)
  self.assertTrue(all(not r['new'] or r['new'] in old for r in rows))
