import unittest

from neptune_steps import Steps


class StepsTest(unittest.TestCase):
    def test_moves_forward_and_names_next(self):
        s = Steps('train')
        self.assertIn('step 1 of 5', s.describe('Downloading robot labels'))
        self.assertIn('step 2 of 5', s.describe('Downloading 2026txcmp1_qm1'))
        text = s.describe('Training robot detector: pass 3 of up to 80')
        self.assertIn('step 3 of 5: Train', text)
        self.assertIn('Next: Compare with the detector in use → Share it if better', text)

    def test_unknown_message_keeps_step(self):
        s = Steps('actions')
        s.describe('Fitting action candidates from human tags')
        self.assertIn('step 3 of 4', s.describe('12 of 14 matches prepared'))

    def test_never_goes_back(self):
        s = Steps('train_field')
        s.describe('Comparing new and current field detector on qm1')
        self.assertIn('step 4 of 5', s.describe('Downloading scoring areas'))


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
