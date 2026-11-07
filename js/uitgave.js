/* Zelf een leesuitgave samenstellen, volledig in de browser. */
(function () {
'use strict';
const $ = id => document.getElementById('uw-' + id);
let books = [], step = 0, controller = null;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const name = s => String(s || '').split(/(<[^>]+>)/g).map((part,i)=>i%2?part:part
 .replace(/\bGod JAHWEH\b/g,'de HEERE God')
 .replace(/\bJAHWEH van de legermachten\b/g,'de HEERE der heirscharen')
 .replace(/\b(op|van|aan|voor|tot|door|in|met|bij|over|onder|naast|achter|jegens|uit|na|sinds) JAHWEH\b/gi,'$1 de HEERE')
 .replace(/\b([Oo]) JAHWEH\b/g,'$1 HEERE').replace(/\bJAHWEH!/g,'HEERE!')
 .replace(/(^|[.!?]\s+)JAHWEH\b/g,'$1De HEERE').replace(/\bJAHWEH\b/g,'de HEERE')
 .replace(/\bde de HEERE\b/g,'de HEERE').replace(/\bDe de HEERE\b/g,'De HEERE')).join('');
const order = 'genesis exodus leviticus numeri deuteronomium jozua richteren ruth 1samuel 2samuel 1koningen 2koningen 1kronieken 2kronieken ezra nehemia esther job psalmen spreuken prediker hooglied jesaja jeremia klaagliederen ezechiel daniel hosea joel amos obadja jona micha nahum habakuk zefanja haggai zacharia maleachi mattheus markus lukas johannes handelingen romeinen 1korinthiers 2korinthiers galaten efeziers filippenzen kolossenzen 1tessalonicensen 2tessalonicensen 1timotheus 2timotheus titus filemon hebreeen jakobus 1petrus 2petrus 1johannes 2johannes 3johannes judas openbaring 3ezra 4ezra tobit judith boekderwijsheid jezussirach baruch estherapocrief gebedvanazaria gezangindevuuroven susanna belenddedraak gebedvanmanasse 1makkabeeen 2makkabeeen 3makkabeeen'.split(' ');
function selection() {
 const mode = $('groep').value;
 const chosen = new Set([...$('lijst').querySelectorAll('input:checked')].map(x => x.value));
 return books.filter(b => mode === 'single' ? b.id === $('boek').value : mode === 'custom' ? chosen.has(b.id) : mode === 'OT' ? b.testament === 'Oude Testament' : mode === 'NT' ? b.testament === 'Nieuwe Testament' : ['Oude Testament','Nieuwe Testament'].includes(b.testament));
}
function jobs() {
 const single = $('groep').value === 'single';
 return selection().flatMap(book => {
  const first = single ? Number($('van').value) : book.eerste_hoofdstuk;
  const last = single ? Number($('tot').value) : book.eerste_hoofdstuk + book.hoofdstukken - 1;
  if (!Number.isInteger(first) || !Number.isInteger(last) || first < book.eerste_hoofdstuk || last < first || last >= book.eerste_hoofdstuk + book.hoofdstukken) throw Error('Kies een geldig hoofdstukbereik.');
  return Array.from({length:last-first+1}, (_, i) => ({book, number:first+i}));
 });
}
function range() {
 const b = books.find(b => b.id === $('boek').value); if (!b) return;
 for (const id of ['van','tot']) { $(id).min=b.eerste_hoofdstuk; $(id).max=b.eerste_hoofdstuk+b.hoofdstukken-1; }
 $('van').value=b.eerste_hoofdstuk; $('tot').value=b.eerste_hoofdstuk+b.hoofdstukken-1;
}
function mode() { $('single').hidden=$('groep').value!=='single'; $('boeken').hidden=$('groep').value!=='custom'; }
function show(n) {
 $('error').textContent=''; step=n;
 document.querySelectorAll('[data-step]').forEach((el,i)=>el.hidden=i!==n);
 document.querySelectorAll('.uw-stappen li').forEach((el,i)=>i===n?el.setAttribute('aria-current','step'):el.removeAttribute('aria-current'));
 $('back').hidden=n===0; $('next').hidden=n===2;
 if (n===2) { const list=jobs(); $('samenvatting').textContent=`${selection().length} boek(en), ${list.length} hoofdstuk(ken) · ${$('formaat').value} · ${$('korps').value} pt · ${$('kolommen').value} kolom(men) · ${$('noten').value==='none'?'zonder kanttekeningen':'kanttekeningen onderaan elke pagina'}.`; }
 document.querySelector(`[data-step="${n}"] h2`).focus();
}
// Alleen bekende tekstmarkeringen doorlaten; nooit bron-HTML rechtstreeks invoegen.
function verseHTML(v, notes) {
 const source = document.createElement('template'); source.innerHTML=name(v.text2026_html || v.text2026 || '');
 function clean(node) {
  if (node.nodeType===3) return esc(node.textContent);
  if (node.nodeType!==1) return '';
  if (['SCRIPT','STYLE','IFRAME','OBJECT'].includes(node.tagName)) return '';
  if (node.tagName==='SUP') return notes && node.hasAttribute('data-note') ? `<sup>${esc(node.getAttribute('data-note'))}</sup>` : '';
  const text=[...node.childNodes].map(clean).join('');
  if (node.classList.contains('god-speaks')) return `<span class="god-speaks">${text}</span>`;
  return text;
 }
 return [...source.content.childNodes].map(clean).join('');
}
function chapterHTML(job, data, notes) {
 if (!Array.isArray(data.verses)) throw Error(`Geen verstekst beschikbaar voor ${job.book.naam} ${job.number}.`);
 const verses=data.verses.filter(v=>v && typeof v==='object');
 const text=verses.map(v=>`<p class="vers" data-verse="${esc(v.number)}"><b class="versnr">${esc(v.number)}</b> ${verseHTML(v,notes)}</p>`).join('');
 const annotations=notes ? verses.flatMap(v=>(Array.isArray(v.marginNotes)?v.marginNotes:[]).filter(n=>n && n.text2026).map(n=>`<p data-verse="${esc(v.number)}"><b>${esc(v.number)}:${esc(n.marker)}</b> ${esc(name(n.text2026))}</p>`)).join('') : '';
 return `<section class="chapter"><h2>${esc(job.book.naam)} ${job.number}</h2><div class="scripture">${text}</div>${annotations?`<aside><h3>Kanttekeningen</h3>${annotations}</aside>`:''}</section>`;
}
function documentHTML(chapters) {
 const format=$('formaat').value, size=Number($('korps').value), columns=Number($('kolommen').value), red=$('rood').checked;
 const title=$('titel').value.trim(), chosen=selection().map(b=>b.naam).join(' · ');
 return `<!doctype html><html lang="nl"><head><meta charset="utf-8"><title>${esc(title)}</title><link rel="stylesheet" href="${location.origin}/css/fonts.css"><style>
 @page{size:${format};margin:0}*{box-sizing:border-box}body{font-family:Georgia,'Noto Serif Hebrew',serif;color:#181818;background:white;font-size:${size}pt;line-height:1.45;margin:0}h1,h2,h3{font-weight:400;line-height:1.2}h2{font-size:1.7em;break-after:avoid}h3{break-after:avoid}.cover{break-after:page;text-align:center;padding:30mm 5mm 10mm;min-height:${format==='A4'?'245':'170'}mm}.brand{letter-spacing:.18em;font-size:9pt}.cover h1{font-size:38pt;margin:25mm 0 8mm;overflow-wrap:anywhere}.cover hr{border:0;border-top:.5pt solid #999;width:40mm;margin:10mm auto}.cover .books{font-size:10pt;line-height:1.6}.chapter{break-before:page}.scripture{column-count:${columns};column-gap:8mm;column-rule:.4pt solid #aaa}.vers{margin:0 0 .35em;orphans:2;widows:2}.versnr{font-size:.75em}.god-speaks{${red?'color:#a6141a;font-style:italic;':''}}sup{font-size:.65em}aside{border-top:.5pt solid #888;margin-top:8mm;padding-top:4mm;font-size:.85em;column-count:${columns};column-gap:8mm}aside h3{column-span:all}aside p{margin:.4em 0;orphans:2;widows:2}.colophon{font-size:9pt;border-top:1px solid #ccc;margin-top:15mm;padding-top:5mm}@media screen{body{padding:24px;max-width:${format==='A4'?'210':'148'}mm;margin:auto}.cover{border-bottom:1px solid #ddd}.chapter{margin-top:40px}}

 .paper{width:${format==='A4'?210:148}mm;height:${format==='A4'?297:210}mm;padding:14mm 15mm 12mm;box-sizing:border-box;break-after:page;position:relative;overflow:hidden;background:white}.paper-body{height:calc(100% - 14mm);position:relative;overflow:hidden}.paper .scripture{column-fill:balance;column-count:${columns};column-gap:6mm;column-rule:.4pt solid #777;overflow:hidden}.paper .page-notes{column-count:3;column-fill:auto;column-gap:4mm;border-top:.5pt solid #777;padding-top:3mm;margin:3mm 0 0;font-size:${Math.max(7,size*.73)}pt;line-height:1.22;overflow:hidden}.paper .page-notes p{margin:0 0 .45em}.running{height:9mm;text-align:center;font-variant:small-caps;font-size:10pt}.paper footer{position:absolute;bottom:6mm;left:0;right:0;text-align:center;font-size:9pt}.cover{box-sizing:border-box;width:${format==='A4'?210:148}mm;height:${format==='A4'?297:210}mm;min-height:0}.paper .page-notes[hidden]{display:none}.colophon{padding:15mm}@media screen{body{padding:0;max-width:none;background:#ddd}.paper,.cover{margin:0 auto 16px;box-shadow:0 2px 10px #0002}}@media print{html,body{padding:0;margin:0}.paper,.cover{margin:0;box-shadow:none;print-color-adjust:exact}.colophon{break-before:page}}
 </style></head><body>${$('cover').checked?`<header class="cover"><p class="brand">OPEN VERTALING</p><h1>${esc(title)}</h1><hr><p>${$('noten').value==='none'?'Leesuitgave':'Met herziene kanttekeningen'}</p><p class="books">${esc(chosen)}</p><p>openvertaling.nl</p></header>`:''}${chapters.join('')}<p class="colophon">Open Vertaling · Samengesteld op ${esc(new Date().toLocaleDateString('nl-NL'))}. Tekst en herziene kanttekeningen: CC0 / publiek domein. ${red?'Gemarkeerde Godscitaten staan rood en cursief.':''}</p></body></html>`;
}
async function build() {
 $('error').textContent=''; $('result').hidden=true;
 const queue=jobs(); if(!queue.length) return;
 controller=new AbortController();const signal=controller.signal;
 $('build').disabled=true;$('back').disabled=true;$('cancel').hidden=false;
 const result=new Array(queue.length);let at=0,done=0;
 $('status').textContent=`Hoofdstukken ophalen: 0 van ${queue.length}…`;
 try {
  await Promise.all(Array.from({length:Math.min(4,queue.length)},async()=>{
   while(at<queue.length) {
    const i=at++, j=queue[i];
    const response=await fetch(`/data/${encodeURIComponent(j.book.id)}/${j.number}.json`,{signal});
    if(!response.ok) throw Error(`${j.book.naam} ${j.number} kon niet worden opgehaald (${response.status}). Probeer opnieuw.`);
    result[i]=chapterHTML(j,await response.json(),$('noten').value!=='none');done++;
    if (!signal.aborted) $('status').textContent=`Hoofdstukken ophalen: ${done} van ${queue.length}…`;
   }
  }));
  if(signal.aborted)return;
  const frame=$('preview'); $('print').disabled=true;
  $('result').hidden=false;
  await new Promise((resolve,reject)=>{
   frame.onload=async()=>{try {
    await window.OVUitgavePaginering(frame.contentDocument,signal,(n,total)=>{
     $('status').textContent=`Pagina's opmaken: ${n} van ${total} hoofdstukken…`;
    });
    if(signal.aborted)throw new DOMException('Geannuleerd','AbortError');
    $('print').disabled=false;resolve();
   }catch(e){reject(e);}};
   frame.srcdoc=documentHTML(result);
  });
  $('status').textContent='Uw uitgave is klaar, met kanttekeningen onderaan de pagina. Open het afdrukvoorbeeld om de PDF op te slaan.';
 } catch(e) {controller.abort();$('status').textContent='';$('error').textContent=e.name==='AbortError'?'Het opbouwen is geannuleerd.':e.message;}
 finally {$('build').disabled=false;$('back').disabled=false;$('cancel').hidden=true;controller=null;}
}
$('groep').addEventListener('change',mode);$('boek').addEventListener('change',range);
$('next').addEventListener('click',()=>{try {
 if(step===0 && !jobs().length) throw Error('Kies minstens één boek.');
 if(step===1 && !$('titel').value.trim()) throw Error('Vul een titel in.');
 show(step+1);
}catch(e){$('error').textContent=e.message;}});
$('back').addEventListener('click',()=>{$('result').hidden=true;show(step-1);});
$('form').addEventListener('submit',e=>e.preventDefault());
$('build').addEventListener('click',build);$('cancel').addEventListener('click',()=>controller?.abort());
$('print').addEventListener('click',()=>{$('preview').contentWindow.focus();$('preview').contentWindow.print();});
fetch('/data/books-index.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{
 books=data.boeken.filter(b=>window.ReaderPolicy.allowsBook(b)).sort((a,b)=>order.indexOf(a.id)-order.indexOf(b.id));
 $('boek').innerHTML=books.map(b=>`<option value="${esc(b.id)}">${esc(b.naam)}</option>`).join('');
 $('lijst').innerHTML=books.map(b=>`<label class="uw-check"><input type="checkbox" value="${esc(b.id)}">${esc(b.naam)}</label>`).join('');
 $('boek').value='johannes';$('boek').disabled=false;$('next').disabled=false;range();$('tot').value='1';
 if(new URLSearchParams(location.search).get('selectie')==='custom') { $('groep').value='custom'; $('titel').value='Bijbelwoorden om te delen'; mode(); }
}).catch(()=>{$('error').textContent='De boekenlijst kon niet worden geladen. Vernieuw de pagina om opnieuw te proberen.';});
})();
