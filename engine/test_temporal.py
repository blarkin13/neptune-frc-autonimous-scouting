import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import neptune_temporal as temporal
import neptune_training as training
import neptune_games as games


class Temporal(unittest.TestCase):
    def facts(self):
        pts=[{'team':1,'t':i/4,'box':[.2,.4,.1,.1], 'scene':0,'track_id':3,'identity_method':'yolo_botsort_ocr'} for i in range(81)]
        return {'source':{'duration_s':180},'periods':{'auto':{'start':0,'end':20},'teleop':{'start':25,'end':165}},
                'tracking':{'band':[.24,.65],'localizations':pts,'scene_cuts':[]}}

    def sight(self,t=10):return {'team':1,'t':t,'box':[.2,.4,.1,.1]}

    def test_automatically_selects_sixteen_tracked_frames(self):
        p=temporal.plan(self.facts(),self.sight())
        self.assertEqual(len(p['frames']),16);self.assertEqual(p['start'],8);self.assertEqual(p['end'],12)
        self.assertEqual(p['team'],1);self.assertEqual(p['track_id'],3)
        self.assertEqual(p['phase'],'auto')
        self.assertTrue(all(.24<=f['box'][1] and f['box'][1]+f['box'][3]<=.65 for f in p['frames']))

    def test_autonomous_end_clip_never_crosses_into_teleop(self):
        p=temporal.plan(self.facts(),self.sight(19.9))
        self.assertEqual((p['start'],p['end']),(16,20))

    def test_missing_track_does_not_use_another_robots_clip(self):
        f=self.facts();f['tracking']['localizations']=[dict(p,team=2) for p in f['tracking']['localizations']]
        with self.assertRaises(temporal.ClipUnavailable) as e:temporal.plan(f,self.sight())
        self.assertEqual(e.exception.reason,'temporal_robot_track_unavailable')

    def test_camera_cut_rejects_clip(self):
        f=self.facts();f['tracking']['scene_cuts']=[9]
        with self.assertRaises(temporal.ClipUnavailable) as e:temporal.plan(f,self.sight())
        self.assertEqual(e.exception.reason,'temporal_camera_cut')

    def test_gap_or_track_identity_change_rejects_clip(self):
        for kind in ('gap','track','scene'):
            f=self.facts()
            if kind=='gap':f['tracking']['localizations']=[p for p in f['tracking']['localizations'] if not 8.5<p['t']<9.5]
            else:
                for p in f['tracking']['localizations']:
                    if p['t']<9:p['track_id' if kind=='track' else 'scene']=99
            with self.assertRaises(temporal.ClipUnavailable):temporal.plan(f,self.sight())

    def test_insufficient_visible_phase_or_short_video_is_unknown(self):
        for kind in ('phase','video'):
            f=self.facts()
            if kind=='phase':f['periods']['auto']={'start':-19.5,'end':.5};sight=self.sight(.1)
            else:f['source']['duration_s']=9;sight=self.sight()
            with self.assertRaises(temporal.ClipUnavailable):temporal.plan(f,sight)

    def test_still_image_or_legacy_sighting_cannot_forge_a_clip(self):
        f=self.facts()
        for p in f['tracking']['localizations']:p['identity_method']='direct_vote_track'
        with self.assertRaises(temporal.ClipUnavailable):temporal.plan(f,self.sight())

    def test_unverified_weights_never_load(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'NEPTUNE_ACTION_MODEL_DIR':tmp}):
            with self.assertRaises(ValueError):temporal.verify_weights()
            (Path(tmp)/temporal.WEIGHT_FILE).write_bytes(b'not weights')
            with self.assertRaises(ValueError):temporal.verify_weights()

    def examples(self):
        return [dict(tag='scoring',x=[float(y)]*512,y=y,label_ids=[split+str(y)+str(i)],source_sha256=split,
                     group=split,split=split,match_key='2026'+split+'_qm1',team=1,t_ms=i*1000)
                for split in ('training','calibration','test') for y in (0,1) for i in range(3)]

    def test_season_heads_train_on_temporal_embeddings_and_record_encoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            game=games.select('2026test_qm1');path=Path(tmp)/'candidate'
            result=training.train_actions(self.examples(),game,path,{})
            model=json.loads((path/'model.json').read_text())
            self.assertEqual(model['feature_version'],temporal.VERSION)
            self.assertEqual(model['action_encoder'],temporal.encoder_document())
            self.assertEqual(model['heads']['scoring']['feature_dimension'],512)
            self.assertFalse(result['release_ready']);training.model_valid(model,game)
            changed=dict(model,game_key='2025-reefscape')
            with self.assertRaises(ValueError):training.model_valid(changed,game)
            changed=copy.deepcopy(model);changed['action_encoder']['weights_sha256']='f'*64
            with self.assertRaises(ValueError):training.model_valid(changed,game)

    def test_cannot_mix_legacy_and_temporal_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows=self.examples();rows[0]['x']=[0.]*1296
            with self.assertRaises(ValueError):training.train_actions(rows,games.select('2026test_qm1'),Path(tmp)/'bad',{})

    def test_unavailable_positive_clip_is_counted_not_a_whole_match_failure(self):
        from test_external_scouting import OutsideScouting
        fixture=OutsideScouting();row=fixture.row();facts=fixture.facts()
        src={'AAAAAAAAAAA':{'status':'verified','sha256':'b'*64,'duration_ms':180000,'file':'video.mp4'}}
        def extract(*args):raise temporal.ClipUnavailable('temporal_robot_identity_gap')
        examples,skipped=training.labeled_examples([row],{'AAAAAAAAAAA':facts},src,Path('/unused'),extractor=extract)
        self.assertFalse(examples);self.assertEqual(skipped['temporal_robot_identity_gap'],1)

    def test_reference_exclusion_checks_entire_clip_not_just_center(self):
        # Real report-4 failure: center 6.333s, clip 6.3333..10.3333s,
        # known positive at 8.469s. The old 1.1s center check missed it.
        sight={'team':1,'t':6.333,'temporal_clip':{'start':6.3333,'end':10.3333}}
        row={'start_ms':8469,'end_ms':8469,'tag_key':'scoring'}
        self.assertGreater(abs(sight['t']-row['start_ms']/1000),1.1)
        self.assertTrue(training.reference_overlaps_label(sight,row))
        self.assertFalse(training.reference_overlaps_label(sight,dict(row,start_ms=20000,end_ms=20000)))

    def test_temporal_reference_pool_excludes_known_actions_and_deduplicates_clips(self):
        f=self.facts();f['source']['sha256']='a'*64
        source={'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':180000,'file':'video.mp4'}}
        row={'id':'a','match_key':'2026test_qm1','video_id':'AAAAAAAAAAA','team_number':1,
             'tag_key':'scoring','polarity':'present','label_scope':'moment','start_ms':8469,'end_ms':8469}
        # Two centers yield the same clean clip. A third center lies outside
        # the old padding but its clip contains the known positive moment.
        sightings=[self.sight(6.333),self.sight(15),self.sight(15.1)]
        def plan(facts,sight):
            start=6.3333 if sight['t']<10 else 13.
            return {'start':start,'end':start+4,'team':1,'track_id':3,'scene':0,'frames':[]}
        with patch('neptune_training.sightings',return_value=sightings),patch('neptune_temporal.plan',side_effect=plan):
            examples=training.unlabeled_examples([row],{'AAAAAAAAAAA':f},source,Path('/unused'),extractor=lambda *a:[0.]*512,temporal_required=True)
        self.assertEqual(len(examples),1)
        self.assertEqual(examples[0]['temporal_clip']['start'],13.)
        self.assertIsNone(examples[0]['y'])


if __name__=='__main__':unittest.main()
