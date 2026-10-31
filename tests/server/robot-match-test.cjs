const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('server/public_html/Neptune/autoscout/robot-labels.php','utf8');
const start=html.indexOf("(()=>{\n const app=document.getElementById('robot-labels-app'),picker=");
const script=html.slice(start,html.indexOf('</script>',start));
class Element{constructor(){this.dataset={};this.value='';this.attrs={};this.events={};this.loads=0;}addEventListener(n,f){this.events[n]=f;}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k]??null;}load(){this.loads++;}replaceChildren(...children){this.children=children;}}
const elements={};const el=id=>elements[id]??=new Element();let tick,data={requests:[{kind:'test_robot',state:'failed',message:'Download failed'}],robot_tests:[],youtube:{connected:true}},upload;
vm.runInNewContext(script,{document:{getElementById:el},location:{pathname:'/autoscout/robot-labels.php'},Option:class{constructor(text,value){this.text=text;this.value=value;}},Date,Number,encodeURIComponent,setInterval:f=>{tick=f;},fetch:async(url,opt)=>{if(opt){upload=JSON.parse(opt.body);return {ok:true,json:async()=>({test:{...data.robot_tests[0],title:upload.title,description:upload.description,youtube_id:'uploadedid1',privacy:'unlisted'}})};}return{ok:true,json:async()=>data};}});
const settle=()=>new Promise(r=>setImmediate(r));
(async()=>{
 await settle();assert.match(el('robot-test-status').textContent,/failed.*Download failed/);
 const test={id:'test1',has_video:false,title:'Default title',description:'Default description',match_key:'2026test_qm1'};
 data={...data,requests:[],robot_tests:[test]};await tick();assert.equal(el('robot-test-viewer').hidden,false);
 data.robot_tests=[{...test,has_video:true}];await tick();assert.match(el('robot-test-video').getAttribute('src'),/robot_test_video=test1/);assert.equal(el('robot-test-download').hidden,false);
 el('robot-test-title').value='My title';el('robot-test-title').events.input();el('robot-test-desc').value='My description';el('robot-test-desc').events.input();await tick();assert.equal(el('robot-test-title').value,'My title');
 await el('robot-test-upload').events.click();assert.equal(upload.action,'upload_robot_test_youtube');assert.equal(upload.title,'My title');assert.equal(upload.description,'My description');assert.match(el('robot-test-yt-status').innerHTML,/uploadedid1/);
 console.log('PASS failed job visible; first result displayed; same-result video availability loads; edits survive polling; YouTube receives edits');
})().catch(e=>{console.error(e);process.exitCode=1;});
