import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import neptune_yolo as yolo


class YoloTracking(unittest.TestCase):
    def det(self, tid=1, alliance='red', box=None, **kw):
        return dict(id=tid, alliance=alliance, box=box or [10, 10, 30, 20], confidence=.9, **kw)

    def read(self, team=123, tid=1, kind='exact'):
        return dict(team=team, track=tid, kind=kind)

    def resolver(self):
        return yolo.Identities({'red': [123, 456, 789], 'blue': [111, 222, 333]})

    def establish(self, r, tid=1, team=123):
        d = self.det(tid)
        self.assertFalse(r.update(0, 0, [d], [self.read(team, tid)]))
        return r.update(0, 1, [d], [self.read(team, tid)])

    def test_two_separate_exact_anchors_then_number_can_disappear(self):
        r = self.resolver()
        self.assertEqual(self.establish(r)[0]['team'], 123)
        self.assertEqual(r.update(0, 2, [self.det()], [])[0]['team'], 123)
        self.assertEqual(r.update(0, 3, [self.det()], [])[0]['team'], 123)

    def test_corrected_or_wrong_alliance_reads_cannot_anchor(self):
        for read in (self.read(kind='corrected'), self.read(team=111), self.read(team=999)):
            r = self.resolver()
            self.assertFalse(r.update(0, 0, [self.det()], [read]))
            self.assertFalse(r.update(0, 1, [self.det()], [read]))

    def test_duplicate_same_moment_is_not_two_anchors(self):
        r = self.resolver()
        self.assertFalse(r.update(0, 0, [self.det()], [self.read(), self.read()]))
        self.assertFalse(r.update(0, .1, [self.det()], [self.read()]))

    def test_camera_cut_drops_identity_even_if_tracker_reuses_id(self):
        r = self.resolver(); self.establish(r)
        self.assertFalse(r.update(1, 2, [self.det()], []))

    def test_long_gap_drops_identity(self):
        r = self.resolver(); self.establish(r)
        self.assertFalse(r.update(0, 3, [self.det()], []))

    def test_number_conflict_immediately_drops_old_identity(self):
        r = self.resolver(); self.establish(r)
        self.assertFalse(r.update(0, 2, [self.det()], [self.read(team=456)]))
        self.assertEqual(r.update(0, 3, [self.det()], [self.read(team=456)])[0]['team'], 456)

    def test_two_numbers_in_one_detection_are_ambiguous(self):
        r = self.resolver(); self.establish(r)
        self.assertFalse(r.update(0, 2, [self.det()], [self.read(), self.read(team=456)]))
        self.assertFalse(r.update(0, 3, [self.det()], []))

    def test_crossing_or_person_occlusion_clears_identity(self):
        for detections in ([self.det(), self.det(2, box=[12, 10, 32, 20])], [self.det(occluded=True)]):
            r = self.resolver(); self.establish(r)
            self.assertFalse(r.update(0, 2, detections, []))
            self.assertFalse(r.update(0, 3, [self.det()], []))

    def test_cannot_assign_one_team_to_two_simultaneous_tracks(self):
        r = self.resolver()
        ds = [self.det(), self.det(2, box=[50, 10, 70, 20])]
        rs = [self.read(), self.read(tid=2)]
        r.update(0, 0, ds, rs)
        self.assertFalse(r.update(0, 1, ds, rs))

    def test_colour_switch_requires_new_anchors(self):
        r = self.resolver(); self.establish(r)
        self.assertFalse(r.update(0, 2, [self.det(alliance='blue')], []))

    def test_implausible_jump_does_not_transfer_identity(self):
        r = self.resolver(); self.establish(r)
        self.assertFalse(r.update(0, 1.2, [self.det(box=[800, 10, 820, 20])], []))

    def test_coco_is_rejected_as_robot_detector(self):
        with self.assertRaises(ValueError):
            yolo.bumper_classes({0: 'person', 1: 'car'})
        self.assertEqual(yolo.bumper_classes({0: 'red', 1: 'blue'}), {0: 'red', 1: 'blue'})

    def test_private_manifest_integrity_season_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'bumper.pt').write_bytes(b'fixture')
            row = dict(file='bumper.pt', sha256=hashlib.sha256(b'fixture').hexdigest())
            data = dict(schema_version=1, seasons=[2026], bumper=row, context=dict(row))
            (p/'manifest.json').write_text(json.dumps(data))
            self.assertEqual(yolo.bundle(p)['seasons'], [2026])
            with self.assertRaises(ValueError):yolo.bundle(p, 2025)
            (p/'bumper.pt').write_bytes(b'changed')
            with self.assertRaises(ValueError):yolo.bundle(p)
            row['file'] = '../bumper.pt'; (p/'manifest.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):yolo.bundle(p)

    def test_crops_stay_in_the_camera(self):
        self.assertEqual(yolo.crop_box([0, 0, 10, 10], 20, 20), [0, 0, 13, 14])

    def test_sample_rate_changes_gap_buffer_not_identity_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'botsort.yaml'
            yolo.tracker_config(p, 6)
            self.assertIn('track_buffer: 9', p.read_text())
            self.assertIn('with_reid: true', p.read_text())

    def test_native_wide_tiles_cover_edge_and_only_add_distinct_boxes(self):
        self.assertEqual(yolo.tile_starts(1920, 960), [0, 720, 960])
        self.assertEqual(yolo.tile_starts(800, 960), [0])
        original=[self.det(box=[10,10,30,20])]
        candidates=[{'box':[20,20,60,40],'alliance':'red','confidence':.9},
                    {'box':[200,20,260,40],'alliance':'blue','confidence':.8}]
        merged,added=yolo.merge_tiled_bumpers(original,candidates,(960,400),(1920,800))
        self.assertEqual(added,1)
        self.assertEqual(merged[-1]['box'],[100,10,130,20])
        self.assertEqual(merged[-1]['box_source'],'tiled_detector')
        self.assertIsNone(merged[-1]['id'])

    def test_native_tile_predictions_map_back_to_the_full_wide_panel(self):
        import numpy as np
        class Values:
            def __init__(self, values):self.values=values
            def cpu(self):return self
            def tolist(self):return self.values
        class Detector:
            def __init__(self):self.widths=[]
            def predict(self, crop, **kw):
                self.widths.append(crop.shape[1])
                values=[[100,10,140,30]] if len(self.widths)==3 else []
                boxes=type('Boxes',(),{'xyxy':Values(values),'cls':Values([0]*len(values)),
                                        'conf':Values([.8]*len(values))})()
                return [type('Result',(),{'boxes':boxes})()]
        model=Detector()
        rows=yolo.tiled_bumpers(model,np.zeros((200,1920,3),dtype=np.uint8),{0:'red'},'cpu')
        self.assertEqual(model.widths,[960,960,960])
        self.assertEqual(rows[0]['box'],[1060.,10,1100.,30])

    def test_production_tracking_never_calls_legacy_linker(self):
        import neptune_tracking
        with patch('neptune_yolo.track_match', return_value={'version': yolo.VERSION}) as run, patch('neptune_tracking.legacy_track_match', side_effect=AssertionError('legacy fallback')):
            self.assertEqual(neptune_tracking.track_match('video', {}, {}, None, '/tmp')['version'], yolo.VERSION)
            run.assert_called_once()

    def test_existing_example_pipeline_accepts_anchored_yolo_crops(self):
        import neptune_training
        sight = {'team': 123, 't': 2., 'box': [.1, .3, .1, .1],
                 'identity_method': 'yolo_botsort_ocr', 'identity_evidence': {'anchor_times': [0., 1.]}}
        self.assertEqual(neptune_training.sightings({'tracking': {'localizations': [sight]}}), [sight])

    def test_cache_rebuilt_when_detector_changes(self):
        import neptune_training
        facts = {'tracking': {'version': yolo.VERSION, 'model_fingerprint': 'old'},
                 'layout': {'profile': 'test'}, 'periods': {'auto': {'start': 0, 'end': 20}}}
        with patch('neptune_yolo.fingerprint', return_value='new'), patch('neptune_ocr.select_backend'), patch('neptune_tracking.track_match', return_value={'version': yolo.VERSION, 'model_fingerprint': 'new'}) as track:
            result = neptune_training.ensure_tracking('video', facts, {'layout_profiles': {'test': {'season': 2026}}}, '/tmp')
            self.assertEqual(result['tracking']['model_fingerprint'], 'new')
            track.assert_called_once()

    def test_old_decoder_tracking_is_rebuilt_but_corrected_tracking_is_reused(self):
        import neptune_training
        from neptune_tracking import FRAME_DECODER_REVISION
        old={'tracking':{'version':yolo.VERSION,'model_fingerprint':'same',
                         'camera_engine':'independent-camera-views-v4'},
             'layout':{'profile':'test'},'periods':{'auto':{'start':0,'end':20}}}
        fresh=dict(old['tracking'],decoder_revision=FRAME_DECODER_REVISION)
        with patch('neptune_yolo.fingerprint',return_value='same'),patch('neptune_ocr.select_backend'),patch('neptune_tracking.track_match',return_value=fresh) as track:
            result=neptune_training.ensure_tracking('video',old,{'layout_profiles':{'test':{'season':2026}}},'/tmp')
            track.assert_called_once()
            self.assertEqual(result['tracking']['decoder_revision'],FRAME_DECODER_REVISION)
            track.reset_mock()
            self.assertIs(neptune_training.ensure_tracking('video',result,{},'/tmp'),result)
            track.assert_not_called()


if __name__ == '__main__':
    unittest.main()
