import unittest,copy
import neptune_field_detector as fd
import neptune_field_training as ft
import neptune_field_regions as fr
class PolygonBoundaries(unittest.TestCase):
 def doc(self):
  base=dict(camera_view='wide',game_key='2026-rebuilt',shot_id='s',start_ms=1000,reference_ms=1500,end_ms=2000,reviewed=True,alliance='neutral')
  polygon=[[.1,.2],[.8,.2],[.9,.4],[.9,.8],[.1,.8],[.05,.4]]
  return dict(schema_version=1,contract='neptune-field-regions-v1',coordinate_system='normalized_full_video_frame',time_basis='video_elapsed_ms',regions=[dict(base,kind='field_boundary',points=polygon),dict(base,kind='scoring_target',points=[[.2,.3],[.3,.3],[.3,.4],[.2,.4]])])
 def test_hexagon_is_eligible_without_inventing_corners(self):
  d=self.doc();self.assertIs(fr.validate(d),d);self.assertTrue(fd.training_geometry(d));self.assertIsNotNone(ft.document_at(d,1.5));self.assertIsNone(ft.document_at(d,2.1));self.assertEqual(fd.visible_corners(d),[]);self.assertIsNone(fd.boundary_corners(d));self.assertEqual(len(fd.yolo_labels(d)),1)
 def test_confirmed_and_inferred_are_separate(self):
  d=self.doc();d['regions'][0].update(corner_indices=[0,1],inferred_corner_indices=[3,4]);fr.validate(d);self.assertEqual(fd.visible_corners(d),[[.1,.2],[.8,.2]]);self.assertEqual(len(fd.yolo_labels(d)),3);self.assertIsNone(fd.boundary_corners(d))
 def test_indices_are_validated(self):
  for bad in [[6],[-1],[True],[0,0],['0'],[[0]]]:
   d=self.doc();d['regions'][0]['corner_indices']=bad
   with self.assertRaises(ValueError):fr.validate(d)
  d=self.doc();d['regions'][0].update(corner_indices=[0],inferred_corner_indices=[0])
  with self.assertRaises(ValueError):fr.validate(d)
 def test_four_vertex_outline_can_explicitly_have_no_corners(self):
  d=self.doc();r=d['regions'][0];r.update(points=[[.1,.2],[.8,.2],[.9,.8],[.1,.8]],corner_indices=[])
  self.assertEqual(fd.visible_corners(d),[]);self.assertIsNone(fd.boundary_corners(d))
  del r['corner_indices'];self.assertEqual(len(fd.visible_corners(d)),4);self.assertIsNotNone(fd.boundary_corners(d))
 def test_targets_without_boundary_are_not_eligible(self):
  d=self.doc();d['regions']=d['regions'][1:];self.assertFalse(fd.training_geometry(d));self.assertIsNone(ft.document_at(d,1.5))
 def test_homography_does_not_use_explicit_outline_only_quad(self):
  import neptune_homography as h
  from unittest.mock import patch
  d=self.doc();r=d['regions'][0];r.update(points=[[.1,.2],[.8,.2],[.9,.8],[.1,.8]],corner_indices=[])
  with patch.object(fr,'load',return_value=d):self.assertEqual(h.trajectories({},'2026-rebuilt')['status'],'needs_reviewed_field_corners')
if __name__=='__main__':unittest.main()
