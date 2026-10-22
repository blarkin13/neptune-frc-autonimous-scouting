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

 def test_youtube_marked_regions_sync_without_file_size(self):
  import tempfile,json as j
  from unittest.mock import patch
  import neptune_field_regions as fr
  with tempfile.TemporaryDirectory() as t:
   video=Path(t)/'jrpeWpe_iqU.mp4';video.write_bytes(b'x'*10)
   doc=copy.deepcopy(d);doc['source']={'id':'youtube:jrpeWpe_iqU','name':'jrpeWpe_iqU.mp4','video_id':'jrpeWpe_iqU','identity_basis':'youtube_video_id'};doc.pop('source_sha256',None)
   class R:
    def __init__(s,b):s.b=b
    def read(s,n):return s.b
    def __enter__(s):return s
    def __exit__(s,*a):return False
   class O:
    def open(s,req,timeout):return R(j.dumps({'document':doc}).encode())
   with patch('urllib.request.build_opener',return_value=O()),patch('neptune_helper.public_https',side_effect=lambda u:u),patch.object(Path,'home',return_value=Path(t)):
    out=fr.sync({'site':'https://example.org','token':'a'*64},video,{'source':{'sha256':d['source_sha256']}})
   self.assertEqual(out['status'],'synced')
   saved=j.loads((Path(t)/'.neptune-trainer/field-regions'/(d['source_sha256']+'.json')).read_text())
   self.assertEqual(saved['source_sha256'],d['source_sha256'])

class EventRegions(unittest.TestCase):
 def match(self,red_x,blue_x,sha='b'*64,key='2026txcmp1_qm9'):
  obs=[{'camera':'wide','t':10+i*.2,'alliance':c,'box':[x,.5,.02,.02]} for i in range(5) for c,x in (('red',red_x),('blue',blue_x))]
  return {'source':{'sha256':sha},'identity':{'checks':{'match_number':{'status':'match','claimed_key':key}}},'periods':{'auto':{'start':10,'end':30}},
          'tracking':{'camera_cuts':{'wide':[5.0]},'observations':obs,'localizations':[]},'bumpers':{'identities':{'1':{'alliance':'red'}}}}
 def test_same_sides_keep_labels(self):
  from neptune_field_regions import event_document
  out=event_document(self.match(.3,.7),'2026-rebuilt',[copy.deepcopy(d)])
  self.assertFalse(out['sides_swapped']);self.assertEqual(out['sides'],'red_left')
  self.assertEqual(sorted(r['alliance'] for r in out['regions']),sorted(r['alliance'] for r in d['regions']))
 def test_swapped_sides_swap_alliances_not_geometry(self):
  from neptune_field_regions import event_document
  out=event_document(self.match(.7,.3),'2026-rebuilt',[copy.deepcopy(d)])
  self.assertTrue(out['sides_swapped'])
  for a,b in zip(d['regions'],out['regions']):
   self.assertEqual(a['points'],b['points']);self.assertEqual(b['alliance'],{'red':'blue','blue':'red','neutral':'neutral'}[a['alliance']])
 def test_unknown_sides_apply_nothing(self):
  from neptune_field_regions import event_document
  f=self.match(.3,.7);f['tracking']['observations']=[]
  self.assertEqual(event_document(f,'2026-rebuilt',[copy.deepcopy(d)])['regions'],[])
 def test_event_regions_ignore_reference_cut_timeline(self):
  from neptune_field_regions import event_document,active
  out=event_document(self.match(.3,.7),'2026-rebuilt',[copy.deepcopy(d)])
  r=next(r for r in out['regions'] if r['camera_view']=='wide')
  self.assertTrue(active(r,100,'wide',self.match(.3,.7)));self.assertFalse(active(r,100,'closeup-left',self.match(.3,.7)))
 def test_load_falls_back_to_event_file(self):
  import tempfile,json as j,neptune_field_regions as fr
  with tempfile.TemporaryDirectory() as t:
   (Path(t)/'events').mkdir();(Path(t)/'events'/'2026txcmp1.json').write_text(j.dumps([d]))
   self.assertEqual(fr.load(self.match(.3,.7),'2026-rebuilt',t)['application'],'event_template')
   self.assertIsNone(fr.load(self.match(.3,.7,key='2026txcmp2_qm1'),'2026-rebuilt',t))
 def test_scoring_reach_uses_own_scoring_zone(self):
  from neptune_field_regions import event_document,scoring_reach
  f=self.match(.3,.7);out=event_document(f,'2026-rebuilt',[copy.deepcopy(d)])
  zone=next(r for r in out['regions'] if r['kind']=='scoring_zone' and r['alliance']=='red' and r['camera_view']=='wide')
  cx=sum(p[0] for p in zone['points'])/len(zone['points']);cy=sum(p[1] for p in zone['points'])/len(zone['points'])
  self.assertTrue(scoring_reach({'team':1,'t':50,'camera':'wide','box':[cx-.01,cy-.02,.02,.02]},out,f))
  self.assertFalse(scoring_reach({'team':1,'t':50,'camera':'wide','box':[.97,.0,.01,.01]},out,f))
  self.assertIsNone(scoring_reach({'team':1,'t':50,'camera':'other','box':[.5,.5,.01,.01]},out,f))
if __name__=='__main__':unittest.main()
