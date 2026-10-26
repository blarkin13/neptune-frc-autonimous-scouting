import copy,unittest
from neptune_persistent_identity import build,state_at
R={'red':[1,2,3],'blue':[4,5,6]};SHA='a'*64

def hist(i):return [float(j==i) for _ in range(3) for j in range(8)]
def point(t,tid,team=None,appearance=0,camera='wide',scene='wide:0',x=.1):
 return dict(t=t,track_id=tid,verified_team=team,read_teams=[team] if team else [],camera=camera,scene=scene,
             alliance='red',box=[x,.3,.1,.1],appearance=hist(appearance),detection_confidence=.9,box_source='detector',occluded=False)

class PersistentIdentityTests(unittest.TestCase):
 def test_long_absence_keeps_record_but_not_position(self):
  d=build([point(0,1,1),point(.5,1,1),point(30,9,1),point(30.5,9,1)],R,SHA)
  self.assertEqual(len(d['records']),6)
  self.assertEqual(d['returns'][0]['unobserved_seconds'],29.5)
  self.assertEqual(d['returns'][0]['status'],'ocr_reconfirmed')
  s=state_at(d,15)[0];self.assertEqual(s['state'],'not_observed');self.assertEqual(s['boxes'],[])
  self.assertEqual(state_at(d,0)[0]['persistent_id'],state_at(d,30)[0]['persistent_id'])
 def test_visual_return_is_proposal_and_never_supervision(self):
  ps=[point(0,1,1,0),point(.5,1,1,0),point(0,2,2,1,x=.4),point(.5,2,2,1,x=.4),point(30,9,None,0),point(30.5,9,None,0)]
  d=build(ps,R,SHA);returns=[r for r in d['returns'] if r['team']==1]
  self.assertEqual(returns[0]['status'],'visual_match_needs_review')
  self.assertEqual(state_at(d,30)[0]['state'],'not_observed')
  self.assertEqual(state_at(d,30,include_proposals=True)[0]['state'],'visible')
  self.assertTrue(all(not p['training_eligible'] and not p['identity_anchor'] for p in d['points']))
 def test_identical_teammates_abstain(self):
  ps=[point(0,1,1),point(.5,1,1),point(0,2,2,x=.4),point(.5,2,2,x=.4),point(30,9),point(30.5,9)]
  d=build(ps,R,SHA);self.assertFalse(any(p['t']==30 for p in d['points']))
 def test_contradictory_anchors_do_not_fill_tracklet(self):
  d=build([point(0,1,1),point(.5,1,2)],R,SHA)
  self.assertEqual(d['tracklets'][0]['reason'],'conflicting_ocr_anchors');self.assertEqual(d['points'],[])
 def test_simultaneous_duplicate_identity_blocked(self):
  d=build([point(0,1,1),point(.5,1,1),point(0,2,1,x=.4),point(.5,2,1,x=.4)],R,SHA)
  self.assertEqual(d['points'],[])
 def test_cameras_share_record_without_visual_cross_camera_matching(self):
  d=build([point(0,1,1),point(.5,1,1),point(30,9,1,camera='closeup',scene='closeup:2'),point(30.5,9,1,camera='closeup',scene='closeup:2')],R,SHA)
  self.assertEqual(len({p['persistent_id'] for p in d['points']}),1)
 def test_competing_visual_returns_both_abstain(self):
  ps=[point(0,1,1,0),point(.5,1,1,0),point(0,2,2,1,x=.4),point(.5,2,2,1,x=.4),point(30,9,None,0),point(30.5,9,None,0),point(30,10,None,0,x=.4),point(30.5,10,None,0,x=.4)]
  d=build(ps,R,SHA);self.assertFalse(any(p['t']==30 for p in d['points']))
 def test_mixed_number_reads_block_tracklet_extension(self):
  ps=[point(0,1,1),point(.5,1,1)];ps[1]['read_teams']=[1,2]
  d=build(ps,R,SHA);self.assertEqual(d['points'],[])
 def test_inputs_not_modified(self):
  ps=[point(0,1,1),point(.5,1,1)];before=copy.deepcopy(ps);build(ps,R,SHA);self.assertEqual(ps,before)
 def test_incompatible_alliance_anchor_rejected(self):
  with self.assertRaises(ValueError):build([point(0,1,4)],R,SHA)
 def test_reused_tracker_after_gap_is_new_fragment(self):
  d=build([point(0,1,1),point(.5,1,1),point(30,1,2),point(30.5,1,2)],R,SHA)
  self.assertEqual(len(d['tracklets']),2);self.assertEqual({p['team'] for p in d['points']},{1,2})

if __name__=='__main__':unittest.main()
