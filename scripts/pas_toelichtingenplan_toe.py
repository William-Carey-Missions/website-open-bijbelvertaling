"""Pas afzonderlijk beoordeelde toelichtingen toe, met broncontrole en wijzigingsspoor."""
import argparse,copy,difflib,hashlib,json
from pathlib import Path
from kanttekeningen_nalezen import bewaar,kern_1888
ROOT=Path(__file__).resolve().parents[1]
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def prepare(plan,root=ROOT):
    output={};changes=[]
    for row in plan['wijzigingen']:
        path=Path(root)/row['bestand']
        if path not in output:output[path]=json.loads(path.read_text())
        data=output[path]
        obj=data['bookIntro'] if row['soort']=='boekinleiding' else next(n for v in data['verses'] if v['number']==row['vers'] for n in v['marginNotes'] if n['marker']==row['marker'])
        field=row.get('veld','text2026');identifier=plan['id']+'/'+row['ref']+'/'+field
        if any(h['id']==identifier for h in obj.get('herzieningen',[])):
            latest=[h for h in obj['herzieningen'] if h.get('veld','text2026')==field][-1]
            assert sha(obj.get(field,''))==latest['na_sha256'],(identifier,'herziening gewijzigd');continue
        before=obj.get(field,'');assert before==row['old'],(identifier,'oude tekst wijkt af')
        assert row['bronpassage'] in obj[row['bronveld']],(identifier,'bron wijkt af')
        record={k:row[k] for k in ['soort','ref','principe','old','new','reden','bronveld','bronpassage']}
        record.update(id=identifier,datum=plan['datum'],veld=field,voor_sha256=sha(before),na_sha256=sha(row['new']),beoordeling='AI-ondersteunde herziening; geen menselijke verificatie')
        record.update(row.get('weergave',{}))
        obj[field]=row['new'];obj.setdefault('herzieningen',[]).append(record);changes.append(record)
    # Alleen het verschil bij gewijzigde noten opnieuw bepalen; ontbrekende bron blijft leeg.
    for data in output.values():
        for v in data.get('verses',[]):
            for n in v.get('marginNotes',[]):
                if not any(h['id'].startswith(plan['id']+'/') for h in n.get('herzieningen',[])):continue
                a=kern_1888(n.get('textSV1888',''),n['text2026']).split();b=n['text2026'].split()
                n['noteDiff']=[{'old':' '.join(a[i:j]),'new':' '.join(b[k:l])} for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b).get_opcodes() if tag!='equal'] if a else []
    return output,changes
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);p.add_argument('--write',action='store_true');args=p.parse_args()
    plan=json.loads(args.plan.read_text());output,changes=prepare(plan)
    if args.write and changes:
        for path,data in output.items():bewaar(path,data)
        report=ROOT/'reviews/herzieningen'/(plan['id']+'-controle.json');report.write_text(json.dumps({'wijzigingen':changes,'volledig_inhoudelijk_gecontroleerd':False},ensure_ascii=False,indent=2)+'\n')
    print(len(changes),'herzieningen', 'geschreven' if args.write else 'voorbereid')
