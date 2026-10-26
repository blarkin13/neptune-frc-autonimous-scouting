import unittest,sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import cv2
import neptune_field_training as ft
import neptune_robot_jobs as rj
import neptune_field_detector as fd
class Tests(unittest.TestCase):
 def doc(self):
  reg=lambda kind,pts:dict(kind=kind,camera_view='wide',shot_id='a',start_ms=1000,reference_ms=1500,end_ms=2000,points=pts)
  return {'regions':[reg('scoring_target',[[.2,.2],[.3,.2],[.3,.3],[.2,.3]]),reg('field_calibration',[[.1,.2],[.8,.2],[.9,.8],[.05,.8]])]}
 def test_interval_and_exact_instant(self):
  d=self.doc();self.assertIsNone(ft.document_at(d,.5));self.assertIsNotNone(ft.document_at(d,1.5));self.assertIsNone(ft.document_at(d,2.1))
  for r in d['regions']:r.update(start_ms=1500,end_ms=1500)
  im=np.zeros((20,30,3),np.uint8);rows=ft.samples(d,[(.5,im),(2,im)],lambda t:im);self.assertEqual([r[0] for r in rows],[1.5]);self.assertEqual(rows[0][1].shape,(720,1280,3))
 def test_reference_title_card_is_not_labeled_as_field(self):
  d=self.doc()
  for r in d['regions']:r['reference_ms']=1500
  field=np.zeros((720,1280,3),np.uint8);title=np.full_like(field,255)
  rows=ft.samples(d,[(1.1,field),(1.3,field),(1.7,field)],lambda t:title)
  self.assertEqual([round(t,1) for t,*_ in rows],[1.1,1.3,1.7])
  rows=ft.samples(d,[(1.1,field),(1.3,field),(1.7,field)],lambda t:field)
  self.assertIn(1.5,[round(t,1) for t,*_ in rows])
 def test_overlapping_shots_do_not_mix(self):
  d=self.doc();d['regions'].append(dict(d['regions'][0],shot_id='b'));self.assertIsNone(ft.document_at(d,1.5))
 def test_same_game_baseline_and_holdout_protection(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);model=p/'model.pt';model.write_bytes(b'field');(p/'trained_on.json').write_text(json.dumps({'2026-rebuilt':['old_match']}))
   with patch.object(fd,'model_path',return_value=model),patch.object(fd,'shared_dir',return_value=p/'shared'),patch.object(fd,'model_dir',return_value=p):
    self.assertEqual(rj.field_training_base('2026-rebuilt','new_match'),(model,'current-game-field-warm-start-v1'))
    with self.assertRaisesRegex(ValueError,'already learned'):rj.field_training_base('2026-rebuilt','old_match')
 def test_full_job_warm_start_and_timed_dataset(self):
  import neptune_robot_labels
  from types import SimpleNamespace
  from contextlib import nullcontext
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);base=root/'baseline.pt';base.write_bytes(b'field');video=root/'video.mp4';video.write_bytes(b'video');fit=root/'fit';(fit/'weights').mkdir(parents=True);(fit/'weights/best.pt').write_bytes(b'new');used=[]
   class Model:
    names={0:'scoring_target',1:'field_corner'}
    def __init__(self,path):used.append(path)
    def add_callback(self,*a):pass
    def train(self,**kw):
     labels=list((Path(kw['data']).parent/'labels/train').glob('*.txt'));self_test.assertEqual(len(labels),9);return SimpleNamespace(save_dir=fit)
   self_test=self;docs=[]
   for key,vid in [('2026train_qm1','abcdefghijk'),('2026held_qm2','lmnopqrstuv')]:docs.append(dict(self.doc(),source={'match_key':key,'video_id':vid}))
   with patch.dict(sys.modules,{'ultralytics':SimpleNamespace(YOLO=Model)}),patch.object(rj,'HOME',root),patch.object(rj,'region_documents',return_value=docs),patch.object(rj,'field_training_base',return_value=(base,'current-game-field-warm-start-v1')),patch.object(rj,'match_video',return_value=video),patch.object(rj,'sample_frames',return_value=[(1+i/8,np.zeros((720,1280,3),np.uint8)) for i in range(9)]),patch.object(rj,'batch_progress'),patch.object(rj,'all_cores',return_value=nullcontext()),patch.object(rj,'placement',side_effect=[{'found':0,'expected':5,'mean_error':None},{'found':1,'expected':5,'mean_error':.05}]),patch.object(rj,'send_review',return_value={}):
    for d in docs:
     for region in d['regions']:region['game_key']='2026-rebuilt'
    result=rj.train_field({}, {'id':'test','holdout':'2026held_qm2','game_key':'2026-rebuilt'},lambda m:None)
   self.assertEqual(used,[str(base)]);self.assertFalse(result['adopted']);self.assertEqual(result['frames_per_match'],{'2026held_qm2':9,'2026train_qm1':9});self.assertEqual(len(result['evaluation_sha256']),64)
if __name__=='__main__':unittest.main()


class EdgeCornersAndPartialCredit(unittest.TestCase):
 def doc(self,corners):
  reg=lambda kind,points:{'kind':kind,'camera_view':'wide','points':points,'game_key':'2026-rebuilt'}
  return {'regions':[reg('scoring_target',[[.2,.2],[.3,.2],[.3,.3],[.2,.3]]),reg('field_calibration',corners)]}
 def test_corner_on_frame_edge_is_not_a_label(self):
  d=self.doc([[.1,.2],[.8,.2],[.996,.8],[.004,.8]])
  self.assertEqual([int(l.split()[0]) for l in fd.yolo_labels(d)],[0,1,1])
  self.assertEqual(fd.visible_corners(d),[[.1,.2],[.8,.2]])
 def test_three_of_four_corners_score_three(self):
  import sys,types
  d=self.doc([[.1,.2],[.8,.2],[.9,.8],[.05,.8]])
  found=[[.3,.3]]+[[x+.01,y+.01] for x,y in ([.1,.2],[.8,.2],[.9,.8])]   # a target and three corners each frame
  class Boxes:
   def __init__(s,rows):s.xyxy=Rows([[x-.01,y-.01,x+.01,y+.01] for x,y in rows]);s.cls=Rows([0]+[1]*(len(rows)-1))
  class Rows(list):
   def tolist(s):return list(s)
  class Model:
   def __init__(s,w):pass
   def predict(s,image,**k):return [types.SimpleNamespace(boxes=Boxes(found))]
  frame=np.zeros((1,1,3),np.uint8)
  with patch.dict(sys.modules,{'ultralytics':types.SimpleNamespace(YOLO=Model)}),patch.object(rj,'train_device',return_value='cpu'):
   r=rj.placement('w.pt',[(t,frame,d) for t in range(3)],d)
  self.assertEqual((r['found'],r['expected']),(4,5))

