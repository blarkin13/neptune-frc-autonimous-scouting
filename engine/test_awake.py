import sys
import unittest
from unittest import mock

import neptune_awake


class AwakeTest(unittest.TestCase):
    def test_modes_follow_jobs(self):
        with mock.patch.object(sys, 'platform', 'linux'), mock.patch.object(neptune_awake.Awake, '_start', return_value=None):
            a = neptune_awake.Awake()
            self.assertFalse(a.wanted)
            a.set_busy(True); self.assertTrue(a.wanted)
            a.set_mode('off'); self.assertFalse(a.wanted)
            a.set_mode('always'); a.set_busy(False); self.assertTrue(a.wanted)
            a.set_mode('nonsense'); self.assertEqual(a.mode, 'always')

    def test_holder_starts_and_stops(self):
        child = mock.Mock(); child.poll.return_value = None
        with mock.patch.object(sys, 'platform', 'linux'), mock.patch.object(neptune_awake.Awake, '_start', return_value=child) as start:
            a = neptune_awake.Awake()
            a.set_busy(True); start.assert_called_once(); self.assertTrue(a.active)
            a.set_busy(False); child.terminate.assert_called_once(); self.assertFalse(a.active)


if __name__ == '__main__':
    unittest.main()
