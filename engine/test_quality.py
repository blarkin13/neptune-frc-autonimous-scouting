import unittest

import neptune_quality as q


def phase(start=10., length=140, step=1., skip=(), frozen=None, outliers=()):
    samples = []
    t = start
    while t <= start + length:
        r = round(length - (t - start))
        if frozen and frozen[0] <= t < frozen[1]:
            r = round(length - (frozen[0] - start))
        if not any(a <= t < b for a, b in skip):
            samples.append({'t': t, 'remaining': r})
        t += step
    return {'start': start, 'end': start + length, 'length_rule': length, 'clock_samples': samples,
            'clock_readings': len(samples), 'clock_outliers': list(outliers), 'start_observed': True}


def facts(**periods):
    return {'rules': {'auto_seconds': 20, 'teleop_seconds': 140}, 'periods': periods}


def outside(i, ms, ph='teleop', team=1, tag='gb:score_1_fuel'):
    return {'id': i, 'external': {'phase': ph}, 'start_ms': ms, 'team_number': team, 'tag_key': tag}


class Clock(unittest.TestCase):
    def test_clean_running_clock_is_usable(self):
        r = q.clock_report(facts(teleop=phase()), [outside(1, 5000), outside(2, 60000)])
        self.assertEqual(r['verdict'], 'usable', r['problems'])
        self.assertEqual(r['aligned'], 2)
        self.assertEqual(r['phases']['teleop']['residual_p90_s'], 0)

    def test_held_start_and_end_values_are_not_counted_as_rejects(self):
        held = [{'t': 5., 'clock': 140}, {'t': 160., 'clock': 0}]
        r = q.clock_report(facts(teleop=phase(outliers=held)))
        self.assertEqual(r['phases']['teleop']['running_rejects'], 0)

    def test_many_running_rejects_mark_match_marginal(self):
        bad = [{'t': 20. + i, 'clock': 100} for i in range(60)]
        r = q.clock_report(facts(teleop=phase(outliers=bad)), [outside(1, 5000)])
        self.assertEqual(r['verdict'], 'marginal')
        self.assertTrue(any('rejected' in p for p in r['problems']))

    def test_frozen_clock_is_measured_and_rows_inside_it_do_not_join(self):
        r = q.clock_report(facts(teleop=phase(frozen=(50., 60.))), [outside(1, 40000)])
        self.assertGreaterEqual(r['phases']['teleop']['longest_frozen_s'], 9)
        self.assertEqual(r['aligned'], 0)
        self.assertEqual(r['verdict'], 'exclude')

    def test_rows_for_a_phase_missing_from_video_are_reported(self):
        r = q.clock_report(facts(teleop=phase()), [outside(1, 3000, ph='auto'), outside(2, 9000)])
        self.assertEqual(r['join_outcomes'].get('unavailable:phase_not_in_video'), 1)
        self.assertEqual(r['aligned_rate'], .5)

    def test_no_clock_is_excluded(self):
        r = q.clock_report(facts(teleop={'length_rule': 140, 'clock_samples': []}), [outside(1, 3000)])
        self.assertEqual(r['verdict'], 'exclude')


class Counts(unittest.TestCase):
    roster = {'red': [1, 2, 3], 'blue': [4, 5, 6]}
    points = {'gb:score_1_fuel': 1, 'gb:climb_lv_3': 30}

    def ev(self, team, ms, tag='gb:score_1_fuel', key='team_number'):
        return {key: team, 'tag_key': tag, 'start_ms': ms}

    def test_matching_within_tolerance_is_one_to_one(self):
        pred = [self.ev(1, 1000, key='team'), self.ev(1, 1200, key='team'), self.ev(1, 9000, key='team')]
        ref = [self.ev(1, 2000), self.ev(1, 20000)]
        c = q.match_events(pred, ref, 3000)[('1', 'gb:score_1_fuel')]
        self.assertEqual((c['matched'], c['missed'], c['extra']), (1, 1, 2))

    def test_points_sum_per_alliance_and_compare_with_score_bug(self):
        pred = [self.ev(1, 1000, key='team'), self.ev(2, 5000, 'gb:climb_lv_3', key='team'), self.ev(4, 1000, key='team')]
        ref = [self.ev(1, 1000), self.ev(2, 5000, 'gb:climb_lv_3')]
        f = {'accepted_scores': {'red': [{'t': 1, 'value': 10}, {'t': 150, 'value': 40}], 'blue': []}}
        r = q.count_report(pred, ref, self.roster, self.points, f, official={'red': 45})
        red = r['alliances']['red']
        self.assertEqual((red['predicted_points'], red['reference_points']), (31, 31))
        self.assertEqual(red['video_score_bug'], 40)
        self.assertEqual(red['predicted_minus_video_score_bug'], -9)
        self.assertEqual(red['predicted_minus_official_total'], -14)
        self.assertIsNone(r['alliances']['blue']['video_score_bug'])
        self.assertEqual((r['recall'], r['precision']), (1.0, round(2 / 3, 3)))

    def test_unpriced_tags_are_listed_not_guessed(self):
        r = q.count_report([self.ev(1, 0, 'gb:defense', key='team')], [], self.roster, self.points)
        self.assertEqual(r['alliances']['red']['unpriced_tags'], ['gb:defense'])
        self.assertEqual(r['alliances']['red']['predicted_points'], 0)

    def test_absence_labels_are_not_counted(self):
        ref = [dict(self.ev(1, 0), polarity='absent')]
        self.assertEqual(q.match_events([], ref), {})


if __name__ == '__main__':
    unittest.main()
