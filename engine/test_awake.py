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

    def test_mode_is_remembered(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sys, 'platform', 'linux'), mock.patch.object(neptune_awake.Awake, '_start', return_value=None):
            saved = Path(d)/'keep-awake.txt'
            neptune_awake.Awake(saved=saved).set_mode('always')
            a = neptune_awake.Awake(saved=saved)
            self.assertEqual(a.mode, 'always'); self.assertTrue(a.wanted)
            a.close(); self.assertEqual(saved.read_text(), 'always')

    def test_windows_holds_after_a_failed_call(self):
        import time
        calls = []
        def call(flags):
            calls.append(flags)
            if len(calls) == 1:
                raise OSError('first call fails')
            return 0x80000000
        with mock.patch.object(sys, 'platform', 'win32'), mock.patch.object(neptune_awake.Awake, '_windows_call', staticmethod(lambda: call)):
            a = neptune_awake.Awake('always')
            deadline = time.monotonic()+2
            while not calls and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertFalse(a.active)
            a.set_mode('jobs'); a.set_mode('always')
            while not a.active and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(a.active); self.assertEqual(calls[-1], 0x80000001)
            a.close()
            while a.active and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertFalse(a.active); self.assertEqual(calls[-1], 0x80000000)


if __name__ == '__main__':
    unittest.main()
