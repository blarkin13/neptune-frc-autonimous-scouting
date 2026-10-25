import unittest
from types import SimpleNamespace

import neptune_telemetry as t


class TelemetryTest(unittest.TestCase):
    def setUp(self):
        t.LOG.clear(); t.clear()

    def test_log_keeps_last_lines_without_repeats(self):
        for i in range(20):
            t.note('line %d' % i); t.note('line %d' % i)
        state, log = t.snapshot()
        self.assertEqual(len(log), 14); self.assertEqual(log[-1][1], 'line 19')

    def test_batch_counter_and_epoch_line(self):
        trainer = SimpleNamespace(epoch=2, train_loader=[0]*38, tloss=[2.1, 2.09, 1.5], metrics={'metrics/mAP50(B)': .552})
        count = t.batch_counter('Training robot detector', 80)
        for _ in range(3):
            count(trainer)
        state, _ = t.snapshot()
        self.assertEqual((state['pass'], state['passes'], state['batch'], state['batches']), (3, 80, 3, 38))
        t.epoch_line('robot', trainer, 80)
        self.assertIn('mAP50 0.552', t.snapshot()[1][-1][1])

    def test_system_never_raises(self):
        self.assertIn('gpu', t.system())


if __name__ == '__main__':
    unittest.main()
