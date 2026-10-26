import unittest
import json
import sys
from types import SimpleNamespace
from contextlib import nullcontext
import tempfile
from pathlib import Path
from unittest.mock import patch

import neptune_robot_jobs as rj


class RobotJobs(unittest.TestCase):
    def test_score_matches_one_to_one_by_band(self):
        wide = [.40, .40, .42, .42]; close = [.10, .80, .14, .84]
        out = rj.score([wide, close], [wide, [.40, .40, .421, .421], [.5, .5, .51, .51]])
        self.assertEqual(out['wide'], [1, 1, 3])          # one match; a duplicate and a stray stay unmatched
        self.assertEqual(out['closeup'], [0, 1, 0])

    def test_adoption_needs_a_clear_margin(self):
        self.assertGreater(rj.ADOPT_MARGIN, 0)
        new, old = {'f1': .70}, {'f1': .69}
        self.assertFalse(new['f1'] >= old['f1']+rj.ADOPT_MARGIN)

    def test_training_starts_from_current_bumper_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); weights = root/'current.pt'; weights.write_bytes(b'weights')
            (root/'manifest.json').write_text(json.dumps({'trained_on': ['2026train_qm1']}))
            with patch.object(rj, 'SHARED', root), patch.object(rj, 'current_wide_weights', return_value=weights):
                self.assertEqual(rj.training_base('2026held_qm2'), weights)

    def test_starting_weights_must_not_have_seen_holdout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); weights = root/'current.pt'; weights.write_bytes(b'weights')
            (root/'manifest.json').write_text(json.dumps({'trained_on': ['2026held_qm2']}))
            with patch.object(rj, 'SHARED', root), patch.object(rj, 'current_wide_weights', return_value=weights):
                with self.assertRaisesRegex(ValueError, 'starting detector trained'):
                    rj.training_base('2026held_qm2')

    def test_no_context_fallback_when_bumper_weights_missing(self):
        with patch.object(rj, 'current_wide_weights', return_value=None):
            with self.assertRaisesRegex(ValueError, 'wide bumper detector'):
                rj.training_base('2026held_qm2')

    def rows(self):
        def row(match, split, t):
            return {'match_key': match, 'split': split, 'source_sha256': 'a'*64,
                    'image_sha256': str(t), 'video_time_ms': t, 'boxes': []}
        return [row('2026few_qm1', 'train', 1000), row('2026held_qm2', 'val', 2000)]

    def test_report_includes_small_training_matches(self):
        audit = rj.dataset_audit({'frames': self.rows()}, '2026held_qm2')
        self.assertEqual(audit['trained_on'], ['2026few_qm1'])
        self.assertEqual(audit['frames_per_match']['2026few_qm1'], 1)

    def test_evaluation_fingerprint_changes_with_reference_not_training_rows(self):
        rows = self.rows(); first = rj.dataset_audit({'frames': rows}, '2026held_qm2')['evaluation_sha256']
        rows[0]['boxes'] = [{'class_id': 0, 'xywh': [.5, .5, .1, .1]}]
        self.assertEqual(first, rj.dataset_audit({'frames': rows}, '2026held_qm2')['evaluation_sha256'])
        rows[1]['boxes'] = rows[0]['boxes']
        self.assertNotEqual(first, rj.dataset_audit({'frames': rows}, '2026held_qm2')['evaluation_sha256'])

    def test_holdout_leakage_in_built_dataset_is_rejected(self):
        rows = self.rows(); rows[1]['split'] = 'train'
        with self.assertRaisesRegex(ValueError, 'never enter'):
            rj.dataset_audit({'frames': rows}, '2026held_qm2')

    def test_full_training_job_uses_warm_start_and_reports_all_matches(self):
        import neptune_robot_labels as labels
        import neptune_detector_training as dataset
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); parent = root/'parent.pt'; parent.write_bytes(b'parent')
            manifest = root/'manifest.json'; rows = self.rows()
            for row in rows:
                row['image'] = 'unused.jpg'
            manifest.write_text(json.dumps({'frames': rows}))
            bestdir = root/'fit'; (bestdir/'weights').mkdir(parents=True)
            (bestdir/'weights/best.pt').write_bytes(b'candidate')
            used = []
            class Model:
                names = {0: 'red', 1: 'blue'}
                def __init__(self, weights): used.append(weights)
                def add_callback(self, *args): pass
                def train(self, **kwargs): return SimpleNamespace(save_dir=bestdir)
            docs = [{'match_key': m, 'frames': {str(i): {'complete': True} for i in range(8)}}
                    for m in ('2026few_qm1', '2026held_qm2')]
            built = {'manifest': str(manifest), 'frames': 2, 'train': 1, 'val': 1, 'boxes': 0, 'skipped': {}}
            with patch.dict(sys.modules, {'ultralytics': SimpleNamespace(YOLO=Model)}), \
                 patch.object(rj, 'HOME', root), patch.object(labels, 'sync', return_value=docs), \
                 patch.object(labels, 'build', return_value=built), patch.object(dataset, 'prepare', return_value=root/'data.yaml'), \
                 patch.object(rj, 'training_base', return_value=parent), patch.object(rj, 'batch_progress'), \
                 patch.object(rj, 'all_cores', return_value=nullcontext()), patch.object(rj, 'train_device', return_value='cpu'), \
                 patch.object(rj, 'current_wide_weights', return_value=parent), \
                 patch.object(rj, 'api', return_value={'datasets': []}), \
                 patch.object(rj, 'evaluate', side_effect=[{'f1': .5}, {'f1': .7}]), patch.object(rj, 'send_review', return_value={}):
                report = rj.train({}, {'id': 'test', 'holdout': '2026held_qm2'}, lambda message: None)
            self.assertEqual(used, [str(parent)])
            self.assertFalse(report['adopted'])
            self.assertEqual(report['training_recipe'], 'adopted-bumper-warm-start-v1')
            self.assertEqual(report['trained_on'], ['2026few_qm1'])
            self.assertEqual(len(report['starting_weights_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
