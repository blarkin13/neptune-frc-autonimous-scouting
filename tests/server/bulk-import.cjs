const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const text=fs.readFileSync('public_html/Neptune/community/assets/training-control.js','utf8');
const begin=text.indexOf(' async function bulkExternalAction('),end=text.indexOf(' function chooseFiles(',begin);
assert(begin>0&&end>begin);
const nodes={};const $=id=>nodes[id]??=( {value:id==='external-format'?'viper':'0',disabled:false,hidden:true,textContent:''});
const calls=[],entries=[{file:{name:'2026week0.dat-2.json'},status:'Not checked'},{file:{name:'2026mawne.dat.json'},status:'Not checked'},{file:{name:'broken.dat.json'},status:'Not checked'}];
const context={$,bulkBusy:false,bulkEntries:entries,renderBulk(){},async refresh(){calls.push('refresh');},async send(action,args){calls.push([action,args]);if(args.csv.name==='broken.dat.json')throw Error('Unreadable JSON');if(action==='preview_external')return {file_sha256:args.csv.name,report:{source_event_key:args.csv.name==='2026week0.dat-2.json'?'2026week0':'2026mawne',video_check:{ready:args.csv.name==='2026week0.dat-2.json'}},event_key:'source'};return {existing:true};}};
vm.createContext(context);vm.runInContext(text.slice(begin,end)+';this.runBulk=bulkExternalAction;',context);
(async()=>{
 await context.runBulk(false);assert.equal(calls.filter(Array.isArray).length,3);assert.equal(entries[0].status,'Ready to import');assert.equal(entries[1].status,'Blocked — video / roster check');assert.equal(entries[2].error,'Unreadable JSON');assert.equal($('import-external').hidden,false);
 calls.length=0;await context.runBulk(true);const sent=calls.filter(Array.isArray);assert.equal(sent.length,1);assert.equal(sent[0][0],'import_external');assert.equal(sent[0][1].source,'https://public.viperscout.com/export.html#event=2026week0');assert.equal(sent[0][1].preview_sha256,'2026week0.dat-2.json');assert.equal(entries[0].status,'Already imported — no duplicate');assert.equal($('external-file').disabled,false);assert.equal(context.bulkBusy,false);
 calls.length=0;await context.runBulk(true);assert.equal(calls.filter(Array.isArray).length,0);
 console.log('PASS multiple event previews, independent errors, video gate, per-file provenance, duplicate handling, controls restored, and repeat import skips saved files');
})().catch(e=>{console.error(e);process.exitCode=1;});
