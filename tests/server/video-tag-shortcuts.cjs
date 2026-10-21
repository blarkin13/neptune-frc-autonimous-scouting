const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),cp=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const controls=JSON.parse(cp.execFileSync('php',['-r',"require 'neptune_secure/community-video-tags.php';echo json_encode(community_video_tag_controls());"],{cwd:root,encoding:'utf8'}));
const source=fs.readFileSync(path.join(root,'public_html/Neptune/community/assets/video-tags.js'),'utf8');
const start=source.indexOf("document.addEventListener('keydown',"),end=source.indexOf("window.addEventListener('beforeunload'",start);assert(start>=0&&end>start);
let handler,clicked=[];
const make=id=>({id,disabled:false,click(){clicked.push(id);}});
const buttons=Object.entries(controls).flatMap(([,entries])=>Object.entries(entries).map(([key,value])=>({...make(key),dataset:{shortcut:value[1].toLowerCase()}})));
const robots=Array.from({length:6},(_,i)=>make('robot'+(i+1))),transport={scoringEditor:{hidden:true},shareEditor:{hidden:true},playPause:make('playPause'),rewind:make('rewind'),undoLast:make('undoLast')};
vm.runInNewContext(source.slice(start,end),{document:{addEventListener(type,fn){assert.equal(type,'keydown');handler=fn;},querySelectorAll(){return robots;}},buttons,byId:id=>transport[id],panView:()=>false});
const event=(key,extra={})=>({key,ctrlKey:false,metaKey:false,altKey:false,repeat:false,target:{closest(){return false;}},preventDefault(){this.prevented=true;},...extra});
for(const b of buttons){clicked=[];const e=event(b.dataset.shortcut);handler(e);assert.deepEqual(clicked,[b.id]);assert(e.prevented);}
for(let i=1;i<=6;i++){clicked=[];handler(event(String(i)));assert.deepEqual(clicked,['robot'+i]);}
for(const [key,id] of [[' ','playPause'],['r','rewind'],['u','undoLast']]){clicked=[];handler(event(key));assert.deepEqual(clicked,[id]);}
for(const extra of [{ctrlKey:true},{metaKey:true},{altKey:true},{repeat:true},{target:{closest(){return true;}}}]){clicked=[];handler(event('s',extra));assert.deepEqual(clicked,[]);}
buttons[0].disabled=true;clicked=[];handler(event(buttons[0].dataset.shortcut));assert.deepEqual(clicked,[]);
console.log('PASS all 19 tag shortcuts, six robot keys, playback/undo keys, input/modifier/repeat guards, and disabled controls');

const panStart=source.indexOf('function panView(event)'),panEnd=source.indexOf("byId('videoZoom').addEventListener",panStart);
let applied=0;const panContext=vm.createContext({zoom:5,origin:[50,50],byId:()=>({getBoundingClientRect:()=>({width:1200,height:600})}),applyView(){applied++;}});
vm.runInContext(source.slice(panStart,panEnd),panContext);
for(const [key,axis,sign] of [['ArrowLeft',0,-1],['ArrowRight',0,1],['ArrowUp',1,-1],['ArrowDown',1,1]]){
 panContext.origin=[50,50];const e=event(key);assert.equal(panContext.panView(e),true);assert.equal(Math.sign(panContext.origin[axis]-50),sign);assert(e.prevented);
}
panContext.origin=[50,50];panContext.panView(event('ArrowRight'));const normal=panContext.origin[0]-50;
panContext.origin=[50,50];panContext.panView(event('ArrowRight',{shiftKey:true,repeat:true}));assert(Math.abs(panContext.origin[0]-50-normal*3)<1e-9);
panContext.origin=[0,100];panContext.panView(event('ArrowLeft'));panContext.panView(event('ArrowDown'));assert.equal(panContext.origin[0],0);assert.equal(panContext.origin[1],100);
panContext.zoom=1;const noZoom=event('ArrowRight');assert.equal(panContext.panView(noZoom),false);assert(!noZoom.prevented);
const page=fs.readFileSync(path.join(root,'public_html/Neptune/community/tag-video.php'),'utf8');assert(page.includes('<option value="4">4×</option>')&&page.includes('<option value="5">5×</option>'));
console.log('PASS 4×/5× zoom, all arrow directions, held-arrow repeats, Shift speed, pan bounds, and 1× passthrough');
