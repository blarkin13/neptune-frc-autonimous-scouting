"""Connection and package checks for generic installable training helpers."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import os
from types import SimpleNamespace
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'common'))
sys.path.insert(0, str(ROOT.parent / 'engine'))
import neptune_trainer_entry as entry
import neptune_trainer_pairing as pairing


class InstallableTrainerTests(unittest.TestCase):
    def test_windows_private_ffmpeg_is_on_path_for_shortcut_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(entry, 'sys', SimpleNamespace(platform='win32')), patch.dict(os.environ, {'LOCALAPPDATA': folder, 'PATH': 'C:\\Windows'}, clear=True):
                entry.configure_private_tools()
                self.assertEqual(os.environ['PATH'].split(os.pathsep)[0], str(Path(folder) / 'Neptune Trainer/tools/bin'))

    def test_connection_saved_without_exposing_token_in_package(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'trainer-connection.json'
            self.assertFalse(entry.valid_connection(target))
            entry.save_connection(target, {'access_token': 'a' * 64,
                                           'expires_at': 4102444800, 'computer_id': 'computer-1'})
            self.assertTrue(entry.valid_connection(target))
            self.assertEqual(json.loads(target.read_text())['site'], 'https://neptunefrc.com')
            self.assertFalse(target.with_name(target.name + '.next').exists())

    def test_private_robot_bundle_downloads_after_pairing_and_reuses_verified_copy(self):
        import neptune_trainer
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            credential = home / 'trainer-connection.json'
            entry.save_connection(credential, {'access_token': 'a' * 64,
                                               'expires_at': 4102444800, 'computer_id': 'computer-1'})
            files = {'best_bumper_model.pt': b'bumper model', 'coco_model.pt': b'context model'}
            manifest = {'schema_version': 1, 'seasons': [2026]}
            for key, name in [('bumper', 'best_bumper_model.pt'), ('context', 'coco_model.pt')]:
                manifest[key] = {'file': name, 'sha256': hashlib.sha256(files[name]).hexdigest()}
            files['manifest.json'] = json.dumps(manifest).encode()
            rows = [{'name': name, 'sha256': hashlib.sha256(data).hexdigest(),
                     'data': base64.b64encode(data).decode()} for name, data in files.items()]
            with patch.object(Path, 'home', return_value=home), patch.object(neptune_trainer, 'api', return_value={'files': rows}) as call:
                entry.ensure_robot_models(credential)
                entry.ensure_robot_models(credential)
            self.assertEqual(call.call_count, 1)
            self.assertEqual((home / '.neptune-trainer/robot-models/best_bumper_model.pt').read_bytes(), b'bumper model')

    def test_browser_pairing_uses_training_api_and_one_use_challenge(self):
        observed = {}
        def request(url, payload):
            if url.endswith('connect_start'):
                observed['start'] = payload
                return {'request_id': 'f' * 32, 'user_code': 'ABCD-1234', 'expires_in': 60}
            self.assertTrue(url.endswith('connect_exchange'))
            observed['exchange'] = payload
            challenge = base64.urlsafe_b64encode(hashlib.sha256(payload['verifier'].encode()).digest()).decode().rstrip('=')
            self.assertEqual(challenge, observed['start']['challenge'])
            self.assertEqual(payload['code'], 'd' * 64)
            return {'access_token': 'a' * 64, 'expires_at': 4102444800, 'computer_id': 'one'}
        def browser(url, new):
            self.assertTrue(url.startswith('https://neptunefrc.com/community/connect-training.php?request='))
            params = observed['start']
            callback = 'http://127.0.0.1:%d/neptune-connect?%s' % (
                params['port'], urllib.parse.urlencode({'state': params['state'], 'code': 'd' * 64}))
            def approve():
                with urllib.request.urlopen(callback, timeout=5) as response:
                    self.assertEqual(response.status, 200)
            thread = threading.Thread(target=approve)
            thread.start()
            observed['thread'] = thread
            return True
        messages = []
        with patch.object(pairing, 'request', side_effect=request), patch.object(pairing.webbrowser, 'open', side_effect=browser):
            result = pairing.connect_account('https://neptunefrc.com', messages.append, threading.Event())
        observed['thread'].join(5)
        self.assertEqual(result['computer_id'], 'one')
        self.assertIn('ABCD-1234', messages[0])


if __name__ == '__main__':
    unittest.main()
