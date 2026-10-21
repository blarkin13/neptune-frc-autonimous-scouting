"""Held-out honesty: match-level folds, the no-video stand-in gate, and outside-label weighting."""
import unittest

import neptune_training as t


def rows(matches=4, confound_time=False, signal=True, external=False, dim=8):
    out = []
    for m in range(matches):
        match = '2026test_qm%d' % (m + 1)
        for i in range(3):
            x = [1.] * dim if signal else [float((m + i) % 2)] * dim
            r = dict(x=x, y=1, match_key=match, source_sha256='v%d' % m, team=1 + i, camera='wide',
                     box=[.1 * i, .4, .1, .2], t_ms=(i * 1000) if confound_time else 1500 + i * 3000)
            if external:
                r['external_sources'] = [{'provider': 'viperscout'}]
            out.append(r)
        for i in range(10):
            x = [float(i == 0)] * dim if signal else [float(i % 2)] * dim
            out.append(dict(x=x, y=None, match_key=match, source_sha256='v%d' % m, team=1 + i % 3, camera='wide',
                            box=[.1 * (i % 3), .4, .1, .2], t_ms=(10000 + i * 1000) if confound_time else i * 1000))
    return out


class Honesty(unittest.TestCase):
    def test_real_signal_passes_and_reports_stand_in(self):
        detail, rate = t.validate_positive_unlabeled(rows())
        self.assertEqual(detail['status'], 'held_out_signal')
        self.assertIsNotNone(detail['nuisance_auc'])
        self.assertGreaterEqual(detail['auc_vs_unlabeled'], detail['nuisance_auc'] + t.NUISANCE_MIN_MARGIN)

    def test_head_explained_by_time_alone_is_withheld(self):
        # Positives all early, references all late: the stand-in ranks perfectly from time.
        detail, rate = t.validate_positive_unlabeled(rows(confound_time=True))
        self.assertEqual(detail['status'], 'no_signal_beyond_shot_time_or_robot')
        self.assertIsNone(rate)

    def test_two_uploads_of_one_match_share_a_fold(self):
        data = rows()
        for r in data:
            if r['match_key'] == '2026test_qm1' and r['t_ms'] % 2000 == 0:
                r['source_sha256'] = 'v0-reupload'
        keys = {t.fold_key(r) for r in data if r['match_key'] == '2026test_qm1'}
        self.assertEqual(keys, {'2026test_qm1'})
        detail, _ = t.validate_positive_unlabeled(data)
        self.assertEqual(detail['positive_sources'], 4)

    def test_auc_reported_per_label_source(self):
        data = rows()
        for r in data:
            if r['y'] == 1 and r['match_key'] in ('2026test_qm3', '2026test_qm4'):
                r['external_sources'] = [{'provider': 'viperscout'}]
        detail, _ = t.validate_positive_unlabeled(data)
        self.assertEqual(detail['auc_by_source']['human']['positives'], 6)
        self.assertEqual(detail['auc_by_source']['outside_scouting']['positives'], 6)

    def test_outside_positives_pull_the_class_mean_half_as_hard(self):
        neg = [dict(x=[0., 0.], y=0) for _ in range(4)]
        human = [dict(x=[1., 0.], y=1), dict(x=[1., 0.], y=1)]
        outside = [dict(x=[0., 1.], y=1, w=t.EXTERNAL_WEIGHT), dict(x=[0., 1.], y=1, w=t.EXTERNAL_WEIGHT)]
        head = t.fit_binary(neg + human + outside)
        equal = t.fit_binary(neg + human + [dict(r, w=1) for r in outside])
        # Human direction dominates when outside rows are down-weighted.
        self.assertGreater(head['weights'][0] / head['weights'][1], equal['weights'][0] / equal['weights'][1])

    def test_stand_in_features_never_include_the_clip(self):
        data = rows(dim=8)
        stand_in = t.nuisance_features(data)
        self.assertTrue(all(len(r['x']) == len(stand_in[0]['x']) for r in stand_in))
        self.assertNotEqual(len(stand_in[0]['x']), 8)
        self.assertEqual(stand_in[0]['x'][0], data[0]['t_ms'] / 180000)


if __name__ == '__main__':
    unittest.main()
