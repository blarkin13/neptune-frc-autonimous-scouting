'use strict';
// Auto Scout pillars (Robots, Field, Actions): helper status bar, model in use, what's needed next, Train, past runs.
// Fills whichever pillar cards are on the page. Data and actions go through train.php.
(()=>{
 const app=document.getElementById('pillar');if(!app)return;
 const season=app.dataset.season,csrf=app.dataset.csrf,endpoint=app.dataset.endpoint||'/autoscout/train.php';
 const $$=s=>[...document.querySelectorAll(s)];
 const esc=t=>String(t??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
 const when=t=>t?new Date(t*1000).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'—';
 const pct=v=>v==null?'—':Math.round(v*100)+'%';
 const slot=(name,key)=>document.querySelector(`[data-part="${name}"] [data-slot="${key}"], [data-part="${name}"][data-slot="${key}"]`);
 const fill=(name,key,html)=>{const s=slot(name,key);if(s)s.innerHTML=html};

 // In-page tabs: [data-tabs] holds buttons [data-tab]; panels are [data-panel] in the same pillar. Remembered in the address.
 const tabs=$$('[data-tabs] [data-tab]'),panels=$$('[data-panel]');
 function show(name){
  if(!tabs.length||!tabs[0].closest('[data-tabs]').offsetParent)return;   // no tabs, or on another view of the page
  if(!tabs.some(t=>t.dataset.tab===name))name=tabs[0].dataset.tab;
  for(const t of tabs)t.setAttribute('aria-selected',String(t.dataset.tab===name));
  for(const p of panels)p.hidden=p.dataset.panel!==name;
  if(location.hash!=='#'+name)history.replaceState(null,'','#'+name);
 }
 for(const t of tabs)t.addEventListener('click',()=>show(t.dataset.tab));
 // Older code scrolls to sections (for example the run report); open their tab first.
 const scroll=Element.prototype.scrollIntoView;
 Element.prototype.scrollIntoView=function(...a){const p=this.closest('[data-panel]');if(p&&p.hidden)show(p.dataset.panel);return scroll.apply(this,a)};
 show(location.hash.slice(1));
 addEventListener('hashchange',()=>show(location.hash.slice(1)));

 async function send(values){
  const body=new FormData();body.set('csrf',csrf);body.set('season',season);for(const [k,v] of Object.entries(values))body.set(k,v);
  const r=await fetch(endpoint,{method:'POST',body,headers:{Accept:'application/json'}});const d=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(d.error||'Could not save');return d;
 }

 const runState=r=>r.state==='done'?(r.report?.adopted?'<span class="tt-badge ok">Switched to it</span>':'<span class="tt-badge">Kept the one in use</span>'):r.state==='failed'?'<span class="tt-badge warn">Failed</span>':r.state==='cancelled'?'<span class="tt-badge">Cancelled</span>':r.state==='claimed'?'<span class="tt-badge ok">Running</span>':'<span class="tt-badge">Waiting</span>';
 function runs(list,score){
  if(!list.length)return '<p class="training-note">No runs yet.</p>';
  return '<table class="tt-runs"><tr><th>Started</th><th>Result</th><th>New vs in use</th><th>Review video</th><th>Details</th></tr>'+list.slice(0,8).map(r=>`<tr><td>${when(r.created_at)}</td><td>${runState(r)}${['queued','claimed'].includes(r.state)?` <button type="button" class="button-secondary tt-cancel" data-cancel="${esc(r.id)}">Cancel</button>`:''}</td><td>${r.report?score(r.report):'—'}</td><td>${video(r.review)}</td><td class="tt-msg">${esc(r.message)}</td></tr>`).join('')+'</table>';
 }
 // Review video on YouTube (private until the API project passes YouTube's audit).
 const video=v=>!v?'—':v.youtube_id?`<a href="https://youtu.be/${esc(v.youtube_id)}" target="_blank" rel="noopener">▶ Watch</a>${v.privacy==='private'?' <small>(private)</small>':''}`:v.status==='youtube_not_connected'?'<a href="/autoscout/youtube.php">Connect YouTube</a>':v.status==='upload_failed'?`<span title="${esc(v.error)}">Upload failed</span>`:'—';
 const placed=p=>!p||!p.found?'none found':`${p.found}/${p.expected} · ${(p.mean_error*100).toFixed(1)}% off`;
 const next=(items)=>items.map(([ok,text])=>`<li class="${ok?'tt-ok':'tt-todo'}">${text}</li>`).join('');
 function trainButton(name,disabled,note){
  const b=document.querySelector(`[data-part="${name}"] [data-train]`);if(b)b.disabled=disabled;
  const s=slot(name,'train-note');if(s)s.textContent=note;
 }
 const rollback=(name,has)=>{for(const b of $$(`[data-rollback="${name}"]`))b.hidden=!has};

 function robot(d,busy){
  const c=d.current,rep=c?.report||{};
  fill('robot','current',c?`<dl><dt>Adopted</dt><dd>${when(c.adopted_at)}</dd><dt>Held-out match</dt><dd>${esc(rep.holdout_match||'—')}</dd><dt>Bumpers found</dt><dd>${pct(rep.new?.recall)} (precision ${pct(rep.new?.precision)})</dd><dt>Learned from</dt><dd>${rep.train_frames??'—'} frames, ${(rep.matches||[]).length} matches</dd></dl>`:'<p>The built-in detector that came with the helper. It has not been retrained here yet.</p>');
  rollback('robot',d.history);
  const m=Object.entries(d.matches),ready=m.filter(([,n])=>n>=d.min_frames),frames=m.reduce((a,[,n])=>a+n,0);
  // Frames per match, fewest first: which matches still need frames before training can use them.
  const rows=(d.rows||[]).map(r=>`<tr${r.frames<d.min_frames?' class="tt-short"':''}><td>${r.match_id?`<a href="/autoscout/robot-labels.php?match_id=${r.match_id}">${esc(r.match_key||r.video_id)}</a>`:esc(r.match_key||r.video_id)}${r.match_key===d.holdout?' <small>(held out)</small>':''}</td><td>${r.frames}</td><td>${r.frames<d.min_frames?`needs ${d.min_frames-r.frames} more`:'✓ used'}</td></tr>`).join('');
  fill('robot','data',`<dl><dt>Labelled frames</dt><dd>${frames}</dd><dt>Matches</dt><dd>${m.length} (${ready.length} with ${d.min_frames}+ frames)</dd><dt>Events</dt><dd>${d.events.length?d.events.map(esc).join(', '):'—'}</dd></dl>`+(rows?`<details class="tt-runs-more" open><summary>Frames per match</summary><table class="tt-runs"><tr><th>Match</th><th>Frames</th><th></th></tr>${rows}</table></details>`:''));
  fill('robot','next',next([
   [ready.length>=2,`Label ${d.min_frames}+ frames in at least 2 matches (${ready.length} so far). One is held back for checking: never one the detector in use learned from.`],
   ...(d.holdout?[[true,`Next run is checked on <strong>${esc(d.holdout)}</strong>.`]]:[]),
   [d.events.length>=2,`Label matches from a second event so the detector works beyond one venue (${d.events.length} so far).`],
   [!!c,c?'A trained detector is in use. Label more frames and retrain whenever tracking misses robots.':'Train the first detector.'],
  ]));
  trainButton('robot',busy||ready.length<2,busy?'A robot detector run is already queued or running.':ready.length<2?'Needs labelled frames in 2 matches first.':'About an hour on a helper. It only switches if the new detector is clearly better.');
  fill('robot','runs',runs(d.runs,r=>`F1 ${r.new?.f1?.toFixed(2)??'—'} vs ${r.current?r.current.f1.toFixed(2):'none'}`));
  return !c||ready.length<2;
 }
 function field(d,busy){
  const c=d.current,rep=c?.report||{};
  fill('field','current',c?`<dl><dt>Adopted</dt><dd>${when(c.adopted_at)}</dd><dt>Held-out match</dt><dd>${esc(rep.holdout_match||'—')}</dd><dt>Targets & corners</dt><dd>${placed(rep.new)}</dd><dt>Learned from</dt><dd>${rep.matches??'—'} matches</dd></dl>`:`<p>No field detector has been trained for ${esc(d.game_key)} here yet.</p>`);
  rollback('field',d.history);
  const m=Object.entries(d.matches),ready=m.filter(([,v])=>v.targets&&v.corners);
  fill('field','data',`<dl><dt>Marked matches</dt><dd>${m.length}</dd><dt>With targets + corners</dt><dd>${ready.length}</dd><dt>Events</dt><dd>${d.events.length?d.events.map(esc).join(', '):'—'}</dd></dl>`);
  fill('field','next',next([
   [ready.length>=2,`Mark scoring targets and all four field corners on at least 2 ${esc(d.game_key)} matches (${ready.length} so far).`],
   ...(d.holdout?[[true,`Next run is checked on <strong>${esc(d.holdout)}</strong>, a match the detector in use never learned from.`]]:[]),
   [d.events.length>=2,`Mark a match from a second event; camera angles differ between venues (${d.events.length} so far).`],
   [!!c,c?'A trained detector is in use. New events get scoring areas without marking.':'Train the first field detector.'],
  ]));
  trainButton('field',busy||ready.length<2,busy?'A field detector run is already queued or running.':ready.length<2?'Needs scoring targets and corners on 2 matches of this game first.':'About 20–40 minutes on a helper. It only switches if targets and corners land closer.');
  fill('field','runs',runs(d.runs,r=>`${placed(r.new)} vs ${r.current?placed(r.current):'none'}`));
  return !c||ready.length<2;
 }
 function actions(d,o){
  const l=d.latest,c=d.counts||{};
  fill('actions','current',l?`<dl><dt>Latest model</dt><dd>${when(l.created_at)}</dd><dt>Released</dt><dd>${d.released?(d.released===l.id?'Yes, this one':'An earlier model'):'Not yet — evaluate it on Test & release'}</dd></dl>`:'<p>No action model yet.</p>');
  fill('actions','data',`<dl><dt>Tagged matches</dt><dd>${c.matches??0}</dd><dt>Human tags</dt><dd>${c.tags??0}</dd><dt>Scoring estimates</dt><dd>${c.scores??0}</dd><dt>Imported actions</dt><dd>${c.external??0}</dd></dl>`);
  const changed=[['robot',o.robot.current],['field',o.field.current]].filter(([,cur])=>cur&&l&&cur.adopted_at>l.created_at).map(([n])=>n==='robot'?'robot detector':'field detector');
  fill('actions','next',next([
   [!!o.robot.current,'Robots pillar trained — tracking follows robots better.'],
   [(c.matches??0)>=10,`Tag at least 10 matches or import scouting (${c.matches??0} so far).`],
   [!changed.length,changed.length?`The ${changed.join(' and ')} changed after this model was trained — retrain so it learns from the better tracking.`:'Model is up to date with the detectors.'],
   [!!l,l?'Try it on a match, then evaluate it on Test & release.':'Train the first model below.'],
  ]));
  fill('actions','runs','<p class="training-note">Every run with its report is on the <a href="#train">Train</a> tab, under “Your training results”.</p>');
  return !l||changed.length>0;
 }

 async function refresh(){
  const status=k=>document.querySelector(`#pillar-status [data-slot="${k}"]`);
  let o;try{const r=await fetch(`${endpoint}?overview=1&season=${encodeURIComponent(season)}`,{headers:{Accept:'application/json'}});o=await r.json();if(!r.ok)throw Error(o.error)}catch(e){if(status('helpers'))status('helpers').textContent='Status unavailable: '+e.message;return}
  const on=o.helpers.filter(h=>h.online);
  if(status('helpers'))status('helpers').textContent=on.length?on.map(h=>`${h.name} · ${h.working?'working':h.ready?'ready':h.status}`).join('\n'):(o.helpers.length?'No helper open. Open the helper app on your computer.':'No helper connected — see Helpers & settings.');
  const running=o.queue.filter(q=>q.state==='running'),waiting=o.queue.filter(q=>q.state==='waiting');
  // "Pillar — part", then the helper's step lines (minus its own job title), then what it learns from.
  const line=q=>[q.label||q.title,(q.message||'').replace(/^[^\n]*? · (step \d+ of \d+)/,'$1'),q.about].filter(Boolean).join('\n');
  // Each running job as a card: what it is, a progress bar with % and time left, the step in plain words, then next.
  const job=q=>{const lines=(q.message||'').split('\n');const get=p=>(lines.find(l=>l.startsWith(p))||'').slice(p.length).trim();
   const step=(lines.find(l=>l.includes(' · step '))||'').replace(/^.*? · step (\d+ of \d+): ?/,'Step $1 · ');const prog=get('Progress:').match(/(\d+)%(?: · (.*))?/);
   let now=get('Now:').replace(/^Training (robot|field) detector: /,''),pct=prog?+prog[1]:null,eta=prog?prog[2]:null;
   // Older helpers send no progress line: estimate from "pass P of up to E · batch B of N" (training is ~80% of a detector run).
   const pass=!prog&&now.match(/pass (\d+) of up to (\d+)(?: · batch (\d+) of (\d+))?/);
   if(pass){const f=((+pass[1]-1)+(pass[3]?pass[3]/pass[4]:0))/pass[2];pct=Math.round(100*(.1+.82*f));
    const ran=q.started?Date.now()/1000-q.started:0;if(ran>60&&pct>3){const s=ran/(pct/100)*(1-pct/100);eta=(s<3600?'about '+Math.round(s/60)+' min':'about '+(s/3600).toFixed(1)+' h')+' left'}}
   return `<div class="tt-job"><div class="tt-job-head"><strong>${esc(q.label||q.title)}</strong>${pct!==null?`<span>${pct}%${eta?' · '+esc(eta):''}</span>`:''}</div>`+
    (pct!==null?`<div class="tt-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>`:'')+
    `<div class="tt-job-step">${esc(step||q.title)}${now?' — '+esc(now):''}</div>`+(get('Next:')?`<div class="tt-job-more">Next: ${esc(get('Next:'))}</div>`:'')+(q.about?`<div class="tt-job-more">${esc(q.about)}</div>`:'')+'</div>'};
  if(status('now'))status('now').innerHTML=running.length?running.map(job).join(''):'<span class="tt-idle">Nothing running</span>';
  if(status('waiting'))status('waiting').textContent=waiting.length?waiting.map(q=>`• ${q.label||q.title}`).join('\n'):'Nothing';
  const busy=k=>o.queue.some(q=>q.part===k);
  const needs={robot:robot(o.robot,busy('robot')),field:field(o.field,busy('field')),actions:actions(o.actions,o)};
  fill('test','videos',(o.test_videos||[]).length?'<table class="tt-runs"><tr><th>Made</th><th>Match</th><th>Video</th></tr>'+o.test_videos.map(v=>`<tr><td>${when(v.saved_at)}</td><td>${esc(v.match_key||'')}</td><td>${video(v)}</td></tr>`).join('')+'</table>':'<p class="training-note">No match test videos yet. Run Preview a match below.</p>');
  // Test & release: the detectors a test uses are always the ones in use; only the Actions model is chosen.
  fill('test','detectors',`Uses the robot detector ${o.robot.current?'you trained (adopted '+when(o.robot.current.adopted_at)+')':'built into the helper'} and ${o.field.current?'the field detector you trained for '+esc(o.field.game_key)+' (adopted '+when(o.field.current.adopted_at)+')':'the field detector built into the helper for '+esc(o.field.game_key)}. Where you marked scoring areas on 2 · Field, those marks are used instead.`);
  const menu=document.getElementById('trial-model'),empty=slot('test','no-model');
  if(menu&&empty){const has=[...menu.options].some(x=>x.value);empty.hidden=has;menu.hidden=!has}
  // A dot on each pillar in the Auto Scout menu that needs something.
  for(const a of $$('.community-nav [data-pillar]')){a.querySelector('.tt-flag')?.remove();if(needs[a.dataset.pillar]){const f=document.createElement('span');f.className='tt-flag';f.title='Needs attention';a.append(f)}}
 }
 for(const b of $$('[data-train]'))b.addEventListener('click',async()=>{b.disabled=true;try{await send({action:'queue_detector',kind:b.dataset.train==='field'?'train_field':'train'});await refresh()}catch(e){alert(e.message);b.disabled=false}});
 document.addEventListener('click',async e=>{const b=e.target.closest('[data-cancel]');if(!b)return;if(!confirm('Cancel this run? The helper stops at its next progress report.'))return;b.disabled=true;try{await send({action:'cancel_detector',request:b.dataset.cancel});await refresh()}catch(err){alert(err.message);b.disabled=false}});
 for(const b of $$('[data-rollback]'))b.addEventListener('click',async()=>{if(!confirm('Go back to the previous model? The current one is set aside, and helpers switch within an hour.'))return;try{await send({action:'rollback_detector',which:b.dataset.rollback});await refresh()}catch(e){alert(e.message)}});
 refresh();setInterval(()=>{if(!document.hidden)refresh()},10000);
})();
