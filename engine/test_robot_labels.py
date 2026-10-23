import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import neptune_robot_labels as rl


class RobotLabels(unittest.TestCase):
    def test_boxes_are_clipped_and_converted(self):
        self.assertEqual(rl.box_xywh({'x': .1, 'y': .2, 'w': .2, 'h': .1}), [.2, .25, .2, .1])
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


if __name__ == '__main__':
    unittest.main()
