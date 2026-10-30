import unittest
from unittest.mock import patch
import neptune_field_detector as fd
import neptune_field_regions as fr
import neptune_homography as h

REFS=h.field_references('2026-rebuilt')
L,W=REFS['size']
# A broadcast whose near field corners are hidden below the picture (capoh qm9 geometry): field inches -> picture.
CAMERA=fd.homography([[0,0],[L,0],[L,W],[0,W]],[[.139,.237],[.872,.248],[1.193,.543],[-.176,.528]])
see=lambda x,y:fd.apply(CAMERA,[x,y])


class FieldReferences(unittest.TestCase):
 def marks(self,skip=()):
  base=dict(kind='field_reference',camera_view='wide',game_key='2026-rebuilt',shot_id='s',alliance='neutral',reviewed=True,start_ms=0,reference_ms=0,end_ms=10**9,event_template=True)
  refs=REFS['references'];out=[]
  for name,ref in refs.items():
   if name in skip:continue
   if 'point' in ref:pts=[see(*ref['point'])]
   elif 'line' in ref:(x0,y0),(x1,y1)=ref['line'];pts=[see(x0+(x1-x0)*t,y0+(y1-y0)*t) for t in (0,.4)]   # upper part only: overlay below
   elif 'parallel' in ref:pts=[see(60,20),see(L-60,20)]
   out.append(dict(base,id=name,reference=name,points=pts))
  return out
 def doc(self,regions):
  return dict(schema_version=1,contract='neptune-field-regions-v1',coordinate_system='normalized_full_video_frame',time_basis='video_elapsed_ms',regions=regions)
 def test_pack_has_the_references_and_marks_are_inside_the_picture(self):
  self.assertIn('left_hub_base',REFS['references'])
  for m in self.marks():self.assertTrue(all(0<=v<=1 for p in m['points'] for v in p),m['reference'])
  fr.validate(self.doc(self.marks()))
 def test_recovers_the_field_without_the_hidden_near_corners(self):
  m=h.reference_map(self.marks(),REFS)
  for x,y in ((100,250),(L/2,W/2),(600,300),(L,W)):
   q=h.project(m,see(x,y));self.assertAlmostEqual(q[0],x/L,4);self.assertAlmostEqual(q[1],y/W,4)
 def test_hubs_and_corners_alone_are_enough(self):
  self.assertIsNotNone(h.reference_map(self.marks(skip=('far_guardrail','left_alliance_wall','right_alliance_wall','center_line','tower_upright_pair')),REFS))
 def test_too_few_marks_give_no_map(self):
  self.assertIsNone(h.reference_map([m for m in self.marks() if m['reference'] in ('far_left_corner','far_right_corner','left_hub_base')],REFS))
 def test_contradicting_marks_give_no_map(self):
  marks=self.marks();hub=next(m for m in marks if m['reference']=='left_hub_base');hub['points']=[[hub['points'][0][0]+.15,hub['points'][0][1]]]
  self.assertIsNone(h.reference_map(marks,REFS))
 def test_unknown_reference_names_are_ignored(self):
  marks=self.marks();marks.append(dict(marks[0],id='x',reference='not_in_pack',points=[[.5,.5]]))
  self.assertIsNotNone(h.reference_map(marks,REFS))
 def test_validation(self):
  for bad in ([[.1,.1],[.2,.2],[.3,.3]],[]):
   m=self.marks()[0];m['points']=bad
   with self.assertRaises(ValueError):fr.validate(self.doc([m]))
  m=self.marks()[0];m['reference']='Bad Name'
  with self.assertRaises(ValueError):fr.validate(self.doc([m]))
 def test_robot_positions_use_references_when_no_corners_are_visible(self):
  foot=see(300,200);facts={'tracking':{'localizations':[{'team':'254','t':5,'camera':'wide','identity_method':'constant_identity','box':[foot[0]-.02,foot[1]-.05,.04,.05]}]}}
  with patch.object(fr,'load',return_value=self.doc(self.marks())):out=h.trajectories(facts,'2026-rebuilt')
  self.assertEqual(out['status'],'mapped');p=out['points'][0]
  self.assertAlmostEqual(p['field_x'],300/L,4);self.assertAlmostEqual(p['field_y'],200/W,4);self.assertEqual(p['calibration_id'],'field-references:s')
 def test_field_references_are_never_zones(self):
  d=self.doc(self.marks());p={'t':5,'camera':'wide','team':'254','identity_method':'constant_identity','box':[.4,.3,.02,.02]}
  self.assertEqual(fr.context(p,d,{'bumpers':{}})['zones'],[])
if __name__=='__main__':unittest.main()
