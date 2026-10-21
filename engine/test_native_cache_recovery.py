import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import neptune_training as training
class CacheRecovery(unittest.TestCase):
    def test_changed_crop_reads_video_and_preserves_original_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'facts.json';facts={'pipeline':'facts-old','source':{'sha256':'a'*64,'duration_s':160}};path.write_text(json.dumps(facts));raw=root/'raw-overlay.jsonl';raw.write_text('immutable evidence')
            fresh={'pipeline':'facts-4.1-clock-context','source':facts['source']};video=root/'video.mp4';video.touch();game={'fingerprint':'b'*64}
            with patch('neptune_facts.replay_alliance_layout',return_value=None),patch('neptune_facts.analyze_video',return_value=fresh) as analyze:
                result=training.refresh_cached_facts(path,facts,{},game,'a'*64,video=video)
            self.assertTrue(result['cache_refresh']['original_evidence_preserved']);self.assertEqual(raw.read_text(),'immutable evidence');self.assertEqual(json.loads(path.read_text()),facts)
            self.assertEqual(analyze.call_args.args[0],video);self.assertNotEqual(analyze.call_args.args[2],root)
    def test_replay_does_not_download_or_reread_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'facts.json';facts={'pipeline':'old'};path.write_text(json.dumps(facts));(path.parent/'raw-overlay.jsonl').touch()
            with patch('neptune_facts.replay_alliance_layout',return_value={'pipeline':'current'}),patch('neptune_facts.analyze_video') as analyze:
                self.assertEqual(training.refresh_cached_facts(path,facts,{}, {},'a'*64)['pipeline'],'current');analyze.assert_not_called()
    def test_refreshed_video_fingerprint_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'facts.json';facts={'pipeline':'old','source':{'duration_s':160}};path.write_text(json.dumps(facts))
            with patch('neptune_facts.analyze_video',return_value={'source':{'sha256':'wrong'}}):
                with self.assertRaisesRegex(ValueError,'fingerprint changed'):training.refresh_cached_facts(path,facts,{}, {'fingerprint':'b'},'a',video=path)
if __name__=='__main__':unittest.main()

class SegmentContinuity(unittest.TestCase):
    def test_two_anchors_verify_only_their_unbroken_segment(self):
        from neptune_yolo import recover_segments
        pts=[dict(identity_segment=i,track_id=7,t=t,camera='wide',scene=0) for i in (1,2) for t in (0,1,2)]
        out=recover_segments(pts,{1:[{'team':123,'anchor_times':[1,2]}]},set(),'x')
        self.assertEqual(len(out),3);self.assertTrue(all(p['identity_segment']==1 and p['team']==123 for p in out));self.assertEqual(out[0]['t'],0)
        self.assertFalse(recover_segments(pts,{1:[{'team':123,'anchor_times':[1,2]}]},{1},'x'))
    def test_clip_uses_verified_visible_boundary_without_changing_identity(self):
        import neptune_temporal as temporal
        pts=[dict(team=1,t=5+i/4,box=[.2,.4,.1,.1],scene=0,track_id=3,identity_segment=4,identity_method='yolo_botsort_ocr') for i in range(17)]
        facts={'source':{'duration_s':20},'periods':{'auto':{'start':0,'end':20}},'tracking':{'continuity_revision':'segment-verified-v3','band':[.24,.65],'localizations':pts,'scene_cuts':[]}}
        plan=temporal.plan(facts,{'team':1,'t':6,'box':[.2,.4,.1,.1]});self.assertEqual(plan['start'],5);self.assertEqual(len(plan['frames']),16)
        facts['tracking']['localizations']=[p for p in pts if p['t']!=6]
        for p in facts['tracking']['localizations']:
            if p['t']>6:p['identity_segment']=5
        with self.assertRaises(temporal.ClipUnavailable):temporal.plan(facts,{'team':1,'t':5.75})

class BumperDuplicates(unittest.TestCase):
    def test_nested_same_bumper_is_not_two_robots(self):
        from neptune_yolo import unique_bumpers
        boxes=[dict(id=1,box=[625,245,770,285],alliance='red',confidence=.63),dict(id=2,box=[624,232,875,286],alliance='red',confidence=.24),dict(id=3,box=[626,254,753,284],alliance='red',confidence=.19)]
        self.assertEqual([p['id'] for p in unique_bumpers(boxes)],[1])
        self.assertEqual(len(unique_bumpers(boxes+[dict(id=4,box=[200,240,350,285],alliance='red',confidence=.8)])),2)
        self.assertEqual(len(unique_bumpers([boxes[0],dict(boxes[0],id=4,alliance='blue')])),2)
    def test_partial_overlap_between_two_robots_is_retained(self):
        from neptune_yolo import unique_bumpers
        boxes=[dict(box=[10,10,30,20],alliance='red',confidence=.8),dict(box=[22,10,42,20],alliance='red',confidence=.7)]
        self.assertEqual(len(unique_bumpers(boxes)),2)
