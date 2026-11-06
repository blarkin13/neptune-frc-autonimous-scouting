import unittest

import neptune_review_video as review


class RobotReview(unittest.TestCase):
    def test_report_explains_actual_holdouts_and_rejected_small_gain(self):
        report = {'holdout_match': '2026txcmp1_qm4',
                  'holdout_matches': ['2026brba_qm5', '2026mnwi_qm5', '2026txcmp1_qm4'],
                  'new': {'f1': .886, 'recall': .881, 'precision': .890},
                  'current': {'f1': .874}, 'margin': .020, 'adopted': False,
                  'train_frames': 3260, 'check_frames': 125}
        title, description = review.describe('train', report, 'test')
        self.assertIn('3 held-out matches', title)
        self.assertIn('0.886 vs 0.874', title)
        for match in report['holdout_matches']:
            self.assertIn(match, description)
        self.assertIn('+0.012', description)
        self.assertIn('0.020', description)
        self.assertIn('kept the detector in use', description)
        self.assertIn('missing reference label', description)
        self.assertFalse(set('<>') & set(title+description), 'YouTube rejects angle brackets')

    def test_overlay_draws_matched_prediction_at_its_actual_extent(self):
        import numpy as np
        truth = [[.20, .30, .40, .40], [.60, .30, .70, .40]]
        predicted = [[.22, .30, .42, .40], [.80, .30, .90, .40]]
        img, found = review.robot_frame_overlay(np.zeros((720, 1280, 3), np.uint8), truth, predicted)
        self.assertEqual(found, {0})
        # Matched prediction and reference differ: both boundaries must remain visible.
        self.assertEqual(tuple(img[250, int(.22*1280)]), review.GREEN)
        self.assertEqual(tuple(img[250, int(.20*1280)]), review.WHITE)
        self.assertEqual(tuple(img[250, int(.60*1280)]), review.RED)
        self.assertEqual(tuple(img[250, int(.80*1280)]), review.YELLOW)

    def test_legacy_single_holdout_report_remains_readable(self):
        held, lines = review.robot_review_summary({'holdout_match': '2026example_qm5'})
        self.assertEqual(held, ['2026example_qm5'])
        self.assertIn('Held out: 2026example_qm5', lines)

    def test_frame_names_come_from_each_image_not_primary_holdout(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'manifest.json').write_text(json.dumps({'frames': [
                {'image': 'images/a.jpg', 'match_key': '2026first_qm5'},
                {'image': 'images/b.jpg', 'match_key': '2026second_qm5'}]}))
            self.assertEqual(review.robot_frame_names([(root/'images/a.jpg', [])]),
                             {'a.jpg': '2026first_qm5', 'b.jpg': '2026second_qm5'})


if __name__ == '__main__':
    unittest.main()
