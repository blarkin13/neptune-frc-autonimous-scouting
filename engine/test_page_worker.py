import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_games as games
import neptune_training as training
import neptune_trainer as trainer
import neptune_page_worker as worker
import neptune_scoring_model as scoring
from test_scoring_model import facts,feature


def make_job(root,kind='training'):
    pack=json.loads(games.BUILTIN.read_text())['seasons']['2026']
    return {'id':'fixture-page-job','lease':'fixture-only','season':2026,'kind':kind,'game_pack':pack,'control':{'kind':kind},'snapshot':'','snapshot_sha256':hashlib.sha256(b'').hexdigest()}


def action_model(root):
    game=games.select('2026fixture',root);training.train([],game,root/'model',{})
    m=json.loads((root/'model/model.json').read_text());m['heads']={'scoring':{'weights':[0.0]*1296,'feature_dimension':1296,'bias':0.0,'threshold':1.0}}
    m['feature_version']=training.FEATURE_VERSION;m.pop('action_encoder',None)
    m.pop('model_id');m['model_id']=training.digest(m);return m


class PageWorker(unittest.TestCase):
    def test_web_stop_is_observed_at_checkpoint_before_next_match(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)):
            sent=[];job=make_job(Path(tmp))
            def call(config,action,payload):sent.append((action,payload));return {'ok':True,'stop_requested':True,'state':'remote_paused'}
            def prepare(*args,checkpoint,should_pause,**kwargs):
                checkpoint({'matches_done':1,'matches_total':2,'current_match':'2026fixture_qm1','phase':'preparing'})
                self.assertTrue(should_pause());return {'state':'paused','matches_done':1,'matches_total':2,'folder':None}
            with patch('neptune_training.run',side_effect=prepare):reply=worker.execute({'site':'https://example.org'},job,{'device':'cpu'},lambda s:None,transport=call)
            self.assertEqual(reply['state'],'remote_paused');self.assertEqual(sent[0][0],'page_heartbeat');self.assertEqual(sent[-1][0],'pause');self.assertFalse(any(a=='finish' for a,_ in sent))
    def test_page_training_uploads_a_real_readiness_report(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)):
            sent=[]
            def call(config,action,payload):sent.append((action,payload));return {'ok':True,'state':'needs_data'}
            reply=worker.execute({'site':'https://example.org'},make_job(Path(tmp)),{'device':'cpu'},lambda s:None,transport=call)
            self.assertEqual(reply['state'],'needs_data');self.assertEqual(sent[-1][0],'finish');self.assertEqual(sent[-1][1]['result']['model']['heads'],{});self.assertIn('scoring',sent[-1][1]['result']['report'])
    def test_queued_action_only_trial_uses_existing_request_and_abstains_on_scores(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)):
            root=Path(tmp);job=make_job(root,'trial');job['model']=action_model(root);job['request']={'match_id':1,'match_key':'2026fixture_qm1','title':'Fixture match','roster':{'red':[1,2,3],'blue':[4,5,6]},'source_url':'https://www.youtube.com/watch?v=AAAAAAAAAAA','alliance_scores':{'red':400,'blue':300}};sent=[]
            def call(config,action,payload):sent.append((action,payload));return {'ok':True,'state':'test_complete'}
            def download(match,path,stage):path.write_bytes(b'fixture')
            with patch('neptune_helper.download_video',side_effect=download),patch('neptune_video_labels.sha256_file',return_value='a'*64),patch('neptune_video_labels.probe_duration_ms',return_value=200000),patch('neptune_facts.analyze_video',return_value=facts()),patch('neptune_training.features',side_effect=feature):
                worker.execute({'site':'https://example.org'},job,{'device':'cpu'},lambda s:None,transport=call)
            self.assertNotIn('trial_start',[a for a,_ in sent]);self.assertEqual(sent[-1][0],'trial_finish');result=sent[-1][1]['result'];self.assertEqual(len(result['scores']),6);self.assertTrue(all(s['robot_points']==0 and s['reason']=='no_recorded_scoring' and s['zero_by_policy'] for s in result['scores']));self.assertNotIn('summary',result)
    def reference_job(self,root):
        job=make_job(root,'evaluation');job['model']=action_model(root);job['request']={'season':2026,'game_key':'2026-rebuilt','tags':['scoring'],'matches':[{'match_key':'2026heldout_qm1','roster':{'red':[1,2,3],'blue':[4,5,6]},'complete_robot_labels':{str(t):True for t in range(1,7)},'source_url':'https://www.youtube.com/watch?v=AAAAAAAAAAA','source_sha256':'a'*64,'duration_ms':200000,'events':[]}]};return job
    def test_evaluation_rejects_changed_video_before_any_accuracy_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=self.reference_job(root);sent=[]
            def download(match,path,stage):path.write_bytes(b'fixture')
            with patch('neptune_helper.download_video',side_effect=download),patch('neptune_video_labels.sha256_file',return_value='b'*64):
                with self.assertRaisesRegex(ValueError,'fingerprint'):worker.evaluate({'site':'https://example.org'},job,lambda s:None,lambda c,a,p:sent.append(a),root)
            self.assertNotIn('page_evaluation_finish',sent)
    def test_independent_evaluation_reports_failure_without_release_or_model_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=self.reference_job(root);sent=[]
            def call(config,action,payload):sent.append((action,payload));return {'ok':True,'state':'evaluation_complete'}
            def download(match,path,stage):path.write_bytes(b'fixture')
            with patch('neptune_helper.download_video',side_effect=download),patch('neptune_video_labels.sha256_file',return_value='a'*64),patch('neptune_video_labels.probe_duration_ms',return_value=200000),patch('neptune_facts.analyze_video',return_value=facts()),patch('neptune_training.features',side_effect=feature):
                worker.evaluate({'site':'https://example.org'},job,lambda s:None,call,root)
            self.assertEqual(sent[-1][0],'page_evaluation_finish');self.assertFalse(sent[-1][1]['benchmark']['release_ready']);self.assertEqual(len(sent[-1][1]['benchmark']['matches']),1);self.assertFalse(job['model']['release_ready'])

if __name__=='__main__':unittest.main()
