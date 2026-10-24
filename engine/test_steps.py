import unittest

from neptune_steps import Steps


class StepsTest(unittest.TestCase):
    def test_moves_forward_and_names_next(self):
        s = Steps('train')
        self.assertIn('step 1 of 6', s.describe('Downloading robot labels'))
        self.assertIn('step 2 of 6', s.describe('Downloading 2026txcmp1_qm1'))
        text = s.describe('Training robot detector: pass 3 of up to 80')
        self.assertIn('step 3 of 6: Train', text)
        self.assertIn('Next: Compare with the detector in use → Make the review video → Share it if better', text)

    def test_unknown_message_keeps_step(self):
        s = Steps('actions')
        s.describe('Fitting action candidates from human tags')
        self.assertIn('step 3 of 4', s.describe('12 of 14 matches prepared'))

    def test_never_goes_back(self):
        s = Steps('train_field')
        s.describe('Comparing new and current field detector on qm1')
        self.assertIn('step 4 of 6', s.describe('Downloading scoring areas'))


if __name__ == '__main__':
    unittest.main()


class LabelDownloadTest(unittest.TestCase):
    def test_download_needs_no_fingerprint(self):
        import sys, types
        from unittest import mock
        import neptune_robot_labels
        seen = {}
        def fake(match, video, stage):
            seen['ok'] = match['source_sha256'] is None and match['source_url'].endswith('abcdefghijk')
        with mock.patch.dict(sys.modules, {'neptune_helper': types.SimpleNamespace(download_video=fake)}):
            neptune_robot_labels.youtube_download('abcdefghijk', '/tmp/x.mp4')
        self.assertTrue(seen['ok'])


class DetectorWorkCleanupTest(unittest.TestCase):
    def test_detector_work_removed_after_six_hours(self):
        import tempfile, time
        from pathlib import Path
        from neptune_housekeeping import sweep
        home = Path(tempfile.mkdtemp()).resolve()
        run = home/'robot-detector-work'/'a'/'frames'; run.mkdir(parents=True); (run/'f.jpg').write_bytes(b'x'*10)
        self.assertEqual(sweep(home, now=time.time()+3600)['removed_files'], 0)
        self.assertEqual(sweep(home, now=time.time()+7*3600)['removed_files'], 1)
        self.assertFalse((home/'robot-detector-work'/'a').exists())


class LabelSyncTest(unittest.TestCase):
    def test_frames_sent_as_list_become_dict(self):
        import io, json, sys, types
        from unittest import mock
        import neptune_robot_labels
        body = json.dumps({'documents': [{'video_id': 'abcdefghijk', 'frames': [{'complete': True, 'boxes': []}]}]}).encode()
        class Opener:
            def open(self, request, timeout):
                return io.BytesIO(body)
        helper = types.SimpleNamespace(public_https=lambda u: u, NoRedirect=object)
        with mock.patch.dict(sys.modules, {'neptune_helper': helper}), mock.patch('urllib.request.build_opener', return_value=Opener()):
            docs = neptune_robot_labels.sync({'site': 'https://x', 'token': 't'})
        self.assertEqual(docs[0]['frames'], {'0': {'complete': True, 'boxes': []}})


class HoldoutTest(unittest.TestCase):
    def test_held_out_match_stays_fixed(self):
        from neptune_robot_jobs import pick_holdout
        self.assertEqual(pick_holdout(['2026a_qm1', '2026b_qm2'], None), '2026b_qm2')            # first run
        self.assertEqual(pick_holdout(['2026a_qm1', '2026b_qm2', '2026z_qm9'], '2026b_qm2'), '2026b_qm2')  # new labels don't move it
        self.assertEqual(pick_holdout(['2026a_qm1', '2026z_qm9'], '2026b_qm2'), '2026z_qm9')      # removed: pick again
        # never a match the detector in use trained on
        self.assertEqual(pick_holdout(['2026a_qm3', '2026a_qm4', '2026b_qm8'], None, ['2026a_qm3', '2026a_qm4']), '2026b_qm8')
        self.assertEqual(pick_holdout(['2026a_qm4', '2026b_qm8'], '2026a_qm4', ['2026a_qm4']), '2026b_qm8')


class SharedVideoCacheTest(unittest.TestCase):
    def test_videos_kept_14_days(self):
        import tempfile, time
        from pathlib import Path
        import neptune_housekeeping as hk
        home = Path(tempfile.mkdtemp()).resolve(); v = home/'cache'/'videos'; v.mkdir(parents=True)
        (v/'match.mp4').write_bytes(b'x'*100)
        hk.sweep(home, now=time.time()+10*86400)
        self.assertTrue((v/'match.mp4').exists())          # 10 days old: kept
        hk.sweep(home, now=time.time()+15*86400)
        self.assertFalse((v/'match.mp4').exists())         # 15 days old: gone

    def test_cap_keeps_newest(self):
        import os, tempfile, time
        from pathlib import Path
        from unittest import mock
        import neptune_housekeeping as hk
        home = Path(tempfile.mkdtemp()).resolve(); v = home/'cache'/'videos'; v.mkdir(parents=True)
        for i, name in enumerate(('a.mp4', 'b.mp4', 'c.mp4')):
            (v/name).write_bytes(b'x'*100); t = time.time()-(3-i)*3600; os.utime(v/name, (t, t))
        with mock.patch.object(hk, 'VIDEO_CAP_BYTES', 250):
            hk.sweep(home, now=time.time()+10)
        self.assertEqual(sorted(p.name for p in v.iterdir()), ['b.mp4', 'c.mp4'])

    def test_bot_check_is_recognised(self):
        from neptune_robot_labels import youtube_blocked
        self.assertTrue(youtube_blocked("ERROR: [youtube] x: Sign in to confirm you’re not a bot. Use --cookies"))
        self.assertFalse(youtube_blocked('Video unavailable'))


class ScoreMomentsTest(unittest.TestCase):
    def test_bursts_group_changes_inside_the_match(self):
        import neptune_score_moments as m
        reads = lambda pts: [{'t': t, 'value': v} for t, v in pts]
        facts = {'periods': {'auto': {'start': 0, 'end': 20}, 'teleop': {'start': 23, 'end': 163}},
                 'accepted_scores': {'red': reads([(1, 0), (5, 2), (6, 4), (7, 5), (40, 5), (41, 8), (300, 30)]), 'blue': reads([(1, 0), (2, 0)])}}
        self.assertEqual(m.bursts(facts), [{'start': 5.0, 'end': 7.0, 'alliance': 'red', 'points': 5, 'phase': 'auto'},
                                           {'start': 41.0, 'end': 41.0, 'alliance': 'red', 'points': 3, 'phase': 'teleop'}])

    def test_misread_drop_does_not_create_a_change(self):
        import neptune_score_moments as m
        facts = {'accepted_scores': {'red': [{'t': 1, 'value': 10}, {'t': 2, 'value': 1}, {'t': 3, 'value': 10}, {'t': 4, 'value': 12}], 'blue': []}}
        self.assertEqual([e['delta'] for e in m.changes(facts)], [2])
