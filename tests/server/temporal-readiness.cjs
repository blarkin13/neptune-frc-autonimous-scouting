const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('public_html/Neptune/community/assets/training-control.js','utf8');
const a=source.indexOf(' function readinessMessage('),b=source.indexOf(' function renderProgress(',a);
assert(a>=0&&b>a);const ctx=vm.createContext({runProblem:s=>s});vm.runInContext(source.slice(a,b),ctx);
const msg=ctx.readinessMessage({state:'needs_data',report:{positive_examples:6,scoring:{examples:2},inventory:{localization_errors:[{},{}]}}});
assert(msg.includes('6 usable positive action examples'));assert(msg.includes('2 usable scoring examples'));assert(msg.includes('2 matches could not be read'));assert(msg.includes('tags and imports are kept'));
assert(!ctx.readinessMessage({state:'needs_data'}).includes('undefined'));
assert.equal(ctx.readinessMessage({state:'candidate',message:'Saved'}),'Saved');
console.log('PASS no-model result reports usable evidence and unreadable matches without claiming tags were lost');
