import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import neptune_cache as cache
import neptune_page_worker as worker
import neptune_training as training
import neptune_trainer as trainer
import test_page_worker as fixtures


class DisposableMedia(unittest.TestCase):
    def test_only_generated_media_and_verified_tracking_evidence_are_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sha='a'*64;video=root/'videos/AAAAAAAAAAA.mp4';video.parent.mkdir();video.write_bytes(b'video')
            work=root/'localizations'/sha/'game';work.mkdir(parents=True)
            for name in ('crop.jpg','frame.ppm','raw-overlay.jsonl','neptune-botsort.yaml'): (work/name).write_bytes(b'temporary')
            (work/'facts.json').write_text(json.dumps({'pipeline':'facts-v1','source':{'sha256':sha}}))
            for name in ('result.json','model.json','report.json','labels.ndjson','features.json'):(work/name).write_text('saved')
            training.write(root/'prepared/example.json',{'features':[1,2,3]})
            report=cache.cleanup(root,'AAAAAAAAAAA',sha,work)
            self.assertEqual(report['removed_files'],5)
            # keep-match-videos-14d-v1: the match video stays for reuse; generated media and evidence go
            self.assertTrue(video.exists());self.assertFalse((work/'facts.json').exists())
            self.assertTrue((root/'prepared/example.json').exists())
            self.assertTrue(all((work/name).read_text()=='saved' for name in ('result.json','model.json','report.json','labels.ndjson','features.json')))

    def test_external_paths_and_symlinks_cannot_delete_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'cache';root.mkdir();outside=Path(tmp)/'original.mp4';outside.write_bytes(b'keep')
            (root/'videos').mkdir();(root/'videos/AAAAAAAAAAA.mp4').symlink_to(outside)
            cache.cleanup(root,'AAAAAAAAAAA');self.assertTrue(outside.exists())
            with self.assertRaises(ValueError):cache.cleanup(root,'AAAAAAAAAAA','a'*64,Path(tmp))
            with self.assertRaises(ValueError):cache.cleanup(root,'../original')

    def test_a_second_process_cannot_clean_an_active_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with cache.session(tmp):
                with self.assertRaisesRegex(ValueError,'Another Neptune process'):
                    with cache.session(tmp):pass
            with cache.session(tmp):pass

    def test_low_disk_is_checked_before_download(self):
        with tempfile.TemporaryDirectory() as tmp,patch('neptune_cache.shutil.disk_usage',return_value=type('Disk',(),{'free':1000})()):
            with self.assertRaisesRegex(ValueError,'2 GB free'):cache.require_space(tmp)

    def test_trial_result_survives_immediate_media_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)):
            root=Path(tmp);job=fixtures.make_job(root,'trial');job['model']=fixtures.action_model(root)
            job['request']={'match_id':1,'match_key':'2026fixture_qm1','title':'Match','roster':{'red':[1,2,3],'blue':[4,5,6]},'source_url':'https://www.youtube.com/watch?v=AAAAAAAAAAA','alliance_scores':{}}
            downloaded=[]
            def download(match,path,stage):path.write_bytes(b'video');downloaded.append(path)
            with patch('neptune_helper.download_video',side_effect=download),patch('neptune_video_labels.sha256_file',return_value='a'*64),patch('neptune_video_labels.probe_duration_ms',return_value=200000),patch('neptune_facts.analyze_video',return_value=fixtures.facts()),patch('neptune_training.features',side_effect=fixtures.feature):
                worker.execute({'site':'https://example.org'},job,{'device':'cpu'},lambda s:None,transport=lambda *args:{'state':'test_complete'})
            self.assertTrue(downloaded[0].exists());self.assertTrue((root/'trials'/job['id']/'result.json').exists())   # video kept for reuse

    def test_completed_training_reuses_features_after_video_removal(self):
        import neptune_video_labels as labels
        import neptune_games as games
        from test_game_action_labels import game_label
        from test_video_labels import ndjson
        with tempfile.TemporaryDirectory() as tmp,patch('neptune_yolo.fingerprint',return_value='test-detector'):
            root=Path(tmp);home=root/'home';work=home/'training';media=root/'cache';store=labels.Store(work/'labels')
            rows=[game_label(1),game_label(2,start_ms=95000,end_ms=95000)]
            export=root/'labels.ndjson';export.write_text(ndjson(rows));labels.ingest(store,path=export)
            source={'status':'verified','sha256':'a'*64,'duration_ms':180400,'file':'AAAAAAAAAAA.mp4'}
            training.write(store.root/'sources.json',{'AAAAAAAAAAA':source})
            game=games.select('2026test',home);signature=training.prepared_signature(source,rows,['gb:score_10_fuel'],game)
            prepared=media/'prepared'/game['fingerprint']/(signature+'.json')
            training.write(prepared,{'schema_version':2,'features':{},'examples':[],'skipped':{},'scoring_examples':[],'scoring_skipped':{},'diagnostics':{}})
            training.write(prepared.with_suffix('.ready'),{'bytes':prepared.stat().st_size,'sha256':labels.sha256_file(prepared)})
            with patch('neptune_video_labels.verify_sources',side_effect=AssertionError('Completed matches must not fetch removed videos')):
                result=training.run(work,2026,export_path=export,cache_root=media,progress=lambda s:None)
            self.assertTrue(Path(result['folder']).joinpath('report.json').exists())
            self.assertFalse((media/'videos/AAAAAAAAAAA.mp4').exists())
            changed=[dict(rows[0],start_ms=94000,end_ms=94000),rows[1]]
            self.assertNotEqual(training.prepared_signature(source,changed,['gb:score_10_fuel'],game),signature)

    def test_evaluation_releases_each_match_before_the_next_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=fixtures.PageWorker().reference_job(root)
            second=copy.deepcopy(job['request']['matches'][0]);second.update(match_key='2026otherheldout_qm1',source_url='https://www.youtube.com/watch?v=BBBBBBBBBBB',source_sha256='b'*64);job['request']['matches'].append(second)
            downloaded=[]
            def download(match,path,stage):
                if downloaded:self.assertTrue(downloaded[-1].exists())   # kept for reuse
                path.write_bytes(b'video');downloaded.append(path)
            def sha(path):return 'b'*64 if Path(path).name.startswith('BBBB') else 'a'*64
            def facts(video,*args,**kwargs):
                result=fixtures.facts();result['source']['sha256']=kwargs['source_sha256'];return result
            with patch('neptune_helper.download_video',side_effect=download),patch('neptune_video_labels.sha256_file',side_effect=sha),patch('neptune_video_labels.probe_duration_ms',return_value=200000),patch('neptune_facts.analyze_video',side_effect=facts),patch('neptune_training.features',side_effect=fixtures.feature):
                worker.evaluate({'site':'https://example.org'},job,lambda s:None,lambda *args:{'state':'evaluation_complete'},root)
            self.assertEqual(len(downloaded),2);self.assertTrue(all(p.exists() for p in downloaded))   # kept for reuse
            saved=root/'evaluations'/job['id'];self.assertTrue((saved/'result.json').exists());self.assertTrue((saved/'evaluation-match-results.json').exists())


if __name__=='__main__':unittest.main()
