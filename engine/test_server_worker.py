"""File transport can return a real readiness report without a server token."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
import neptune_games as games

class ServerWorker(unittest.TestCase):
    def test_empty_fixture_returns_honest_report_through_file_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);job={'id':'server-fixture','lease':'fixture-only','season':2026,'kind':'training','control':{'kind':'training'},'snapshot':'','snapshot_sha256':hashlib.sha256(b'').hexdigest(),'game_pack':json.loads(games.BUILTIN.read_text())['seasons']['2026']}
            (folder/'job.json').write_text(json.dumps(job));(folder/'commands.json').write_text('{}')
            script=Path(__file__).resolve().parents[1]/'neptune_secure/community-learning/server_run.py'
            code="import runpy,sys; n=runpy.run_path(sys.argv.pop(1)); n['main'].__globals__['check']=lambda:{'ready':True}; n['main']()"
            env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent))
            run=subprocess.run([sys.executable,'-c',code,str(script),'--job',str(folder/'job.json'),'--root',str(folder/'work'),'--output',str(folder/'result.json'),'--commands',str(folder/'commands.json'),'--progress',str(folder/'progress.json')],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr);output=json.loads((folder/'result.json').read_text());self.assertEqual(output['action'],'finish');result=output['payload']['result'];self.assertEqual(result['model']['heads'],{});self.assertFalse(result['model']['release_ready']);self.assertEqual(result['report']['scoring'].get('training_robots',0),0)

if __name__=='__main__':unittest.main()
