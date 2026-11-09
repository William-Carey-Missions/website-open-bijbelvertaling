"""Beoordeelde herzieningen van Genesis-inleiding en kanttekeningen, brongebonden."""
import argparse
import copy
import difflib
import hashlib
import json
from pathlib import Path
from kanttekeningen_nalezen import bewaar, kern_1888
ROOT = Path(__file__).resolve().parents[1]


def prepare(chapter, book):
    chapter, book = copy.deepcopy(chapter), copy.deepcopy(book)
    changes = []
    def change(obj,old,new,pid,kind,ref,reason,quote):
        identifier=f'{ref}/{pid}/2026-11-09'
        if any(x['id']==identifier for x in obj.get('herzieningen',[])):
            assert new in obj['text2026'], identifier
            return
        before=obj['text2026'];assert before.count(old)==1,(ref,old)
        assert quote in (obj.get('textSV1888','')+' '+obj.get('text1637','')),ref
        after=before.replace(old,new,1)
        sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
        r={'id':identifier,'datum':'2026-11-09','soort':kind,'ref':ref,'principe':pid,'old':old,'new':new,'reden':reason,'bronveld':'textSV1888' if quote in obj.get('textSV1888','') else 'text1637','bronpassage':quote,'voor_sha256':sha(before),'na_sha256':sha(after),'beoordeling':'AI-ondersteunde herziening; geen menselijke verificatie'}
        obj['text2026']=after;obj.setdefault('herzieningen',[]).append(r);changes.append(r)
    note=lambda v,m:next(n for row in chapter['verses'] if row['number']==v for n in row.get('marginNotes',[]) if n['marker']==str(m))
    change(note(4,12),'God beschouwde zijn schepping als goed.','Hier wordt op menselijke wijze over God gesproken. De betekenis is dat God zijn schepsel als goed beschouwde.','KT1','kanttekening','genesis/1/4/12','De uitleg over de menselijke spreekwijze was weggevallen. Hersteld vanuit de historische bron, zonder nieuwe exegese.','Dat is menselijker wijze van God gesproken. De zin is, dat God zijn schepsel voor goed kende.')
    change(note(2,8),'zoals die toen was','zoals die toen waren','KT2','kanttekening','genesis/1/2/8','Het historische meervoud verwijst naar aarde en wateren. De enkelvoudsvorm was bij de herziening ontstaan.','gelijk die toen waren')
    for row in chapter['verses']:
        for n in row.get('marginNotes',[]):
            if not n.get('herzieningen'):continue
            a=kern_1888(n.get('textSV1888',''),n['text2026']).split();b=n['text2026'].split()
            n['noteDiff']=[{'old':' '.join(a[i:j]),'new':' '.join(b[k:l])} for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b).get_opcodes() if tag!='equal']
    intro=book['bookIntro']
    change(intro,'voornaamste oogmerk','belangrijkste doel','BI1','boekinleiding','genesis/inleiding/1','Hedendaagse formulering met behoud van het historische doel dat aan Mozes wordt toegeschreven.','voorneemste oogemerck')
    change(intro,'de herstelling van de Kerk','het herstel van de Kerk','BI1','boekinleiding','genesis/inleiding/2','Hedendaagse formulering van de historische wederoprichting; geen verandering van de theologische inhoud.','vveder-oprechtinge der Kercke')
    return chapter,book,changes


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    cp,bp=ROOT/'data/genesis/1.json',ROOT/'data/genesis.json'
    oldc,oldb=json.loads(cp.read_text()),json.loads(bp.read_text());chapter,book,changes=prepare(oldc,oldb)
    for old,new in zip(oldc['verses'],chapter['verses']):
        assert {k:v for k,v in old.items() if k!='marginNotes'}=={k:v for k,v in new.items() if k!='marginNotes'}
    if args.write and changes:
        bewaar(cp,chapter);bewaar(bp,book)
        p=ROOT/'reviews/herzieningen/2026-11-09.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'wijzigingen':changes,'volledig_inhoudelijk_gecontroleerd':False},ensure_ascii=False,indent=2)+'\n')
    print(len(changes),'herzieningen met principe en bronpassage', 'geschreven' if args.write else 'voorbereid')
