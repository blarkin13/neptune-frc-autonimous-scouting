import copy,json,re,threading,tempfile,unittest,urllib.request
from pathlib import Path
from neptune_events import stationary_disabled
from neptune_scoring_model import apply_recorded_contributions
from neptune_identity_review import HTML,CATALOG_HTML,ReviewServer,save_json
from neptune_identity import reconcile

class Rules(unittest.TestCase):
 def facts(self,seconds=8):
  return {'periods':{'auto':{'start':0,'end':1},'teleop':{'start':2,'end':30,'clock_samples':[{'t':t,'remaining':30-t} for t in range(2,31)]}},'tracking':{'localizations':[{'team':1,'t':t/2,'box':[.2,.3,.1,.1],'scene':'wide:1','camera':'wide','track_id':1,'identity_method':'yolo_botsort_ocr'} for t in range(4,int(seconds*2)+1)]}}
 def test_over_five_seconds_one_episode_with_end(self):
  rows=stationary_disabled(self.facts(),'m');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['start_ms'],2000);self.assertEqual(rows[0]['end_ms'],8000)
 def test_exactly_five_seconds_is_not_over_five(self):self.assertEqual(stationary_disabled(self.facts(7),'m'),[])
 def test_autonomous_never_disabled(self):
  f=self.facts();f['periods']={'auto':{'start':0,'end':30}};self.assertEqual(stationary_disabled(f,'m'),[])
 def test_gap_occlusion_and_cut_do_not_count(self):
  for mode in ('gap','cut','occluded'):
   f=self.facts()
   if mode=='gap':f['tracking']['localizations']=[p for p in f['tracking']['localizations'] if not 4<p['t']<7]
   elif mode=='cut':
    for p in f['tracking']['localizations']:p['scene']='wide:1' if p['t']<5 else 'wide:2'
   else:
    for p in f['tracking']['localizations']:p['occluded']=True
   self.assertEqual(stationary_disabled(f,'m'),[],mode)
 def test_moving_or_zooming_robot_does_not_trigger(self):
  for zoom in (False,True):
   f=self.facts()
   for p in f['tracking']['localizations']:
    if zoom:p['box'][2]=.1+p['t']*.02
    else:p['box'][0]+=.03*p['t']
   self.assertEqual(stationary_disabled(f,'m'),[])
 def test_frozen_clock_unidentified_or_flow_does_not_trigger(self):
  for mode in ('clock','identity','flow'):
   f=self.facts()
   if mode=='clock':
    for p in f['periods']['teleop']['clock_samples']:p['remaining']=20
   else:
    for p in f['tracking']['localizations']:
     if mode=='identity':p['identity_method']='inferred'
     else:p['box_source']='optical_flow'
   self.assertEqual(stationary_disabled(f,'m'),[],mode)
 def test_two_views_do_not_duplicate_episode(self):
  f=self.facts();extra=copy.deepcopy(f['tracking']['localizations'])
  for p in extra:p['camera']='closeup'
  f['tracking']['localizations']+=extra;self.assertEqual(len(stationary_disabled(f,'m')),1)
 def scores(self):return [dict(team=i,alliance='red' if i<=3 else 'blue',status='predicted',robot_points=i*10,share_percent=i*10,alliance_score=300,observed_points=None) for i in range(1,7)]
 def test_zero_without_scoring_and_separate_alliance_totals(self):
  scores=self.scores();out=apply_recorded_contributions(scores,[dict(team=i,tag_key='scoring') for i in (1,2,4,5,6)])
  self.assertEqual(out[2]['robot_points'],0);self.assertEqual(out[2]['contribution_percent'],0)
  for a in ('red','blue'):self.assertEqual(sum(round(r['contribution_percent']*1000) for r in out if r['alliance']==a),100000)
  self.assertEqual(scores[2]['robot_points'],30)
 def test_feed_defense_failed_attempts_are_not_scoring(self):
  out=apply_recorded_contributions(self.scores(),[dict(team=1,tag_key=k) for k in ('gb:feed','attempted_defense','gb:score_attempt','gb:score_failed')]);self.assertTrue(all(r['contribution_percent']==0 for r in out));self.assertTrue(all(r['robot_points']==0 for r in out))
 def test_event_count_fallback_when_point_model_unavailable(self):
  scores=self.scores()
  for r in scores:r.update(robot_points=None,status='unknown')
  out=apply_recorded_contributions(scores,[{'team':1,'tag_key':'gb:score_10_fuel'},{'team':2,'tag_key':'gb:score_1_fuel'}]);self.assertEqual([r['contribution_percent'] for r in out[:3]],[50,50,0]);self.assertEqual(out[0]['contribution_basis'],'recorded_scoring_event_count');self.assertIsNone(out[0]['robot_points'])
 def test_all_zero_never_assigns_fake_percentages(self):
  out=apply_recorded_contributions(self.scores(),[]);self.assertTrue(all(r['contribution_status']=='no_scoring_recorded' for r in out));self.assertEqual(sum(r['contribution_percent'] for r in out),0)

class Review(unittest.TestCase):
 def test_unknown_label_has_its_own_hit_region_and_roster_buttons(self):
  self.assertIn('contains(h.label,x,y)',HTML);self.assertIn('Label selected robot ',HTML);self.assertIn('video.pause();select(hit.point.review_track)',HTML)
 def test_polls_bounded_serialized_and_hidden_tabs_skip(self):
  self.assertIn('if(polling)return',CATALOG_HTML);self.assertIn('AbortSignal.timeout(10000)',CATALOG_HTML);self.assertIn('if(!document.hidden)',CATALOG_HTML);self.assertIn('Saved corrections are kept.',CATALOG_HTML)
 def test_stream_honors_open_range_and_reseek_works(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);video=root/'v.mp4';video.write_bytes(b'a'*(4*1024*1024));path=root/'review.json';review=reconcile([{'t':0,'box':[.2,.2,.1,.1],'alliance':'red','scene':'wide:1','camera':'wide','track_id':1}],{'red':[1,2,3],'blue':[4,5,6]},'a'*64);save_json(path,review)
   server=ReviewServer(video,review,path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    for start in (0,1000,2000000,0):
     with urllib.request.urlopen(urllib.request.Request(server.url+'video',headers={'Range':f'bytes={start}-'}),timeout=3) as r:
      data=r.read();self.assertEqual(r.status,206);self.assertEqual(len(data),video.stat().st_size-start);self.assertEqual(int(r.headers['Content-Length']),len(data));self.assertTrue(r.headers['Content-Range'].startswith(f'bytes {start}-'))
    with urllib.request.urlopen(server.url+'project') as r:self.assertEqual(json.load(r)['corrected']['points'][0]['identity_status'],'unknown')
   finally:server.shutdown();server.server_close();thread.join()
