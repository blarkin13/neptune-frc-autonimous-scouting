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


    def test_engine_shipped_wide_detector_is_added_to_the_private_bundle(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name in ('bumper.pt', 'context.pt'):
                (root/name).write_bytes(b'x')
            sha = hashlib.sha256(b'x').hexdigest()
            (root/'manifest.json').write_text(json.dumps({'schema_version': 1, 'seasons': [2026], 'bumper': {'file': 'bumper.pt', 'sha256': sha}, 'context': {'file': 'context.pt', 'sha256': sha}}))
            from unittest.mock import patch
            with patch.object(neptune_yolo, 'bundled_detectors', return_value={'wide': {'file': 'bumper_wide.pt', 'sha256': 'y', 'path': '/x/bumper_wide.pt'}}):
                data = neptune_yolo.bundle(root, season=2026)
            self.assertEqual(data['by_camera']['wide']['path'], '/x/bumper_wide.pt')
            self.assertEqual(data['bumper']['file'], 'bumper.pt')


if __name__ == '__main__':
    unittest.main()
