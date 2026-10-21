import json,subprocess,tempfile,unittest
from pathlib import Path
import neptune_games as games
import neptune_training as training
class ModelTransport(unittest.TestCase):
 def test_game_fingerprint_ignores_integral_float_formatting(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);pack=json.loads(games.BUILTIN.read_text())['seasons']['2026'];pack['season']=2026
   file=root/'pack.json';file.write_text(json.dumps(pack));games.install(file,root);first=games.select('2026test',root)
   pack=games.fingerprint_content(pack);file.write_text(json.dumps(pack));games.install(file,root);second=games.select('2026test',root)
   self.assertEqual(first['fingerprint'],second['fingerprint'])

 def test_php_transport_preserves_empty_head_maps_and_integral_floats(self):
  with tempfile.TemporaryDirectory() as tmp:
   game=games.select('2026test',Path(tmp));training.train([],game,Path(tmp)/'model',{})
   model=json.loads((Path(tmp)/'model/model.json').read_text());model['transport_fixture']=[0.0,1.0,0.12345];model.pop('model_id');model['model_id']=training.digest(model)
   source=Path(__file__).resolve().parents[1]/'neptune_secure/community-model-json.php'
   php="require $argv[1]; $m=json_decode(stream_get_contents(STDIN),true); echo community_model_document($m);"
   raw=subprocess.run(['php','-r',php,str(source)],input=json.dumps(model),capture_output=True,text=True,check=True).stdout
   returned=json.loads(raw);self.assertIsInstance(returned['heads'],dict);self.assertIs(type(returned['transport_fixture'][0]),float);training.model_valid(returned,game)
if __name__=='__main__':unittest.main()
