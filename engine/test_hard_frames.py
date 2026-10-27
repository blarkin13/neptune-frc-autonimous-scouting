import unittest

import neptune_hard_frames as hf


def point(t, status, track, scene='wide:0', camera='wide'):
    return {'t': t, 'identity_status': status, 'review_track': track, 'scene': scene, 'camera': camera}


class HardFrames(unittest.TestCase):
    def review(self, points, match='2026txcmp1_qm1'):
        return {'match_key': match, 'source_sha256': 'a'*64, 'points': points}

    def test_lost_robot_gap_inside_one_view(self):
        rows = hf.picks(self.review([point(10, 'corrected', 'a'), point(10.5, 'corrected', 'a'), point(14.5, 'corrected', 'a')]))
        self.assertEqual(rows, [{'t_ms': 12500, 'why': 'robot_lost', 'camera': 'wide'}])

    def test_camera_cut_is_not_a_lost_robot(self):
        rows = hf.picks(self.review([point(10, 'corrected', 'a'), point(14, 'corrected', 'a', scene='wide:1')]))
        self.assertEqual(rows, [])

    def test_false_positive_track_gives_first_middle_last(self):
        rows = hf.picks(self.review([point(t, 'excluded', 'x', 'closeup-left:0', 'closeup-left') for t in range(20, 41)]))
        self.assertEqual([r['t_ms'] for r in rows], [20000, 30000, 40000])
        self.assertTrue(all(r['why'] == 'false_positive' for r in rows))

    def test_frames_kept_apart_and_capped(self):
        pts = [point(t/10, 'excluded', 'x%d' % t) for t in range(0, 2000, 3)]
        rows = hf.picks(self.review(pts))
        self.assertLessEqual(len(rows), hf.MAX_FRAMES)
        self.assertTrue(all(b['t_ms']-a['t_ms'] >= 1000 for a, b in zip(rows, rows[1:])))

    def test_held_out_and_reserved_matches_refused(self):
        with self.assertRaisesRegex(ValueError, 'held-out'):
            hf.picks(self.review([], '2026txcmp1_qm4'), holdout=['2026txcmp1_qm4'])
        with self.assertRaisesRegex(ValueError, 'reserved'):
            hf.picks(self.review([], '2026txcmp1_qm7'))


if __name__ == '__main__':
    unittest.main()
