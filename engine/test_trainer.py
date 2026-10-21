import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import neptune_games as games
import neptune_trainer as trainer

class Trainer(unittest.TestCase):
    def test_cpu_does_not_install_a_gpu_library(self):
        with patch('subprocess.Popen',side_effect=AssertionError('unneeded installation')):
            self.assertEqual(trainer.setup_device('CPU',lambda s:None)['device'],'cpu')

    def test_unavailable_gpu_requires_explicit_cpu_choice(self):
        torch=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda:False))
        with patch.dict('sys.modules',{'torch':torch}):
            with self.assertRaisesRegex(ValueError,'GPU unavailable'):trainer.setup_device('NVIDIA GPU',lambda s:None)

    def test_snapshot_fingerprint_required(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)):
            with self.assertRaisesRegex(ValueError,'fingerprint'):trainer.run_job({},dict(id='job',snapshot='',snapshot_sha256='bad'),{'device':'cpu'},lambda s:None)

    def test_real_readiness_run_returns_report_and_keeps_local_result(self):
        pack=json.loads(games.BUILTIN.read_text())['seasons']['2026']
        job={'id':'test','season':2026,'lease':'local-only','game_pack':pack,'snapshot':'','snapshot_sha256':hashlib.sha256(b'').hexdigest()}
        sent=[]
        def api(config,action,payload):
            sent.append((action,payload));return {'ok':True,'state':'needs_data'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(trainer,'HOME',Path(tmp)),patch.object(trainer,'api',api),patch.dict(os.environ,{},clear=False):
            result=trainer.run_job({'site':'https://example.org'},job,{'device':'cpu'},lambda s:None)
            self.assertEqual(result['state'],'needs_data')
            self.assertTrue((Path(tmp)/'jobs/test/result.json').exists())
            action,payload=sent[-1];self.assertEqual(action,'finish')
            self.assertEqual(payload['result']['model']['heads'],{})
            self.assertFalse(payload['result']['model']['release_ready'])
            self.assertEqual(payload['result']['report']['training_computer']['device'],'cpu')

if __name__=='__main__':unittest.main()
