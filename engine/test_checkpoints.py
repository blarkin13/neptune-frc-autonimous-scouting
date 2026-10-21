import hashlib,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_training as training
import neptune_trainer as trainer
import neptune_games as games

class Checkpoints(unittest.TestCase):
    def snapshot(self,root):
        rows=[]
        for vid,match in [('AAAAAAAAAAA','2026same_qm1'),('BBBBBBBBBBB','2026same_qm2')]:
            for index,t in enumerate([1000,3000]):
                rows.append(dict(id=hashlib.sha256((vid+str(index)).encode()).hexdigest()[:32],schema_version=2,evidence_type='human_video_label',time_basis='video_elapsed_ms',match_id=1 if vid[0]=='A' else 2,match_key=match,source_url='https://www.youtube.com/watch?v='+vid,video_id=vid,roster={'red':[1,2,3],'blue':[4,5,6]},team_number=1,tag_key='scoring',tag_label='Scoring',tag_category='Scoring',definition_version='neptune-match-tags-v1',label_scope='moment',start_ms=t,end_ms=t,video_duration_ms=12000,certainty='observed',polarity='present',note='',review_state='contributed',created_at=index))
        path=root/'labels.ndjson';path.write_text(''.join(json.dumps(r)+'\n' for r in rows));return path
    def verify(self,store,videos,download,only_video_ids):
        sources=store.load('sources.json',{})
        for vid in only_video_ids:sources[vid]={'status':'verified','sha256':vid[0].lower()*64,'file':vid+'.mp4','duration_ms':12000,'label_checks':{}}
        store.save('sources.json',sources);return sources
    def facts(self,video,match,cache,*args,**kwargs):
        sha=Path(video).name[0].lower()*64
        return {'tracking':{'band':[.24,.65],'scene_cuts':[],'localizations':[{'team':1,'t':k/4,'box':[.2,.4,.1,.1],'scene':0,'track_id':1,'identity_method':'yolo_botsort_ocr'} for k in range(49)]},'source':{'sha256':sha,'duration_s':12},'periods':{'auto':{'start':0,'end':12}},'bumpers':{'identities':{'1':{'status':'confirmed','alliance':'red'}},'reads':[{'team':1,'t':t,'kind':'exact','background':'red','frame_box':[.2,.2,.05,.02],'frame':str(t)} for t in [1,3,5,6,7,8,9,10]]}}
    def test_one_match_then_resume_then_new_job_reuses_all_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);snapshot=self.snapshot(root);cache=root/'shared'
            with patch('neptune_training.labels.verify_sources',side_effect=self.verify),patch('neptune_facts.analyze_video',side_effect=self.facts) as ocr,patch('neptune_training.action_features',side_effect=lambda video,sight,duration,facts:[float(sight['t'] in (1,3))]*512) as extraction:
                first=training.run(root/'job1',2026,export_path=snapshot,cache_root=cache,max_matches=1,progress=lambda s:None)
                self.assertEqual((first['state'],first['matches_done']),( 'paused',1));self.assertEqual(ocr.call_count,1)
                second=training.run(root/'job1',2026,export_path=snapshot,cache_root=cache,max_matches=1,progress=lambda s:None)
                self.assertTrue((Path(second['folder'])/'model.json').exists());self.assertEqual(ocr.call_count,2)
                count=extraction.call_count
                third=training.run(root/'job2',2026,export_path=snapshot,cache_root=cache,progress=lambda s:None)
                self.assertEqual(ocr.call_count,2);self.assertEqual(extraction.call_count,count)
                model=json.loads((Path(third['folder'])/'model.json').read_text());self.assertFalse(model['release_ready'])
                # Two matches cannot show held-out signal, so the fitted head is withheld rather than shipped.
                self.assertEqual(model['heads'],{});self.assertEqual(third['tags']['scoring']['status'],'needs_more_positive_examples_across_matches')
    def test_stop_during_match_finishes_that_match_and_skips_next(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);snapshot=self.snapshot(root);stop=threading.Event()
            def extract(video,sight,duration,facts):stop.set();return [float(sight['t'] in (1,3))]*512
            with patch('neptune_training.labels.verify_sources',side_effect=self.verify),patch('neptune_facts.analyze_video',side_effect=self.facts) as ocr,patch('neptune_training.action_features',side_effect=extract):
                result=training.run(root/'job',2026,export_path=snapshot,cache_root=root/'shared',should_pause=stop.is_set,progress=lambda s:None)
                self.assertEqual(result['state'],'paused');self.assertEqual(result['matches_done'],1);self.assertEqual(ocr.call_count,1)
                saved=list((root/'shared/prepared').glob('*/*.json'));self.assertEqual(len(saved),1)
                payload=json.loads(saved[0].read_text());self.assertTrue(payload['examples']);self.assertTrue(payload['features'])
    def test_rejected_saved_result_retries_without_video_or_fit(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(trainer,'HOME',Path(temp)),patch('neptune_training.run',side_effect=AssertionError('must not rerun')):
            root=Path(temp)/'jobs'/'saved';root.mkdir(parents=True);snapshot='saved labels';(root/'labels.ndjson').write_text(snapshot)
            output={'report':{},'model':{'heads':{'auto_partial':{}}},'benchmark':None};(root/'result.json').write_text(json.dumps(output))
            sent=[]
            with patch.object(trainer,'api',side_effect=lambda config,action,payload:sent.append((action,payload)) or {'ok':True,'state':'candidate'}):
                reply=trainer.run_job({'site':'https://example.org'},{'id':'saved','snapshot':snapshot,'snapshot_sha256':hashlib.sha256(snapshot.encode()).hexdigest(),'lease':'new'}, {'device':'cpu'},lambda s:None)
            self.assertEqual(reply['state'],'candidate');self.assertEqual(sent[0][0],'finish');self.assertTrue((root/'receipt.json').exists())

if __name__=='__main__':unittest.main()
