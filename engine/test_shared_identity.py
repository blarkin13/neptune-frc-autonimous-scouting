"""The organization's shared robot-identity model: reported only after it passes, used where a helper has none of its own."""
import json
from pathlib import Path
import tempfile
import unittest

import neptune_review_learning as rl

MODEL = {'weights': [.1, -.2, .3, .4, -.5], 'bias': -1.2}


class SharedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)

    def test_candidate_is_reported_without_its_model(self):
        (self.root / 'association-candidate.json').write_text(json.dumps({'version': rl.VERSION, 'status': 'candidate', 'reason': 'check needed', 'pairs': 9, 'matches': ['2026x_qm1'], 'model': MODEL}))
        out = rl.report(self.root)
        self.assertEqual((out['report']['status'], out['model']), ('candidate', None))

    def test_passed_model_is_reported_with_its_model(self):
        (self.root / 'association-active.json').write_text(json.dumps({'version': rl.VERSION, 'model': MODEL, 'pairs': 9, 'matches': ['2026x_qm1'], 'independent_identity_validation': {'passed': True, 'correct': 200}}))
        out = rl.report(self.root)
        self.assertEqual((out['report']['status'], out['model']), ('active', MODEL))

    def test_shared_model_is_used_when_this_helper_has_none(self):
        self.assertIsNone(rl.active_association(self.root))
        rl.save_shared({'version': rl.VERSION, 'model': MODEL, 'sha256': 'x', 'trained_by': 'mac'}, self.root)
        self.assertEqual(rl.active_association(self.root), MODEL)

    def test_invalid_shared_model_is_refused(self):
        with self.assertRaises(ValueError):
            rl.save_shared({'version': rl.VERSION, 'model': {'weights': [1, 2], 'bias': 0}}, self.root)
        with self.assertRaises(ValueError):
            rl.save_shared({'version': 'other', 'model': MODEL}, self.root)


if __name__ == '__main__':
    unittest.main()
