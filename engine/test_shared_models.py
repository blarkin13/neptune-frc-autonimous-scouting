import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import queue
import neptune_games as games
import neptune_shared_models as shared
from neptune_helper_gui import HelperWindow

class Field:
    def __init__(self,value=''):self.value=value
    def get(self):return self.value
    def set(self,v):self.value=v
    def current(self):return 0
class Immediate:
    def __init__(self,target,**kw):self.target=target
    def start(self):self.target()

@patch("neptune_shared_models.public_https",side_effect=lambda url:url)
@patch("neptune_helper_gui.public_https",side_effect=lambda url:url)
class SharedTests(unittest.TestCase):
    def test_public_catalog_without_token(self,*_):
        # A recovered unsubmitted draft used to leave the catalog permanently blank.
        w=S(busy=False,prepared=True,season=Field('2026'),event_picker=Field(),site=Field('https://neptunefrc.com'),events=[],messages=queue.Queue(),activity=lambda text:None)
        with patch('neptune_helper_gui.threading.Thread',Immediate),patch('neptune_helper_gui.request',return_value={'events':[{'key':'2026test','name':'Test'}]}) as req:
            HelperWindow.load_events(w)
        self.assertEqual(w.messages.get()[0],'events');self.assertNotIn('token',req.call_args.kwargs)
        w.events=[{'key':'2026test'}]
        with patch('neptune_helper_gui.threading.Thread',Immediate),patch('neptune_helper_gui.request',return_value={'matches':[]}) as req:
            HelperWindow.load(w)
        self.assertEqual(w.messages.get(),('matches',[]));self.assertNotIn('token',req.call_args.kwargs)

    def test_close_keeps_saved_draft(self,*_):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder);claim=state/'active.json';draft=state/'saved-result.json'
            claim.write_text('{"saved":true}');draft.write_text('{"summary":"Keep this"}')
            w=S(busy=False,process=None,prepared=True,review_heartbeat='timer',root=Mock(),runtime=Mock(),state=state)
            HelperWindow.close(w)
            self.assertTrue(claim.exists());self.assertTrue(draft.exists());self.assertEqual(draft.read_text(),'{"summary":"Keep this"}')
            w.root.destroy.assert_called_once();w.root.after_cancel.assert_called_once_with('timer')

    def test_recovered_draft_without_login_does_not_heartbeat(self,*_):
        from unittest.mock import Mock
        w=S(prepared=True,review_heartbeat=None,token=Field(),site=Field('https://neptunefrc.com'),root=Mock())
        with patch('neptune_helper_gui.request') as req:HelperWindow.renew_review(w)
        req.assert_not_called();w.root.after.assert_not_called()

    def test_no_release_does_not_use_local_training(self,*_):
        with tempfile.TemporaryDirectory() as home:
            response={'schema_version':1,'season':2026,'game_pack':games.profiles()[str(2026)],'model':None}
            with patch.object(shared,'request',return_value=response):data,game,model=shared.refresh('https://neptunefrc.com',2026,Path(home))
            self.assertIsNone(model);self.assertEqual(game['fingerprint'],games.select('2026test')['fingerprint'])
            self.assertTrue((Path(home)/'shared-models/2026.json').is_file())
            self.assertFalse((Path(home)/'training').exists())

    def test_wrong_season_and_failed_benchmark_rejected(self,*_):
        with tempfile.TemporaryDirectory() as home:
            with patch.object(shared,'request',return_value={'schema_version':1,'season':2025}):
                with self.assertRaises(ValueError):shared.refresh('https://neptunefrc.com',2026,Path(home))
            response={'schema_version':1,'season':2026,'game_pack':games.profiles()['2026'],'model':{'heads':{'scoring':{}},'release_ready':True,'model_id':'test'},'benchmark':{'release_ready':False,'model_id':'test'}}
            with patch.object(shared,'request',return_value=response),patch('neptune_training.model_valid'):
                with self.assertRaises(ValueError):shared.refresh('https://neptunefrc.com',2026,Path(home))
