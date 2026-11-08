// Gebruik: NODE_PATH=... node tests/render_woordkoppelingen.cjs <repository> <woordnummers.js> <rapport.json>
const fs=require('fs'),path=require('path'),{JSDOM}=require('jsdom');
const root=process.argv[2],renderer=process.argv[3],destination=process.argv[4];
const dom=new JSDOM('',{runScripts:'outside-only'});dom.window.eval(fs.readFileSync(renderer,'utf8'));
const books=JSON.parse(fs.readFileSync(path.join(root,'data/books.json'))).books;
let verses=0,buttons=0,failures=[];
for(const book of books){for(const n of book.chaptersIncluded){
 const chapter=JSON.parse(fs.readFileSync(path.join(root,`data/${book.id}/${n}.json`)));
 for(const v of chapter.verses){
  const maps=v.woordnummers||[],html=v.text2026_html||v.text2026||'';
  const out=dom.window.document.createElement('div');out.innerHTML=dom.window.OVWoordnummers.renderInline(html,maps);
  const bs=out.querySelectorAll('button.strongs-inline');const expected=maps.filter(m=>(m.tekst||m.anker)&&(!m.reviewstatus||['handmatig_gecontroleerd','automatisch_hoog_vertrouwen'].includes(m.reviewstatus))).reduce((sum,m)=>sum+(m.strongs||[]).flatMap(x=>String(x||'').match(/(?:OVL|OVG)\d+|[HG]\d+[A-Za-z]?/g)||[]).length,0);
  if(bs.length!==expected)failures.push({ref:`${book.id}/${n}/${v.number}`,expected,actual:bs.length});buttons+=bs.length;verses++;bs.forEach(b=>b.remove());const original=dom.window.document.createElement('div');original.innerHTML=html;
  if(original.textContent!==out.textContent)failures.push({ref:`${book.id}/${n}/${v.number}`,type:'text_changed'});
 }
}}
const result={books:books.length,verses,buttons,failures};fs.writeFileSync(destination,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({...result,failures:failures.length,examples:failures.slice(0,5)}));process.exitCode=failures.length?1:0;
