"""Public human video tags: ingestion, privacy, withdrawal handling, verification gating, duplicates, splits."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import neptune_video_labels as vl

ROSTER = {'red': [1296, 254, 118], 'blue': [971, 1678, 2056]}


def label(i, team=254, tag='scoring', start=10000, scope='moment', certainty='observed', match='2026txcmp1_qm1', video='AAAAAAAAAAA', state='contributed', duration=180400):
    return {'schema_version': 2, 'evidence_type': 'human_video_label', 'review_required': False, 'time_basis': 'video_elapsed_ms', 'source_sha256': None,
            'id': '%032x' % i, 'match_id': 1, 'match_key': match, 'source_url': 'https://www.youtube.com/watch?v=' + video, 'video_id': video,
            'roster': ROSTER, 'team_number': team, 'tag_key': tag, 'tag_label': tag.title(), 'tag_category': 'Scoring', 'definition_version': 'neptune-match-tags-v1',
            'label_scope': scope, 'start_ms': None if scope == 'match' else start, 'end_ms': None if scope == 'match' else start,
            'video_duration_ms': duration, 'certainty': certainty, 'note': '', 'review_state': state, 'created_at': 1792300000 + i}


def ndjson(rows):
    return ''.join(json.dumps(r) + '\n' for r in rows)


SQL_HEAD = "INSERT INTO `community_video_labels` (`id`, `match_id`, `contributor_key`, `user_id`, `ip_key`, `source_url`, `video_id`, `roster_json`, `team_number`, `tag_key`, `tag_label`, `tag_category`, `definition_version`, `label_scope`, `start_ms`, `end_ms`, `video_duration_ms`, `certainty`, `note`, `review_state`, `created_at`, `updated_at`) VALUES\n"


def sql_row(r, state):
    q = lambda v: 'NULL' if v is None else ("'" + str(v).replace("'", "''") + "'")
    return '(%s, %d, %s, NULL, %s, %s, %s, %s, %d, %s, %s, %s, %s, %s, %s, %s, %d, %s, %s, %s, %d, %d)' % (
        q(r['id']), r['match_id'], q('c' * 64), q('i' * 64), q(r['source_url']), q(r['video_id']), q(json.dumps(r['roster'])), r['team_number'],
        q(r['tag_key']), q(r['tag_label']), q(r['tag_category']), q(r['definition_version']), q(r['label_scope']),
        'NULL' if r['start_ms'] is None else r['start_ms'], 'NULL' if r['end_ms'] is None else r['end_ms'], r['video_duration_ms'],
        q(r['certainty']), q("it's fine"), q(state), r['created_at'], r['created_at'])


class IngestTests(unittest.TestCase):
    def test_whole_match_share_is_not_a_piece_count(self):
        share={'schema_version':1,'mode':'alliance_share','source':'human_video_contribution','method':'estimated','count_min':None,'count_max':None,'robot_points':80,'alliance_score':400,'share_percent':20.0,'score_basis':'full_final_alliance_score'}
        r=dict(label(9,scope='match',certainty='uncertain'),scoring=share)
        rows,errors=vl.read_export(ndjson([r]));self.assertFalse(errors);self.assertEqual(rows[0]['scoring']['robot_points'],80)
        self.assertIsNotNone(vl.validate_label(dict(r,certainty='observed')))
        self.assertIsNotNone(vl.validate_label(dict(r,label_scope='moment',start_ms=1000,end_ms=1000)))
        self.assertIsNotNone(vl.validate_label(dict(r,scoring=dict(share,robot_points=401))))

    def test_scoring_evidence_is_preserved_and_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=vl.Store(root/'store');file=root/'labels.ndjson'
            scoring={'schema_version':1,'source':'human_video_contribution','season':2026,'game':'REBUILT','method':'estimated','component':'fuel','count_min':8,'count_max':12,'points_min':None,'points_max':None,'hub_state':'unknown','phase':'teleop','rules_version':'community-scoring-v1'}
            r=dict(label(1),scoring=scoring,replaces_id='a'*32)
            file.write_text(ndjson([r]));vl.ingest(store,path=file)
            saved=store.load('ledger.json',{})[r['id']]['original']
            self.assertEqual(saved['scoring'],scoring);self.assertIsNone(saved['scoring']['points_min'])
            unknown=dict(scoring,method='unknown',count_min=None,count_max=None)
            self.assertIsNone(vl.validate_label(dict(r,scoring=unknown)))
            self.assertIsNotNone(vl.validate_label(dict(r,scoring=dict(unknown,count_min=0))))
            self.assertIsNotNone(vl.validate_label(dict(r,polarity='absent')))
            file.write_text(ndjson([]));vl.ingest(store,path=file)
            self.assertEqual(store.load('ledger.json',{})[r['id']]['state'],'absent_from_latest_export')

    def test_invalid_records_are_reported_not_fixed(self):
        bad = [label(1, team=9999), dict(label(2), schema_version=1), dict(label(3), start_ms=5, end_ms=9), dict(label(4, scope='match'), start_ms=1)]
        labels, problems = vl.read_export(ndjson(bad + [label(5)]) + 'not json\n')
        self.assertEqual([r['id'] for r in labels], ['%032x' % 5])
        self.assertEqual(len(problems), 5)

    def test_sql_dump_private_columns_never_stored(self):
        with tempfile.TemporaryDirectory() as d:
            sql = Path(d) / 'dump.sql'
            sql.write_text(SQL_HEAD + ',\n'.join([sql_row(label(1), 'contributed'), sql_row(label(2), 'withdrawn')]) + ';\n')
            store = vl.Store(Path(d) / 'store')
            vl.ingest(store, path=sql, kind='sqldump')
            for p in list((store.root / 'snapshots').glob('*')) + [store.root / 'ledger.json']:
                text = p.read_text()
                for private in ('c' * 64, 'i' * 64):              # private values: nowhere
                    self.assertNotIn(private, text, p.name)
                if not p.name.endswith('.meta.json'):              # column names only in the drop notice
                    for column in vl.PRIVATE_COLUMNS:
                        self.assertNotIn(column, text, p.name)
            ledger = store.load('ledger.json', {})
            self.assertEqual(ledger['%032x' % 2]['state'], 'withdrawn')
            self.assertEqual(ledger['%032x' % 1]['original']['note'], "it's fine")

    def test_withdrawal_and_disappearance_keep_originals(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            store = vl.Store(d / 'store')
            (d / 'a.ndjson').write_text(ndjson([label(1), label(2), label(3, certainty='uncertain')]))
            vl.ingest(store, path=d / 'a.ndjson')
            (d / 'b.ndjson').write_text(ndjson([label(1), label(3, certainty='uncertain')]))
            vl.ingest(store, path=d / 'b.ndjson')
            ledger = store.load('ledger.json', {})
            self.assertEqual(ledger['%032x' % 2]['state'], 'absent_from_latest_export')
            self.assertEqual(ledger['%032x' % 2]['original']['id'], '%032x' % 2)
            self.assertEqual(ledger['%032x' % 3]['original']['certainty'], 'uncertain')
            (d / 'c.ndjson').write_text(ndjson([label(1), label(2), label(3, certainty='uncertain')]))
            vl.ingest(store, path=d / 'c.ndjson')
            self.assertEqual(store.load('ledger.json', {})['%032x' % 2]['state'], 'contributed')
            self.assertEqual(len(list((store.root / 'snapshots').glob('export-*.ndjson'))), 3)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.store = vl.Store(d / 'store')
        rows = [label(1, start=10000), label(2, start=10800), label(3, start=30000), label(4, scope='match', tag='no_defense'),
                label(5, team=971, match='2026txcmp1_qm2', video='BBBBBBBBBBB', start=5000, certainty='uncertain'),
                label(6, match='2026txcmp1_qm2', video='BBBBBBBBBBB', start=5000, duration=150000)]
        (d / 'e.ndjson').write_text(ndjson(rows))
        vl.ingest(self.store, path=d / 'e.ndjson')
        self.videos = d / 'videos'
        self.videos.mkdir()
        for v in ('AAAAAAAAAAA', 'BBBBBBBBBBB'):
            (self.videos / ('%s.mp4' % v)).write_bytes(v.encode())
        with patch('neptune_video_labels.probe_duration_ms', return_value=180000):
            vl.verify_sources(self.store, self.videos)
        self.out = d / 'out'

    def tearDown(self):
        self.tmp.cleanup()

    def test_dataset_rules(self):
        m = vl.build(self.store, self.videos, self.out, split_by='match', eval_fraction=0.5, frames=False)
        rows = {r['label_id'][-1]: r for r in map(json.loads, (self.out / 'labels.jsonl').read_text().splitlines())}
        self.assertNotIn('6', rows)                                        # browser duration 150 s vs verified 180 s
        self.assertTrue(any('differs from the verified' in e['reason'] for e in m['excluded']))
        self.assertEqual(rows['5']['certainty'], 'uncertain')              # preserved exactly
        self.assertEqual(rows['4']['example_kind'], 'absence_assessment')
        self.assertIsNone(rows['4']['start_ms'])
        self.assertEqual({r['example_kind'] for r in rows.values()} - {'positive_moment', 'absence_assessment'}, set())  # no negatives
        self.assertEqual(rows['1']['duplicate_group'], rows['2']['duplicate_group'])   # 800 ms apart
        self.assertNotEqual(rows['1']['duplicate_group'], rows['3']['duplicate_group'])
        self.assertEqual(len(rows), 5)                                     # duplicates kept
        self.assertEqual(rows['1']['source_sha256_verified'], vl.sha256_bytes(b'AAAAAAAAAAA'))
        splits = {r['match_key']: r['split'] for r in rows.values()}
        self.assertEqual(len(splits), 2)

    def test_unverified_video_is_never_used(self):
        sources = self.store.load('sources.json', {})
        sources['BBBBBBBBBBB'] = {'status': 'not_retrieved'}
        self.store.save('sources.json', sources)
        m = vl.build(self.store, self.videos, self.out, frames=False)
        rows = [json.loads(l) for l in (self.out / 'labels.jsonl').read_text().splitlines()]
        self.assertFalse(any(r['video_id'] == 'BBBBBBBBBBB' for r in rows))
        self.assertTrue(any('not verified' in e['reason'] for e in m['excluded']))

    def test_split_is_by_event_and_explicit_overrides(self):
        vl.build(self.store, self.videos, self.out, split_by='event', explicit={'2026txcmp1': 'evaluation'}, frames=False)
        rows = [json.loads(l) for l in (self.out / 'labels.jsonl').read_text().splitlines()]
        self.assertEqual({r['split'] for r in rows}, {'evaluation'})


if __name__ == '__main__':
    unittest.main()
