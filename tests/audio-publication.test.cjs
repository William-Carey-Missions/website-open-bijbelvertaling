const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function audio(voice='m') {
 const ctx={localStorage:{getItem:()=>voice,setItem:()=>{}},OV_ASSETS:{url:p=>'https://kleineark.com/assets/openvertaling/'+p}};ctx.window=ctx;
 vm.runInNewContext(fs.readFileSync('js/audio-available.js','utf8'),ctx);
 return ctx;
}
test('only finished published chapters become playable in the correct edition',()=>{
 const c=audio();const a=c.OV_AUDIO;
 a.published={exodus:{m:[1]}};
 assert.equal(a.available('exodus',1),true);
 assert.equal(a.available('exodus',2),false);
 assert.equal(a.src('exodus',1),'/audio/higgs-20261109/nl-ov/exodus/1-m.mp3');
 assert.equal(a.timingSrc('exodus',1,'m'),'/audio/higgs-20261109/nl-ov/exodus/1-m.json');
 c.TekstEditie={code:()=> 'nl-opv'};assert.equal(a.available('exodus',1),false);
});
test('a chapter with only a new male voice falls back from unavailable female voice',()=>{
 const a=audio('v').OV_AUDIO;a.published={exodus:{m:[1]}};
 assert.deepEqual(Array.from(a.voices('exodus',1)),['m']);
 assert.equal(a.voiceFor('exodus',1),'m');
 assert.match(a.src('exodus',1),/1-m\.mp3$/);
});
test('existing female audio keeps its original asset location',()=>{
 const a=audio('v').OV_AUDIO;a.published={genesis:{m:[1]}};
 assert.equal(a.voiceFor('genesis',1),'v');
 assert.equal(a.src('genesis',1),'https://kleineark.com/assets/openvertaling/audio/genesis/1-v.mp3');
});
test('Open Parafrase uses its own recordings and never the legacy Open Vertaling files',()=>{
 const c=audio('v'),a=c.OV_AUDIO;
 a.published={genesis:{m:[1,2]}};
 a.publishedEditions={'nl-opv':{genesis:{m:[1]}}};
 c.TekstEditie={code:()=> 'nl-opv'};
 assert.equal(a.available('genesis',1),true);
 assert.equal(a.available('genesis',2),false);
 assert.equal(a.voiceFor('genesis',1),'m');
 assert.equal(a.src('genesis',1),'/audio/higgs-20261109/nl-opv/genesis/1-m.mp3');
 assert.equal(a.timingSrc('genesis',1,'m'),'/audio/higgs-20261109/nl-opv/genesis/1-m.json');
});
