import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import neptune_robot_labels as rl


class RobotLabels(unittest.TestCase):
    def test_boxes_are_clipped_and_converted(self):
        for got, want in zip(rl.box_xywh({'x': .1, 'y': .2, 'w': .2, 'h': .1}), [.2, .25, .2, .1]):
            self.assertAlmostEqual(got, want)
        x = rl.box_xywh({'x': -.05, 'y': .9, 'w': .1, 'h': .2})
        self.assertAlmostEqual(x[0], .025); self.assertAlmostEqual(x[3], .1)
        self.assertIsNone(rl.box_xywh({'x': 1.1, 'y': .5, 'w': .1, 'h': .1}))

    def test_matches_without_a_video_are_skipped_and_reported(self):
        doc = {'video_id': 'AAAAAAAAAAA', 'match_key': '2026test_qm1', 'frames': {'1000': {'complete': True, 'boxes': []}}}
        with tempfile.TemporaryDirectory() as t, patch.object(rl, 'local_video', return_value=None):
            r = rl.build([doc], t)
        self.assertEqual(r['frames'], 0); self.assertEqual(r['skipped'], {'2026test_qm1': 'video_not_available'})

    def test_incomplete_frames_are_not_training_data(self):
        doc = {'video_id': 'AAAAAAAAAAA', 'match_key': '2026test_qm1', 'frames': {'1000': {'complete': False, 'boxes': []}}}
        with tempfile.TemporaryDirectory() as t, patch.object(rl, 'local_video', return_value=None):
            self.assertEqual(rl.build([doc], t)['skipped'], {})


    def test_training_reuses_exact_labelled_image_without_reextracting(self):
        import hashlib
        raw=b'exact-reviewed-frame'; sha=hashlib.sha256(raw).hexdigest()
        doc={'video_id':'AAAAAAAAAAA','match_key':'2026test_qm1','frames':{'1000':{'complete':True,'boxes':[],'frame_sha256':sha}}}
        with tempfile.TemporaryDirectory() as folder:
            video=Path(folder)/'source.mp4';video.write_bytes(b'source')
            def fetch(vid,t,digest,path):
                self.assertEqual((vid,t,digest),('AAAAAAAAAAA',1000,sha));path.write_bytes(raw)
            with patch.object(rl,'local_video',return_value=video),patch.object(rl.subprocess,'run',side_effect=AssertionError('must not re-extract')):
                r=rl.build([doc],Path(folder)/'output',snapshot_download=fetch)
                self.assertEqual(r['frames'],1)
                self.assertEqual((Path(folder)/'output/images/AAAAAAAAAAA_00001000.jpg').read_bytes(),raw)

    def test_changed_training_image_is_rejected(self):
        import hashlib
        doc={'video_id':'AAAAAAAAAAA','match_key':'2026test_qm1','frames':{'1000':{'complete':True,'boxes':[],'frame_sha256':hashlib.sha256(b'correct').hexdigest()}}}
        with tempfile.TemporaryDirectory() as folder:
            video=Path(folder)/'source.mp4';video.write_bytes(b'source')
            with patch.object(rl,'local_video',return_value=video):
                with self.assertRaisesRegex(ValueError,'does not match'):
                    rl.build([doc],Path(folder)/'output',snapshot_download=lambda vid,t,sha,p:p.write_bytes(b'wrong'))


if __name__ == '__main__':
    unittest.main()
