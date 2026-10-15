const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('reader always uses Open Vertaling despite a saved or linked edition', () => {
    const context = { window: { addEventListener() {} }, location: { href: 'https://openvertaling.nl/?editie=en-webbe' }, URL,
        localStorage: { getItem: () => JSON.stringify({ teksteditie: 'fr-lsg1910' }) } };
    vm.runInNewContext(fs.readFileSync('js/teksteditie.js', 'utf8'), context);
    assert.equal(context.window.TekstEditie.code(), 'nl-ov');
});

test('saved research and translation options cannot change the fixed reading text', () => {
    const context = { window: {} };
    vm.runInNewContext(fs.readFileSync('js/optie-maten.js', 'utf8'), context);
    vm.runInNewContext(fs.readFileSync('js/opties.js', 'utf8') + ';globalThis.options = Opties;', context);
    const options = context.options;
    options.state = { godsnaam: 'ov', strongs: 'aan', teksteditie: 'en-webbe', parallelEdities: ['fr-lsg1910'], ethiopischeBoeken: 'aan', heereNT: 'here' };
    options.enforceReaderOptions();
    assert.equal(options.state.godsnaam, 'klassiek');
    assert.equal(options.state.strongs, 'uit');
    assert.equal(options.state.teksteditie, 'nl-ov');
    assert.equal(options.state.parallelEdities.length, 0);
    assert.equal(options.state.ethiopischeBoeken, 'uit');
    assert.equal(options.state.heereNT, 'heere');
    assert.match(options.transformOV('JAHWEH schiep de hemel.', 'OT'), /HEERE/);
});

test('all New Testament books are verified without a concept warning', () => {
    const context = { window: {}, document: { addEventListener() {} } };
    vm.runInNewContext(fs.readFileSync('js/reader-policy.js', 'utf8'), context);
    context.ReaderPolicy = context.window.ReaderPolicy;
    vm.runInNewContext(fs.readFileSync('js/verification.js', 'utf8'), context);
    const books = JSON.parse(fs.readFileSync('data/books.json', 'utf8')).books;
    assert.equal(books.filter(book => book.testament === 'NT').length, 27);
    for (const book of books.filter(book => book.testament === 'NT')) {
        assert.equal(context.window.Verification.chapterVerified({}, book.id, 1), true);
        assert.equal(context.window.Verification.warning(book.id, 1), '');
    }
    assert.equal(context.ReaderPolicy.allowsBook({ id: 'henoch' }), false);
});
test('published pages only reference scripts that still exist', () => {
    for (const file of fs.readdirSync('.').filter(name => name.endsWith('.html'))) {
        const html = fs.readFileSync(file, 'utf8');
        for (const match of html.matchAll(/<script[^>]+src="([^"?]+)(?:\?[^"\s]*)?"/g)) {
            if (/^https?:/.test(match[1])) continue;
            assert.ok(fs.existsSync(match[1].replace(/^\//, '')), file + ': ' + match[1]);
        }
    }
});

test('concurrent chapter reads fetch once and keep nonstandard chapter numbers', async () => {
    let manifestRequests = 0, chapterRequests = 0;
    const context = {
        window: {}, ReaderPolicy: { allowsBook: book => book.id !== 'henoch' },
        fetch: async () => { manifestRequests++; return { ok: true, json: async () => ({ books: [
            {id:'estherapocrief',chaptersIncluded:[10,11],totalChapters:2}, {id:'henoch',chaptersIncluded:[1]}
        ] }) }; },
        Verification: { loadJSON: async () => { chapterRequests++; await Promise.resolve(); return { verses: [] }; } },
        Storage: { getEdits: () => null }
    };
    vm.runInNewContext(fs.readFileSync('js/data-loader.js','utf8'), context);
    const loader = context.window.DataLoader;
    const [a,b] = await Promise.all([loader.loadChapter('estherapocrief',10),loader.loadChapter('estherapocrief',10)]);
    assert.equal(a,b);
    assert.equal(manifestRequests,1);
    assert.equal(chapterRequests,1);
    assert.equal(await loader.loadChapter('estherapocrief',1),null);
    assert.equal(await loader.loadChapter('henoch',1),null);
    assert.equal(chapterRequests,1);
});

test('offline shell only precaches files present in the publication', () => {
    const context = { self: { addEventListener() {} } };
    vm.runInNewContext(fs.readFileSync('sw.js','utf8') + ';globalThis.urls=PRECACHE_URLS;', context);
    for (const url of context.urls) assert.ok(url === '/' || fs.existsSync(url.slice(1)), url);
});

test('rendering a chapter never reads hidden research data or decorates the first letter', async () => {
    const nodes = new Map();
    const container = { children: [], appendChild(node) {this.children.push(node);} };
    nodes.set('verses-container',container);
    const document = { getElementById: id => nodes.get(id) || null,
        createElement: () => ({dataset:{},querySelector:()=>({addEventListener(){}})}) };
    const verse = {number:1,text2026:'Paulus, een apostel.'};
    for (const name of ['grondtekst','phraseDiff','textSV1888']) Object.defineProperty(verse,name,{get(){throw Error('Hidden research was accessed');}});
    const context = {window:{},document,
        App: {_laadVerified:async()=>{},_pericopen:{},_isVerified:()=>true,_setTitle(){},_updateAudioPlayer(){},_updateVerifiedBanner(){},_afterRenderContinuous(){},_clearVerseFocus(){},_applyDropcap(){throw Error('Decorative initial was applied');}},
        DataLoader:{loadBook:async()=>({id:'efeziers',nameDutch:'Efeziërs',testament:'NT'}),loadChapter:async()=>({verses:[verse]}),prefetchAdjacent(){}},
        Opties:{transformOV:text=>text},Editor:{attachVerseListeners(){}},Verification:{readerRendered(){}}
    };
    vm.runInNewContext(fs.readFileSync('js/chapter-renderer.js','utf8')+';globalThis.renderer=ChapterRenderer;',context);
    await context.renderer.renderChapter.call({updateProgress(){},updateGrid(){}},'efeziers',1);
    assert.equal(container.children.length,1);
    assert.match(container.children[0].innerHTML,/Paulus, een apostel/);
    assert.equal((container.children[0].innerHTML.match(/<div/g)||[]).length,2);
});

test('reader startup renders a chapter with the audio updater present', async () => {
const ids=new Set([...fs.readFileSync('index.html','utf8').matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
function node(){return {style:{},dataset:{},children:[],classList:{add(){},remove(){},toggle(){},contains(){return false}},appendChild(n){this.children.push(n)},querySelector(){return node()},querySelectorAll(){return []},addEventListener(){},setAttribute(){},remove(){},pause(){},removeAttribute(){},closest(){return null},checked:true};}
const nodes=new Map([...ids].map(id=>[id,node()]));
const c={console,setTimeout(){},window:null,location:{hash:'#johannes/1'},localStorage:{getItem(){return null},setItem(){}},document:{addEventListener(){},getElementById:id=>nodes.get(id)||null,querySelectorAll:()=>[],querySelector:()=>null,createElement:node,body:node(),documentElement:node()},addEventListener(){},scrollTo(){},matchMedia(){return {matches:false}},fetch:async url=>{const p=String(url); const data=JSON.parse(fs.readFileSync(p,'utf8'));return {ok:true,json:async()=>data}},ReaderPolicy:{allowsBook:()=>true},Verification:{loadChapters:async()=>{},loadJSON:async url=>JSON.parse(fs.readFileSync(url,'utf8')),chapterVerified:()=>true,readerRendered(){}},VerificationDisplay:{readerTitle(){},banner(){}},Editor:{init(){},attachVerseListeners(){}},References:{init(){}},Storage:{getEdits(){return null}}};
c.window=c;vm.createContext(c);
for(const f of ['js/optie-maten.js','js/opties.js','js/book-orders.js','js/data-loader.js','js/navigation.js','js/sidebar.js','js/chapter-renderer.js','js/app.js'])vm.runInContext(fs.readFileSync(f,'utf8'),c,{filename:f});
await vm.runInContext('App._setupAudioPlayer=()=>{};App.init()',c);
assert.ok(nodes.get('verses-container').children.some(row => /Woord/.test(row.innerHTML || '')));
});

test('about page explains Open Vertaling and credits William Carey Missions', () => {
const html=fs.readFileSync('over-ov.html','utf8');
for(const text of ['Wat is de Open Vertaling?','Doel en aanleiding','Uitgangspunt: een eerlijke vermenging','Werkwijze','William Carey Missions']) assert.ok(html.includes(text),text);
assert.ok(html.replace(/<[^>]*>/g,'').length>4500);
assert.ok(fs.readFileSync('js/topnav.js','utf8').includes('href="/over-ov.html">Over ons'));
});
