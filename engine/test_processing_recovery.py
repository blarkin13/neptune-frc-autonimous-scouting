import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from neptune_helper import analyze, infer

class RecoveryTests(unittest.TestCase):
    def test_cut_off_or_invalid_ai_response_has_clear_error(self):
        for choice,phrase in [({'finish_reason':'length','message':{'content':'{"x":'}},'cut off'),({'finish_reason':'stop','message':{'content':'{"x":'}},'invalid response')]:
            with patch('neptune_helper.request',return_value={'choices':[choice]}):
                with self.assertRaisesRegex(ValueError,phrase):infer('local','model',[])

    def test_completed_segments_survive_retry(self):
        with tempfile.TemporaryDirectory() as path:
            folder=Path(path);video=b'test video';(folder/'source.mp4').write_bytes(video)
            for i in range(6):(folder/f'frame-{i:04}.jpg').write_bytes(b'test frame')
            match={'source_url':'https://example.org/video.mp4','source_sha256':hashlib.sha256(video).hexdigest(),'duration_ms':12000,'roster':{'red':[1,2,3],'blue':[4,5,6]},'rules':'Test rules'}
            def batch(start):return {'observations':[{'start_ms':start,'end_ms':start+1000,'team':None,'certainty':'uncertain','note':'Identity obscured.'}]}
            with patch('neptune_helper.subprocess.check_output',return_value=b'12'),patch('neptune_helper.infer',side_effect=[batch(0),ValueError('interrupted')]):
                with self.assertRaisesRegex(ValueError,'interrupted'):analyze({'match':match},'local','model',folder,['Starting'],pipeline='ai')
            self.assertEqual(len(list(folder.glob('*-segment-[0-9][0-9][0-9][0-9].json'))),1)
            with patch('neptune_helper.subprocess.check_output',return_value=b'12'),patch('neptune_helper.infer',return_value=batch(6000)) as engine,patch('neptune_helper.summarize_observations',return_value='Uncertain identity.'):
                result=analyze({'match':match},'local','model',folder,['Starting'],pipeline='ai')
                self.assertEqual(engine.call_count,1)
                images=[c for c in engine.call_args.args[2] if c['type']=='image_url']
                self.assertEqual(len(images),3)
                self.assertEqual(len(result['observations']),2)

    def test_reconnect_reclaims_stale_device_job_without_deleting_work(self):
        import json
        import sys
        from neptune_helper import main, RemoteError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            match={'id':7,'source_url':'https://example.org/video.mp4','source_sha256':'a'*64,'duration_ms':10000,'roster':{'red':[1,2,3],'blue':[4,5,6]},'rules':'Rules'}
            old={'attempt_id':'old','lease_token':'old-secret','_site':'https://example.org','match':dict(match)}
            (root/'active.json').write_text(json.dumps(old));(root/'match-7').mkdir();(root/'match-7/keep.txt').write_text('saved segment')
            actions=[]
            def api(url,payload=None,token=None):
                action=url.split('action=')[1];actions.append(action)
                if action=='heartbeat':raise RemoteError(403,'Invalid attempt credentials.')
                if action=='claim':return {'attempt_id':'new','lease_token':'new-secret','match':dict(match)}
                raise AssertionError(action)
            result={'schema_version':1,'source_sha256':'a'*64,'summary':'Draft','model':'model','runtime':'local','prompt_version':'test','inference_location':'local','observations':[{'start_ms':0,'end_ms':1000,'team':None,'certainty':'uncertain','note':'Unknown identity.'}]}
            with patch.object(sys,'argv',['helper','--site','https://example.org','--match','7','--model','model','--prepare-only','--state',directory]),patch.dict('os.environ',{'NEPTUNE_HELPER_TOKEN':'test-token'}),patch('neptune_helper.public_https',side_effect=lambda url:url),patch('neptune_helper.request',side_effect=api),patch('neptune_helper.shutil.which',return_value='/tool'),patch('neptune_setup.video_js_runtime',return_value={}),patch('neptune_helper.analyze',return_value=result):
                main()
            self.assertEqual(actions,['heartbeat','claim'])
            self.assertEqual(json.loads((root/'active.json').read_text())['attempt_id'],'new')
            self.assertTrue((root/'reservation-backups/old.json').is_file())
            self.assertEqual((root/'match-7/keep.txt').read_text(),'saved segment')

    def test_observation_schema_has_real_enum_values(self):
        from neptune_helper import observation_schema,validate_segment
        schema=observation_schema(1000,6000,[1,2,3,4,5,6])
        props=schema['properties']['observations']['items']['properties']
        self.assertEqual(props['certainty']['enum'],['observed','uncertain'])
        self.assertEqual(props['team']['enum'],[None,1,2,3,4,5,6])
        self.assertEqual(props['start_ms']['minimum'],1000)
        with self.assertRaisesRegex(ValueError,'must use observed or uncertain'):
            validate_segment({'observations':[{'start_ms':1000,'end_ms':2000,'team':None,'certainty':'observed_or_uncertain','note':'Unknown identity.'}]},{},1000,6000,'model')

    def test_bad_certainty_is_retained_and_retried_without_relabeling(self):
        with tempfile.TemporaryDirectory() as path:
            folder=Path(path);video=b'video';(folder/'source.mp4').write_bytes(video)
            for i in range(3):(folder/f'frame-{i:04}.jpg').write_bytes(b'frame')
            match={'source_url':'https://example.org/video.mp4','source_sha256':hashlib.sha256(video).hexdigest(),'duration_ms':6000,'roster':{'red':[1,2,3],'blue':[4,5,6]},'rules':'Rules'}
            invalid={'observations':[{'start_ms':0,'end_ms':1000,'team':None,'certainty':'observed_or_uncertain','note':'Identity unclear.'}]}
            valid={'observations':[dict(invalid['observations'][0],certainty='uncertain')]}
            with patch('neptune_helper.subprocess.check_output',return_value=b'6'),patch('neptune_helper.infer',side_effect=[invalid,valid]) as engine,patch('neptune_helper.summarize_observations',return_value='Identity remains unclear.'):
                result=analyze({'match':match},'local','model',folder,['Starting'],pipeline='ai')
                self.assertEqual(engine.call_count,2)
                self.assertIn('schema',engine.call_args.kwargs)
            self.assertEqual(result['observations'][0]['certainty'],'uncertain')
            import json
            raw=next(folder.glob('*response-0.json'))
            self.assertEqual(json.loads(raw.read_text())['observations'][0]['certainty'],'observed_or_uncertain')


class StaleReleaseTests(unittest.TestCase):
    def test_release_of_an_already_ended_reservation_clears_local_state(self):
        import json, sys, io, contextlib
        from neptune_helper import main, RemoteError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'active.json').write_text(json.dumps({'attempt_id':'old','lease_token':'x','_site':'https://example.org','match':{'id':7}}))
            (root/'claim-request.json').write_text('{}');(root/'old-result.json').write_text('{"draft":true}')
            def api(url,payload=None,token=None):raise RemoteError(403,'Invalid attempt credentials.')
            with patch.object(sys,'argv',['helper','--site','https://example.org','--release','--state',directory]),patch.dict('os.environ',{'NEPTUNE_HELPER_TOKEN':'t'}),patch('neptune_helper.public_https',side_effect=lambda u:u),patch('neptune_helper.request',side_effect=api),contextlib.redirect_stdout(io.StringIO()) as out:
                main()
            self.assertFalse((root/'active.json').exists())
            self.assertTrue((root/'old-result.json').exists())
            self.assertIn('already ended',out.getvalue())
