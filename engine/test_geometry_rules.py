import unittest

import neptune_geometry_rules as rules
import neptune_score_labels as sl

ZONE = {'id': 'z', 'kind': 'scoring_zone', 'alliance': 'blue', 'camera_view': 'wide', 'start_ms': 0, 'end_ms': 10**7, 'reference_ms': 0, 'points': [[0, 0], [.5, 0], [.5, 1], [0, 1]], 'event_template': True}
IDS = {'1': {'alliance': 'red'}, '2': {'alliance': 'blue'}, '3': {'alliance': 'blue'}}


def facts(locs):
    return {'bumpers': {'identities': IDS}, 'tracking': {'localizations': [dict(team=t, t=s, camera='wide', box=[x, .4, .02, .1], identity_method='yolo_botsort_ocr') for t, s, x in locs]}}


class Defense(unittest.TestCase):
    def test_sustained_presence_in_opponent_zone_counts(self):
        f = facts([(1, s / 2, .2) for s in range(10)] + [(1, 20, .8)])
        r = rules.defense(f, {'regions': [ZONE]})
        self.assertEqual(r['robots'][1]['intervals'], [[0.0, 4.5]])

    def test_short_visit_and_own_zone_do_not(self):
        f = facts([(1, 0, .2), (1, 1, .2)] + [(2, s, .2) for s in range(10)])
        r = rules.defense(f, {'regions': [ZONE]})
        self.assertEqual(r['robots'][1]['seconds'], 0)
        self.assertNotIn(2, r['robots'])

    def test_unmarked_is_unavailable(self):
        self.assertEqual(rules.defense(facts([(1, 0, .2)]), None)['status'], 'unavailable')
        self.assertEqual(rules.climb(facts([(1, 0, .2)]), {'regions': [ZONE]}, 'climb_zone')['status'], 'unavailable')


class Allocate(unittest.TestCase):
    def test_points_split_among_robots_in_zone_and_total_kept(self):
        f = {'bumpers': {'identities': IDS}, 'accepted_scores': {'blue': [{'t': t, 'value': v} for t, v in ((0, 0), (1, 0), (10, 6), (11, 6), (20, 9), (21, 9))]}}
        sights = [{'team': 2, 't': 8}, {'team': 3, 't': 8}, {'team': 2, 't': 18}]
        a = sl.allocate(sl.score_events(f), f, sights, lambda s: s['t'] < 15 or None, delay=1.)
        self.assertEqual(a['robots'], {2: 3.0, 3: 3.0})
        self.assertEqual(a['unassigned'], {'blue': 3})
        self.assertEqual(sum(a['robots'].values()) + a['unassigned']['blue'], a['displayed']['blue'])


if __name__ == '__main__':
    unittest.main()
