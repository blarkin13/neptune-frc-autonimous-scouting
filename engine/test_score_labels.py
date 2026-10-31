"""Scoreboard score-change labels and the alliance-total check (neptune_score_labels)."""
import unittest

import neptune_score_labels as sl


def reads(values, start=0.):
    return [{'t': start + i, 'value': v} for i, v in enumerate(values)]


def facts(red, blue=(0, 0, 0), results=None):
    ids = {'1': {'alliance': 'red'}, '2': {'alliance': 'red'}, '3': {'alliance': 'red'},
           '4': {'alliance': 'blue'}, '5': {'alliance': 'blue'}, '6': {'alliance': 'blue'}}
    return {'accepted_scores': {'red': reads(red), 'blue': reads(blue)}, 'bumpers': {'identities': ids},
            'results_screen': results or {'status': 'unknown'}}


class Events(unittest.TestCase):
    def test_held_increases_only(self):
        f = facts([0, 0, 5, 5, 9, 5, 5, 12, 12, 3, 12, 12])
        self.assertEqual([(e['t'], e['from'], e['to'], e['points']) for e in sl.score_events(f)], [(2, 0, 5, 5), (7, 5, 12, 7)])

    def test_one_read_jump_is_flicker(self):
        self.assertEqual(sl.score_events(facts([0, 0, 40, 0, 0])), [])


class Delay(unittest.TestCase):
    def test_most_common_lag(self):
        pairs = [(t, t + 4.9) for t in range(12)] + [(t, t + 1) for t in range(3)]
        self.assertAlmostEqual(sl.measure_delay(pairs), 4.9, places=1)

    def test_too_few_pairs(self):
        self.assertIsNone(sl.measure_delay([(0, 4)] * 5))


class Attribution(unittest.TestCase):
    def setUp(self):
        self.f = facts([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 5, 5])   # +5 at t=10

    def sight(self, team, t, zone):
        return {'team': team, 't': t, 'zone': zone}

    def attr(self, sights):
        return sl.attribute(sl.score_events(self.f), self.f, sights, lambda s: s['zone'], delay=4., window=3.)[0]

    def test_single_robot_in_zone(self):
        e = self.attr([self.sight(1, 5, True), self.sight(2, 5, False), self.sight(4, 5, True)])
        self.assertEqual((e['team'], e['reason'], e['source'], e['weight']), (1, 'only_robot_in_scoring_zone', sl.SOURCE, sl.WEIGHT))

    def test_two_in_zone_stays_unattributed(self):
        self.assertEqual(self.attr([self.sight(1, 5, True), self.sight(2, 6, True)])['reason'], 'several_robots_in_zone')

    def test_outside_window_or_no_zone(self):
        self.assertEqual(self.attr([self.sight(1, 9, True)])['reason'], 'no_alliance_robot_seen')
        self.assertEqual(self.attr([self.sight(1, 5, None)])['reason'], 'no_marked_zone')

    def test_metrics_and_weak_rows(self):
        a = [self.attr([self.sight(1, 5, True)])]
        m = sl.attribution_metrics(a, [{'team': 1, 't': 5.5}, {'team': 2, 't': 20}], self.f, tolerance=1.)
        self.assertEqual((m['precision'], m['recall'], m['coverage']), (1.0, .5, 1.0))
        rows = sl.weak_label_rows(a, self.f, '2026test_qm1', 'gb:score_1_fuel')
        self.assertEqual((rows[0]['team_number'], rows[0]['source'], rows[0]['weak_supervision'], rows[0]['end_ms']), (1, sl.SOURCE, True, 6000))


class AllianceCheck(unittest.TestCase):
    game = {'results_screen_components': {'auto': ['A'], 'teleop': ['B'], 'penalty': ['P']}}

    def scores(self, red):
        return [{'team': t, 'alliance': 'red', 'robot_points': p} for t, p in red]

    def test_gap_against_final_display(self):
        r = sl.alliance_check(self.scores([(1, 10), (2, 20), (3, 25)]), facts([0, 0, 50, 50]), self.game)
        red = r['alliances'][0]
        self.assertEqual((red['target'], red['predicted_robot_total'], red['gap']), (50, 55, 5)); self.assertEqual(r['mean_abs_gap'], 5)

    def test_game_pack_alliance_parts_removed(self):
        f = facts([0, 0, 50, 50], results={'alliances': {'red': {'penalty': 8, 'auto': 12}}})
        self.assertEqual(sl.alliance_check(self.scores([(1, 10), (2, 20), (3, 12)]), f, self.game)['alliances'][0]['target'], 42)

    def test_duplicates_averaged_and_missing_robot_flagged(self):
        r = sl.alliance_check(self.scores([(1, 10), (1, 20), (2, 20), (3, 5)]), facts([0, 0, 50, 50]), self.game)
        self.assertEqual(r['alliances'][0]['predicted_robot_total'], 40)
        self.assertEqual(sl.alliance_check(self.scores([(1, 10)]), facts([0, 0, 50, 50]), self.game)['alliances'][0]['status'], 'incomplete_robots')


if __name__ == '__main__':
    unittest.main()
