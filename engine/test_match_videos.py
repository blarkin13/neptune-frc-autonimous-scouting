import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import neptune_match_videos as mv

class MatchVideos(unittest.TestCase):
    def test_fetch_verifies_and_publishes_original_bytes(self):
        raw=b'original source bytes'; sha=hashlib.sha256(raw).hexdigest()
        def api(config, action, data):
            if action=='video_cache_info': return {'available':True,'video':{'bytes':len(raw),'sha256':sha}}
            return {'offset':0,'sha256':sha,'data_b64':base64.b64encode(raw).decode()}
        with tempfile.TemporaryDirectory() as d, patch.object(mv,'_api',side_effect=api):
            p=Path(d)/'v.mp4'; self.assertTrue(mv.fetch({},'AAAAAAAAAAA',p,lambda s:None)); self.assertEqual(p.read_bytes(),raw)

    def test_bad_shared_source_never_replaces_existing_file(self):
        raw=b'wrong source video bytes'; sha=hashlib.sha256(raw).hexdigest()
        def api(config, action, data):
            if action=='video_cache_info': return {'available':True,'video':{'bytes':len(raw),'sha256':'a'*64}}
            return {'offset':0,'sha256':sha,'data_b64':base64.b64encode(raw).decode()}
        with tempfile.TemporaryDirectory() as d, patch.object(mv,'_api',side_effect=api):
            p=Path(d)/'v.mp4';p.write_bytes(b'previous')
            with self.assertRaisesRegex(ValueError,'SHA-256'):mv.fetch({},'AAAAAAAAAAA',p,lambda s:None)
            self.assertEqual(p.read_bytes(),b'previous');self.assertEqual(list(Path(d).glob('*.pending')),[])

    def test_resume_upload_starts_at_acknowledged_chunk(self):
        raw=b'x'*(mv.CHUNK_BYTES+16); sha=hashlib.sha256(raw).hexdigest();calls=[]
        def api(config,action,data):
            calls.append((action,data))
            if action=='video_cache_begin':return {'available':False,'offset':mv.CHUNK_BYTES,'upload_id':'lease'}
            self.assertEqual(data['offset'],mv.CHUNK_BYTES);self.assertEqual(base64.b64decode(data['data_b64']),b'x'*16)
            return {'available':True,'offset':len(raw),'video':{'sha256':sha}}
        with tempfile.TemporaryDirectory() as d,patch.object(mv,'_api',side_effect=api):
            p=Path(d)/'v.mp4';p.write_bytes(raw);self.assertTrue(mv.upload({},'AAAAAAAAAAA',p,lambda s:None)['available'])
        self.assertEqual(len(calls),2)

    def test_cache_hit_never_requests_youtube(self):
        import neptune_robot_labels as rl
        with tempfile.TemporaryDirectory() as d,patch.object(rl,'local_video',return_value=None),patch.object(mv,'fetch',return_value=True),patch.object(rl,'youtube_download',side_effect=AssertionError('must use cache')):
            self.assertEqual(mv.acquire({'site':'https://example.com'},'AAAAAAAAAAA',Path(d)/'v.mp4'),Path(d)/'v.mp4')
