const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const cp=require('node:child_process');
test('site sync with --delete preserves independent audio and reinstalls its symlink',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'ov-audio-storage-'));
 try {
  const storage=path.join(root,'persistent'),stage=path.join(root,'stage'),site=path.join(root,'site');
  for(const p of [storage,path.join(stage,'audio'),path.join(site,'audio')]) fs.mkdirSync(p,{recursive:true});
  fs.writeFileSync(path.join(storage,'verse.mp3'),'completed audio');
  fs.symlinkSync(storage,path.join(stage,'audio','higgs-20261109'));
  fs.symlinkSync(storage,path.join(site,'audio','higgs-20261109'));
  for(let i=0;i<2;i++) cp.execFileSync('rsync',['-a','--delete',stage+'/',site+'/']);
  assert.equal(fs.readFileSync(path.join(site,'audio','higgs-20261109','verse.mp3'),'utf8'),'completed audio');
  assert.equal(fs.lstatSync(path.join(site,'audio','higgs-20261109')).isSymbolicLink(),true);
 } finally {fs.rmSync(root,{recursive:true,force:true});}
});
