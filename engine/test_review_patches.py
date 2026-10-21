"""Regression tests for the independent-review patches (synthetic fixtures, not match evidence)."""
from pathlib import Path
import unittest
from unittest.mock import patch

import neptune_temporal as temporal
import neptune_training as training

VID = 'AAAAAAAAAAA'
SOURCE = {VID: {'status': 'verified', 'sha256': 'a'*64, 'duration_ms': 180000, 'file': 'video.mp4'}}


def facts():
    return {'source': {'sha256': 'a'*64, 'duration_s': 180},
            'periods': {'auto': {'start': 0, 'end': 20}, 'teleop': {'start': 25, 'end': 165}},
            'tracking': {'band': [.24, .65], 'localizations': [], 'scene_cuts': []}}


def row(tag, t_ms, team=1, category='Scoring', id='a'):
    return {'id': id, 'match_key': '2026test_qm1', 'video_id': VID, 'team_number': team, 'tag_key': tag,
            'tag_category': category, 'polarity': 'present', 'label_scope': 'moment', 'start_ms': t_ms, 'end_ms': t_ms}


class Diagnostics(unittest.TestCase):
    def test_label_after_the_buzzer_is_a_phase_rejection_not_a_localization_failure(self):
        audit = []
        # Tracking and OCR stop at teleop end (165 s), so a 170 s climb has no sightings at all.
        with patch('neptune_training.sightings', return_value=[{'team': 1, 't': 160, 'box': [.2, .4, .1, .1]}]):
            out, skipped = training.labeled_examples([row('gb:climb_lv_1', 170000, category='Endgame')], {VID: facts()}, SOURCE,
                                                     Path('/unused'), extractor=lambda *a: [0.]*512, audit=audit, temporal_required=True)
        self.assertEqual(out, []); self.assertEqual(skipped, {'label_outside_eligible_phase': 1})

    def test_rejection_reports_nearest_candidate_and_keeps_all_reasons(self):
        audit = []
        near = {'team': 1, 't': 50.1, 'box': [.2, .4, .1, .1], 'camera': 'wide'}
        far = {'team': 1, 't': 51.0, 'box': [.2, .4, .1, .1]}
        def plan(f, sight):
            raise temporal.ClipUnavailable('temporal_robot_identity_gap' if sight is near else 'temporal_robot_track_unavailable')
        with patch('neptune_training.sightings', return_value=[far, near]), patch('neptune_temporal.plan', side_effect=plan):
            _, skipped = training.labeled_examples([row('gb:feed', 50000, category='Alliance')], {VID: facts()}, SOURCE,
                                                   Path('/unused'), extractor=lambda *a: [0.]*512, audit=audit, temporal_required=True)
        # The old code reported the last (farther) candidate's reason.
        self.assertEqual(skipped, {'temporal_robot_identity_gap': 1})
        self.assertEqual(audit[-1]['candidate_reasons'], {'temporal_robot_identity_gap': 1, 'temporal_robot_track_unavailable': 1})


class ReferencePool(unittest.TestCase):
    def references(self, labelled):
        sight = {'team': 1, 't': 60, 'box': [.2, .4, .1, .1]}
        clip = {'start': 58., 'end': 62., 'team': 1, 'track_id': 3, 'scene': 0, 'frames': []}
        with patch('neptune_training.sightings', return_value=[sight]), patch('neptune_temporal.plan', return_value=clip):
            return training.unlabeled_examples(labelled, {VID: facts()}, SOURCE, Path('/unused'), extractor=lambda *a: [0.]*512,
                                               temporal_required=True)

    def test_sibling_scoring_label_is_not_unknown_footage(self):
        # Score 2 fuel at 60.5 s: that clip must not be an "unknown" reference for Score 1 fuel.
        refs = self.references([row('gb:score_1_fuel', 20000, id='a'), row('gb:score_2_fuel', 60500, id='b')])
        self.assertNotIn('gb:score_1_fuel', {r['tag'] for r in refs})
        self.assertNotIn('gb:score_2_fuel', {r['tag'] for r in refs})

    def test_other_category_and_distinct_codes_are_kept(self):
        refs = self.references([row('gb:feed', 20000, category='Alliance', id='a'), row('gb:score_2_fuel', 60500, id='b')])
        # Feeding is a different category, so the scoring moment remains unknown footage for it.
        self.assertIn('gb:feed', {r['tag'] for r in refs})
        self.assertEqual({r['tag'] for r in refs if r['tag'] != 'gb:feed'}, set())


class TrackingCache(unittest.TestCase):
    def test_changed_identity_resolver_rebuilds_cached_tracking(self):
        import neptune_yolo
        old = {'version': 'yolo-botsort-1', 'model_fingerprint': 'f', 'camera_engine': 'independent-camera-views-v4',
               'decoder_revision': 'explicit-rawvideo-geometry-v2', 'continuity_revision': 'segment-verified-v2'}
        cached = dict(facts(), tracking=old, layout={'profile': 'p'})
        game = {'layout_profiles': {'p': {'camera_top': .24}}}
        fresh = dict(old, continuity_revision=neptune_yolo.CONTINUITY_REVISION, localizations=[])
        with patch('neptune_yolo.fingerprint', return_value='f'), patch('neptune_tracking.track_match', return_value=fresh) as rerun, \
             patch('neptune_ocr.select_backend', return_value=None):
            out = training.ensure_tracking('video.mp4', cached, game, Path('/unused'))
            self.assertEqual(rerun.call_count, 1); self.assertEqual(out['tracking']['continuity_revision'], neptune_yolo.CONTINUITY_REVISION)
            training.ensure_tracking('video.mp4', out, game, Path('/unused'))
            self.assertEqual(rerun.call_count, 1)

class EvidenceMetrics(unittest.TestCase):
    def test_camera_duplicates_and_sparse_frames_do_not_inflate_seconds(self):
        f=facts();f['tracking'].update(fps=4,localizations=[{'team':1,'t':t,'camera':cam,'identity_method':'yolo_botsort_ocr'} for t in (30.,30.25,35.) for cam in ('wide','closeup')])
        f['bumpers']={'reads':[{'team':1,'kind':'exact','t':30,'alliance':'red','background':'red'}]*3+[{'team':1,'kind':'exact','t':31,'alliance':'red','background':'blue'},{'team':1,'kind':'exact','t':32}]}
        metrics=training.robot_evidence_metrics(f,1)
        self.assertEqual(metrics['direct_bumper_reads'],5)
        self.assertEqual(metrics['direct_read_moments'],1)
        self.assertEqual(metrics['verified_track_seconds'],.75)
    def test_unverified_points_and_outside_phase_do_not_count(self):
        f=facts();f['tracking'].update(fps=4,localizations=[{'team':1,'t':30},{'team':1,'t':170,'identity_method':'yolo_botsort_ocr'}])
        self.assertEqual(training.robot_evidence_metrics(f,1)['verified_track_seconds'],0)


if __name__ == '__main__':
    unittest.main()
