import unittest,sys,copy,json
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
from neptune_field_regions import validate,inside,context,enrich,load,observations
ROOT=Path(__file__).parent/'fixtures'/'field-regions';d=json.loads(next(ROOT.glob('*.json')).read_text())
def facts():return {'source':{'sha256':d['source_sha256']},'tracking':{'camera_cuts':{'wide':[],'closeup-left':[],'closeup-right':[]},'localizations':[]},'bumpers':{'identities':{'1':{'alliance':'red'}}}}
class Regions(unittest.TestCase):
 def test_export_valid(self):self.assertEqual(len(validate(d)['regions']),11)
 def test_wrong_video(self):
  f=facts();f['source']['sha256']='0'*64;self.assertIsNone(load(f,'2026-rebuilt',ROOT))
 def test_wrong_game(self):self.assertEqual(load(facts(),'2025-reefscape',ROOT)['regions'],[])
 def test_polygon_boundary(self):
  p=[[0,0],[1,0],[1,1],[0,1]]
  self.assertTrue(inside([0,0],p));self.assertTrue(inside([.5,.5],p));self.assertFalse(inside([2,.5],p))
 def test_camera_cut(self):
  f=facts();f['tracking']['camera_cuts']['wide']=[10]
  p={'team':1,'t':20,'camera':'wide','box':[.2,.5,.03,.03],'identity_method':'yolo_botsort_ocr'}
  self.assertEqual(context(p,d,f)['targets'],[])
 def test_camera_isolation(self):
  p={'team':1,'t':20,'camera':'other','box':[.2,.5,.03,.03],'identity_method':'yolo_botsort_ocr'}
  self.assertEqual(context(p,d,facts())['targets'],[])
 def test_inferred_identity_rejected(self):
  p={'team':1,'t':20,'camera':'wide','box':[.2,.5,.03,.03],'identity_method':'nearest_track'}
  self.assertIsNone(context(p,d,facts()))
 def test_enrichment_preserves_scores(self):
  f=facts();f['tracking']['localizations']=[{'team':1,'t':20,'camera':'wide','box':[.2,.5,.03,.03],'identity_method':'yolo_botsort_ocr'}]
  t={'team':1,'start_ms':20000,'score':.8,'tag_key':'scoring'}
  out,a=enrich([t],f,'2026-rebuilt',ROOT)
  self.assertEqual(out[0]['score'],.8);self.assertFalse(out[0]['field_context']['scoring_proven']);self.assertNotIn('field_context',t)
if __name__=='__main__':unittest.main()
