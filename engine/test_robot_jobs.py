import unittest

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


if __name__ == '__main__':
    unittest.main()
