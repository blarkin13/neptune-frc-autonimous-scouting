import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_training as training
import neptune_videomae as video
import neptune_games as games

class VideoMAE(unittest.TestCase):
 def rows(self):
  return [dict(tag='scoring',x=[float(y)]*768,y=y,label_ids=[split+str(y)+str(i)],source_sha256=split,group=split,split=split,match_key='2026'+split+'_qm1',team=1,t_ms=i*1000) for split in ('training','calibration','test') for y in (0,1) for i in range(3)]
 def test_opt_in_and_unknown_backend(self):
  with patch.dict(os.environ,{},clear=True):self.assertEqual(training.selected_action_version(),training.ACTION_FEATURE_VERSION)
  with patch.dict(os.environ,NEPTUNE_ACTION_BACKEND='videomae'):self.assertEqual(training.selected_action_version(),video.VERSION)
  with patch.dict(os.environ,NEPTUNE_ACTION_BACKEND='untrusted'):
   with self.assertRaises(ValueError):training.selected_action_version()
 def test_train_and_validate_768_dimensional_game_head(self):
  with tempfile.TemporaryDirectory() as tmp:
   game=games.select('2026test_qm1');folder=Path(tmp)/'model';report=training.train_actions(self.rows(),game,folder,{})
   model=json.loads((folder/'model.json').read_text());training.model_valid(model,game)
   self.assertEqual(model['feature_version'],video.VERSION);self.assertEqual(model['action_encoder'],video.encoder_document());self.assertEqual(model['heads']['scoring']['feature_dimension'],768);self.assertFalse(report['release_ready'])
   bad=copy.deepcopy(model);bad['action_encoder']['weights_sha256']='0'*64
   with self.assertRaises(ValueError):training.model_valid(bad,game)
 def test_mixed_encoders_are_rejected(self):
  rows=self.rows();rows[0]['x']=[0.]*512
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):training.train_actions(rows,games.select('2026test_qm1'),Path(tmp)/'bad',{})
 def test_missing_or_modified_public_weights_rejected(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,NEPTUNE_VIDEOMAE_MODEL_DIR=tmp):
   with self.assertRaises(ValueError):video.verify_weights()
   for name in video.FILES:(Path(tmp)/name).write_text('changed')
   with self.assertRaises(ValueError):video.verify_weights()
 def test_existing_r3d_model_keeps_its_own_encoder_under_videomae_selection(self):
  rows=[dict(r,x=r['x'][:512]) for r in self.rows()]
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,NEPTUNE_ACTION_BACKEND='videomae'):
   game=games.select('2026test_qm1');folder=Path(tmp)/'old';training.train_actions(rows,game,folder,{})
   m=json.loads((folder/'model.json').read_text());training.model_valid(m,game);self.assertEqual(m['feature_version'],training.ACTION_FEATURE_VERSION)

if __name__=='__main__':unittest.main()
