const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('public_html/Neptune/community/assets/training-control.js','utf8');
const getSource=source.slice(source.indexOf(' async function get('),source.indexOf(' async function send('));
const refreshSource=source.slice(source.indexOf(' async function refresh('),source.indexOf(' async function checkServer('));
(async()=>{
 let timer,cleared=false;
 const ctx=vm.createContext({URL,AbortController,TypeError,Error,season:2026,location:{pathname:'/admin/community-learning.php',origin:'https://neptunefrc.com'},setTimeout(fn){timer=fn;return 1;},clearTimeout(){cleared=true;},fetch:async()=>{throw new TypeError('Load failed');}});
 vm.runInContext(getSource,ctx);
 await assert.rejects(ctx.get({panel:1}),/progress connection was interrupted/);assert(cleared);
 ctx.fetch=async(_url,opts)=>new Promise((_,reject)=>opts.signal.addEventListener('abort',()=>reject(Object.assign(new Error('timeout'),{name:'AbortError'}))));
 const pending=ctx.get({panel:1});timer();await assert.rejects(pending,/progress connection was interrupted/);
 const saved={jobs:[{id:'saved',state:'candidate'}]};let warning='';const message={hidden:false};let calls=0;
 Object.assign(ctx,{panel:saved,polling:false,selectedRun:'saved',following:null,$:()=>message,pageMessage:text=>warning=text,render(){},get:async()=>{calls++;if(calls===1)throw new Error('Neptune’s progress connection was interrupted.');return {jobs:[{id:'saved',state:'candidate',report:{saved:true}}]};}});
 vm.runInContext(refreshSource,ctx);await ctx.refresh();assert.equal(ctx.panel,saved);assert.equal(ctx.polling,false);assert.match(warning,/do not need to restart training/);
 await ctx.refresh();assert.equal(ctx.panel.jobs[0].report.saved,true);assert.equal(message.hidden,true);
 console.log('PASS interrupted and timed-out progress requests preserve state, release polling, and recover on the next read without restarting training');
})().catch(e=>{console.error(e);process.exitCode=1;});
