"""Offline held-out action evaluation from a prepared cache (engine/evaluation/evaluate_actions.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent/'evaluation'))
import evaluate_actions as ev  # noqa: E402
from test_training_honesty import rows  # noqa: E402


def prepared(folder, examples, cache_features=True):
    by_match = {}
    for i, r in enumerate(examples):
        r = dict(r, tag='gb:score_1_fuel', split='training', label_ids=['c%d' % (i // 2)] if r['y'] == 1 else [])
        if cache_features:
            r['feature'] = 'f%d' % i; x = r.pop('x')
            by_match.setdefault(r['match_key'], {'examples': [], 'features': {}})['features'][r['feature']] = x
        by_match.setdefault(r['match_key'], {'examples': [], 'features': {}})['examples'].append(r)
    for key, doc in by_match.items():
        (Path(folder)/(key+'.json')).write_text(json.dumps(dict(doc, schema_version=2, scoring_examples=[])))


class EvaluateActions(unittest.TestCase):
    def test_reports_held_out_check_and_click_duplication(self):
        with tempfile.TemporaryDirectory() as d:
            prepared(d, rows(matches=4))
            actions, scores = ev.load(d)
            self.assertEqual(len(actions), 52); self.assertEqual(scores, [])
            tag = ev.action_report(actions)['gb:score_1_fuel']
            self.assertEqual(tag['status'], 'held_out_signal')
            self.assertEqual(tag['positive_sources'], 4); self.assertEqual(tag['max_rows_per_click'], 2)
            self.assertEqual(sum(tag['positives_by_match'].values()), 12)

    def test_confounded_signal_is_reported_not_passed(self):
        with tempfile.TemporaryDirectory() as d:
            prepared(d, rows(matches=4, confound_time=True, signal=False), cache_features=False)
            tag = ev.action_report(ev.load(d)[0])['gb:score_1_fuel']
            self.assertNotEqual(tag['status'], 'held_out_signal')

    def test_reserved_benchmark_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data = rows(matches=3); data[0]['match_key'] = '2026txcmp1_qm7'
            prepared(d, data)
            with self.assertRaises(ValueError):
                ev.load(d)


if __name__ == '__main__':
    unittest.main()
