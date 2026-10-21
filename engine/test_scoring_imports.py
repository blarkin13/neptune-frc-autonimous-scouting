import copy,json,tempfile,unittest
from pathlib import Path
import neptune_facts as facts_reader
import neptune_games as games
import neptune_scoring_model as scoring
import neptune_video_labels as labels
from test_scoring_model import row,facts,feature


def imported(team,points):
    r=row(team,points);r.update(evidence_type='external_scouting_label',definition_version='viper-2026-points-v1',video_duration_ms=0)
    r['scoring'].update(source='external_scouting_estimate',alliance_score=None)
    r['external']={'provider':'viperscout','adapter_version':'viper-2026-points-v1','kind':'reported_score_total','weak_supervision':True,
                   'components':{'auto_fuel_score':0,'tele_fuel_score':points,'auto_climb_level':0,'tele_climb_level':0}}
    return r


class ImportedScores(unittest.TestCase):
    def test_source_totals_are_estimates_not_forged_human_evidence(self):
        r=imported(1,80);parsed,errors=labels.read_export(json.dumps(r));self.assertFalse(errors);self.assertEqual(len(parsed),1)
        self.assertTrue(labels.external_score_label(parsed[0]));self.assertIsNone(scoring.target(r))
        r['scoring']['robot_points']=90;self.assertFalse(labels.external_score_label(r));self.assertTrue(labels.read_export(json.dumps(r))[1])
    def test_points_fit_and_predict_without_inventing_alliance_total(self):
        rows=[imported(1,80),imported(2,150)]
        examples,skip=scoring.examples(rows,{'AAAAAAAAAAA':facts()},{'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':200000,'file':'video.mp4'}},Path('/unused'),feature)
        self.assertFalse(skip);self.assertEqual(len(examples),2);self.assertTrue(all(e['y'] is None and e['alliance_score'] is None for e in examples))
        head,report=scoring.fit(examples,point_mode=True);scoring.valid(head);self.assertEqual(head['version'],scoring.POINT_VERSION);self.assertFalse(head['release_ready'])
        head['validation']={'video':{'status':'evaluated','robots':6,'point_mae_video':10,'point_mae_training_mean':20}}
        predictions=scoring.predict('/unused',facts(),head,rows[0]['roster'],{},feature)
        self.assertTrue(all(p['robot_points'] is not None and p['share_percent'] is None for p in predictions))
        constrained=scoring.predict('/unused',facts(),head,rows[0]['roster'],{'red':100,'blue':200},feature)
        self.assertLessEqual(sum(p['robot_points'] or 0 for p in constrained if p['alliance']=='red'),100)
    def test_missing_robot_identity_is_still_rejected(self):
        f=facts();f['identity']['checks']['roster']['status']='partial'
        examples,skip=scoring.examples([imported(1,80)],{'AAAAAAAAAAA':f},{'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':200000,'file':'video.mp4'}},Path('/unused'),feature)
        self.assertFalse(examples);self.assertEqual(skip['match_identity_incomplete'],1)
    def test_human_estimate_takes_priority_over_import(self):
        examples,skip=scoring.examples([row(1,100),imported(1,200)],{'AAAAAAAAAAA':facts()},{'AAAAAAAAAAA':{'status':'verified','sha256':'a'*64,'duration_ms':200000,'file':'video.mp4'}},Path('/unused'),feature)
        self.assertEqual(examples[0]['points'],100);self.assertEqual(examples[0]['target_kind'],'human_contribution');self.assertEqual(skip['imported_duplicate_superseded_by_human'],1)
    def test_real_blue_left_readings_verify_correct_alliance_rosters(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/age-blue-left-overlay.json').read_text());rules=json.loads(games.BUILTIN.read_text())['seasons']['2026']
        rows=fixture['rows'];frames=[(r['t'],Path('/evidence')/r['frame']) for r in rows];texts={str(Path('/evidence')/r['frame']):r['items'] for r in rows}
        pid,profile,_=facts_reader.detect_layout(frames,texts,2026,rules['layout_profiles']);self.assertEqual(pid,'frc-2026-age-blue-left-v1')
        reading=facts_reader.parse_overlay(rows[0]['items'],profile);self.assertEqual(reading['blue']['t'],'4');self.assertEqual(reading['red']['t'],'37')
        samples,_=facts_reader.overlay_samples(frames,texts,profile,rules,Path('/evidence'))
        identity=facts_reader.verify_identity(samples,{'key':fixture['match_key'],'roster':fixture['roster']},None,None);self.assertEqual(identity['checks']['roster']['status'],'match')
        legacy=facts_reader.parse_overlay(rows[0]['items'],rules['layout_profiles']['frc-2026-week0-overlay-v1']);self.assertNotEqual(reading['red']['t'],legacy['red']['t'])
    def test_replay_never_accepts_a_different_video_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'facts.json';p.write_text(json.dumps({'source':{'sha256':'a'*64}}))
            self.assertIsNone(facts_reader.replay_alliance_layout(p,{}, {},'b'*64))

if __name__=='__main__':unittest.main()
