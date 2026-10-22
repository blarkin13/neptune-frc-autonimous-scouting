import copy,json,re,shutil,subprocess,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from neptune_identity import reconcile,apply_corrections,digest
R={'red':[1,2,3],'blue':[4,5,6]};SHA='a'*64

def point(t,track,x,team=None,alliance='red',scene='wide:0',camera='wide'):
 return {'t':t,'track_id':track,'box':[x,.4,.07,.1],'alliance':alliance,'scene':scene,'camera':camera,'verified_team':team}
class Identity(unittest.TestCase):
 def test_later_anchors_fill_earlier_distinct_tracks_backwards(self):
  obs=[point(t,k,k*.2,k if t==2 else None) for t in (0,1,2) for k in (1,2,3)]
  review=reconcile(obs,R,SHA);self.assertEqual([p['team'] for p in review['points'] if p['t']==0],[1,2,3]);self.assertTrue(all(p['identity_status']=='inferred' for p in review['points'] if p['t']==0))
 def test_earlier_anchors_propagate_forward(self):
  obs=[point(t,k,k*.2,k if t==0 else None) for t in (0,.5,1) for k in (1,2,3)]
  self.assertEqual([p['team'] for p in reconcile(obs,R,SHA)['points'] if p['t']==1],[1,2,3])
 def test_two_verified_robots_resolve_third_by_roster(self):
  review=reconcile([point(0,1,.1,1),point(0,2,.4,2),point(0,3,.7)],R,SHA)
  self.assertEqual(review['points'][-1]['team'],3);self.assertFalse(review['points'][-1]['identity_evidence']['training_eligible'])
 def test_one_of_two_unknown_robots_does_not_resolve_a_missing_third(self):
  review=reconcile([point(0,1,.1,1),point(0,2,.4)],R,SHA)
  self.assertIsNone(review['points'][1]['team']);self.assertEqual(review['points'][1]['candidate_teams'],[2,3])
 def test_no_anchors_cannot_create_six_robot_identities(self):
  review=reconcile([point(0,k,k*.2) for k in (1,2,3)]+[point(0,k,(k-3)*.2,alliance='blue') for k in (4,5,6)],R,SHA)
  self.assertTrue(all(p['team'] is None for p in review['points']))
 def test_cuts_camera_changes_and_long_gaps_block_identity_transfer(self):
  for extra in (point(1,1,.1,scene='wide:1'),point(1,1,.1,camera='closeup'),point(4,1,.1)):
   review=reconcile([point(0,1,.1,1),extra],R,SHA);self.assertIsNone(review['points'][-1]['team'])
 def test_exchanged_post_anchors_do_not_force_unchanged_ids(self):
  obs=[point(0,1,.2,1),point(0,2,.6,2),point(.5,1,.39),point(.5,2,.41),point(1,1,.6,2),point(1,2,.2,1)]
  review=reconcile(obs,R,SHA);self.assertTrue(all(p['team'] is None for p in review['points'] if p['t']==.5))
 def test_conflicting_anchors_stay_unknown(self):
  review=reconcile([point(0,1,.1,1),point(0,2,.5,1)],R,SHA)
  self.assertTrue(all(p['team'] is None for p in review['points']))
 def test_extra_or_duplicate_detections_disable_elimination(self):
  for obs in ([point(0,k,.1*k) for k in range(4)],[point(0,1,.1),point(0,1,.3)]):
   self.assertTrue(all(p['team'] is None for p in reconcile(obs,R,SHA)['points']))
 def test_wrong_alliance_and_invalid_roster_are_rejected(self):
  with self.assertRaises(ValueError):reconcile([point(0,1,.1,4)],R,SHA)
  with self.assertRaises(ValueError):reconcile([],{'red':[1,2,3],'blue':[3,4,5]},SHA)
 def test_corrections_are_bounded_and_leave_original_data_unchanged(self):
  original=reconcile([point(t,1,.1) for t in (0,.5,1)],R,SHA);before=copy.deepcopy(original);track=original['points'][0]['review_track'];edit={'review_track':track,'start':.5,'end':1,'team':2}
  out=apply_corrections(original,[edit]);self.assertEqual(out['points'][0]['team'],2);self.assertEqual(out['points'][0]['identity_status'],'inferred');self.assertEqual([p['team'] for p in out['points'][1:]],[2,2]);self.assertEqual(original,before)
  with self.assertRaises(ValueError):apply_corrections(original,[dict(edit,team=4)])
 def test_duplicate_human_assignments_are_rejected(self):
  review=reconcile([point(0,1,.1),point(0,2,.5)],R,SHA)
  edits=[{'review_track':p['review_track'],'start':0,'end':0,'team':1} for p in review['points']]
  with self.assertRaises(ValueError):apply_corrections(review,edits)
 def test_native_ocr_scaling_and_panel_skip(self):
  from neptune_yolo import native_ocr_width,scaled_ocr_box
  self.assertEqual(native_ocr_width(1920,[0,.24,1,.65],960),1920);self.assertIsNone(native_ocr_width(1920,[0,.65,.5,1],960))
  self.assertEqual(scaled_ocr_box([10,20,30,40],(960,400),(1920,800)),[20,40,60,80])
 def test_short_gap_with_unique_visual_match_is_review_only(self):
  a=point(0,11,.1,1);b=point(2,19,.105)
  a['appearance']=[.125]*24;b['appearance']=[.125]*24
  review=reconcile([a,b],R,SHA);result=review['points']
  self.assertEqual(result[1]['team'],1)
  self.assertEqual(result[1]['identity_status'],'inferred')
  self.assertEqual(result[1]['reason'],'short_gap_visual_match_needs_review')
  self.assertFalse(result[1]['identity_evidence']['training_eligible'])
  self.assertEqual(review['summary']['short_gap_suggestions'],1)
 def test_short_gap_needs_visual_support_and_cannot_cross_a_cut(self):
  a=point(0,11,.1,1);b=point(2,19,.105)
  a['appearance']=[0.]*24;b['appearance']=[1.]*24
  self.assertIsNone(reconcile([a,b],R,SHA)['points'][1]['team'])
  b['appearance']=[0.]*24;b['scene']='wide:1'
  self.assertIsNone(reconcile([a,b],R,SHA)['points'][1]['team'])
 def test_short_gap_does_not_guess_between_similar_teammates(self):
  first=[point(0,11,.1,1),point(0,12,.12,2)]
  later=point(2,19,.11)
  for p in first+[later]:p['appearance']=[.125]*24
  self.assertIsNone(reconcile(first+[later],R,SHA)['points'][-1]['team'])
 def test_changed_track_id_inside_continuous_shot_is_a_review_suggestion(self):
  obs=[point(0,11,.1,1),point(0,2,.6),point(.5,2,.6),point(1,2,.6),point(1,19,.11)]
  for p in obs:p['appearance']=[.125]*24
  result=reconcile(obs,R,SHA)['points']
  target=next(p for p in result if p['track_id']==19)
  self.assertEqual((target['team'],target['identity_status']),(1,'inferred'))
  self.assertFalse(target['identity_evidence']['training_eligible'])
 def test_fragment_link_rejects_unresolved_teammate_rival(self):
  obs=[point(0,11,.1,1),point(0,12,.12,2),point(.5,3,.7),point(1,19,.11)]
  for p in obs:p['appearance']=[.125]*24
  target=next(p for p in reconcile(obs,R,SHA)['points'] if p['track_id']==19)
  self.assertNotEqual(target.get('reason'),'short_gap_visual_match_needs_review')

class HTTP(unittest.TestCase):
 def setUp(self):
  from neptune_identity_review import ReviewServer,save_json
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.video=root/'v.mp4';self.video.write_bytes(b'0123456789');self.path=root/'review.json';self.review=reconcile([point(0,1,.1)],R,SHA);save_json(self.path,self.review)
  self.server=ReviewServer(self.video,self.review,self.path);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url=self.server.url.rstrip('/');self.origin='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def request(self,path,body=None,headers=None):return urllib.request.urlopen(urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=headers or {}))
 def test_project_and_video_range(self):
  with self.request('/project') as r:self.assertEqual(json.load(r)['review']['source_sha256'],SHA)
  with self.request('/video',headers={'Range':'bytes=2-5'}) as r:self.assertEqual(r.status,206);self.assertEqual(r.read(),b'2345')
 def test_origin_and_token_protection(self):
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.origin+'/project')
  self.assertEqual(e.exception.code,404)
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/corrections',{'corrections':[]},headers={'Content-Type':'application/json','Origin':'http://evil.test'})
  self.assertEqual(e.exception.code,403)
 def test_save_reload_revision_and_no_video_mutation(self):
  edit={'review_track':self.review['points'][0]['review_track'],'start':0,'end':0,'team':2};headers={'Content-Type':'application/json','Origin':self.origin,'If-Match':digest([])}
  with self.request('/corrections',{'corrections':[edit]},headers) as r:self.assertEqual(json.load(r)['corrected']['points'][0]['team'],2)
  self.assertEqual(json.loads(self.path.read_text())['corrections'],[edit]);self.assertEqual(self.video.read_bytes(),b'0123456789')
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/corrections',{'corrections':[]},headers)
  self.assertEqual(e.exception.code,409)

class Catalog(unittest.TestCase):
 def test_picker_script_is_valid_javascript(self):
  from neptune_identity_review import CATALOG_HTML
  script=re.search(r'<script>(.*?)</script>',CATALOG_HTML,re.S)
  self.assertIsNotNone(script)
  node=shutil.which('node')
  if not node:self.skipTest('JavaScript parser unavailable')
  with tempfile.NamedTemporaryFile(mode='w',suffix='.js') as f:
   f.write(script.group(1));f.flush()
   result=subprocess.run([node,'--check',f.name],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_only_tagged_rostered_local_snapshots_are_listed(self):
  from neptune_identity_review import local_matches
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)/'job';folder.mkdir();p=folder/'labels.ndjson'
   rows=[{'evidence_type':'human_video_label','match_key':'2026test_qm3','video_id':'AAAAAAAAAAA','roster':R},{'evidence_type':'external_activity','match_key':'2026test_qm4','video_id':'BBBBBBBBBBB','roster':R},{}]
   p.write_text('\n'.join(json.dumps(r) for r in rows));result=local_matches(tmp);self.assertEqual(list(result),['2026test_qm3']);self.assertEqual(result['2026test_qm3']['labels'],1)

class Refinement(unittest.TestCase):
 def test_one_correction_revisits_before_and_after(self):
  review=reconcile([point(t,1,.1) for t in (0,.5,1)],R,SHA);track=review['points'][0]['review_track']
  out=apply_corrections(review,[{'review_track':track,'start':.5,'end':.5,'team':2}])
  self.assertEqual([p['team'] for p in out['points']],[2,2,2]);self.assertEqual([p['identity_status'] for p in out['points']],['inferred','corrected','inferred'])
 def test_false_detection_is_excluded_without_erasing_other_boxes(self):
  review=reconcile([point(0,1,.1),point(0,2,.5)],R,SHA);track=review['points'][0]['review_track']
  out=apply_corrections(review,[{'review_track':track,'start':0,'end':0,'team':None,'ignored':True}]);self.assertEqual(len(out['points']),2);self.assertEqual(out['points'][0]['identity_status'],'excluded');self.assertEqual(out['points'][1]['identity_status'],'unknown')
 def test_corrections_resolve_other_visible_roster_members(self):
  review=reconcile([point(0,1,.1,1),point(0,2,.4),point(0,3,.7)],R,SHA);track=review['points'][1]['review_track']
  out=apply_corrections(review,[{'review_track':track,'start':0,'end':0,'team':2}]);self.assertEqual([p['team'] for p in out['points']],[1,2,3]);self.assertEqual(out['points'][2]['identity_status'],'inferred')
if __name__=='__main__':unittest.main()
