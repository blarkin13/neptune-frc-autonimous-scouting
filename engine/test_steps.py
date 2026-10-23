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
