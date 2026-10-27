import unittest
from neptune_constant_identity import label, tracklets, with_constant_identity
from neptune_identity_metrics import evaluate
R = {'red': [1, 2, 3], 'blue': [4, 5, 6]}


def obs(t, tid, x, y=.3, camera='wide', scene='wide:0', alliance='red', reads=(), look=0, w=.05):
    hist = [float(j == look) for _ in range(3) for j in range(8)]
    return dict(t=t, track_id=tid, box=[x, y, w, .08], camera=camera, scene=scene, alliance=alliance, read_teams=list(reads),
                appearance=hist, detection_confidence=.8, occluded=False, box_source='detector', verified_team=None)


def seed(p, team):
    return dict(p, team=team, identity_method='yolo_botsort_ocr', identity_segment=1)


def run(observations, seeds, review=()):
    tracking = {'observations': observations, 'localizations': seeds, 'identity_review': {'points': list(review)}}
    return {(p['t'], p['track_id']): p['team'] for p in label(tracking, R)['points']}


class ConstantIdentityTests(unittest.TestCase):
    def test_seed_labels_whole_tracklet(self):
        ps = [obs(i/3, 7, .2+i*.005) for i in range(9)]
        out = run(ps, [seed(ps[4], 1)])
        self.assertTrue(all(out[(p['t'], 7)] == 1 for p in ps))

    def test_new_tracker_number_after_short_gap_is_linked(self):
        a = [obs(i/3, 7, .2+i*.005) for i in range(6)]
        b = [obs(2.5+i/3, 9, .23+i*.005) for i in range(6)]
        out = run(a+b, [seed(a[0], 1)])
        self.assertEqual(out[(b[3]['t'], 9)], 1)

    def test_link_refused_after_long_unseen_gap(self):
        # QM1: a 1.8 s gap between two blue robots carried 6672's read back onto 5261.
        a = [obs(i/3, 7, .2+i*.005) for i in range(6)]
        b = [obs(a[-1]['t']+1.8+i/3, 9, .23+i*.005) for i in range(6)]
        out = run(a+b, [seed(b[0], 1)])
        self.assertIsNone(out[(a[0]['t'], 7)])

    def test_link_refused_across_camera_cut(self):
        a = [obs(i/3, 7, .2) for i in range(6)]
        b = [obs(2.5+i/3, 9, .2, scene='wide:1') for i in range(6)]
        out = run(a+b, [seed(a[0], 1)])
        self.assertIsNone(out[(b[0]['t'], 9)])

    def test_link_refused_for_far_jump_or_other_colour_or_other_read(self):
        a = [obs(i/3, 7, .2) for i in range(6)]
        for b in ([obs(2.5+i/3, 9, .7) for i in range(6)], [obs(2.5+i/3, 9, .2, look=5) for i in range(6)],
                  [obs(2.5+i/3, 9, .2, reads=[2]) for i in range(6)]):
            self.assertIsNone(run(a+b, [seed(a[0], 1)])[(b[0]['t'], 9)])

    def test_two_candidates_close_together_abstain(self):
        a = [obs(i/3, 7, .2) for i in range(6)]
        b = [obs(2.5+i/3, 9, .2) for i in range(6)]
        c = [obs(2.5+i/3, 11, .21) for i in range(6)]
        out = run(a+b+c, [seed(a[0], 1)])
        self.assertIsNone(out[(b[0]['t'], 9)]); self.assertIsNone(out[(c[0]['t'], 11)])

    def test_unnamed_robot_ending_nearby_blocks_the_link(self):
        a = [obs(i/3, 7, .2) for i in range(6)]
        other = [obs(i/3, 8, .215, look=0) for i in range(6)]
        b = [obs(2.5+i/3, 9, .21) for i in range(6)]
        out = run(a+other+b, [seed(a[0], 1)])
        self.assertIsNone(out[(b[0]['t'], 9)])

    def test_contact_ends_tracklet_so_swap_does_not_carry(self):
        a = [obs(i/3, 7, .2+i*.01) for i in range(4)]
        b = [obs(i/3, 8, .4-i*.01) for i in range(4)]
        touch = [obs(4/3, 7, .3), obs(4/3, 8, .305)]
        after = [obs(5/3+i/3, 7, .4-i*.01) for i in range(4)]+[obs(5/3+i/3, 8, .2+i*.01) for i in range(4)]
        nodes = tracklets(a+b+touch+after)
        self.assertTrue(any(n['contact'] for n in nodes))
        out = run(a+b+touch+after, [seed(a[0], 1), seed(b[0], 2)])
        self.assertIsNone(out[(4/3, 7)])

    def test_contact_stretch_kept_when_same_track_leaves_with_same_number(self):
        a = [obs(i/3, 7, .2) for i in range(4)]
        touch = [obs(4/3, 7, .2), obs(4/3, 8, .21)]
        after = [obs(5/3+i/3, 7, .2) for i in range(4)]
        out = run(a+touch+after, [seed(a[0], 1), seed(after[-1], 1)])
        self.assertEqual(out[(4/3, 7)], 1)

    def test_same_team_twice_in_one_camera_drops_both(self):
        a = [obs(i/3, 7, .2) for i in range(4)]
        b = [obs(i/3, 8, .6) for i in range(4)]
        out = run(a+b, [seed(a[0], 1), seed(b[0], 1)])
        self.assertIsNone(out[(0, 7)]); self.assertIsNone(out[(0, 8)])

    def test_roster_guess_carries_in_wide_view_but_not_closeup(self):
        for camera, expected in (('wide', 3), ('closeup-left', None)):
            ps = [obs(i/3, 7, .2, camera=camera, scene=camera+':0') for i in range(6)]
            review = [dict(ps[0], team=3, identity_status='inferred', reason='bidirectional_motion_and_roster')]
            self.assertEqual(run(ps, [], review)[(ps[-1]['t'], 7)], expected)

    def test_elimination_names_third_moving_robot_in_wide_view(self):
        a = [obs(i/3, 1, .1) for i in range(9)]
        b = [obs(i/3, 2, .5) for i in range(9)]
        c = [obs(i/3, 3, .8-i*.02) for i in range(9)]
        out = run(a+b+c, [seed(a[0], 1), seed(b[0], 2)])
        self.assertEqual(out[(0, 3)], 3)
        still = [obs(i/3, 3, .8) for i in range(9)]
        self.assertIsNone(run(a+b+still, [seed(a[0], 1), seed(b[0], 2)])[(0, 3)])

    def test_look_fallback_names_wide_tracklet_only_with_a_clear_margin(self):
        a = [obs(i/3, 1, .1, look=1) for i in range(6)]
        b = [obs(i/3, 2, .5, look=2) for i in range(6)]
        c = [obs(i/3, 3, .8, look=3) for i in range(6)]
        late = [obs(20+i/3, 9, .3, look=2) for i in range(6)]
        seeds = [seed(a[0], 1), seed(b[0], 2), seed(c[0], 3)]
        out = run(a+b+c+late, seeds)
        self.assertEqual(out[(20, 9)], 2)
        close = [dict(p, camera='closeup-left', scene='closeup-left:0') for p in a+b+c+late]
        self.assertIsNone(run(close, [seed(close[0], 1), seed(close[6], 2), seed(close[12], 3)])[(20, 9)])
        twin = [obs(i/3, 3, .8, look=2) for i in range(6)]
        self.assertIsNone(run(a+b+twin+late, [seed(a[0], 1), seed(b[0], 2), seed(twin[0], 3)])[(20, 9)])

    def test_added_localizations_never_training_and_keep_trusted_labels(self):
        ps = [obs(i/3, 7, .2) for i in range(6)]
        base = [seed(ps[0], 1)]
        out = with_constant_identity({'observations': ps, 'localizations': base}, R)
        added = [p for p in out['localizations'] if p['identity_method'] == 'constant_identity']
        self.assertEqual(len(added), 5)
        self.assertTrue(all(not p['identity_evidence']['training_eligible'] for p in added))
        self.assertEqual(sum(p['identity_method'] == 'yolo_botsort_ocr' for p in out['localizations']), 1)
        bad = with_constant_identity({'observations': ps, 'localizations': base}, {'red': [1]})
        self.assertEqual(bad['localizations'], base)


class RosterInferredTests(unittest.TestCase):
    def test_closeup_roster_guess_needs_a_read_on_its_track(self):
        from neptune_identity import with_roster_inferred
        def guess(camera, tid, reads=()):
            return dict(obs(1, tid, .2, camera=camera, scene=camera+':0', reads=reads), team=3, identity_status='inferred',
                        reason='bidirectional_motion_and_roster', review_track=str(tid))
        points = [guess('closeup-left', 1), guess('closeup-right', 2, reads=[3]), guess('wide', 4)]
        added = with_roster_inferred({'localizations': [], 'identity_review': {'points': points}})['localizations']
        self.assertEqual(sorted(p['camera'] for p in added), ['closeup-right', 'wide'])


class IdentityMetricTests(unittest.TestCase):
    def test_switches_lost_seconds_and_non_robots(self):
        review = {'roster': R, 'points': [
            dict(obs(0, 1, .2), team=1, identity_status='corrected'), dict(obs(1, 1, .2), team=1, identity_status='corrected'),
            dict(obs(2, 1, .2), team=1, identity_status='corrected'), dict(obs(0, 2, .6), team=None, identity_status='excluded')]}
        labeled = [dict(obs(0, 1, .2), team=1), dict(obs(1, 1, .2), team=2), dict(obs(2, 1, .2), team=1), dict(obs(0, 2, .6), team=3)]
        m = evaluate(labeled, review, 0, 2)
        self.assertEqual((m['correct'], m['wrong'], m['identity_switches'], m['labeled_non_robots']), (2, 1, 2, 1))
        self.assertEqual(m['lost_track_seconds']['4'], 2.3)

    def test_reviewed_box_matches_its_own_unlabeled_detection(self):
        # QM1: an unlabeled box overlapping a correctly labeled neighbour was scored "wrong".
        mine, near = obs(0, 1, .20, w=.08), obs(0, 2, .23, w=.08)
        review = {'roster': R, 'points': [dict(mine, team=2, identity_status='corrected')]}
        m = evaluate([dict(near, team=1)], review, 0, 0, detections=[mine, near])
        self.assertEqual((m['wrong'], m['unlabeled']), (0, 1))


if __name__ == '__main__':
    unittest.main()
