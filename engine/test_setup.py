import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import neptune_helper
from neptune_setup import LocalSetup, MODEL, MODEL_DIGESTS


class SetupTests(unittest.TestCase):
    def test_facts_pipeline_needs_no_model(self):
        setup = LocalSetup()
        setup.pipeline = 'facts'
        setup.ocr = {'backend': 'apple-vision'}
        with patch.object(setup, 'start'), patch('neptune_setup.local_request') as network:
            progress = []
            setup.install(progress.append)
            network.assert_not_called()
            self.assertIn('ready', progress[-1])

    def test_correct_installed_model_reused(self):
        setup = LocalSetup()
        setup.pipeline = 'ai'
        with patch.object(setup, 'start'), patch.object(setup, 'tags', return_value=[{'name':MODEL,'digest':MODEL_DIGESTS[0]}]), patch('neptune_setup.local_request') as network:
            setup.install(lambda _:None)
            network.assert_not_called()

    def test_missing_model_is_downloaded_with_progress(self):
        setup = LocalSetup()
        setup.pipeline = 'ai'
        setup.base = 'http://127.0.0.1:12345'
        progress=[]
        stream=io.BytesIO(b'{"status":"pulling","total":100,"completed":50}\n{"status":"success"}\n')
        with patch.object(setup, 'start'), patch.object(setup, 'ready', side_effect=[False,True]), patch('neptune_setup.shutil.disk_usage') as disk, patch('neptune_setup.local_request', return_value=stream) as network:
            disk.return_value.free=10*1024**3
            setup.install(progress.append)
            self.assertIn('/api/pull', network.call_args.args[0])
            self.assertEqual(network.call_args.args[1]['model'],MODEL)
            self.assertTrue(any('50%' in text for text in progress))

    def test_missing_model_checks_disk_before_download(self):
        setup = LocalSetup()
        setup.pipeline = 'ai'
        with patch.object(setup, 'start'), patch.object(setup, 'ready', return_value=False), patch('neptune_setup.shutil.disk_usage') as disk, patch('neptune_setup.local_request') as network:
            disk.return_value.free=100
            with self.assertRaisesRegex(ValueError,'5 GB'):
                setup.install(lambda _:None)
            network.assert_not_called()

    def test_wrong_model_version_not_reused(self):
        setup = LocalSetup()
        with patch.object(setup, 'tags', return_value=[{'name':MODEL,'digest':'unknown'}]):
            self.assertFalse(setup.ready())

    def test_existing_draft_requires_explicit_submit(self):
        match={'id':1,'source_sha256':'a'*64,'duration_ms':10000,'roster':{'red':[1,2,3],'blue':[4,5,6]}}
        payload={'schema_version':1,'source_sha256':'a'*64,'summary':'Draft.', 'model':'local','runtime':'local','prompt_version':'1','inference_location':'local','observations':[{'start_ms':0,'end_ms':1000,'team':None,'certainty':'uncertain','note':'Obscured.'}]}
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            claim={'attempt_id':'attempt','lease_token':'token','match':match,'_site':'https://neptunefrc.com'}
            (folder/'active.json').write_text(json.dumps(claim));(folder/'attempt-result.json').write_text(json.dumps(payload))
            args=['helper','--site','https://neptunefrc.com','--match','1','--model','local','--state',tmp]
            with patch.object(sys,'argv',args),patch.dict('os.environ',{'NEPTUNE_HELPER_TOKEN':'test'}),patch('neptune_helper.public_https',side_effect=lambda x:x),patch('neptune_helper.shutil.which',return_value='/bundled/tool'),patch('neptune_helper.request') as api,contextlib.redirect_stdout(io.StringIO()) as output:
                neptune_helper.main()
                self.assertTrue(all('action=heartbeat' in c.args[0] for c in api.call_args_list))
                self.assertIn('RESULT_READY',output.getvalue())
                self.assertTrue((folder/'active.json').exists())
            with patch.object(sys,'argv',args+['--submit']),patch.dict('os.environ',{'NEPTUNE_HELPER_TOKEN':'test'}),patch('neptune_helper.public_https',side_effect=lambda x:x),patch('neptune_helper.request',return_value={'submitted':True}) as api,contextlib.redirect_stdout(io.StringIO()):
                neptune_helper.main()
                self.assertEqual(api.call_count,1)
                self.assertIn('action=submit',api.call_args.args[0])
                self.assertFalse((folder/'active.json').exists())
                self.assertTrue((folder/'attempt-result.json').exists())


if __name__=='__main__':unittest.main()
