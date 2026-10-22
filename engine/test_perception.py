import json
import tempfile
import unittest
from pathlib import Path

import neptune_perception as perception
import neptune_yolo


class Perception(unittest.TestCase):
    def test_identities_separate_reusable_and_season_parts(self):
        p = perception.perception_identity(); g = perception.game_identity({'game_key': '2027-next', 'fingerprint': 'f'}, 'robot-r3d18-clip-v1')
        self.assertEqual(set(p['components']), {'robot_detector', 'tracking', 'identity_solver', 'field_layout_detector'})
        self.assertEqual(g['components']['game_key'], '2027-next')
        self.assertNotIn('game_key', p['components'])

    def test_game_independent_detector_serves_a_new_season(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name in ('bumper.pt', 'context.pt'):
                (root/name).write_bytes(b'x')
            import hashlib
            sha = hashlib.sha256(b'x').hexdigest()
            row = lambda f: {'file': f, 'sha256': sha}
            (root/'manifest.json').write_text(json.dumps({'schema_version': 1, 'seasons': [2026], 'bumper': row('bumper.pt'), 'context': row('context.pt')}))
            with self.assertRaises(ValueError):
                neptune_yolo.bundle(root, season=2027)
            (root/'manifest.json').write_text(json.dumps({'schema_version': 1, 'game_independent': True, 'bumper': row('bumper.pt'), 'context': row('context.pt')}))
            self.assertTrue(neptune_yolo.bundle(root, season=2027)['game_independent'])


if __name__ == '__main__':
    unittest.main()
