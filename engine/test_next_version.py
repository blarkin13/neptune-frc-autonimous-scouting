import unittest,tempfile,time,os,sys,json
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
from neptune_homography import calibrate,project
from neptune_reacquisition import Reacquisition
from neptune_housekeeping import sweep
class Next(unittest.TestCase):
 def test_homography_corners(self):
  p=[[.2,.2],[.8,.25],[.95,.8],[.05,.8]];h=calibrate(p)
  for a,b in zip(p,[(0,0),(1,0),(1,1),(0,1)]):
   self.assertAlmostEqual(project(h,a)[0],b[0]);self.assertAlmostEqual(project(h,a)[1],b[1])
 def test_degenerate_calibration(self):
  with self.assertRaises(ValueError):calibrate([[0,0],[0,0],[1,1],[0,1]])
 def test_crossed_calibration(self):
  with self.assertRaises(ValueError):calibrate([[0,0],[1,1],[1,0],[0,1]])
 def state(self):return {1:{'team':123,'last':0,'box':[0,0,20,20],'alliance':'red'}}
 def detection(self,tid=2,x=20):return {'id':tid,'box':[x,0,x+20,20],'alliance':'red'}
 def test_proximity_only_provisional(self):
  r=Reacquisition().propose(0,1,[self.detection()],self.state(),[])
  self.assertEqual(r[0]['status'],'provisional_requires_ocr');self.assertFalse(r[0]['can_supply_action_identity'])
 def test_confirmed_priority(self):
  states=self.state();states[3]={'team':123,'last':0,'box':[100,0,120,20],'alliance':'red'}
  r=Reacquisition().propose(0,1,[self.detection(3,100),self.detection()],states,[])
  self.assertEqual(r[0]['priority'],1)
 def test_other_number_excluded(self):
  r=Reacquisition().propose(0,1,[self.detection()],self.state(),[{'track':2,'team':456,'kind':'exact'}]);self.assertEqual(r,[])
 def test_cut_reset(self):
  q=Reacquisition();q.propose(0,1,[],self.state(),[])
  self.assertEqual(q.propose(1,2,[self.detection()],{},[]),[])
 def test_radius(self):self.assertEqual(Reacquisition().propose(0,1,[self.detection(x=100)],self.state(),[]),[])
 def test_cleanup_preserves_durable(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t).resolve();site=home/'cache'/('a'*24);video=site/'videos'/'abcdefghijk.mp4';video.parent.mkdir(parents=True);video.write_bytes(b'abc')
   model=site/'models'/'model.json';model.parent.mkdir();model.write_text('{}')
   ann=home/'field-regions'/'a.json';ann.parent.mkdir();ann.write_text('{}')
   r=sweep(home,now=time.time()+2*86400)
   self.assertEqual(r['removed_bytes'],3);self.assertTrue(model.exists());self.assertTrue(ann.exists());self.assertFalse(video.exists())
 def test_active_cache_skipped(self):
  from neptune_cache import session
  with tempfile.TemporaryDirectory() as t:
   home=Path(t).resolve();site=home/'cache'/('a'*24);p=site/'videos'/'abcdefghijk.mp4';p.parent.mkdir(parents=True);p.write_bytes(b'abc')
   with session(site):r=sweep(home,now=time.time()+2*86400)
   self.assertEqual(r['skipped_active'],1);self.assertTrue(p.exists())
 def test_symlinks_not_followed(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();home=root/'home';videos=home/'cache'/('a'*24)/'videos';videos.mkdir(parents=True);outside=root/'keep.mp4';outside.write_bytes(b'abc');(videos/'abcdefghijk.mp4').symlink_to(outside)
   sweep(home,now=time.time()+2*86400);self.assertTrue(outside.exists())

class Integration(unittest.TestCase):
 def test_trainer_cleans_at_start_after_each_job_and_hourly_when_idle(self):
  import threading,neptune_trainer as trainer,neptune_housekeeping as hk
  from unittest.mock import patch
  calls=[];closing=threading.Event();jobs=[{'id':1,'lease':'x'},None,None]
  def api(config,action,payload):
   if action=='page_claim':
    if not jobs:closing.set();return {}
    return {'job':jobs.pop(0)}
   return {}
  with patch.object(trainer,'api',side_effect=api),patch.object(hk,'sweep',side_effect=lambda *a,**k:calls.append(1)),patch.object(closing,'wait',lambda *a:None):
   trainer.watch_jobs({},{},lambda *a,**k:{'state':'done'},lambda s:None,closing,threading.Event())
  # startup, after the job; the idle polls that follow are inside the hourly limit
  self.assertEqual(len(calls),2)
 def test_scouting_rule_events_never_add_disabled(self):
  src=open(Path(__file__).with_name('neptune_scoring_model.py')).read()
  self.assertIn("r['tag_key'] not in ('stationary','disabled')",src)
 def test_ocr_cadence_is_time_based(self):
  import inspect,neptune_yolo
  self.assertEqual(inspect.signature(neptune_yolo._track_camera).parameters['read_every'].default,.5)
  self.assertNotIn('sample_step=3',inspect.getsource(neptune_yolo._track_camera))
if __name__=='__main__':unittest.main()
